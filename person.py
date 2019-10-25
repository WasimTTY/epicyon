__filename__ = "person.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.0.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@freedombone.net"
__status__ = "Production"

import json
import time
import commentjson
import os
import fileinput
import subprocess
import shutil
from pprint import pprint
from pathlib import Path
from Crypto.PublicKey import RSA
from shutil import copyfile
from webfinger import createWebfingerEndpoint
from webfinger import storeWebfingerEndpoint
from posts import createDMTimeline
from posts import createRepliesTimeline
from posts import createMediaTimeline
from posts import createInbox
from posts import createOutbox
from posts import createModeration
from auth import storeBasicCredentials
from auth import removePassword
from roles import setRole
from media import removeMetaData
from utils import validNickname
from utils import noOfAccounts
from utils import loadJson
from utils import saveJson
from auth import createPassword
from config import setConfigParam
from config import getConfigParam

def generateRSAKey() -> (str,str):
    key = RSA.generate(2048)
    privateKeyPem = key.exportKey("PEM").decode("utf-8")
    publicKeyPem = key.publickey().exportKey("PEM").decode("utf-8")
    return privateKeyPem,publicKeyPem

def setProfileImage(baseDir: str,httpPrefix :str,nickname: str,domain: str, \
                    port :int,imageFilename: str,imageType :str,resolution :str) -> bool:
    """Saves the given image file as an avatar or background
    image for the given person
    """
    imageFilename=imageFilename.replace('\n','')
    if not (imageFilename.endswith('.png') or \
            imageFilename.endswith('.jpg') or \
            imageFilename.endswith('.jpeg') or \
            imageFilename.endswith('.gif')):
        print('Profile image must be png, jpg or gif format')
        return False

    if imageFilename.startswith('~/'):
        imageFilename=imageFilename.replace('~/',str(Path.home())+'/')

    if ':' in domain:
        domain=domain.split(':')[0]
    fullDomain=domain
    if port:
        if port!=80 and port!=443:
            if ':' not in domain:
                fullDomain=domain+':'+str(port)

    handle=nickname.lower()+'@'+domain.lower()
    personFilename=baseDir+'/accounts/'+handle+'.json'
    if not os.path.isfile(personFilename):
        print('person definition not found: '+personFilename)
        return False
    if not os.path.isdir(baseDir+'/accounts/'+handle):
        print('Account not found: '+baseDir+'/accounts/'+handle)
        return False

    iconFilenameBase='icon'
    if imageType=='avatar' or imageType=='icon':
        iconFilenameBase='icon'
    else:
        iconFilenameBase='image'
        
    mediaType='image/png'
    iconFilename=iconFilenameBase+'.png'
    if imageFilename.endswith('.jpg') or \
       imageFilename.endswith('.jpeg'):
        mediaType='image/jpeg'
        iconFilename=iconFilenameBase+'.jpg'
    if imageFilename.endswith('.gif'):
        mediaType='image/gif'
        iconFilename=iconFilenameBase+'.gif'
    profileFilename=baseDir+'/accounts/'+handle+'/'+iconFilename

    personJson=loadJson(personFilename)
    if personJson:
        personJson[iconFilenameBase]['mediaType']=mediaType
        personJson[iconFilenameBase]['url']=httpPrefix+'://'+fullDomain+'/users/'+nickname+'/'+iconFilename
        saveJson(personJson,personFilename)
            
        cmd = '/usr/bin/convert '+imageFilename+' -size '+resolution+' -quality 50 '+profileFilename
        subprocess.call(cmd, shell=True)
        removeMetaData(profileFilename,profileFilename)
        return True
    return False

def setOrganizationScheme(baseDir: str,nickname: str,domain: str, \
                          schema: str) -> bool:
    """Set the organization schema within which a person exists
    This will define how roles, skills and availability are assembled
    into organizations
    """
    # avoid giant strings
    if len(schema)>256:
        return False
    actorFilename=baseDir+'/accounts/'+nickname+'@'+domain+'.json'
    if not os.path.isfile(actorFilename):
        return False

    actorJson=loadJson(actorFilename)
    if actorJson:
        actorJson['orgSchema']=schema
        saveJson(actorJson,actorFilename)
    return True

def accountExists(baseDir: str,nickname: str,domain: str) -> bool:
    """Returns true if the given account exists
    """
    if ':' in domain:
        domain=domain.split(':')[0]
    return os.path.isdir(baseDir+'/accounts/'+nickname+'@'+domain)

