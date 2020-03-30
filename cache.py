__filename__="cache.py"
__author__="Bob Mottram"
__license__="AGPL3+"
__version__="1.1.0"
__maintainer__="Bob Mottram"
__email__="bob@freedombone.net"
__status__="Production"

import os
import time
import datetime
from utils import loadJson
from utils import saveJson

def storePersonInCache(baseDir: str,personUrl: str, \
                       personJson: {},personCache: {}) -> None:
    """Store an actor in the cache
    """
    currTime=datetime.datetime.utcnow()
    personCache[personUrl]={
        "actor": personJson,
        "timestamp": currTime.strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    if not baseDir:
        return

    # store to file
    if os.path.isdir(baseDir+'/cache/actors'):
        cacheFilename= \
            baseDir+'/cache/actors/'+personUrl.replace('/','#')+'.json'
        if not os.path.isfile(cacheFilename):
            saveJson(personJson,cacheFilename)

def getPersonFromCache(baseDir: str,personUrl: str,personCache: {}) -> {}:
    """Get an actor from the cache
    """
    # if the actor is not in memory then try to load it from file
    loadedFromFile=False
    if not personCache.get(personUrl):
        cacheFilename=baseDir+'/cache/actors/'+personUrl.replace('/','#')+'.json'
        if os.path.isfile(cacheFilename):
            personJson=loadJson(cacheFilename)
            if personJson:
                storePersonInCache(baseDir,personUrl,personJson,personCache)
                loadedFromFile=True

    if personCache.get(personUrl):
        if not loadedFromFile:
            # update the timestamp for the last time the actor was retrieved
            currTime=datetime.datetime.utcnow()
            personCache[personUrl]['timestamp']=currTime.strftime("%Y-%m-%dT%H:%M:%SZ")
        return personCache[personUrl]['actor']
    return None

def expirePersonCache(personCache: {}):
    """Expires old entries from the cache in memory
    """
    currTime=datetime.datetime.utcnow()
    removals=[]
    for personUrl,cacheJson in personCache.items():
        cacheTime= \
            datetime.datetime.strptime(cacheJson['timestamp'], \
                                       "%Y-%m-%dT%H:%M:%SZ")
        daysSinceCached=(currTime - cacheTime).days
        if daysSinceCached > 2:
            removals.append(personUrl)
    if len(removals)>0:
        for personUrl in removals:
            del personCache[personUrl]
        print(str(len(removals))+' actors were expired from the cache')

def storeWebfingerInCache(handle: str,wf,cachedWebfingers: {}) -> None:
    """Store a webfinger endpoint in the cache
    """
    cachedWebfingers[handle]=wf

def getWebfingerFromCache(handle: str,cachedWebfingers: {}) -> {}:
    """Get webfinger endpoint from the cache
    """
    if cachedWebfingers.get(handle):
        return cachedWebfingers[handle]
    return None
