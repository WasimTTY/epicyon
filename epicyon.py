__filename__ = "epicyon.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.1.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@freedombone.net"
__status__ = "Production"

from person import createPerson
from person import createGroup
from person import createSharedInbox
from person import createCapabilitiesInbox
from person import setDisplayNickname
from person import setBio
from person import setProfileImage
from person import removeAccount
from person import activateAccount
from person import deactivateAccount
from skills import setSkillLevel
from roles import setRole
from person import setOrganizationScheme
from webfinger import webfingerHandle
from posts import getPosts
from posts import createPublicPost
from posts import deleteAllPosts
from posts import createOutbox
from posts import archivePosts
from posts import sendPostViaServer
from posts import getPublicPostsOfPerson
from posts import getUserUrl
from posts import archivePosts
from session import createSession
from session import getJson
from blocking import addBlock
from blocking import removeBlock
from filters import addFilter
from filters import removeFilter
import json
import os
import shutil
import sys
import requests
import time
from pprint import pprint
from tests import testHttpsig
from daemon import runDaemon
import socket
from follow import clearFollows
from follow import clearFollowers
from follow import followerOfPerson
from follow import unfollowPerson
from follow import unfollowerOfPerson
from follow import getFollowersOfPerson
from tests import testPostMessageBetweenServers
from tests import testFollowBetweenServers
from tests import testClientToServer
from tests import runAllTests
from config import setConfigParam
from config import getConfigParam
from auth import storeBasicCredentials
from auth import removePassword
from auth import createPassword
from utils import getDomainFromActor
from utils import getNicknameFromActor
from utils import followPerson
from utils import validNickname
from media import archiveMedia
from media import getAttachmentMediaType
from delete import sendDeleteViaServer
from like import sendLikeViaServer
from like import sendUndoLikeViaServer
from blocking import sendBlockViaServer
from blocking import sendUndoBlockViaServer
from roles import sendRoleViaServer
from skills import sendSkillViaServer
from availability import setAvailability
from availability import sendAvailabilityViaServer
from manualapprove import manualDenyFollowRequest
from manualapprove import manualApproveFollowRequest
from shares import sendShareViaServer
from shares import sendUndoShareViaServer
from shares import addShare
from theme import setTheme
import argparse

def str2bool(v):
    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

parser = argparse.ArgumentParser(description='ActivityPub Server')
parser.add_argument('-n','--nickname', dest='nickname', type=str,default=None, \
                    help='Nickname of the account to use')
parser.add_argument('--fol','--follow', dest='follow', type=str,default=None, \
                    help='Handle of account to follow. eg. nickname@domain')
parser.add_argument('--unfol','--unfollow', dest='unfollow', type=str,default=None, \
                    help='Handle of account stop following. eg. nickname@domain')
parser.add_argument('-d','--domain', dest='domain', type=str,default=None, \
                    help='Domain name of the server')
parser.add_argument('-o','--onion', dest='onion', type=str,default=None, \
                    help='Onion domain name of the server if primarily on clearnet')
parser.add_argument('-p','--port', dest='port', type=int,default=None, \
                    help='Port number to run on')
parser.add_argument('--postcache', dest='maxRecentPosts', type=int,default=100, \
                    help='The maximum number of recent posts to store in RAM')
parser.add_argument('--proxy', dest='proxyPort', type=int,default=None, \
                    help='Proxy port number to run on')
parser.add_argument('--path', dest='baseDir', \
                    type=str,default=os.getcwd(), \
                    help='Directory in which to store posts')
parser.add_argument('--language', dest='language', \
                    type=str,default=None, \
                    help='Language code, eg. en/fr/de/es')
parser.add_argument('-a','--addaccount', dest='addaccount', \
                    type=str,default=None, \
                    help='Adds a new account')
parser.add_argument('-g','--addgroup', dest='addgroup', \
                    type=str,default=None, \
                    help='Adds a new group')
parser.add_argument('--activate', dest='activate', \
                    type=str,default=None, \
                    help='Activate a previously deactivated account')
parser.add_argument('--deactivate', dest='deactivate', \
                    type=str,default=None, \
                    help='Deactivate an account')
parser.add_argument('-r','--rmaccount', dest='rmaccount', \
                    type=str,default=None, \
                    help='Remove an account')
parser.add_argument('--rmgroup', dest='rmgroup', \
                    type=str,default=None, \
                    help='Remove a group')
parser.add_argument('--pass','--password', dest='password', \
                    type=str,default=None, \
                    help='Set a password for an account')
parser.add_argument('--chpass','--changepassword', \
                    nargs='+',dest='changepassword', \
                    help='Change the password for an account')
parser.add_argument('--actor', dest='actor', type=str,default=None, \
                    help='Show the json actor the given handle')
parser.add_argument('--posts', dest='posts', type=str,default=None, \
                    help='Show posts for the given handle')
parser.add_argument('--postsraw', dest='postsraw', type=str,default=None, \
                    help='Show raw json of posts for the given handle')
parser.add_argument('--json', dest='json', type=str,default=None, \
                    help='Show the json for a given activitypub url')
parser.add_argument('-f','--federate', nargs='+',dest='federationList', \
                    help='Specify federation list separated by spaces')