def createPersonBase(baseDir: str,nickname: str,domain: str,port: int, \
                     httpPrefix: str, saveToFile: bool,password=None) -> (str,str,{},{}):
    """Returns the private key, public key, actor and webfinger endpoint
    """
    privateKeyPem,publicKeyPem=generateRSAKey()
    webfingerEndpoint= \
        createWebfingerEndpoint(nickname,domain,port,httpPrefix,publicKeyPem)
    if saveToFile:
        storeWebfingerEndpoint(nickname,domain,port,baseDir,webfingerEndpoint)

    handle=nickname.lower()+'@'+domain.lower()
    originalDomain=domain
    if port:
        if port!=80 and port!=443:
            if ':' not in domain:
                domain=domain+':'+str(port)

    personType='Person'
    approveFollowers=False
    personName=nickname
    personId=httpPrefix+'://'+domain+'/users/'+nickname
    inboxStr=personId+'/inbox'
    personUrl=httpPrefix+'://'+domain+'/@'+personName
    if nickname=='inbox':
        # shared inbox
        inboxStr=httpPrefix+'://'+domain+'/actor/inbox'
        personId=httpPrefix+'://'+domain+'/actor'
        personUrl=httpPrefix+'://'+domain+'/about/more?instance_actor=true'
        personName=originalDomain
        approveFollowers=True
        personType='Application'

    newPerson = {'@context': ['https://www.w3.org/ns/activitystreams',
                              'https://w3id.org/security/v1',
                              {'Emoji': 'toot:Emoji',
                               'Hashtag': 'as:Hashtag',
                               'IdentityProof': 'toot:IdentityProof',
                               'PropertyValue': 'schema:PropertyValue',
                               'alsoKnownAs': {'@id': 'as:alsoKnownAs', '@type': '@id'},
                               'focalPoint': {'@container': '@list', '@id': 'toot:focalPoint'},
                               'manuallyApprovesFollowers': 'as:manuallyApprovesFollowers',
                               'movedTo': {'@id': 'as:movedTo', '@type': '@id'},
                               'schema': 'http://schema.org#',
                               'value': 'schema:value'}],
                 'attachment': [],
                 'endpoints': {
                     'id': personId+'/endpoints',
                     'sharedInbox': httpPrefix+'://'+domain+'/inbox',
                 },
                 'capabilityAcquisitionEndpoint': httpPrefix+'://'+domain+'/caps/new',
                 'followers': personId+'/followers',
                 'following': personId+'/following',
                 'shares': personId+'/shares',
                 'orgSchema': None,
                 'skills': {},
                 'roles': {},
                 'availability': None,
                 'icon': {'mediaType': 'image/png',
                          'type': 'Image',
                          'url': personId+'/avatar.png'},
                 'id': personId,
                 'image': {'mediaType': 'image/png',
                           'type': 'Image',
                           'url': personId+'/image.png'},
                 'inbox': inboxStr,
                 'manuallyApprovesFollowers': approveFollowers,
                 'name': personName,
                 'outbox': personId+'/outbox',
                 'preferredUsername': personName,
                 'summary': '',
                 'publicKey': {
                     'id': personId+'#main-key',
                     'owner': personId,
                     'publicKeyPem': publicKeyPem
                 },
                 'tag': [],
                 'type': personType,
                 'url': personUrl
    }

    if nickname=='inbox':
        # fields not needed by the shared inbox
        del newPerson['outbox']
        del newPerson['icon']
        del newPerson['image']
        del newPerson['skills']
        del newPerson['shares']
        del newPerson['roles']
        del newPerson['tag']
        del newPerson['availability']
        del newPerson['followers']
        del newPerson['following']
        del newPerson['attachment']

    if saveToFile:
        # save person to file
        peopleSubdir='/accounts'
        if not os.path.isdir(baseDir+peopleSubdir):
            os.mkdir(baseDir+peopleSubdir)
        if not os.path.isdir(baseDir+peopleSubdir+'/'+handle):
            os.mkdir(baseDir+peopleSubdir+'/'+handle)
        if not os.path.isdir(baseDir+peopleSubdir+'/'+handle+'/inbox'):
            os.mkdir(baseDir+peopleSubdir+'/'+handle+'/inbox')
        if not os.path.isdir(baseDir+peopleSubdir+'/'+handle+'/outbox'):
            os.mkdir(baseDir+peopleSubdir+'/'+handle+'/outbox')
        if not os.path.isdir(baseDir+peopleSubdir+'/'+handle+'/ocap'):
            os.mkdir(baseDir+peopleSubdir+'/'+handle+'/ocap')
        if not os.path.isdir(baseDir+peopleSubdir+'/'+handle+'/queue'):
            os.mkdir(baseDir+peopleSubdir+'/'+handle+'/queue')
        filename=baseDir+peopleSubdir+'/'+handle+'.json'
        saveJson(newPerson,filename)

        # save to cache
        if not os.path.isdir(baseDir+'/cache'):
            os.mkdir(baseDir+'/cache')
        if not os.path.isdir(baseDir+'/cache/actors'):
            os.mkdir(baseDir+'/cache/actors')
        cacheFilename=baseDir+'/cache/actors/'+newPerson['id'].replace('/','#')+'.json'
        saveJson(newPerson,cacheFilename)

        # save the private key
        privateKeysSubdir='/keys/private'
        if not os.path.isdir(baseDir+'/keys'):
            os.mkdir(baseDir+'/keys')
        if not os.path.isdir(baseDir+privateKeysSubdir):
            os.mkdir(baseDir+privateKeysSubdir)
        filename=baseDir+privateKeysSubdir+'/'+handle+'.key'
        with open(filename, "w") as text_file:
            print(privateKeyPem, file=text_file)

        # save the public key
        publicKeysSubdir='/keys/public'
        if not os.path.isdir(baseDir+publicKeysSubdir):
            os.mkdir(baseDir+publicKeysSubdir)
        filename=baseDir+publicKeysSubdir+'/'+handle+'.pem'
        with open(filename, "w") as text_file:
            print(publicKeyPem, file=text_file)

        if password:
            storeBasicCredentials(baseDir,nickname,password)

    return privateKeyPem,publicKeyPem,newPerson,webfingerEndpoint

