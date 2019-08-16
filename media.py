__filename__ = "media.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "0.0.1"
__maintainer__ = "Bob Mottram"
__email__ = "bob@freedombone.net"
__status__ = "Production"

from blurhash import blurhash_encode as blurencode
from PIL import Image
import numpy
import os
import sys
import json
import commentjson
import datetime
from auth import createPassword
from shutil import copyfile
from shutil import rmtree
from shutil import move

def removeMetaData(imageFilename: str,outputFilename: str):
    imageFile = open(imageFilename)
    image = Image.open(imageFilename)
    data = list(image.getdata())
    imageWithoutExif = Image.new(image.mode, image.size)
    imageWithoutExif.putdata(data)
    imageWithoutExif.save(outputFilename)

def getImageHash(imageFilename: str) -> str:
    return blurencode(numpy.array(Image.open(imageFilename).convert("RGB")))

def isImage(imageFilename: str) -> bool:
    if imageFilename.endswith('.png') or \
       imageFilename.endswith('.jpg') or \
       imageFilename.endswith('.gif'):
        return True
    return False

def createMediaDirs(baseDir: str,mediaPath: str) -> None:    
    if not os.path.isdir(baseDir+'/media'):
        os.mkdir(baseDir+'/media')
    if not os.path.isdir(baseDir+'/'+mediaPath):
        os.mkdir(baseDir+'/'+mediaPath)

def getMediaPath() -> str:
    currTime=datetime.datetime.utcnow()
    weeksSinceEpoch=int((currTime - datetime.datetime(1970,1,1)).days/7)
    return 'media/'+str(weeksSinceEpoch)
        
def attachImage(baseDir: str,httpPrefix: str,domain: str,port: int, \
                postJson: {},imageFilename: str,description: str, \
                useBlurhash: bool) -> {}:
    """Attaches an image to a json object post
    The description can be None
    Blurhash is optional, since low power systems may take a long time to calculate it
    """
    if not isImage(imageFilename):
        return postJson

    mediaType='image/png'
    fileExtension='png'
    if imageFilename.endswith('.jpg'):
        mediaType='image/jpeg'
        fileExtension='jpg'
    if imageFilename.endswith('.gif'):
        mediaType='image/gif'        
        fileExtension='gif'

    if port:
        if port!=80 and port!=443:
            if ':' not in domain:
                domain=domain+':'+str(port)

    mPath=getMediaPath()
    mediaPath=mPath+'/'+createPassword(32)+'.'+fileExtension
    if baseDir:
        createMediaDirs(baseDir,mPath)
        mediaFilename=baseDir+'/'+mediaPath

    attachmentJson={
        'mediaType': mediaType,
        'name': description,
        'type': 'Document',
        'url': httpPrefix+'://'+domain+'/'+mediaPath
    }
    if useBlurhash:
        attachmentJson['blurhash']=getImageHash(imageFilename)
    postJson['attachment']=[attachmentJson]

    if baseDir:
        removeMetaData(imageFilename,mediaFilename)
        #copyfile(imageFilename,mediaFilename)
             
    return postJson

def archiveMedia(baseDir: str,archiveDirectory: str,maxWeeks=4) -> None:
    """Any media older than the given number of weeks gets archived
    """
    currTime=datetime.datetime.utcnow()
    weeksSinceEpoch=int((currTime - datetime.datetime(1970,1,1)).days/7)
    minWeek=weeksSinceEpoch-maxWeeks

    if archiveDirectory:
        if not os.path.isdir(archiveDirectory):
            os.mkdir(archiveDirectory)
        if not os.path.isdir(archiveDirectory+'/media'):
            os.mkdir(archiveDirectory+'/media')
    
    for subdir, dirs, files in os.walk(baseDir+'/media'):
        for weekDir in dirs:
            if int(weekDir)<minWeek:
                if archiveDirectory:
                    move(os.path.join(baseDir+'/media', weekDir),archiveDirectory+'/media')
                else:
                    # archive to /dev/null
                    rmtree(os.path.join(baseDir+'/media', weekDir))