parser.add_argument("--mediainstance", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Media Instance - favor media over text")
parser.add_argument("--blogsinstance", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Blogs Instance - favor blogs over microblogging")
parser.add_argument("--debug", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Show debug messages")
parser.add_argument("--authenticatedFetch", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Enable authentication on GET requests for json (authenticated fetch)")
parser.add_argument("--instanceOnlySkillsSearch", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Skills searches only return results from this instance")
parser.add_argument("--http", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Use http only")
parser.add_argument("--dat", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Use dat protocol only")
parser.add_argument("--i2p", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Use i2p protocol only")
parser.add_argument("--tor", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Route via Tor")
parser.add_argument("--tests", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Run unit tests")
parser.add_argument("--testsnetwork", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Run network unit tests")
parser.add_argument("--testdata", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Generate some data for testing purposes")
parser.add_argument("--ocap", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Always strictly enforce object capabilities")
parser.add_argument("--noreply", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Default capabilities don't allow replies on posts")
parser.add_argument("--nolike", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Default capabilities don't allow likes/favourites on posts")
parser.add_argument("--nopics", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Default capabilities don't allow attached pictures")
parser.add_argument("--noannounce","--norepeat", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Default capabilities don't allow announce/repeat")
parser.add_argument("--cw", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Default capabilities don't allow posts without content warnings")
parser.add_argument('--icon','--avatar', dest='avatar', type=str,default=None, \
                    help='Set the avatar filename for an account')
parser.add_argument('--image','--background', dest='backgroundImage', type=str,default=None, \
                    help='Set the profile background image for an account')
parser.add_argument('--archive', dest='archive', type=str,default=None, \
                    help='Archive old files to the given directory')
parser.add_argument('--archiveweeks', dest='archiveWeeks', type=str,default=None, \
                    help='Specify the number of weeks after which data will be archived')
parser.add_argument('--maxposts', dest='archiveMaxPosts', type=str,default=None, \
                    help='Maximum number of posts in in/outbox')
parser.add_argument('--message', dest='message', type=str,default=None, \
                    help='Message content')
parser.add_argument('--delete', dest='delete', type=str,default=None, \
                    help='Delete a specified post')
parser.add_argument("--allowdeletion", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Do not allow deletions")
parser.add_argument('--repeat','--announce', dest='announce', type=str,default=None, \
                    help='Announce/repeat a url')
parser.add_argument('--favorite','--like', dest='like', type=str,default=None, \
                    help='Like a url')
parser.add_argument('--undolike','--unlike', dest='undolike', type=str,default=None, \
                    help='Undo a like of a url')
parser.add_argument('--sendto', dest='sendto', type=str,default=None, \
                    help='Address to send a post to')
parser.add_argument('--attach', dest='attach', type=str,default=None, \
                    help='File to attach to a post')
parser.add_argument('--imagedescription', dest='imageDescription', type=str,default=None, \
                    help='Description of an attached image')
parser.add_argument("--blurhash", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Create blurhash for an image")
parser.add_argument('--warning','--warn','--cwsubject','--subject', dest='subject', type=str,default=None, \
                    help='Subject of content warning')
parser.add_argument('--reply','--replyto', dest='replyto', type=str,default=None, \
                    help='Url of post to reply to')
parser.add_argument("--followersonly", type=str2bool, nargs='?', \
                    const=True, default=True, \
                    help="Send to followers only")
parser.add_argument("--followerspending", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Show a list of followers pending")
parser.add_argument('--approve', dest='approve', type=str,default=None, \
                    help='Approve a follow request')
parser.add_argument('--deny', dest='deny', type=str,default=None, \
                    help='Deny a follow request')
parser.add_argument("-c","--client", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Use as an ActivityPub client")
parser.add_argument('--maxreplies', dest='maxReplies', type=int,default=64, \
                    help='Maximum number of replies to a post')
parser.add_argument('--maxMentions','--hellthread', dest='maxMentions', type=int,default=10, \
                    help='Maximum number of mentions within a post')
parser.add_argument('--maxEmoji','--maxemoji', dest='maxEmoji', type=int,default=10, \
                    help='Maximum number of emoji within a post')
parser.add_argument('--role', dest='role', type=str,default=None, \
                    help='Set a role for a person')
parser.add_argument('--organization','--project', dest='project', type=str,default=None, \
                    help='Set a project for a person')
parser.add_argument('--skill', dest='skill', type=str,default=None, \
                    help='Set a skill for a person')
parser.add_argument('--level', dest='skillLevelPercent', type=int,default=None, \
                    help='Set a skill level for a person as a percentage, or zero to remove')
parser.add_argument('--status','--availability', dest='availability', type=str,default=None, \
                    help='Set an availability status')
parser.add_argument('--block', dest='block', type=str,default=None, \
                    help='Block a particular address')
parser.add_argument('--unblock', dest='unblock', type=str,default=None, \
                    help='Remove a block on a particular address')
parser.add_argument('--delegate', dest='delegate', type=str,default=None, \
                    help='Address of an account to delegate a role to')
parser.add_argument('--undodelegate','--undelegate', dest='undelegate', type=str,default=None, \
                    help='Removes a delegated role for the given address')
parser.add_argument('--filter', dest='filterStr', type=str,default=None, \
                    help='Adds a word or phrase which if present will cause a message to be ignored')
parser.add_argument('--unfilter', dest='unfilterStr', type=str,default=None, \
                    help='Remove a filter on a particular word or phrase')
parser.add_argument('--domainmax', dest='domainMaxPostsPerDay', type=int,default=8640, \
                    help='Maximum number of received posts from a domain per day')
parser.add_argument('--accountmax', dest='accountMaxPostsPerDay', type=int,default=8640, \
                    help='Maximum number of received posts from an account per day')
parser.add_argument('--itemName', dest='itemName', type=str,default=None, \
                    help='Name of an item being shared')
parser.add_argument('--undoItemName', dest='undoItemName', type=str,default=None, \
                    help='Name of an shared item to remove')
parser.add_argument('--summary', dest='summary', type=str,default=None, \
                    help='Description of an item being shared')
parser.add_argument('--itemImage', dest='itemImage', type=str,default=None, \
                    help='Filename of an image for an item being shared')
parser.add_argument('--itemType', dest='itemType', type=str,default=None, \
                    help='Type of item being shared')
parser.add_argument('--itemCategory', dest='itemCategory', type=str,default=None, \
                    help='Category of item being shared')
parser.add_argument('--location', dest='location', type=str,default=None, \
                    help='Location/City of item being shared')
parser.add_argument('--duration', dest='duration', type=str,default=None, \
                    help='Duration for which to share an item')
parser.add_argument('--registration', dest='registration', type=str,default=None, \
                    help='Whether new registrations are open or closed')
parser.add_argument("--nosharedinbox", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help='Disable shared inbox')
parser.add_argument('--maxregistrations', dest='maxRegistrations', type=int,default=None, \
                    help='The maximum number of new registrations')
parser.add_argument("--resetregistrations", type=str2bool, nargs='?', \
                    const=True, default=False, \
                    help="Reset the number of remaining registrations")
args = parser.parse_args()

debug=False
if args.debug:
    debug=True

if args.tests:
    runAllTests()
    sys.exit()

if args.testsnetwork:
    print('Network Tests')
    testPostMessageBetweenServers()
    testFollowBetweenServers()
    testClientToServer()
    print('All tests succeeded')
    sys.exit()

httpPrefix='https'
if args.http:
    httpPrefix='http'

baseDir=args.baseDir
if baseDir.endswith('/'):
    print("--path option should not end with '/'")
    sys.exit()

if args.posts:
    if '@' not in args.posts:
        print('Syntax: --posts nickname@domain')
        sys.exit()
    if not args.http:
        args.port=443
    nickname=args.posts.split('@')[0]
    domain=args.posts.split('@')[1]
    getPublicPostsOfPerson(baseDir,nickname,domain,False,True, \
                           args.tor,args.port,httpPrefix,debug, \
                           __version__)
    sys.exit()

if args.postsraw:
    if '@' not in args.postsraw:
        print('Syntax: --postsraw nickname@domain')
        sys.exit()        
    if not args.http:
        args.port=443
    nickname=args.postsraw.split('@')[0]
    domain=args.postsraw.split('@')[1]
    getPublicPostsOfPerson(baseDir,nickname,domain,False,False, \
                           args.tor,args.port,httpPrefix,debug, \
                           __version__)
    sys.exit()

if args.json:
    session = createSession(False)
    asHeader = {'Accept': 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'}
    testJson = getJson(session,args.json,asHeader,None,__version__,httpPrefix,None)
    pprint(testJson)
    sys.exit()

# create cache for actors
if not os.path.isdir(baseDir+'/cache'):
    os.mkdir(baseDir+'/cache')
if not os.path.isdir(baseDir+'/cache/actors'):
    print('Creating actors cache')
    os.mkdir(baseDir+'/cache/actors')
if not os.path.isdir(baseDir+'/cache/announce'):
    print('Creating announce cache')
    os.mkdir(baseDir+'/cache/announce')

# set the theme in config.json
themeName=getConfigParam(baseDir,'theme')
if not themeName:
    setConfigParam(baseDir,'theme','default')
    themeName='default'

if not args.mediainstance:
    mediaInstance=getConfigParam(baseDir,'mediaInstance')
    if mediaInstance!=None:
        args.mediainstance=mediaInstance

if not args.blogsinstance:
    blogsInstance=getConfigParam(baseDir,'blogsInstance')
    if blogsInstance!=None:
        args.blogsinstance=blogsInstance
    
# set the instance title in config.json
title=getConfigParam(baseDir,'instanceTitle')
if not title:
    setConfigParam(baseDir,'instanceTitle','Epicyon')

# set the instance description in config.json
descFull=getConfigParam(baseDir,'instanceDescription')
if not descFull:
    setConfigParam(baseDir,'instanceDescription','Just another ActivityPub server')

# set the short instance description in config.json
descShort=getConfigParam(baseDir,'instanceDescriptionShort')
if not descShort:
    setConfigParam(baseDir,'instanceDescriptionShort','Just another ActivityPub server')

if args.domain:
    domain=args.domain
    setConfigParam(baseDir,'domain',domain)

if args.onion:
    if not args.onion.endswith('.onion'):
        print(args.onion+' does not look like an onion domain')
        sys.exit()
    if '://' in args.onion:
        args.onion=args.onion.split('://')[1]
    onionDomain=args.onion
    setConfigParam(baseDir,'onion',onionDomain)

if not args.language:
    languageCode=getConfigParam(baseDir,'language')
    if languageCode:
        args.language=languageCode

# maximum number of new registrations
if not args.maxRegistrations:
    maxRegistrations=getConfigParam(baseDir,'maxRegistrations')
    if not maxRegistrations:
        maxRegistrations=10
        setConfigParam(baseDir,'maxRegistrations',str(maxRegistrations))
    else:
        maxRegistrations=int(maxRegistrations)
else:
    maxRegistrations=args.maxRegistrations
    setConfigParam(baseDir,'maxRegistrations',str(maxRegistrations))

# if this is the initial run then allow new registrations
if not getConfigParam(baseDir,'registration'):
    setConfigParam(baseDir,'registration','open')
    setConfigParam(baseDir,'maxRegistrations',str(maxRegistrations))
    setConfigParam(baseDir,'registrationsRemaining',str(maxRegistrations))

if args.resetregistrations:    
    setConfigParam(baseDir,'registrationsRemaining',str(maxRegistrations))
    print('Number of new registrations reset to '+str(maxRegistrations))
    
# whether new registrations are open or closed
if args.registration:
    if args.registration.lower()=='open':        
        registration=getConfigParam(baseDir,'registration')
        if not registration:
            setConfigParam(baseDir,'registrationsRemaining',str(maxRegistrations))
        else:
            if registration!='open':
                setConfigParam(baseDir,'registrationsRemaining',str(maxRegistrations))
        setConfigParam(baseDir,'registration','open')
        print('New registrations open')
    else:
        setConfigParam(baseDir,'registration','closed')
        print('New registrations closed')
    
# unique ID for the instance
instanceId=getConfigParam(baseDir,'instanceId')
if not instanceId:
    instanceId=createPassword(32)
    setConfigParam(baseDir,'instanceId',instanceId)
    print('Instance ID: '+instanceId)

# get domain name from configuration
configDomain=getConfigParam(baseDir,'domain')
if configDomain:
    domain=configDomain
else:
    domain='localhost'

# get onion domain name from configuration
configOnionDomain=getConfigParam(baseDir,'onion')
if configOnionDomain:
    onionDomain=configOnionDomain
else:
    onionDomain=None

# get port number from configuration
configPort=getConfigParam(baseDir,'port')
if configPort:
    port=configPort
else:
    port=8085

configProxyPort=getConfigParam(baseDir,'proxyPort')
if configProxyPort:
    proxyPort=configProxyPort
else:
    proxyPort=port

nickname=None
if args.nickname:
    nickname=nickname

federationList=[]
if args.federationList:
    if len(args.federationList)==1:
        if not (args.federationList[0].lower()=='any' or \
                args.federationList[0].lower()=='all' or \
                args.federationList[0].lower()=='*'):
            for federationDomain in args.federationList:
                if '@' in federationDomain:
                    print(federationDomain+': Federate with domains, not individual accounts')
                    sys.exit()
            federationList=args.federationList.copy()
        setConfigParam(baseDir,'federationList',federationList)
else:
    configFederationList=getConfigParam(baseDir,'federationList')
    if configFederationList:
        federationList=configFederationList

useTor=args.tor
if domain.endswith('.onion'):
    useTor=True

if args.approve:
    if not args.nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()
    if '@' not in args.approve:
        print('syntax: --approve nick@domain')
        sys.exit()
    session = createSession(useTor)        
    sendThreads=[]
    postLog=[]
    cachedWebfingers={}
    personCache={}
    acceptedCaps=[]
    manualApproveFollowRequest(session,baseDir, \
                               httpPrefix,
                               args.nickname,domain,port, \
                               args.approve, \
                               federationList, \
                               sendThreads,postLog, \
                               cachedWebfingers,personCache, \
                               acceptedCaps, \
                               debug,__version__)
    sys.exit()

if args.deny:
    if not args.nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()
    if '@' not in args.deny:
        print('syntax: --deny nick@domain')
        sys.exit()
    session = createSession(useTor)        
    sendThreads=[]
    postLog=[]
    cachedWebfingers={}
    personCache={}
    manualDenyFollowRequest(session,baseDir, \
                            httpPrefix,
                            args.nickname,domain,port, \
                            args.deny, \
                            federationList, \
                            sendThreads,postLog, \
                            cachedWebfingers,personCache, \
                            debug,__version__)
    sys.exit()

if args.followerspending:
    if not args.nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()

    accountsDir=baseDir+'/accounts/'+args.nickname+'@'+domain
    approveFollowsFilename=accountsDir+'/followrequests.txt'
    approveCtr=0
    if os.path.isfile(approveFollowsFilename):
        with open(approveFollowsFilename, 'r') as approvefile:
            for approve in approvefile:
                print(approve.replace('\n',''))
                approveCtr+=1
    if approveCtr==0:
        print('There are no follow requests pending approval.')
    sys.exit()
        
    
if args.message:
    if not args.nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()
        
    if not args.password:
        print('Specify a password with the --password option')
        sys.exit()
        
    session = createSession(useTor)        
    if not args.sendto:
        print('Specify an account to sent to: --sendto [nickname@domain]')
        sys.exit()        
    if '@' not in args.sendto and \
       not args.sendto.lower().endswith('public') and \
       not args.sendto.lower().endswith('followers'):
        print('syntax: --sendto [nickname@domain]')
        print('        --sendto public')
        print('        --sendto followers')
        sys.exit()
    if '@' in args.sendto:
        toNickname=args.sendto.split('@')[0]
        toDomain=args.sendto.split('@')[1].replace('\n','')
        toPort=443
        if ':' in toDomain:
            toPort=toDomain.split(':')[1]
            toDomain=toDomain.split(':')[0]
    else:
        if args.sendto.endswith('followers'):
            toNickname=None
            toDomain='followers'
            toPort=port
        else:
            toNickname=None
            toDomain='public'
            toPort=port
        
    #ccUrl=httpPrefix+'://'+domain+'/users/'+nickname+'/followers'
    ccUrl=None
    sendMessage=args.message
    followersOnly=args.followersonly
    clientToServer=args.client
    attachedImageDescription=args.imageDescription
    useBlurhash=args.blurhash
    sendThreads = []
    postLog = []
    personCache={}
    cachedWebfingers={}
    subject=args.subject
    attach=args.attach
    mediaType=None
    if attach:
        mediaType=getAttachmentMediaType(attach)
    replyTo=args.replyto
    followersOnly=False
    isArticle=False
    print('Sending post to '+args.sendto)

    sendPostViaServer(__version__, \
                      baseDir,session,args.nickname,args.password, \
                      domain,port, \
                      toNickname,toDomain,toPort,ccUrl, \
                      httpPrefix,sendMessage,followersOnly, \
                      attach,mediaType, \
                      attachedImageDescription,useBlurhash, \
                      cachedWebfingers,personCache,isArticle, \
                      args.debug,replyTo,replyTo,subject)
    for i in range(10):
        # TODO detect send success/fail
        time.sleep(1)
    sys.exit()

if args.announce:
    if not args.nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()
        
    if not args.password:
        print('Specify a password with the --password option')
        sys.exit()
        
    session = createSession(useTor)        
    personCache={}
    cachedWebfingers={}
    print('Sending announce/repeat of '+args.announce)

    sendAnnounceViaServer(baseDir,session,args.nickname,args.password,
                          domain,port, \
                          httpPrefix,args.announce, \
                          cachedWebfingers,personCache, \
                          True,__version__)
    for i in range(10):
        # TODO detect send success/fail
        time.sleep(1)
    sys.exit()

if args.itemName:
    if not args.password:
        print('Specify a password with the --password option')
        sys.exit()

    if not args.nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()

    if not args.summary:
        print('Specify a description for your shared item with the --summary option')
        sys.exit()

    if not args.itemType:
        print('Specify a type of shared item with the --itemType option')
        sys.exit()

    if not args.itemCategory:
        print('Specify a category of shared item with the --itemCategory option')
        sys.exit()

    if not args.location:
        print('Specify a location or city where theshared item resides with the --location option')
        sys.exit()

    if not args.duration:
        print('Specify a duration to share the object with the --duration option')
        sys.exit()

    session = createSession(useTor)        
    personCache={}
    cachedWebfingers={}
    print('Sending shared item: '+args.itemName)

    sendShareViaServer(baseDir,session, \
                       args.nickname,args.password, \
                       domain,port, \
                       httpPrefix, \
                       args.itemName, \
                       args.summary, \
                       args.itemImage, \
                       args.itemType, \
                       args.itemCategory, \
                       args.location, \
                       args.duration, \
                       cachedWebfingers,personCache, \
                       debug,__version__)
    for i in range(10):
        # TODO detect send success/fail
        time.sleep(1)
    sys.exit()

if args.undoItemName:
    if not args.password:
        print('Specify a password with the --password option')
        sys.exit()

    if not args.nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()

    session = createSession(useTor)        
    personCache={}
    cachedWebfingers={}
    print('Sending undo of shared item: '+args.undoItemName)

    sendUndoShareViaServer(session, \
                           args.nickname,args.password, \
                           domain,port, \
                           httpPrefix, \
                           args.undoItemName, \
                           cachedWebfingers,personCache, \
                           debug,__version__)
    for i in range(10):
        # TODO detect send success/fail
        time.sleep(1)
    sys.exit()

if args.like:
    if not args.nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()
        
    if not args.password:
        print('Specify a password with the --password option')
        sys.exit()
        
    session = createSession(useTor)        
    personCache={}
    cachedWebfingers={}
    print('Sending like of '+args.like)

    sendLikeViaServer(baseDir,session, \
                      args.nickname,args.password, \
                      domain,port, \
                      httpPrefix,args.like, \
                      cachedWebfingers,personCache, \
                      True,__version__)
    for i in range(10):
        # TODO detect send success/fail
        time.sleep(1)
    sys.exit()

if args.undolike:
    if not args.nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()
        
    if not args.password:
        print('Specify a password with the --password option')
        sys.exit()
        
    session = createSession(useTor)        
    personCache={}
    cachedWebfingers={}
    print('Sending undo like of '+args.undolike)

    sendUndoLikeViaServer(baseDir,session, \
                          args.nickname,args.password, \
                          domain,port, \
                          httpPrefix,args.undolike, \
                          cachedWebfingers,personCache, \
                          True,__version__)
    for i in range(10):
        # TODO detect send success/fail
        time.sleep(1)
    sys.exit()

if args.delete:
    if not args.nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()
        
    if not args.password:
        print('Specify a password with the --password option')
        sys.exit()
        
    session = createSession(useTor)        
    personCache={}
    cachedWebfingers={}
    print('Sending delete request of '+args.delete)

    sendDeleteViaServer(baseDir,session, \
                        args.nickname,args.password, \
                        domain,port, \
                        httpPrefix,args.delete, \
                        cachedWebfingers,personCache, \
                        True,__version__)
    for i in range(10):
        # TODO detect send success/fail
        time.sleep(1)
    sys.exit()

if args.follow:
    # follow via c2s protocol
    if '.' not in args.follow:
        print("This doesn't look like a fediverse handle")
        sys.exit()
    if not args.nickname:
        print('Please specify the nickname for the account with --nickname')
        sys.exit()
    if not args.password:
        print('Please specify the password for '+args.nickname+' on '+domain)
        sys.exit()
        
    followNickname=getNicknameFromActor(args.follow)
    if not followNickname:
        print('Unable to find nickname in '+args.follow)
        sys.exit()        
    followDomain,followPort=getDomainFromActor(args.follow)

    session = createSession(useTor)
    personCache={}
    cachedWebfingers={}
    followHttpPrefix=httpPrefix
    if args.follow.startswith('https'):
        followHttpPrefix='https'

    sendFollowRequestViaServer(baseDir,session, \
                               args.nickname,args.password, \
                               domain,port, \
                               followNickname,followDomain,followPort, \
                               httpPrefix, \
                               cachedWebfingers,personCache, \
                               debug,__version__)
    for t in range(20):
        time.sleep(1)
        # TODO some method to know if it worked
    print('Ok')
    sys.exit()

if args.unfollow:
    # unfollow via c2s protocol
    if '.' not in args.follow:
        print("This doesn't look like a fediverse handle")
        sys.exit()
    if not args.nickname:
        print('Please specify the nickname for the account with --nickname')
        sys.exit()
    if not args.password:
        print('Please specify the password for '+args.nickname+' on '+domain)
        sys.exit()
        
    followNickname=getNicknameFromActor(args.unfollow)
    if not followNickname:
        print('WARN: unable to find nickname in '+args.unfollow)
        sys.exit()        
    followDomain,followPort=getDomainFromActor(args.unfollow)

    session = createSession(useTor)
    personCache={}
    cachedWebfingers={}
    followHttpPrefix=httpPrefix
    if args.follow.startswith('https'):
        followHttpPrefix='https'

    sendUnfollowRequestViaServer(baseDir,session, \
                                 args.nickname,args.password, \
                                 domain,port, \
                                 followNickname,followDomain,followPort, \
                                 httpPrefix, \
                                 cachedWebfingers,personCache, \
                                 debug,__version__)
    for t in range(20):
        time.sleep(1)
        # TODO some method to know if it worked
    print('Ok')
    sys.exit()

nickname='admin'
if args.domain:
    domain=args.domain
    setConfigParam(baseDir,'domain',domain)
if args.port:
    port=args.port
    setConfigParam(baseDir,'port',port)
if args.proxyPort:
    proxyPort=args.proxyPort
    setConfigParam(baseDir,'proxyPort',proxyPort)
ocapAlways=False    
if args.ocap:
    ocapAlways=args.ocap
if args.dat:
    httpPrefix='dat'
if args.i2p:
    httpPrefix='i2p'

if args.actor:
    originalActor=args.actor
    if '/@' in args.actor or '/users/' in args.actor or args.actor.startswith('http') or args.actor.startswith('dat'):
        # format: https://domain/@nick
        args.actor=args.actor.replace('https://','').replace('http://','').replace('dat://','').replace('i2p://','').replace('/@','/users/')
        if '/users/' not in args.actor and \
           '/channel/' not in args.actor and \
           '/profile/' not in args.actor:
            print('Expected actor format: https://domain/@nick or https://domain/users/nick')
            sys.exit()
        if '/users/' in args.actor:
            nickname=args.actor.split('/users/')[1].replace('\n','')
            domain=args.actor.split('/users/')[0]
        elif '/profile/' in args.actor:
            nickname=args.actor.split('/profile/')[1].replace('\n','')
            domain=args.actor.split('/profile/')[0]
        else:
            nickname=args.actor.split('/channel/')[1].replace('\n','')
            domain=args.actor.split('/channel/')[0]
    else:
        # format: @nick@domain
        if '@' not in args.actor:
            print('Syntax: --actor nickname@domain')
            sys.exit()
        if args.actor.startswith('@'):
            args.actor=args.actor[1:]
        if '@' not in args.actor:
            print('Syntax: --actor nickname@domain')
            sys.exit()
        nickname=args.actor.split('@')[0]
        domain=args.actor.split('@')[1].replace('\n','')
    wfCache={}
    if args.http or domain.endswith('.onion'):
        httpPrefix='http'
        port=80
    else:
        httpPrefix='https'
        port=443
    session=createSession(useTor)
    if nickname=='inbox':
        nickname=domain

    wfRequest=webfingerHandle(session,nickname+'@'+domain,httpPrefix,wfCache, \
                              None,__version__)
    if not wfRequest:
        print('Unable to webfinger '+nickname+'@'+domain)
        sys.exit()

    pprint(wfRequest)

    personUrl=None
    if wfRequest.get('errors'):
        print('wfRequest error: '+str(wfRequest['errors']))
        if '/users/' in args.actor or \
           '/profile/' in args.actor or \
           '/channel/' in args.actor:
            personUrl=originalActor
        else:
            sys.exit()
        
    asHeader = {'Accept': 'application/activity+json; profile="https://www.w3.org/ns/activitystreams"'}
    if not personUrl:
        personUrl = getUserUrl(wfRequest)
    if nickname==domain:
        personUrl=personUrl.replace('/users/','/actor/').replace('/channel/','/actor/').replace('/profile/','/actor/')
    if not personUrl:
        # try single user instance
        personUrl=httpPrefix+'://'+domain
        asHeader = {'Accept': 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'}
    if '/channel/' in personUrl:
        asHeader = {'Accept': 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'}
    personJson = getJson(session,personUrl,asHeader,None,__version__,httpPrefix,None)
    if personJson:
        pprint(personJson)
    else:
        asHeader = {'Accept': 'application/jrd+json; profile="https://www.w3.org/ns/activitystreams"'}
        personJson = getJson(session,personUrl,asHeader,None,__version__,httpPrefix,None)
        if personJson:
            pprint(personJson)
        else:
            print('Failed to get '+personUrl)
    sys.exit()

if args.addaccount:
    if '@' in args.addaccount:
        nickname=args.addaccount.split('@')[0]
        domain=args.addaccount.split('@')[1]
    else:
        nickname=args.addaccount
        if not args.domain or not getConfigParam(baseDir,'domain'):
            print('Use the --domain option to set the domain name')
            sys.exit()
    if not validNickname(domain,nickname):
        print(nickname+' is a reserved name. Use something different.')
        sys.exit()        
    if not args.password:
        print('Use the --password option to set the password for '+nickname)
        sys.exit()
    if len(args.password.strip())<8:
        print('Password should be at least 8 characters')
        sys.exit()            
    if os.path.isdir(baseDir+'/accounts/'+nickname+'@'+domain):
        print('Account already exists')
        sys.exit()
    if os.path.isdir(baseDir+'/deactivated/'+nickname+'@'+domain):
        print('Account is deactivated')
        sys.exit()
    createPerson(baseDir,nickname,domain,port,httpPrefix,True,args.password.strip())
    if os.path.isdir(baseDir+'/accounts/'+nickname+'@'+domain):
        print('Account created for '+nickname+'@'+domain)
    else:
        print('Account creation failed')
    sys.exit()

if args.addgroup:
    if '@' in args.addgroup:
        nickname=args.addgroup.split('@')[0]
        domain=args.addgroup.split('@')[1]
    else:
        nickname=args.addgroup
        if not args.domain or not getConfigParam(baseDir,'domain'):
            print('Use the --domain option to set the domain name')
            sys.exit()
    if not validNickname(domain,nickname):
        print(nickname+' is a reserved name. Use something different.')
        sys.exit()
    if not args.password:
        print('Use the --password option to set the password for '+nickname)
        sys.exit()
    if len(args.password.strip())<8:
        print('Password should be at least 8 characters')
        sys.exit()
    if os.path.isdir(baseDir+'/accounts/'+nickname+'@'+domain):
        print('Group already exists')
        sys.exit()
    createGroup(baseDir,nickname,domain,port,httpPrefix,True,args.password.strip())
    if os.path.isdir(baseDir+'/accounts/'+nickname+'@'+domain):
        print('Group created for '+nickname+'@'+domain)
    else:
        print('Group creation failed')
    sys.exit()

if args.rmgroup:
    args.rmaccount=args.rmgroup

if args.deactivate:
    args.rmaccount=args.deactivate

if args.rmaccount:
    if '@' in args.rmaccount:
        nickname=args.rmaccount.split('@')[0]
        domain=args.rmaccount.split('@')[1]
    else:
        nickname=args.rmaccount
        if not args.domain or not getConfigParam(baseDir,'domain'):
            print('Use the --domain option to set the domain name')
            sys.exit()
    if args.deactivate:
        if deactivateAccount(baseDir,nickname,domain):
            print('Account for '+handle+' was deactivated')
        else:
            print('Account for '+handle+' was not found')
        sys.exit()
    if removeAccount(baseDir,nickname,domain,port):
        if not args.rmgroup:
            print('Account for '+handle+' was removed')
        else:
            print('Group '+handle+' was removed')
        sys.exit()

if args.activate:
    if '@' in args.activate:
        nickname=args.activate.split('@')[0]
        domain=args.activate.split('@')[1]
    else:
        nickname=args.activate
        if not args.domain or not getConfigParam(baseDir,'domain'):
            print('Use the --domain option to set the domain name')
            sys.exit()
    if activateAccount(baseDir,nickname,domain):
        print('Account for '+handle+' was activated')
    else:
        print('Deactivated account for '+handle+' was not found')
    sys.exit()

if args.changepassword:
    if len(args.changepassword)!=2:
        print('--changepassword [nickname] [new password]')
        sys.exit()
    if '@' in args.changepassword[0]:
        nickname=args.changepassword[0].split('@')[0]
        domain=args.changepassword[0].split('@')[1]
    else:
        nickname=args.changepassword[0]
        if not args.domain or not getConfigParam(baseDir,'domain'):
            print('Use the --domain option to set the domain name')
            sys.exit()
    newPassword=args.changepassword[1]
    if len(newPassword)<8:
        print('Password should be at least 8 characters')
        sys.exit()
    if not os.path.isdir(baseDir+'/accounts/'+nickname+'@'+domain):
        print('Account '+nickname+'@'+domain+' not found')
        sys.exit()
    passwordFile=baseDir+'/accounts/passwords'
    if os.path.isfile(passwordFile):
        if nickname+':' in open(passwordFile).read():
            storeBasicCredentials(baseDir,nickname,newPassword)
            print('Password for '+nickname+' was changed')
        else:
            print(nickname+' is not in the passwords file')
    else:
        print('Passwords file not found')
    sys.exit()

archiveWeeks=4
if args.archiveWeeks:
    archiveWeeks=args.archiveWeeks
archiveMaxPosts=32000
if args.archiveMaxPosts:
    archiveMaxPosts=args.archiveMaxPosts

if args.archive:
    if args.archive.lower().endswith('null') or \
       args.archive.lower().endswith('delete') or \
       args.archive.lower().endswith('none'):
        args.archive=None
        print('Archiving with deletion of old posts...')
    else:
        print('Archiving to '+args.archive+'...')
    archiveMedia(baseDir,args.archive,archiveWeeks)
    archivePosts(baseDir,httpPrefix,args.archive,archiveMaxPosts)
    print('Archiving complete')
    sys.exit()

if not args.domain and not domain:
    print('Specify a domain with --domain [name]')
    sys.exit()

if args.avatar:
    if not os.path.isfile(args.avatar):
        print(args.avatar+' is not an image filename')
        sys.exit()
    if not args.nickname:
        print('Specify a nickname with --nickname [name]')
        sys.exit()
    if setProfileImage(baseDir,httpPrefix,args.nickname,domain, \
                       port,args.avatar,'avatar','128x128'):
        print('Avatar added for '+args.nickname)
    else:
        print('Avatar was not added for '+args.nickname)
    sys.exit()    

if args.backgroundImage:
    if not os.path.isfile(args.backgroundImage):
        print(args.backgroundImage+' is not an image filename')
        sys.exit()
    if not args.nickname:
        print('Specify a nickname with --nickname [name]')
        sys.exit()
    if setProfileImage(baseDir,httpPrefix,args.nickname,domain, \
                       port,args.backgroundImage,'background','256x256'):
        print('Background image added for '+args.nickname)
    else:
        print('Background image was not added for '+args.nickname)
    sys.exit()    

if args.project:
    if not args.delegate and not args.undelegate:        
        if not nickname:
            print('No nickname given')
            sys.exit()
        
        if args.role.lower()=='none' or \
           args.role.lower()=='remove' or \
           args.role.lower()=='delete':
            args.role=None
        if args.role:
            if setRole(baseDir,nickname,domain,args.project,args.role):
                print('Role within '+args.project+' set to '+args.role)
        else:
            if setRole(baseDir,nickname,domain,args.project,None):
                print('Left '+args.project)
        sys.exit()

if args.skill:
    if not nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()
        
    if not args.password:
        print('Specify a password with the --password option')
        sys.exit()

    if not args.skillLevelPercent:
        print('Specify a skill level in the range 0-100')
        sys.exit()

    if int(args.skillLevelPercent)<0 or int(args.skillLevelPercent)>100:
        print('Skill level should be a percentage in the range 0-100')
        sys.exit()

    session = createSession(useTor)        
    personCache={}
    cachedWebfingers={}
    print('Sending '+args.skill+' skill level '+str(args.skillLevelPercent)+' for '+nickname)

    sendSkillViaServer(baseDir,session, \
                       nickname,args.password, \
                       domain,port, \
                       httpPrefix, \
                       args.skill,args.skillLevelPercent, \
                       cachedWebfingers,personCache, \
                       True,__version__)
    for i in range(10):
        # TODO detect send success/fail
        time.sleep(1)
    sys.exit()

if args.availability:
    if not nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()
        
    if not args.password:
        print('Specify a password with the --password option')
        sys.exit()

    session = createSession(useTor)        
    personCache={}
    cachedWebfingers={}
    print('Sending availability status of '+nickname+' as '+args.availability)

    sendAvailabilityViaServer(baseDir,session,nickname,args.password,
                              domain,port, \
                              httpPrefix, \
                              args.availability, \
                              cachedWebfingers,personCache, \
                              True,__version__)
    for i in range(10):
        # TODO detect send success/fail
        time.sleep(1)
    sys.exit()

if federationList:
    print('Federating with: '+str(federationList))

#if not os.path.isdir(baseDir+'/accounts/'+nickname+'@'+domain):
#    print('Creating default admin account '+nickname+'@'+domain)
#    print('See config.json for the password. You can remove the password from config.json after moving it elsewhere.')
#    adminPassword=createPassword(10)
#    setConfigParam(baseDir,'adminPassword',adminPassword)
#    createPerson(baseDir,nickname,domain,port,httpPrefix,True,adminPassword)

if args.block:
    if not nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()
        
    if not args.password:
        print('Specify a password with the --password option')
        sys.exit()

    if '@' in args.block:
        blockedDomain=args.block.split('@')[1].replace('\n','')
        blockedNickname=args.block.split('@')[0]
        blockedActor=httpPrefix+'://'+blockedDomain+'/users/'+blockedNickname
        args.block=blockedActor
    else:
        if '/users/' not in args.block:
            print(args.block+' does not look like an actor url')
            sys.exit()

    session = createSession(useTor)        
    personCache={}
    cachedWebfingers={}
    print('Sending block of '+args.block)

    sendBlockViaServer(baseDir,session,nickname,args.password,
                       domain,port, \
                       httpPrefix,args.block, \
                       cachedWebfingers,personCache, \
                       True,__version__)
    for i in range(10):
        # TODO detect send success/fail
        time.sleep(1)
    sys.exit()

if args.delegate:
    if not nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()
        
    if not args.password:
        print('Specify a password with the --password option')
        sys.exit()

    if not args.project:
        print('Specify a project with the --project option')
        sys.exit()

    if not args.role:
        print('Specify a role with the --role option')
        sys.exit()

    if '@' in args.delegate:
        delegatedNickname=args.delegate.split('@')[0]
        args.delegate=blockedActor

    session = createSession(useTor)        
    personCache={}
    cachedWebfingers={}
    print('Sending delegation for '+args.delegate+' with role '+args.role+' in project '+args.project)

    sendRoleViaServer(baseDir,session, \
                      nickname,args.password, \
                      domain,port, \
                      httpPrefix,args.delegate, \
                      args.project,args.role, \
                      cachedWebfingers,personCache, \
                      True,__version__)
    for i in range(10):
        # TODO detect send success/fail
        time.sleep(1)
    sys.exit()

if args.undelegate:
    if not nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()
        
    if not args.password:
        print('Specify a password with the --password option')
        sys.exit()

    if not args.project:
        print('Specify a project with the --project option')
        sys.exit()

    if '@' in args.undelegate:
        delegatedNickname=args.undelegate.split('@')[0]
        args.undelegate=blockedActor

    session = createSession(useTor)        
    personCache={}
    cachedWebfingers={}
    print('Sending delegation removal for '+args.undelegate+' from role '+args.role+' in project '+args.project)

    sendRoleViaServer(baseDir,session, \
                      nickname,args.password, \
                      domain,port, \
                      httpPrefix,args.delegate, \
                      args.project,None, \
                      cachedWebfingers,personCache, \
                      True,__version__)
    for i in range(10):
        # TODO detect send success/fail
        time.sleep(1)
    sys.exit()

if args.unblock:
    if not nickname:
        print('Specify a nickname with the --nickname option')
        sys.exit()
        
    if not args.password:
        print('Specify a password with the --password option')
        sys.exit()

    if '@' in args.unblock:
        blockedDomain=args.unblock.split('@')[1].replace('\n','')
        blockedNickname=args.unblock.split('@')[0]
        blockedActor=httpPrefix+'://'+blockedDomain+'/users/'+blockedNickname
        args.unblock=blockedActor
    else:
        if '/users/' not in args.unblock:
            print(args.unblock+' does not look like an actor url')
            sys.exit()

    session = createSession(useTor)        
    personCache={}
    cachedWebfingers={}
    print('Sending undo block of '+args.unblock)

    sendUndoBlockViaServer(baseDir,session,nickname,args.password,
                           domain,port, \
                           httpPrefix,args.unblock, \
                           cachedWebfingers,personCache, \
                           True,__version__)
    for i in range(10):
        # TODO detect send success/fail
        time.sleep(1)
    sys.exit()

if args.filterStr:
    if not args.nickname:
        print('Please specify a nickname')
        sys.exit()
    if addFilter(baseDir,args.nickname,domain,args.filterStr):
        print('Filter added to '+args.nickname+': '+args.filterStr)
    sys.exit()

if args.unfilterStr:
    if not args.nickname:
        print('Please specify a nickname')
        sys.exit()
    if removeFilter(baseDir,args.nickname,domain,args.unfilterStr):
        print('Filter removed from '+args.nickname+': '+args.unfilterStr)
    sys.exit()

if args.testdata:
    useBlurhash=False    
    nickname='testuser567'
    password='boringpassword'
    print('Generating some test data for user: '+nickname)

    if os.path.isdir(baseDir+'/tags'):
        shutil.rmtree(baseDir+'/tags')
    if os.path.isdir(baseDir+'/accounts'):
        shutil.rmtree(baseDir+'/accounts')
    if os.path.isdir(baseDir+'/keys'):
        shutil.rmtree(baseDir+'/keys')
    if os.path.isdir(baseDir+'/media'):
        shutil.rmtree(baseDir+'/media')
    if os.path.isdir(baseDir+'/sharefiles'):
        shutil.rmtree(baseDir+'/sharefiles')
    if os.path.isdir(baseDir+'/wfendpoints'):
        shutil.rmtree(baseDir+'/wfendpoints')
    
    setConfigParam(baseDir,'registrationsRemaining',str(maxRegistrations))

    createPerson(baseDir,'maxboardroom',domain,port,httpPrefix,True,password)
    createPerson(baseDir,'ultrapancake',domain,port,httpPrefix,True,password)
    createPerson(baseDir,'drokk',domain,port,httpPrefix,True,password)
    createPerson(baseDir,'sausagedog',domain,port,httpPrefix,True,password)

    createPerson(baseDir,nickname,domain,port,httpPrefix,True,'likewhateveryouwantscoob')
    setSkillLevel(baseDir,nickname,domain,'testing',60)
    setSkillLevel(baseDir,nickname,domain,'typing',50)
    setRole(baseDir,nickname,domain,'instance','admin')
    setRole(baseDir,nickname,domain,'epicyon','hacker')
    setRole(baseDir,nickname,domain,'someproject','assistant')
    setAvailability(baseDir,nickname,domain,'busy')

    addShare(baseDir, \
             httpPrefix,nickname,domain,port, \
             "spanner", \
             "It's a spanner", \
             "img/shares1.png", \
             "tool", \
             "mechanical", \
             "City", \
             "2 months",
             debug)
    addShare(baseDir, \
             httpPrefix,nickname,domain,port, \
             "witch hat", \
             "Spooky", \
             "img/shares2.png", \
             "hat", \
             "clothing", \
             "City", \
             "3 months",
             debug)
    
    deleteAllPosts(baseDir,nickname,domain,'inbox')
    deleteAllPosts(baseDir,nickname,domain,'outbox')
    createPublicPost(baseDir,nickname,domain,port,httpPrefix,"like, this is totally just a #test, man",False,True,False,None,None,useBlurhash)
    createPublicPost(baseDir,nickname,domain,port,httpPrefix,"Zoiks!!!",False,True,False,None,None,useBlurhash)
    createPublicPost(baseDir,nickname,domain,port,httpPrefix,"Hey scoob we need like a hundred more #milkshakes",False,True,False,None,None,useBlurhash)
    createPublicPost(baseDir,nickname,domain,port,httpPrefix,"Getting kinda spooky around here",False,True,False,None,None,useBlurhash,'someone')
    createPublicPost(baseDir,nickname,domain,port,httpPrefix,"And they would have gotten away with it too if it wasn't for those pesky hackers",False,True,False,'img/logo.png','Description of image',useBlurhash)
    createPublicPost(baseDir,nickname,domain,port,httpPrefix,"man, these centralized sites are, like, the worst!",False,True,False,None,None,useBlurhash)
    createPublicPost(baseDir,nickname,domain,port,httpPrefix,"another mystery solved #test",False,True,False,None,None,useBlurhash)
    createPublicPost(baseDir,nickname,domain,port,httpPrefix,"let's go bowling",False,True,False,None,None,useBlurhash)

    domainFull=domain+':'+str(port)
    clearFollows(baseDir,nickname,domain)
    followPerson(baseDir,nickname,domain,'maxboardroom',domainFull,federationList,False)
    followPerson(baseDir,nickname,domain,'ultrapancake',domainFull,federationList,False)
    followPerson(baseDir,nickname,domain,'sausagedog',domainFull,federationList,False)
    followPerson(baseDir,nickname,domain,'drokk',domainFull,federationList,False)
    followerOfPerson(baseDir,nickname,domain,'drokk',domainFull,federationList,False)
    followerOfPerson(baseDir,nickname,domain,'maxboardroom',domainFull,federationList,False)
    setConfigParam(baseDir,'admin',nickname)

# set a lower bound to the maximum mentions
# so that it can't be accidentally set to zero and disable replies
if args.maxMentions<4:
    args.maxMentions=4

registration=getConfigParam(baseDir,'registration')
if not registration:
    registration=False

if setTheme(baseDir,themeName):
    print('Theme set to '+themeName)

runDaemon(args.blogsinstance,args.mediainstance, \
          args.maxRecentPosts, \
          not args.nosharedinbox, \
          registration,args.language,__version__, \
          instanceId,args.client,baseDir, \
          domain,onionDomain,port,proxyPort,httpPrefix, \
          federationList,args.maxMentions, \
          args.maxEmoji,args.authenticatedFetch, \
          args.noreply,args.nolike,args.nopics, \
          args.noannounce,args.cw,ocapAlways, \
          useTor,args.maxReplies, \
          args.domainMaxPostsPerDay,args.accountMaxPostsPerDay, \
          args.allowdeletion,debug,False, \
          args.instanceOnlySkillsSearch,[], \
          args.blurhash)