def registerAccount(baseDir: str,httpPrefix: str,domain: str,port: int, \
                    nickname: str,password: str) -> bool:
    """Registers a new account from the web interface
    """
    if accountExists(baseDir,nickname,domain):
        return False
    if not validNickname(domain,nickname):
        print('REGISTER: Nickname '+nickname+' is invalid')
        return False
    if len(password)<8:
        print('REGISTER: Password should be at least 8 characters')
        return False
    privateKeyPem,publicKeyPem,newPerson,webfingerEndpoint= \
        createPerson(baseDir,nickname,domain,port, \
                     httpPrefix,True,password)
    if privateKeyPem:
        return True
    return False

def createGroup(baseDir: str,nickname: str,domain: str,port: int, \
                httpPrefix: str, saveToFile: bool,password=None) -> (str,str,{},{}):
    """Returns a group
    """
    privateKeyPem,publicKeyPem,newPerson,webfingerEndpoint= \
        createPerson(baseDir,nickname,domain,port, \
                     httpPrefix,saveToFile,password)
    newPerson['type']='Group'
    return privateKeyPem,publicKeyPem,newPerson,webfingerEndpoint

def createPerson(baseDir: str,nickname: str,domain: str,port: int, \
                 httpPrefix: str, saveToFile: bool,password=None) -> (str,str,{},{}):
    """Returns the private key, public key, actor and webfinger endpoint
    """
    if not validNickname(domain,nickname):
       return None,None,None,None

    # If a config.json file doesn't exist then don't decrement
    # remaining registrations counter
    remainingConfigExists=getConfigParam(baseDir,'registrationsRemaining')
    if remainingConfigExists:
        registrationsRemaining=int(remainingConfigExists)
        if registrationsRemaining<=0:
            return None,None,None,None

    privateKeyPem,publicKeyPem,newPerson,webfingerEndpoint = \
        createPersonBase(baseDir,nickname,domain,port,httpPrefix,saveToFile,password)
    if noOfAccounts(baseDir)==1:
        #print(nickname+' becomes the instance admin and a moderator')
        setRole(baseDir,nickname,domain,'instance','admin')
        setRole(baseDir,nickname,domain,'instance','moderator')
        setRole(baseDir,nickname,domain,'instance','delegator')
        setConfigParam(baseDir,'admin',nickname)

    if not os.path.isdir(baseDir+'/accounts'):
        os.mkdir(baseDir+'/accounts')
    if not os.path.isdir(baseDir+'/accounts/'+nickname+'@'+domain):
        os.mkdir(baseDir+'/accounts/'+nickname+'@'+domain)
    
    if os.path.isfile(baseDir+'/img/default-avatar.png'):
        copyfile(baseDir+'/img/default-avatar.png',baseDir+'/accounts/'+nickname+'@'+domain+'/avatar.png')
    theme=getConfigParam(baseDir,'theme')
    defaultProfileImageFilename=baseDir+'/img/image.png'
    if theme:
        if os.path.isfile(baseDir+'/img/image_'+theme+'.png'):
            defaultBannerFilename=baseDir+'/img/image_'+theme+'.png'        
    if os.path.isfile(defaultProfileImageFilename):
        copyfile(defaultProfileImageFilename,baseDir+'/accounts/'+nickname+'@'+domain+'/image.png')
    defaultBannerFilename=baseDir+'/img/banner.png'
    if theme:
        if os.path.isfile(baseDir+'/img/banner_'+theme+'.png'):
            defaultBannerFilename=baseDir+'/img/banner_'+theme+'.png'        
    if os.path.isfile(defaultBannerFilename):
        copyfile(defaultBannerFilename,baseDir+'/accounts/'+nickname+'@'+domain+'/banner.png')
    if remainingConfigExists:
        registrationsRemaining-=1
        setConfigParam(baseDir,'registrationsRemaining',str(registrationsRemaining))
    return privateKeyPem,publicKeyPem,newPerson,webfingerEndpoint

def createSharedInbox(baseDir: str,nickname: str,domain: str,port: int, \
                      httpPrefix: str) -> (str,str,{},{}):
    """Generates the shared inbox
    """
    return createPersonBase(baseDir,nickname,domain,port,httpPrefix,True,None)

def createCapabilitiesInbox(baseDir: str,nickname: str,domain: str,port: int, \
                            httpPrefix: str) -> (str,str,{},{}):
    """Generates the capabilities inbox to sign requests
    """
    return createPersonBase(baseDir,nickname,domain,port,httpPrefix,True,None)
    
def personLookup(domain: str,path: str,baseDir: str) -> {}:
    """Lookup the person for an given nickname
    """
    if path.endswith('#main-key'):
        path=path.replace('#main-key','')
    # is this a shared inbox lookup?
    isSharedInbox=False
    if path=='/inbox' or path=='/users/inbox' or path=='/sharedInbox':
        # shared inbox actor on @domain@domain
        path='/users/'+domain
        isSharedInbox=True
    else:
        notPersonLookup=['/inbox','/outbox','/outboxarchive', \
                         '/followers','/following','/featured', \
                         '.png','.jpg','.gif','.mpv']
        for ending in notPersonLookup:        
            if path.endswith(ending):
                return None
    nickname=None
    if path.startswith('/users/'):
        nickname=path.replace('/users/','',1)
    if path.startswith('/@'):
        nickname=path.replace('/@','',1)
    if not nickname:
        return None
    if not isSharedInbox and not validNickname(domain,nickname):
        return None
    if ':' in domain:
        domain=domain.split(':')[0]
    handle=nickname+'@'+domain
    filename=baseDir+'/accounts/'+handle+'.json'
    if not os.path.isfile(filename):
        return None
    personJson=loadJson(filename)
    #if not personJson:
    #    personJson={"user": "unknown"}
    return personJson

def personBoxJson(session,baseDir: str,domain: str,port: int,path: str, \
                  httpPrefix: str,noOfItems: int,boxname: str, \
                  authorized: bool,ocapAlways: bool) -> []:
    """Obtain the inbox/outbox/moderation feed for the given person
    """
    if boxname!='inbox' and boxname!='dm' and \
       boxname!='tlreplies' and boxname!='tlmedia' and \
       boxname!='outbox' and boxname!='moderation':
        return None

    if not '/'+boxname in path:
        return None

    # Only show the header by default
    headerOnly=True

    # handle page numbers
    pageNumber=None    
    if '?page=' in path:
        pageNumber=path.split('?page=')[1]
        if pageNumber=='true':
            pageNumber=1
        else:
            try:
                pageNumber=int(pageNumber)
            except:
                pass
        path=path.split('?page=')[0]
        headerOnly=False

    if not path.endswith('/'+boxname):
        return None
    nickname=None
    if path.startswith('/users/'):
        nickname=path.replace('/users/','',1).replace('/'+boxname,'')
    if path.startswith('/@'):
        nickname=path.replace('/@','',1).replace('/'+boxname,'')
    if not nickname:
        return None
    if not validNickname(domain,nickname):
        return None
    if boxname=='inbox':
        return createInbox(session,baseDir,nickname,domain,port,httpPrefix, \
                           noOfItems,headerOnly,ocapAlways,pageNumber)
    if boxname=='dm':
        return createDMTimeline(session,baseDir,nickname,domain,port,httpPrefix, \
                                noOfItems,headerOnly,ocapAlways,pageNumber)
    elif boxname=='tlreplies':
        return createRepliesTimeline(session,baseDir,nickname,domain,port,httpPrefix, \
                                     noOfItems,headerOnly,ocapAlways,pageNumber)
    elif boxname=='tlmedia':
        return createMediaTimeline(session,baseDir,nickname,domain,port,httpPrefix, \
                                   noOfItems,headerOnly,ocapAlways,pageNumber)
    elif boxname=='outbox':
        return createOutbox(session,baseDir,nickname,domain,port,httpPrefix, \
                            noOfItems,headerOnly,authorized,pageNumber)
    elif boxname=='moderation':
        return createModeration(baseDir,nickname,domain,port,httpPrefix, \
                                noOfItems,headerOnly,authorized,pageNumber)
    return None

def personInboxJson(baseDir: str,domain: str,port: int,path: str, \
                    httpPrefix: str,noOfItems: int,ocapAlways: bool) -> []:
    """Obtain the inbox feed for the given person
    Authentication is expected to have already happened
    """
    if not '/inbox' in path:
        return None

    # Only show the header by default
    headerOnly=True

    # handle page numbers
    pageNumber=None    
    if '?page=' in path:
        pageNumber=path.split('?page=')[1]
        if pageNumber=='true':
            pageNumber=1
        else:
            try:
                pageNumber=int(pageNumber)
            except:
                pass
        path=path.split('?page=')[0]
        headerOnly=False

    if not path.endswith('/inbox'):
        return None
    nickname=None
    if path.startswith('/users/'):
        nickname=path.replace('/users/','',1).replace('/inbox','')
    if path.startswith('/@'):
        nickname=path.replace('/@','',1).replace('/inbox','')
    if not nickname:
        return None
    if not validNickname(domain,nickname):
        return None
    return createInbox(baseDir,nickname,domain,port,httpPrefix, \
                       noOfItems,headerOnly,ocapAlways,pageNumber)

def setDisplayNickname(baseDir: str,nickname: str, domain: str, \
                       displayName: str) -> bool:
    if len(displayName)>32:
        return False
    handle=nickname.lower()+'@'+domain.lower()
    filename=baseDir+'/accounts/'+handle.lower()+'.json'
    if not os.path.isfile(filename):
        return False

    personJson=loadJson(filename)            
    if not personJson:
        return False
    personJson['name']=displayName
    saveJson(personJson,filename)
    return True

def setBio(baseDir: str,nickname: str, domain: str, bio: str) -> bool:
    if len(bio)>32:
        return False
    handle=nickname.lower()+'@'+domain.lower()
    filename=baseDir+'/accounts/'+handle.lower()+'.json'
    if not os.path.isfile(filename):
        return False

    personJson=loadJson(filename)
    if not personJson:
        return False
    if not personJson.get('summary'):
        return False
    personJson['summary']=bio

    saveJson(personJson,filename)        
    return True

def isSuspended(baseDir: str,nickname: str) -> bool:
    """Returns true if the given nickname is suspended
    """
    adminNickname=getConfigParam(baseDir,'admin')
    if nickname==adminNickname:
        return False

    suspendedFilename=baseDir+'/accounts/suspended.txt'
    if os.path.isfile(suspendedFilename):
        with open(suspendedFilename, "r") as f:
            lines = f.readlines()
        suspendedFile=open(suspendedFilename,"w+")
        for suspended in lines:
            if suspended.strip('\n')==nickname:
                return True
    return False

def unsuspendAccount(baseDir: str,nickname: str) -> None:
    """Removes an account suspention
    """
    suspendedFilename=baseDir+'/accounts/suspended.txt'
    if os.path.isfile(suspendedFilename):
        with open(suspendedFilename, "r") as f:
            lines = f.readlines()
        suspendedFile=open(suspendedFilename,"w+")
        for suspended in lines:
            if suspended.strip('\n')!=nickname:
                suspendedFile.write(suspended)
        suspendedFile.close()

def suspendAccount(baseDir: str,nickname: str) -> None:
    """Suspends the given account
    """
    # Don't suspend the admin
    adminNickname=getConfigParam(baseDir,'admin')
    if nickname==adminNickname:
        return

    # Don't suspend moderators
    moderatorsFile=baseDir+'/accounts/moderators.txt'
    if os.path.isfile(moderatorsFile):
        with open(moderatorsFile, "r") as f:
            lines = f.readlines()
        for moderator in lines:
            if moderator.strip('\n')==nickname:
                return

    suspendedFilename=baseDir+'/accounts/suspended.txt'
    if os.path.isfile(suspendedFilename):
        with open(suspendedFilename, "r") as f:
            lines = f.readlines()
        for suspended in lines:
            if suspended.strip('\n')==nickname:
                return
        suspendedFile=open(suspendedFilename,'a+')
        if suspendedFile:
            suspendedFile.write(nickname+'\n')
            suspendedFile.close()
    else:
        suspendedFile=open(suspendedFilename,'w+')
        if suspendedFile:
            suspendedFile.write(nickname+'\n')
            suspendedFile.close()

def canRemovePost(baseDir: str,nickname: str,domain: str,port: int,postId: str) -> bool:
    """Returns true if the given post can be removed
    """
    if '/statuses/' not in postId:
        return False

    domainFull=domain
    if port:
        if port!=80 and port!=443:
            if ':' not in domain:
                domainFull=domain+':'+str(port)

    # is the post by the admin?
    adminNickname=getConfigParam(baseDir,'admin')
    if domainFull+'/users/'+adminNickname+'/' in postId:
        return False

    # is the post by a moderator?
    moderatorsFile=baseDir+'/accounts/moderators.txt'
    if os.path.isfile(moderatorsFile):
        with open(moderatorsFile, "r") as f:
            lines = f.readlines()
        for moderator in lines:
            if domainFull+'/users/'+moderator.strip('\n')+'/' in postId:
                return False
    return True

def removeTagsForNickname(baseDir: str,nickname: str,domain: str,port: int) -> None:
    """Removes tags for a nickname
    """
    if not os.path.isdir(baseDir+'/tags'):
        return
    domainFull=domain
    if port:
        if port!=80 and port!=443:
            if ':' not in domain:
                domainFull=domain+':'+str(port)
    matchStr=domainFull+'/users/'+nickname+'/'
    directory = os.fsencode(baseDir+'/tags/')
    for f in os.scandir(directory):
        f=f.name
        filename = os.fsdecode(f)
        if not filename.endswith(".txt"):
            continue
        tagFilename=os.path.join(baseDir+'/accounts/',filename)
        if matchStr not in open(tagFilename).read():
            continue
        with open(tagFilename, "r") as f:
            lines = f.readlines()
        tagFile=open(tagFilename,"w+")
        if tagFile:
            for tagline in lines:
                if matchStr not in tagline:
                    tagFile.write(tagline)
            tagFile.close()                

def removeAccount(baseDir: str,nickname: str,domain: str,port: int) -> bool:
    """Removes an account
    """    
    # Don't remove the admin
    adminNickname=getConfigParam(baseDir,'admin')
    if nickname==adminNickname:
        return False

    # Don't remove moderators
    moderatorsFile=baseDir+'/accounts/moderators.txt'
    if os.path.isfile(moderatorsFile):
        with open(moderatorsFile, "r") as f:
            lines = f.readlines()
        for moderator in lines:
            if moderator.strip('\n')==nickname:
                return False

    unsuspendAccount(baseDir,nickname)
    handle=nickname+'@'+domain
    removePassword(baseDir,nickname)
    removeTagsForNickname(baseDir,nickname,domain,port)
    if os.path.isdir(baseDir+'/accounts/'+handle):
        shutil.rmtree(baseDir+'/accounts/'+handle)
    if os.path.isfile(baseDir+'/accounts/'+handle+'.json'):
        os.remove(baseDir+'/accounts/'+handle+'.json')
    if os.path.isfile(baseDir+'/wfendpoints/'+handle+'.json'):
        os.remove(baseDir+'/wfendpoints/'+handle+'.json')
    if os.path.isfile(baseDir+'/keys/private/'+handle+'.key'):
        os.remove(baseDir+'/keys/private/'+handle+'.key')
    if os.path.isfile(baseDir+'/keys/public/'+handle+'.pem'):
        os.remove(baseDir+'/keys/public/'+handle+'.pem')
    if os.path.isdir(baseDir+'/sharefiles/'+nickname):
        shutil.rmtree(baseDir+'/sharefiles/'+nickname)
    return True
