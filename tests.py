__filename__ = "tests.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.1.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@freedombone.net"
__status__ = "Production"

import time
import os
import shutil
import json
from time import gmtime, strftime
from pprint import pprint
from httpsig import signPostHeaders
from httpsig import verifyPostHeaders
from httpsig import messageContentDigest
from cache import storePersonInCache
from cache import getPersonFromCache
from threads import threadWithTrace
from daemon import runDaemon
from session import createSession
from posts import deleteAllPosts
from posts import createPublicPost
from posts import sendPost
from posts import noOfFollowersOnDomain
from posts import groupFollowersByDomain
from posts import archivePostsForPerson
from posts import sendPostViaServer
from follow import clearFollows
from follow import clearFollowers
from follow import sendFollowRequestViaServer
from follow import sendUnfollowRequestViaServer
from utils import updateRecentPostsCache
from utils import followPerson
from utils import getNicknameFromActor
from utils import getDomainFromActor
from utils import copytree
from utils import loadJson
from utils import saveJson
from utils import getStatusNumber
from follow import followerOfPerson
from follow import unfollowPerson
from follow import unfollowerOfPerson
from follow import getFollowersOfPerson
from follow import sendFollowRequest
from person import createPerson
from person import setDisplayNickname
from person import setBio
from skills import setSkillLevel
from roles import setRole
from roles import outboxDelegate
from auth import createBasicAuthHeader
from auth import authorizeBasic
from auth import storeBasicCredentials
from like import likePost
from like import sendLikeViaServer
from announce import announcePublic
from announce import sendAnnounceViaServer
from media import getMediaPath
from media import getAttachmentMediaType
from delete import sendDeleteViaServer
from inbox import validInbox
from inbox import validInboxFilenames
from content import addWebLinks
from content import replaceEmojiFromTags
from content import addHtmlTags
from content import removeLongWords
from content import replaceContentDuplicates
from theme import setCSSparam

testServerAliceRunning = False
testServerBobRunning = False
testServerEveRunning = False
thrAlice = None
thrBob = None
thrEve = None


def testHttpsigBase(withDigest):
    print('testHttpsig(' + str(withDigest) + ')')

    baseDir = os.getcwd()
    path = baseDir + '/.testHttpsigBase'
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.mkdir(path)
    os.chdir(path)

    contentType = 'application/activity+json'
    nickname = 'socrates'
    domain = 'argumentative.social'
    httpPrefix = 'https'
    port = 5576
    password = 'SuperSecretPassword'
    privateKeyPem, publicKeyPem, person, wfEndpoint = \
        createPerson(path, nickname, domain, port, httpPrefix, False, password)
    assert privateKeyPem
    messageBodyJson = {
        "a key": "a value",
        "another key": "A string",
        "yet another key": "Another string"
    }
    messageBodyJsonStr = json.dumps(messageBodyJson)

    headersDomain = domain
    if port:
        if port != 80 and port != 443:
            if ':' not in domain:
                headersDomain = domain + ':' + str(port)

    dateStr = strftime("%a, %d %b %Y %H:%M:%S %Z", gmtime())
    boxpath = '/inbox'
    if not withDigest:
        headers = {
            'host': headersDomain,
            'date': dateStr,
            'content-type': 'application/json'
        }
        signatureHeader = \
            signPostHeaders(dateStr, privateKeyPem, nickname,
                            domain, port,
                            domain, port,
                            boxpath, httpPrefix, None)
    else:
        bodyDigest = messageContentDigest(messageBodyJsonStr)
        contentLength = len(messageBodyJsonStr)
        headers = {
            'host': headersDomain,
            'date': dateStr,
            'digest': f'SHA-256={bodyDigest}',
            'content-type': contentType,
            'content-length': str(contentLength)
        }
        signatureHeader = \
            signPostHeaders(dateStr, privateKeyPem, nickname,
                            domain, port,
                            domain, port,
                            boxpath, httpPrefix, messageBodyJsonStr)

    headers['signature'] = signatureHeader
    assert verifyPostHeaders(httpPrefix, publicKeyPem, headers,
                             boxpath, False, None,
                             messageBodyJsonStr, False)
    if withDigest:
        # everything correct except for content-length
        headers['content-length'] = str(contentLength + 2)
        assert verifyPostHeaders(httpPrefix, publicKeyPem, headers,
                                 boxpath, False, None,
                                 messageBodyJsonStr, False) is False
    assert verifyPostHeaders(httpPrefix, publicKeyPem, headers,
                             '/parambulator' + boxpath, False, None,
                             messageBodyJsonStr, False) is False
    assert verifyPostHeaders(httpPrefix, publicKeyPem, headers,
                             boxpath, True, None,
                             messageBodyJsonStr, False) is False
    if not withDigest:
        # fake domain
        headers = {
            'host': 'bogon.domain',
            'date': dateStr,
            'content-type': 'application/json'
        }
    else:
        # correct domain but fake message
        messageBodyJsonStr = \
            '{"a key": "a value", "another key": "Fake GNUs", ' + \
            '"yet another key": "More Fake GNUs"}'
        contentLength = len(messageBodyJsonStr)
        bodyDigest = messageContentDigest(messageBodyJsonStr)
        headers = {
            'host': domain,
            'date': dateStr,
            'digest': f'SHA-256={bodyDigest}',
            'content-type': contentType,
            'content-length': str(contentLength)
        }
    headers['signature'] = signatureHeader
    assert verifyPostHeaders(httpPrefix, publicKeyPem, headers,
                             boxpath, True, None,
                             messageBodyJsonStr, False) is False

    os.chdir(baseDir)
    shutil.rmtree(path)


def testHttpsig():
    testHttpsigBase(True)
    testHttpsigBase(False)


def testCache():
    print('testCache')
    personUrl = "cat@cardboard.box"
    personJson = {
        "id": 123456,
        "test": "This is a test"
    }
    personCache = {}
    storePersonInCache(None, personUrl, personJson, personCache)
    result = getPersonFromCache(None, personUrl, personCache)
    assert result['id'] == 123456
    assert result['test'] == 'This is a test'


def testThreadsFunction(param: str):
    for i in range(10000):
        time.sleep(2)


def testThreads():
    print('testThreads')
    thr = \
        threadWithTrace(target=testThreadsFunction,
                        args=('test',),
                        daemon=True)
    thr.start()
    assert thr.isAlive() is True
    time.sleep(1)
    thr.kill()
    thr.join()
    assert thr.isAlive() is False


def createServerAlice(path: str, domain: str, port: int,
                      bobAddress: str, federationList: [],
                      hasFollows: bool, hasPosts: bool,
                      ocapAlways: bool, sendThreads: []):
    print('Creating test server: Alice on port ' + str(port))
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.mkdir(path)
    os.chdir(path)
    nickname = 'alice'
    httpPrefix = 'http'
    proxyType = None
    password = 'alicepass'
    noreply = False
    nolike = False
    nopics = False
    noannounce = False
    cw = False
    useBlurhash = True
    maxReplies = 64
    domainMaxPostsPerDay = 1000
    accountMaxPostsPerDay = 1000
    allowDeletion = True
    privateKeyPem, publicKeyPem, person, wfEndpoint = \
        createPerson(path, nickname, domain, port, httpPrefix, True, password)
    deleteAllPosts(path, nickname, domain, 'inbox')
    deleteAllPosts(path, nickname, domain, 'outbox')
    assert setSkillLevel(path, nickname, domain, 'hacking', 90)
    assert setRole(path, nickname, domain, 'someproject', 'guru')
    if hasFollows:
        followPerson(path, nickname, domain, 'bob', bobAddress,
                     federationList, False)
        followerOfPerson(path, nickname, domain, 'bob', bobAddress,
                         federationList, False)
    if hasPosts:
        clientToServer = False
        createPublicPost(path, nickname, domain, port, httpPrefix,
                         "No wise fish would go anywhere without a porpoise",
                         False, True, clientToServer, None, None, useBlurhash)
        createPublicPost(path, nickname, domain, port, httpPrefix,
                         "Curiouser and curiouser!", False, True,
                         clientToServer, None, None, useBlurhash)
        createPublicPost(path, nickname, domain, port, httpPrefix,
                         "In the gardens of memory, in the palace " +
                         "of dreams, that is where you and I shall meet",
                         False, True, clientToServer, None, None, useBlurhash)
    global testServerAliceRunning
    testServerAliceRunning = True
    maxMentions = 10
    maxEmoji = 10
    onionDomain = None
    i2pDomain = None
    print('Server running: Alice')
    runDaemon(False, False, 5, True, True, 'en', __version__,
              "instanceId", False, path, domain,
              onionDomain, i2pDomain, port, port,
              httpPrefix, federationList, maxMentions, maxEmoji, False,
              noreply, nolike, nopics, noannounce, cw, ocapAlways,
              proxyType, maxReplies,
              domainMaxPostsPerDay, accountMaxPostsPerDay,
              allowDeletion, True, True, False, sendThreads, False)


def createServerBob(path: str, domain: str, port: int,
                    aliceAddress: str, federationList: [],
                    hasFollows: bool, hasPosts: bool,
                    ocapAlways: bool, sendThreads: []):
    print('Creating test server: Bob on port ' + str(port))
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.mkdir(path)
    os.chdir(path)
    nickname = 'bob'
    httpPrefix = 'http'
    proxyType = None
    clientToServer = False
    password = 'bobpass'
    noreply = False
    nolike = False
    nopics = False
    noannounce = False
    cw = False
    useBlurhash = False
    maxReplies = 64
    domainMaxPostsPerDay = 1000
    accountMaxPostsPerDay = 1000
    allowDeletion = True
    privateKeyPem, publicKeyPem, person, wfEndpoint = \
        createPerson(path, nickname, domain, port, httpPrefix, True, password)
    deleteAllPosts(path, nickname, domain, 'inbox')
    deleteAllPosts(path, nickname, domain, 'outbox')
    assert setRole(path, nickname, domain, 'bandname', 'bass player')
    assert setRole(path, nickname, domain, 'bandname', 'publicist')
    if hasFollows:
        followPerson(path, nickname, domain,
                     'alice', aliceAddress, federationList, False)
        followerOfPerson(path, nickname, domain,
                         'alice', aliceAddress, federationList, False)
    if hasPosts:
        createPublicPost(path, nickname, domain, port, httpPrefix,
                         "It's your life, live it your way.",
                         False, True, clientToServer, None, None, useBlurhash)
        createPublicPost(path, nickname, domain, port, httpPrefix,
                         "One of the things I've realised is that " +
                         "I am very simple",
                         False, True, clientToServer, None, None, useBlurhash)
        createPublicPost(path, nickname, domain, port, httpPrefix,
                         "Quantum physics is a bit of a passion of mine",
                         False, True, clientToServer, None, None, useBlurhash)
    global testServerBobRunning
    testServerBobRunning = True
    maxMentions = 10
    maxEmoji = 10
    onionDomain = None
    i2pDomain = None
    print('Server running: Bob')
    runDaemon(False, False, 5, True, True, 'en', __version__,
              "instanceId", False, path, domain,
              onionDomain, i2pDomain, port, port,
              httpPrefix, federationList, maxMentions, maxEmoji, False,
              noreply, nolike, nopics, noannounce, cw, ocapAlways,
              proxyType, maxReplies,
              domainMaxPostsPerDay, accountMaxPostsPerDay,
              allowDeletion, True, True, False, sendThreads, False)


def createServerEve(path: str, domain: str, port: int, federationList: [],
                    hasFollows: bool, hasPosts: bool,
                    ocapAlways: bool, sendThreads: []):
    print('Creating test server: Eve on port ' + str(port))
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.mkdir(path)
    os.chdir(path)
    nickname = 'eve'
    httpPrefix = 'http'
    proxyType = None
    password = 'evepass'
    noreply = False
    nolike = False
    nopics = False
    noannounce = False
    cw = False
    maxReplies = 64
    allowDeletion = True
    privateKeyPem, publicKeyPem, person, wfEndpoint = \
        createPerson(path, nickname, domain, port, httpPrefix, True, password)
    deleteAllPosts(path, nickname, domain, 'inbox')
    deleteAllPosts(path, nickname, domain, 'outbox')
    global testServerEveRunning
    testServerEveRunning = True
    maxMentions = 10
    maxEmoji = 10
    onionDomain = None
    i2pDomain = None
    print('Server running: Eve')
    runDaemon(False, False, 5, True, True, 'en', __version__,
              "instanceId", False, path, domain,
              onionDomain, i2pDomain, port, port,
              httpPrefix, federationList, maxMentions, maxEmoji, False,
              noreply, nolike, nopics, noannounce, cw, ocapAlways,
              proxyType, maxReplies, allowDeletion, True, True, False,
              sendThreads, False)


def testPostMessageBetweenServers():
    print('Testing sending message from one server to the inbox of another')

    global testServerAliceRunning
    global testServerBobRunning
    testServerAliceRunning = False
    testServerBobRunning = False

    httpPrefix = 'http'
    proxyType = None

    baseDir = os.getcwd()
    if os.path.isdir(baseDir + '/.tests'):
        shutil.rmtree(baseDir + '/.tests')
    os.mkdir(baseDir + '/.tests')

    ocapAlways = False

    # create the servers
    aliceDir = baseDir + '/.tests/alice'
    aliceDomain = '127.0.0.50'
    alicePort = 61935
    aliceAddress = aliceDomain + ':' + str(alicePort)

    bobDir = baseDir + '/.tests/bob'
    bobDomain = '127.0.0.100'
    bobPort = 61936
    federationList = [bobDomain, aliceDomain]
    aliceSendThreads = []
    bobSendThreads = []
    bobAddress = bobDomain + ':' + str(bobPort)

    global thrAlice
    if thrAlice:
        while thrAlice.isAlive():
            thrAlice.stop()
            time.sleep(1)
        thrAlice.kill()

    thrAlice = \
        threadWithTrace(target=createServerAlice,
                        args=(aliceDir, aliceDomain, alicePort, bobAddress,
                              federationList, False, False,
                              ocapAlways, aliceSendThreads),
                        daemon=True)

    global thrBob
    if thrBob:
        while thrBob.isAlive():
            thrBob.stop()
            time.sleep(1)
        thrBob.kill()

    thrBob = \
        threadWithTrace(target=createServerBob,
                        args=(bobDir, bobDomain, bobPort, aliceAddress,
                              federationList, False, False,
                              ocapAlways, bobSendThreads),
                        daemon=True)

    thrAlice.start()
    thrBob.start()
    assert thrAlice.isAlive() is True
    assert thrBob.isAlive() is True

    # wait for both servers to be running
    while not (testServerAliceRunning and testServerBobRunning):
        time.sleep(1)

    time.sleep(1)

    print('\n\n*******************************************************')
    print('Alice sends to Bob')
    os.chdir(aliceDir)
    sessionAlice = createSession(proxyType)
    inReplyTo = None
    inReplyToAtomUri = None
    subject = None
    alicePostLog = []
    followersOnly = False
    saveToFile = True
    clientToServer = False
    ccUrl = None
    alicePersonCache = {}
    aliceCachedWebfingers = {}
    attachedImageFilename = baseDir + '/img/logo.png'
    mediaType = getAttachmentMediaType(attachedImageFilename)
    attachedImageDescription = 'Logo'
    useBlurhash = True
    isArticle = False
    # nothing in Alice's outbox
    outboxPath = aliceDir + '/accounts/alice@' + aliceDomain + '/outbox'
    assert len([name for name in os.listdir(outboxPath)
                if os.path.isfile(os.path.join(outboxPath, name))]) == 0

    sendResult = \
        sendPost(__version__,
                 sessionAlice, aliceDir, 'alice', aliceDomain, alicePort,
                 'bob', bobDomain, bobPort, ccUrl, httpPrefix,
                 'Why is a mouse when it spins? ' +
                 'यह एक परीक्षण है #sillyquestion',
                 followersOnly,
                 saveToFile, clientToServer, attachedImageFilename, mediaType,
                 attachedImageDescription, useBlurhash, federationList,
                 aliceSendThreads, alicePostLog, aliceCachedWebfingers,
                 alicePersonCache, isArticle, inReplyTo,
                 inReplyToAtomUri, subject)
    print('sendResult: ' + str(sendResult))

    queuePath = bobDir + '/accounts/bob@' + bobDomain + '/queue'
    inboxPath = bobDir + '/accounts/bob@' + bobDomain + '/inbox'
    mPath = getMediaPath()
    mediaPath = aliceDir + '/' + mPath
    for i in range(30):
        if os.path.isdir(inboxPath):
            if len([name for name in os.listdir(inboxPath)
                    if os.path.isfile(os.path.join(inboxPath, name))]) > 0:
                if len([name for name in os.listdir(outboxPath)
                        if os.path.isfile(os.path.join(outboxPath,
                                                       name))]) == 1:
                    if len([name for name in os.listdir(mediaPath)
                            if os.path.isfile(os.path.join(mediaPath,
                                                           name))]) > 0:
                        if len([name for name in os.listdir(queuePath)
                                if os.path.isfile(os.path.join(queuePath,
                                                               name))]) == 0:
                            break
        time.sleep(1)

    # Image attachment created
    assert len([name for name in os.listdir(mediaPath)
                if os.path.isfile(os.path.join(mediaPath, name))]) > 0
    # inbox item created
    assert len([name for name in os.listdir(inboxPath)
                if os.path.isfile(os.path.join(inboxPath, name))]) == 1
    # queue item removed
    testval = len([name for name in os.listdir(queuePath)
                   if os.path.isfile(os.path.join(queuePath, name))])
    print('queuePath: ' + queuePath + ' '+str(testval))
    assert testval == 0
    assert validInbox(bobDir, 'bob', bobDomain)
    assert validInboxFilenames(bobDir, 'bob', bobDomain,
                               aliceDomain, alicePort)
    print('Check that message received from Alice contains the expected text')
    for name in os.listdir(inboxPath):
        filename = os.path.join(inboxPath, name)
        assert os.path.isfile(filename)
        receivedJson = loadJson(filename, 0)
        if receivedJson:
            pprint(receivedJson['object']['content'])
        assert receivedJson
        assert 'Why is a mouse when it spins?' in \
            receivedJson['object']['content']
        assert 'यह एक परीक्षण है' in receivedJson['object']['content']

    print('\n\n*******************************************************')
    print("Bob likes Alice's post")

    followerOfPerson(bobDir, 'bob', bobDomain, 'alice',
                     aliceDomain + ':' + str(alicePort), federationList, False)
    followPerson(aliceDir, 'alice', aliceDomain, 'bob',
                 bobDomain + ':' + str(bobPort), federationList, False)

    sessionBob = createSession(proxyType)
    bobPostLog = []
    bobPersonCache = {}
    bobCachedWebfingers = {}
    statusNumber = None
    outboxPostFilename = None
    outboxPath = aliceDir + '/accounts/alice@' + aliceDomain + '/outbox'
    for name in os.listdir(outboxPath):
        if '#statuses#' in name:
            statusNumber = \
                int(name.split('#statuses#')[1].replace('.json', ''))
            outboxPostFilename = outboxPath + '/' + name
    assert statusNumber > 0
    assert outboxPostFilename
    assert likePost({}, sessionBob, bobDir, federationList,
                    'bob', bobDomain, bobPort, httpPrefix,
                    'alice', aliceDomain, alicePort, [],
                    statusNumber, False, bobSendThreads, bobPostLog,
                    bobPersonCache, bobCachedWebfingers,
                    True, __version__)

    for i in range(20):
        if 'likes' in open(outboxPostFilename).read():
            break
        time.sleep(1)

    alicePostJson = loadJson(outboxPostFilename, 0)
    if alicePostJson:
        pprint(alicePostJson)

    assert 'likes' in open(outboxPostFilename).read()

    print('\n\n*******************************************************')
    print("Bob repeats Alice's post")
    objectUrl = \
        httpPrefix + '://' + aliceDomain + ':' + str(alicePort) + \
        '/users/alice/statuses/' + str(statusNumber)
    inboxPath = aliceDir + '/accounts/alice@' + aliceDomain + '/inbox'
    outboxPath = bobDir + '/accounts/bob@' + bobDomain + '/outbox'
    outboxBeforeAnnounceCount = \
        len([name for name in os.listdir(outboxPath)
             if os.path.isfile(os.path.join(outboxPath, name))])
    beforeAnnounceCount = \
        len([name for name in os.listdir(inboxPath)
             if os.path.isfile(os.path.join(inboxPath, name))])
    print('inbox items before announce: ' + str(beforeAnnounceCount))
    print('outbox items before announce: ' + str(outboxBeforeAnnounceCount))
    assert outboxBeforeAnnounceCount == 0
    assert beforeAnnounceCount == 0
    announcePublic(sessionBob, bobDir, federationList,
                   'bob', bobDomain, bobPort, httpPrefix,
                   objectUrl,
                   False, bobSendThreads, bobPostLog,
                   bobPersonCache, bobCachedWebfingers,
                   True, __version__)
    announceMessageArrived = False
    outboxMessageArrived = False
    for i in range(10):
        time.sleep(1)
        if not os.path.isdir(inboxPath):
            continue
        if len([name for name in os.listdir(outboxPath)
                if os.path.isfile(os.path.join(outboxPath, name))]) > 0:
            outboxMessageArrived = True
            print('Announce created by Bob')
        if len([name for name in os.listdir(inboxPath)
                if os.path.isfile(os.path.join(inboxPath, name))]) > 0:
            announceMessageArrived = True
            print('Announce message sent to Alice!')
        if announceMessageArrived and outboxMessageArrived:
            break
    afterAnnounceCount = \
        len([name for name in os.listdir(inboxPath)
             if os.path.isfile(os.path.join(inboxPath, name))])
    outboxAfterAnnounceCount = \
        len([name for name in os.listdir(outboxPath)
             if os.path.isfile(os.path.join(outboxPath, name))])
    print('inbox items after announce: ' + str(afterAnnounceCount))
    print('outbox items after announce: ' + str(outboxAfterAnnounceCount))
    assert afterAnnounceCount == beforeAnnounceCount+1
    assert outboxAfterAnnounceCount == outboxBeforeAnnounceCount + 1
    # stop the servers
    thrAlice.kill()
    thrAlice.join()
    assert thrAlice.isAlive() is False

    thrBob.kill()
    thrBob.join()
    assert thrBob.isAlive() is False

    os.chdir(baseDir)
    shutil.rmtree(aliceDir)
    shutil.rmtree(bobDir)


def testFollowBetweenServers():
    print('Testing sending a follow request from one server to another')

    global testServerAliceRunning
    global testServerBobRunning
    testServerAliceRunning = False
    testServerBobRunning = False

    httpPrefix = 'http'
    proxyType = None
    federationList = []

    baseDir = os.getcwd()
    if os.path.isdir(baseDir + '/.tests'):
        shutil.rmtree(baseDir + '/.tests')
    os.mkdir(baseDir + '/.tests')

    ocapAlways = False

    # create the servers
    aliceDir = baseDir + '/.tests/alice'
    aliceDomain = '127.0.0.47'
    alicePort = 61935
    aliceSendThreads = []
    aliceAddress = aliceDomain + ':' + str(alicePort)

    bobDir = baseDir + '/.tests/bob'
    bobDomain = '127.0.0.79'
    bobPort = 61936
    bobSendThreads = []
    bobAddress = bobDomain + ':' + str(bobPort)

    global thrAlice
    if thrAlice:
        while thrAlice.isAlive():
            thrAlice.stop()
            time.sleep(1)
        thrAlice.kill()

    thrAlice = \
        threadWithTrace(target=createServerAlice,
                        args=(aliceDir, aliceDomain, alicePort, bobAddress,
                              federationList, False, False,
                              ocapAlways, aliceSendThreads),
                        daemon=True)

    global thrBob
    if thrBob:
        while thrBob.isAlive():
            thrBob.stop()
            time.sleep(1)
        thrBob.kill()

    thrBob = \
        threadWithTrace(target=createServerBob,
                        args=(bobDir, bobDomain, bobPort, aliceAddress,
                              federationList, False, False,
                              ocapAlways, bobSendThreads),
                        daemon=True)

    thrAlice.start()
    thrBob.start()
    assert thrAlice.isAlive() is True
    assert thrBob.isAlive() is True

    # wait for all servers to be running
    ctr = 0
    while not (testServerAliceRunning and testServerBobRunning):
        time.sleep(1)
        ctr += 1
        if ctr > 60:
            break
    print('Alice online: ' + str(testServerAliceRunning))
    print('Bob online: ' + str(testServerBobRunning))
    assert ctr <= 60
    time.sleep(1)

    # In the beginning all was calm and there were no follows

    print('*********************************************************')
    print('Alice sends a follow request to Bob')
    os.chdir(aliceDir)
    sessionAlice = createSession(proxyType)
    inReplyTo = None
    inReplyToAtomUri = None
    subject = None
    alicePostLog = []
    followersOnly = False
    saveToFile = True
    clientToServer = False
    ccUrl = None
    alicePersonCache = {}
    aliceCachedWebfingers = {}
    alicePostLog = []
    sendResult = \
        sendFollowRequest(sessionAlice, aliceDir,
                          'alice', aliceDomain, alicePort, httpPrefix,
                          'bob', bobDomain, bobPort, httpPrefix,
                          clientToServer, federationList,
                          aliceSendThreads, alicePostLog,
                          aliceCachedWebfingers, alicePersonCache,
                          True, __version__)
    print('sendResult: ' + str(sendResult))

    for t in range(10):
        if os.path.isfile(bobDir + '/accounts/bob@' +
                          bobDomain + '/followers.txt'):
            if os.path.isfile(aliceDir + '/accounts/alice@' +
                              aliceDomain + '/following.txt'):
                break
        time.sleep(1)

    assert validInbox(bobDir, 'bob', bobDomain)
    assert validInboxFilenames(bobDir, 'bob', bobDomain,
                               aliceDomain, alicePort)

    print('\n\n*********************************************************')
    print('Alice sends a message to Bob')
    alicePostLog = []
    alicePersonCache = {}
    aliceCachedWebfingers = {}
    alicePostLog = []
    useBlurhash = False
    isArticle = False
    sendResult = \
        sendPost(__version__,
                 sessionAlice, aliceDir, 'alice', aliceDomain, alicePort,
                 'bob', bobDomain, bobPort, ccUrl,
                 httpPrefix, 'Alice message', followersOnly, saveToFile,
                 clientToServer, None, None, None, useBlurhash, federationList,
                 aliceSendThreads, alicePostLog, aliceCachedWebfingers,
                 alicePersonCache, isArticle, inReplyTo,
                 inReplyToAtomUri, subject)
    print('sendResult: ' + str(sendResult))

    queuePath = bobDir + '/accounts/bob@' + bobDomain + '/queue'
    inboxPath = bobDir + '/accounts/bob@' + bobDomain + '/inbox'
    aliceMessageArrived = False
    for i in range(20):
        time.sleep(1)
        if os.path.isdir(inboxPath):
            if len([name for name in os.listdir(inboxPath)
                    if os.path.isfile(os.path.join(inboxPath, name))]) > 0:
                aliceMessageArrived = True
                print('Alice message sent to Bob!')
                break

    assert aliceMessageArrived is True
    print('Message from Alice to Bob succeeded')

    # stop the servers
    thrAlice.kill()
    thrAlice.join()
    assert thrAlice.isAlive() is False

    thrBob.kill()
    thrBob.join()
    assert thrBob.isAlive() is False

    assert 'alice@' + aliceDomain in open(bobDir + '/accounts/bob@' +
                                          bobDomain + '/followers.txt').read()
    assert 'bob@' + bobDomain in open(aliceDir + '/accounts/alice@' +
                                      aliceDomain + '/following.txt').read()

    # queue item removed
    time.sleep(4)
    assert len([name for name in os.listdir(queuePath)
                if os.path.isfile(os.path.join(queuePath, name))]) == 0

    os.chdir(baseDir)
    shutil.rmtree(baseDir + '/.tests')


def testFollowersOfPerson():
    print('testFollowersOfPerson')
    currDir = os.getcwd()
    nickname = 'mxpop'
    domain = 'diva.domain'
    password = 'birb'
    port = 80
    httpPrefix = 'https'
    federationList = []
    baseDir = currDir + '/.tests_followersofperson'
    if os.path.isdir(baseDir):
        shutil.rmtree(baseDir)
    os.mkdir(baseDir)
    os.chdir(baseDir)
    createPerson(baseDir, nickname, domain, port,
                 httpPrefix, True, password)
    createPerson(baseDir, 'maxboardroom', domain, port,
                 httpPrefix, True, password)
    createPerson(baseDir, 'ultrapancake', domain, port,
                 httpPrefix, True, password)
    createPerson(baseDir, 'drokk', domain, port,
                 httpPrefix, True, password)
    createPerson(baseDir, 'sausagedog', domain, port,
                 httpPrefix, True, password)

    clearFollows(baseDir, nickname, domain)
    followPerson(baseDir, nickname, domain, 'maxboardroom', domain,
                 federationList, False)
    followPerson(baseDir, 'drokk', domain, 'ultrapancake', domain,
                 federationList, False)
    # deliberate duplication
    followPerson(baseDir, 'drokk', domain, 'ultrapancake', domain,
                 federationList, False)
    followPerson(baseDir, 'sausagedog', domain, 'ultrapancake', domain,
                 federationList, False)
    followPerson(baseDir, nickname, domain, 'ultrapancake', domain,
                 federationList, False)
    followPerson(baseDir, nickname, domain, 'someother', 'randodomain.net',
                 federationList, False)

    followList = getFollowersOfPerson(baseDir, 'ultrapancake', domain)
    assert len(followList) == 3
    assert 'mxpop@' + domain in followList
    assert 'drokk@' + domain in followList
    assert 'sausagedog@' + domain in followList
    os.chdir(currDir)
    shutil.rmtree(baseDir)


def testNoOfFollowersOnDomain():
    print('testNoOfFollowersOnDomain')
    currDir = os.getcwd()
    nickname = 'mxpop'
    domain = 'diva.domain'
    otherdomain = 'soup.dragon'
    password = 'birb'
    port = 80
    httpPrefix = 'https'
    federationList = []
    baseDir = currDir + '/.tests_nooffollowersOndomain'
    if os.path.isdir(baseDir):
        shutil.rmtree(baseDir)
    os.mkdir(baseDir)
    os.chdir(baseDir)
    createPerson(baseDir, nickname, domain, port, httpPrefix, True, password)
    createPerson(baseDir, 'maxboardroom', otherdomain, port,
                 httpPrefix, True, password)
    createPerson(baseDir, 'ultrapancake', otherdomain, port,
                 httpPrefix, True, password)
    createPerson(baseDir, 'drokk', otherdomain, port,
                 httpPrefix, True, password)
    createPerson(baseDir, 'sausagedog', otherdomain, port,
                 httpPrefix, True, password)

    followPerson(baseDir, 'drokk', otherdomain, nickname, domain,
                 federationList, False)
    followPerson(baseDir, 'sausagedog', otherdomain, nickname, domain,
                 federationList, False)
    followPerson(baseDir, 'maxboardroom', otherdomain, nickname, domain,
                 federationList, False)

    followerOfPerson(baseDir, nickname, domain,
                     'cucumber', 'sandwiches.party',
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain,
                     'captainsensible', 'damned.zone',
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain, 'pilchard', 'zombies.attack',
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain, 'drokk', otherdomain,
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain, 'sausagedog', otherdomain,
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain, 'maxboardroom', otherdomain,
                     federationList, False)

    followersOnOtherDomain = \
        noOfFollowersOnDomain(baseDir, nickname + '@' + domain, otherdomain)
    assert followersOnOtherDomain == 3

    unfollowerOfPerson(baseDir, nickname, domain, 'sausagedog', otherdomain)
    followersOnOtherDomain = \
        noOfFollowersOnDomain(baseDir, nickname + '@' + domain, otherdomain)
    assert followersOnOtherDomain == 2

    os.chdir(currDir)
    shutil.rmtree(baseDir)


def testGroupFollowers():
    print('testGroupFollowers')

    currDir = os.getcwd()
    nickname = 'test735'
    domain = 'mydomain.com'
    password = 'somepass'
    port = 80
    httpPrefix = 'https'
    federationList = []
    baseDir = currDir + '/.tests_testgroupfollowers'
    if os.path.isdir(baseDir):
        shutil.rmtree(baseDir)
    os.mkdir(baseDir)
    os.chdir(baseDir)
    createPerson(baseDir, nickname, domain, port, httpPrefix, True, password)

    clearFollowers(baseDir, nickname, domain)
    followerOfPerson(baseDir, nickname, domain, 'badger', 'wild.domain',
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain, 'squirrel', 'wild.domain',
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain, 'rodent', 'wild.domain',
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain, 'utterly', 'clutterly.domain',
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain, 'zonked', 'zzz.domain',
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain, 'nap', 'zzz.domain',
                     federationList, False)

    grouped = groupFollowersByDomain(baseDir, nickname, domain)
    assert len(grouped.items()) == 3
    assert grouped.get('zzz.domain')
    assert grouped.get('clutterly.domain')
    assert grouped.get('wild.domain')
    assert len(grouped['zzz.domain']) == 2
    assert len(grouped['wild.domain']) == 3
    assert len(grouped['clutterly.domain']) == 1

    os.chdir(currDir)
    shutil.rmtree(baseDir)


def testFollows():
    print('testFollows')
    currDir = os.getcwd()
    nickname = 'test529'
    domain = 'testdomain.com'
    password = 'mypass'
    port = 80
    httpPrefix = 'https'
    federationList = ['wild.com', 'mesh.com']
    baseDir = currDir + '/.tests_testfollows'
    if os.path.isdir(baseDir):
        shutil.rmtree(baseDir)
    os.mkdir(baseDir)
    os.chdir(baseDir)
    createPerson(baseDir, nickname, domain, port, httpPrefix, True, password)

    clearFollows(baseDir, nickname, domain)
    followPerson(baseDir, nickname, domain, 'badger', 'wild.com',
                 federationList, False)
    followPerson(baseDir, nickname, domain, 'squirrel', 'secret.com',
                 federationList, False)
    followPerson(baseDir, nickname, domain, 'rodent', 'drainpipe.com',
                 federationList, False)
    followPerson(baseDir, nickname, domain, 'batman', 'mesh.com',
                 federationList, False)
    followPerson(baseDir, nickname, domain, 'giraffe', 'trees.com',
                 federationList, False)

    f = open(baseDir + '/accounts/' + nickname + '@' + domain +
             '/following.txt', "r")
    domainFound = False
    for followingDomain in f:
        testDomain = followingDomain.split('@')[1]
        testDomain = testDomain.replace('\n', '').replace('\r', '')
        if testDomain == 'mesh.com':
            domainFound = True
        if testDomain not in federationList:
            print(testDomain)
            assert(False)

    assert(domainFound)
    unfollowPerson(baseDir, nickname, domain, 'batman', 'mesh.com')

    domainFound = False
    for followingDomain in f:
        testDomain = followingDomain.split('@')[1]
        testDomain = testDomain.replace('\n', '').replace('\r', '')
        if testDomain == 'mesh.com':
            domainFound = True
    assert(domainFound is False)

    clearFollowers(baseDir, nickname, domain)
    followerOfPerson(baseDir, nickname, domain, 'badger', 'wild.com',
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain, 'squirrel', 'secret.com',
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain, 'rodent', 'drainpipe.com',
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain, 'batman', 'mesh.com',
                     federationList, False)
    followerOfPerson(baseDir, nickname, domain, 'giraffe', 'trees.com',
                     federationList, False)

    f = open(baseDir + '/accounts/' + nickname + '@' + domain +
             '/followers.txt', "r")
    for followerDomain in f:
        testDomain = followerDomain.split('@')[1]
        testDomain = testDomain.replace('\n', '').replace('\r', '')
        if testDomain not in federationList:
            print(testDomain)
            assert(False)

    os.chdir(currDir)
    shutil.rmtree(baseDir)


def testCreatePerson():
    print('testCreatePerson')
    currDir = os.getcwd()
    nickname = 'test382'
    domain = 'badgerdomain.com'
    password = 'mypass'
    port = 80
    httpPrefix = 'https'
    clientToServer = False
    useBlurhash = False
    baseDir = currDir + '/.tests_createperson'
    if os.path.isdir(baseDir):
        shutil.rmtree(baseDir)
    os.mkdir(baseDir)
    os.chdir(baseDir)

    privateKeyPem, publicKeyPem, person, wfEndpoint = \
        createPerson(baseDir, nickname, domain, port,
                     httpPrefix, True, password)
    assert os.path.isfile(baseDir + '/accounts/passwords')
    deleteAllPosts(baseDir, nickname, domain, 'inbox')
    deleteAllPosts(baseDir, nickname, domain, 'outbox')
    setDisplayNickname(baseDir, nickname, domain, 'badger')
    setBio(baseDir, nickname, domain, 'Randomly roaming in your backyard')
    archivePostsForPerson(nickname, domain, baseDir, 'inbox', None, 4)
    archivePostsForPerson(nickname, domain, baseDir, 'outbox', None, 4)
    createPublicPost(baseDir, nickname, domain, port, httpPrefix,
                     "G'day world!", False, True, clientToServer,
                     None, None, useBlurhash, None, None,
                     'Not suitable for Vogons')

    os.chdir(currDir)
    shutil.rmtree(baseDir)


def testDelegateRoles():
    print('testDelegateRoles')
    currDir = os.getcwd()
    nickname = 'test382'
    nicknameDelegated = 'test383'
    domain = 'badgerdomain.com'
    password = 'mypass'
    port = 80
    httpPrefix = 'https'
    baseDir = currDir + '/.tests_delegaterole'
    if os.path.isdir(baseDir):
        shutil.rmtree(baseDir)
    os.mkdir(baseDir)
    os.chdir(baseDir)

    privateKeyPem, publicKeyPem, person, wfEndpoint = \
        createPerson(baseDir, nickname, domain, port,
                     httpPrefix, True, password)
    privateKeyPem, publicKeyPem, person, wfEndpoint = \
        createPerson(baseDir, nicknameDelegated, domain, port,
                     httpPrefix, True, 'insecure')

    httpPrefix = 'http'
    project = 'artechoke'
    role = 'delegator'
    actorDelegated = \
        httpPrefix + '://' + domain + '/users/' + nicknameDelegated
    newRoleJson = {
        'type': 'Delegate',
        'actor': httpPrefix + '://' + domain + '/users/' + nickname,
        'object': {
            'type': 'Role',
            'actor': actorDelegated,
            'object': project + ';' + role,
            'to': [],
            'cc': []
        },
        'to': [],
        'cc': []
    }

    assert outboxDelegate(baseDir, nickname, newRoleJson, False)
    # second time delegation has already happened so should return false
    assert outboxDelegate(baseDir, nickname, newRoleJson, False) is False

    assert '"delegator"' in open(baseDir + '/accounts/' + nickname +
                                 '@' + domain + '.json').read()
    assert '"delegator"' in open(baseDir + '/accounts/' + nicknameDelegated +
                                 '@' + domain + '.json').read()

    newRoleJson = {
        'type': 'Delegate',
        'actor': httpPrefix + '://' + domain + '/users/' + nicknameDelegated,
        'object': {
            'type': 'Role',
            'actor': httpPrefix + '://' + domain + '/users/' + nickname,
            'object': 'otherproject;otherrole',
            'to': [],
            'cc': []
        },
        'to': [],
        'cc': []
    }

    # non-delegators cannot assign roles
    assert outboxDelegate(baseDir, nicknameDelegated,
                          newRoleJson, False) is False
    assert '"otherrole"' not in open(baseDir + '/accounts/' +
                                     nickname + '@' + domain + '.json').read()

    os.chdir(currDir)
    shutil.rmtree(baseDir)


def testAuthentication():
    print('testAuthentication')
    currDir = os.getcwd()
    nickname = 'test8743'
    password = 'SuperSecretPassword12345'

    baseDir = currDir + '/.tests_authentication'
    if os.path.isdir(baseDir):
        shutil.rmtree(baseDir)
    os.mkdir(baseDir)
    os.chdir(baseDir)

    assert storeBasicCredentials(baseDir, 'othernick', 'otherpass')
    assert storeBasicCredentials(baseDir, 'bad:nick', 'otherpass') is False
    assert storeBasicCredentials(baseDir, 'badnick', 'otherpa:ss') is False
    assert storeBasicCredentials(baseDir, nickname, password)

    authHeader = createBasicAuthHeader(nickname, password)
    assert authorizeBasic(baseDir, '/users/' + nickname + '/inbox',
                          authHeader, False)
    assert authorizeBasic(baseDir, '/users/' + nickname,
                          authHeader, False) is False
    assert authorizeBasic(baseDir, '/users/othernick/inbox',
                          authHeader, False) is False

    authHeader = createBasicAuthHeader(nickname, password + '1')
    assert authorizeBasic(baseDir, '/users/' + nickname + '/inbox',
                          authHeader, False) is False

    password = 'someOtherPassword'
    assert storeBasicCredentials(baseDir, nickname, password)

    authHeader = createBasicAuthHeader(nickname, password)
    assert authorizeBasic(baseDir, '/users/' + nickname + '/inbox',
                          authHeader, False)

    os.chdir(currDir)
    shutil.rmtree(baseDir)


def testClientToServer():
    print('Testing sending a post via c2s')

    global testServerAliceRunning
    global testServerBobRunning
    testServerAliceRunning = False
    testServerBobRunning = False

    httpPrefix = 'http'
    proxyType = None
    federationList = []

    baseDir = os.getcwd()
    if os.path.isdir(baseDir + '/.tests'):
        shutil.rmtree(baseDir + '/.tests')
    os.mkdir(baseDir + '/.tests')

    ocapAlways = False

    # create the servers
    aliceDir = baseDir + '/.tests/alice'
    aliceDomain = '127.0.0.42'
    alicePort = 61935
    aliceSendThreads = []
    aliceAddress = aliceDomain + ':' + str(alicePort)

    bobDir = baseDir + '/.tests/bob'
    bobDomain = '127.0.0.64'
    bobPort = 61936
    bobSendThreads = []
    bobAddress = bobDomain + ':' + str(bobPort)

    global thrAlice
    if thrAlice:
        while thrAlice.isAlive():
            thrAlice.stop()
            time.sleep(1)
        thrAlice.kill()

    thrAlice = \
        threadWithTrace(target=createServerAlice,
                        args=(aliceDir, aliceDomain, alicePort, bobAddress,
                              federationList, False, False,
                              ocapAlways, aliceSendThreads),
                        daemon=True)

    global thrBob
    if thrBob:
        while thrBob.isAlive():
            thrBob.stop()
            time.sleep(1)
        thrBob.kill()

    thrBob = \
        threadWithTrace(target=createServerBob,
                        args=(bobDir, bobDomain, bobPort, aliceAddress,
                              federationList, False, False,
                              ocapAlways, bobSendThreads),
                        daemon=True)

    thrAlice.start()
    thrBob.start()
    assert thrAlice.isAlive() is True
    assert thrBob.isAlive() is True

    # wait for both servers to be running
    ctr = 0
    while not (testServerAliceRunning and testServerBobRunning):
        time.sleep(1)
        ctr += 1
        if ctr > 60:
            break
    print('Alice online: ' + str(testServerAliceRunning))
    print('Bob online: ' + str(testServerBobRunning))

    time.sleep(1)

    print('\n\n*******************************************************')
    print('Alice sends to Bob via c2s')

    sessionAlice = createSession(proxyType)
    followersOnly = False
    attachedImageFilename = baseDir+'/img/logo.png'
    mediaType = getAttachmentMediaType(attachedImageFilename)
    attachedImageDescription = 'Logo'
    useBlurhash = False
    isArticle = False
    cachedWebfingers = {}
    personCache = {}
    password = 'alicepass'
    outboxPath = aliceDir + '/accounts/alice@' + aliceDomain + '/outbox'
    inboxPath = bobDir + '/accounts/bob@' + bobDomain + '/inbox'
    assert len([name for name in os.listdir(outboxPath)
                if os.path.isfile(os.path.join(outboxPath, name))]) == 0
    assert len([name for name in os.listdir(inboxPath)
                if os.path.isfile(os.path.join(inboxPath, name))]) == 0
    sendResult = \
        sendPostViaServer(__version__,
                          aliceDir, sessionAlice, 'alice', password,
                          aliceDomain, alicePort,
                          'bob', bobDomain, bobPort, None,
                          httpPrefix, 'Sent from my ActivityPub client',
                          followersOnly,
                          attachedImageFilename, mediaType,
                          attachedImageDescription, useBlurhash,
                          cachedWebfingers, personCache, isArticle,
                          True, None, None, None)
    print('sendResult: ' + str(sendResult))

    for i in range(30):
        if os.path.isdir(outboxPath):
            if len([name for name in os.listdir(outboxPath)
                    if os.path.isfile(os.path.join(outboxPath, name))]) == 1:
                break
        time.sleep(1)

    assert len([name for name in os.listdir(outboxPath)
                if os.path.isfile(os.path.join(outboxPath, name))]) == 1
    print(">>> c2s post arrived in Alice's outbox")

    for i in range(30):
        if os.path.isdir(inboxPath):
            if len([name for name in os.listdir(inboxPath)
                    if os.path.isfile(os.path.join(inboxPath, name))]) == 1:
                break
        time.sleep(1)

    assert len([name for name in os.listdir(inboxPath)
                if os.path.isfile(os.path.join(inboxPath, name))]) == 1
    print(">>> s2s post arrived in Bob's inbox")
    print("c2s send success")

    print('\n\nGetting message id for the post')
    statusNumber = 0
    outboxPostFilename = None
    outboxPostId = None
    for name in os.listdir(outboxPath):
        if '#statuses#' in name:
            statusNumber = name.split('#statuses#')[1].replace('.json', '')
            statusNumber = int(statusNumber.replace('#activity', ''))
            outboxPostFilename = outboxPath + '/' + name
            postJsonObject = loadJson(outboxPostFilename, 0)
            if postJsonObject:
                outboxPostId = postJsonObject['id'].replace('/activity', '')
    assert outboxPostId
    print('message id obtained: ' + outboxPostId)
    assert validInbox(bobDir, 'bob', bobDomain)
    assert validInboxFilenames(bobDir, 'bob', bobDomain,
                               aliceDomain, alicePort)

    print('\n\nAlice follows Bob')
    sendFollowRequestViaServer(aliceDir, sessionAlice,
                               'alice', password,
                               aliceDomain, alicePort,
                               'bob', bobDomain, bobPort,
                               httpPrefix,
                               cachedWebfingers, personCache,
                               True, __version__)
    aliceFollowingFilename = \
        aliceDir + '/accounts/alice@' + aliceDomain + '/following.txt'
    bobFollowersFilename = \
        bobDir + '/accounts/bob@' + bobDomain + '/followers.txt'
    for t in range(10):
        if os.path.isfile(bobFollowersFilename):
            if 'alice@' + aliceDomain + ':' + str(alicePort) in \
               open(bobFollowersFilename).read():
                if os.path.isfile(aliceFollowingFilename):
                    if 'bob@' + bobDomain + ':' + str(bobPort) in \
                       open(aliceFollowingFilename).read():
                        break
        time.sleep(1)

    assert os.path.isfile(bobFollowersFilename)
    assert os.path.isfile(aliceFollowingFilename)
    print('alice@' + aliceDomain + ':' + str(alicePort) + ' in ' +
          bobFollowersFilename)
    assert 'alice@' + aliceDomain + ':' + str(alicePort) in \
        open(bobFollowersFilename).read()
    print('bob@' + bobDomain + ':' + str(bobPort) + ' in ' +
          aliceFollowingFilename)
    assert 'bob@' + bobDomain + ':' + str(bobPort) in \
        open(aliceFollowingFilename).read()
    assert validInbox(bobDir, 'bob', bobDomain)
    assert validInboxFilenames(bobDir, 'bob', bobDomain,
                               aliceDomain, alicePort)

    print('\n\nBob follows Alice')
    sendFollowRequestViaServer(aliceDir, sessionAlice,
                               'bob', 'bobpass',
                               bobDomain, bobPort,
                               'alice', aliceDomain, alicePort,
                               httpPrefix,
                               cachedWebfingers, personCache,
                               True, __version__)
    for t in range(10):
        if os.path.isfile(aliceDir + '/accounts/alice@' + aliceDomain +
                          '/followers.txt'):
            if 'bob@' + bobDomain + ':' + str(bobPort) in \
               open(aliceDir + '/accounts/alice@' + aliceDomain +
                    '/followers.txt').read():
                if os.path.isfile(bobDir + '/accounts/bob@' + bobDomain +
                                  '/following.txt'):
                    if 'alice@' + aliceDomain + ':' + str(alicePort) in \
                       open(bobDir + '/accounts/bob@' + bobDomain +
                            '/following.txt').read():
                        break
        time.sleep(1)

    assert os.path.isfile(aliceDir + '/accounts/alice@' + aliceDomain +
                          '/followers.txt')
    assert os.path.isfile(bobDir + '/accounts/bob@' + bobDomain +
                          '/following.txt')
    assert 'bob@' + bobDomain + ':' + str(bobPort) in \
        open(aliceDir + '/accounts/alice@' + aliceDomain +
             '/followers.txt').read()
    assert 'alice@' + aliceDomain + ':' + str(alicePort) in \
        open(bobDir + '/accounts/bob@' + bobDomain + '/following.txt').read()

    print('\n\nBob likes the post')
    sessionBob = createSession(proxyType)
    password = 'bobpass'
    outboxPath = bobDir + '/accounts/bob@' + bobDomain + '/outbox'
    inboxPath = aliceDir + '/accounts/alice@' + aliceDomain + '/inbox'
    print(str(len([name for name in os.listdir(outboxPath)
                   if os.path.isfile(os.path.join(outboxPath, name))])))
    assert len([name for name in os.listdir(outboxPath)
                if os.path.isfile(os.path.join(outboxPath, name))]) == 1
    print(str(len([name for name in os.listdir(inboxPath)
                   if os.path.isfile(os.path.join(inboxPath, name))])))
    assert len([name for name in os.listdir(inboxPath)
                if os.path.isfile(os.path.join(inboxPath, name))]) == 1
    sendLikeViaServer(bobDir, sessionBob,
                      'bob', 'bobpass',
                      bobDomain, bobPort,
                      httpPrefix, outboxPostId,
                      cachedWebfingers, personCache,
                      True, __version__)
    for i in range(20):
        if os.path.isdir(outboxPath) and os.path.isdir(inboxPath):
            if len([name for name in os.listdir(outboxPath)
                    if os.path.isfile(os.path.join(outboxPath, name))]) == 2:
                test = len([name for name in os.listdir(inboxPath)
                            if os.path.isfile(os.path.join(inboxPath, name))])
                if test == 1:
                    break
        time.sleep(1)
    assert len([name for name in os.listdir(outboxPath)
                if os.path.isfile(os.path.join(outboxPath, name))]) == 2
    assert len([name for name in os.listdir(inboxPath)
                if os.path.isfile(os.path.join(inboxPath, name))]) == 1
    print('Post liked')

    print('\n\nBob repeats the post')
    print(str(len([name for name in os.listdir(outboxPath)
                   if os.path.isfile(os.path.join(outboxPath, name))])))
    assert len([name for name in os.listdir(outboxPath)
                if os.path.isfile(os.path.join(outboxPath, name))]) == 2
    print(str(len([name for name in os.listdir(inboxPath)
                   if os.path.isfile(os.path.join(inboxPath, name))])))
    assert len([name for name in os.listdir(inboxPath)
                if os.path.isfile(os.path.join(inboxPath, name))]) == 1
    sendAnnounceViaServer(bobDir, sessionBob, 'bob', password,
                          bobDomain, bobPort,
                          httpPrefix, outboxPostId,
                          cachedWebfingers,
                          personCache, True, __version__)
    for i in range(20):
        if os.path.isdir(outboxPath) and os.path.isdir(inboxPath):
            if len([name for name in os.listdir(outboxPath)
                    if os.path.isfile(os.path.join(outboxPath, name))]) == 3:
                if len([name for name in os.listdir(inboxPath)
                        if os.path.isfile(os.path.join(inboxPath,
                                                       name))]) == 2:
                    break
        time.sleep(1)

    assert len([name for name in os.listdir(outboxPath)
                if os.path.isfile(os.path.join(outboxPath, name))]) == 3
    assert len([name for name in os.listdir(inboxPath)
                if os.path.isfile(os.path.join(inboxPath, name))]) == 2
    print('Post repeated')

    inboxPath = bobDir + '/accounts/bob@' + bobDomain + '/inbox'
    outboxPath = aliceDir + '/accounts/alice@' + aliceDomain + '/outbox'
    postsBefore = \
        len([name for name in os.listdir(inboxPath)
             if os.path.isfile(os.path.join(inboxPath, name))])
    print('\n\nAlice deletes her post: ' + outboxPostId + ' ' +
          str(postsBefore))
    password = 'alicepass'
    sendDeleteViaServer(aliceDir, sessionAlice, 'alice', password,
                        aliceDomain, alicePort,
                        httpPrefix, outboxPostId,
                        cachedWebfingers, personCache,
                        True, __version__)
    for i in range(30):
        if os.path.isdir(inboxPath):
            test = len([name for name in os.listdir(inboxPath)
                        if os.path.isfile(os.path.join(inboxPath, name))])
            if test == postsBefore-1:
                break
        time.sleep(1)

    test = len([name for name in os.listdir(inboxPath)
                if os.path.isfile(os.path.join(inboxPath, name))])
    assert test == postsBefore - 1
    print(">>> post deleted from Alice's outbox and Bob's inbox")
    assert validInbox(bobDir, 'bob', bobDomain)
    assert validInboxFilenames(bobDir, 'bob', bobDomain,
                               aliceDomain, alicePort)

    print('\n\nAlice unfollows Bob')
    password = 'alicepass'
    sendUnfollowRequestViaServer(baseDir, sessionAlice,
                                 'alice', password,
                                 aliceDomain, alicePort,
                                 'bob', bobDomain, bobPort,
                                 httpPrefix,
                                 cachedWebfingers, personCache,
                                 True, __version__)
    for t in range(10):
        if 'alice@' + aliceDomain + ':' + str(alicePort) not in \
           open(bobFollowersFilename).read():
            if 'bob@' + bobDomain + ':' + str(bobPort) not in \
               open(aliceFollowingFilename).read():
                break
        time.sleep(1)

    assert os.path.isfile(bobFollowersFilename)
    assert os.path.isfile(aliceFollowingFilename)
    assert 'alice@' + aliceDomain + ':' + str(alicePort) \
        not in open(bobFollowersFilename).read()
    assert 'bob@' + bobDomain + ':' + str(bobPort) \
        not in open(aliceFollowingFilename).read()
    assert validInbox(bobDir, 'bob', bobDomain)
    assert validInboxFilenames(bobDir, 'bob', bobDomain,
                               aliceDomain, alicePort)
    assert validInbox(aliceDir, 'alice', aliceDomain)
    assert validInboxFilenames(aliceDir, 'alice', aliceDomain,
                               bobDomain, bobPort)

    # stop the servers
    thrAlice.kill()
    thrAlice.join()
    assert thrAlice.isAlive() is False

    thrBob.kill()
    thrBob.join()
    assert thrBob.isAlive() is False

    os.chdir(baseDir)
    # shutil.rmtree(aliceDir)
    # shutil.rmtree(bobDir)


def testActorParsing():
    print('testActorParsing')
    actor = 'https://mydomain:72/users/mynick'
    domain, port = getDomainFromActor(actor)
    assert domain == 'mydomain'
    assert port == 72
    nickname = getNicknameFromActor(actor)
    assert nickname == 'mynick'

    actor = 'https://randomain/users/rando'
    domain, port = getDomainFromActor(actor)
    assert domain == 'randomain'
    nickname = getNicknameFromActor(actor)
    assert nickname == 'rando'

    actor = 'https://otherdomain:49/@othernick'
    domain, port = getDomainFromActor(actor)
    assert domain == 'otherdomain'
    assert port == 49
    nickname = getNicknameFromActor(actor)
    assert nickname == 'othernick'


def testWebLinks():
    print('testWebLinks')

    exampleText = \
        '<p><span class=\"h-card\"><a href=\"https://something/@orother' + \
        '\" class=\"u-url mention\">@<span>foo</span></a></span> Some ' + \
        'random text.</p><p>AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' + \
        'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' + \
        'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' + \
        'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' + \
        'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' + \
        'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA</p>'
    resultText = removeLongWords(exampleText, 40, [])
    assert resultText == \
        '<p><span class="h-card"><a href="https://something/@orother"' + \
        ' class="u-url mention">@<span>foo</span></a></span> ' + \
        'Some random text.</p>'

    exampleText = \
        'This post has a web links https://somesite.net\n\nAnd some other text'
    linkedText = addWebLinks(exampleText)
    assert \
        '<a href="https://somesite.net" rel="nofollow noopener"' + \
        ' target="_blank"><span class="invisible">https://' + \
        '</span><span class="ellipsis">somesite.net</span></a' in linkedText

    exampleText = \
        'This post has a very long web link\n\nhttp://' + \
        'cbwebewuvfuftdiudbqd33dddbbyuef23fyug3bfhcyu2fct2' + \
        'cuyqbcbucuwvckiwyfgewfvqejbchevbhwevuevwbqebqekve' + \
        'qvuvjfkf.onion\n\nAnd some other text'
    linkedText = addWebLinks(exampleText)
    assert 'ellipsis' in linkedText

    exampleText = \
        '<p>1. HAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAH' + \
        'AHAHAHHAHAHAHAHAHAHAHAHAHAHAHAHHAHAHAHAHAHAHAHAH</p>'
    resultText = removeLongWords(exampleText, 40, [])
    assert resultText == '<p>1. HAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHAHA</p>'

    exampleText = \
        '<p>Tox address is 88AB9DED6F9FBEF43E105FB72060A2D89F9B93C74' + \
        '4E8C45AB3C5E42C361C837155AFCFD9D448 </p>'
    resultText = removeLongWords(exampleText, 40, [])
    assert resultText == exampleText

    exampleText = \
        '<p>Tox address is 88AB9DED6F9FBEF43E105FB72060A2D89F9B93C74' + \
        '4E8C45AB3C5E42C361C837155AFCFD9D448</p>'
    resultText = removeLongWords(exampleText, 40, [])
    assert resultText == \
        '<p>Tox address is 88AB9DED6F9FBEF43E105FB72060A2D89F9B93C7\n' + \
        '44E8C45AB3C5E42C361C837155AFCFD9D448</p>'

    exampleText = \
        '<p>ABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCA' + \
        'BCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCAB' + \
        'CABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABC' + \
        'ABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCA' + \
        'BCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCAB' + \
        'CABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABC' + \
        'ABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCA' + \
        'BCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCABCAB' + \
        'CABCABCABCABCABCABCABCABC</p>'
    resultText = removeLongWords(exampleText, 40, [])
    assert resultText == r'<p>ABCABCABCABCABCABCABCABCABCABCABCABCABCA<\p>'

    exampleText = \
        '"the nucleus of mutual-support institutions, habits, and customs ' + \
        'remains alive with the millions; it keeps them together; and ' + \
        'they prefer to cling to their customs, beliefs, and traditions ' + \
        'rather than to accept the teachings of a war of each ' + \
        'against all"\n\n--Peter Kropotkin'
    resultText = removeLongWords(addWebLinks(exampleText), 40, [])
    assert resultText == exampleText
    assert 'ellipsis' not in resultText

    exampleText = \
        '<p>ｆｉｌｅｐｏｐｏｕｔ＝' + \
        'ＴｅｍｐｌａｔｅＡｔｔａｃｈｍｅｎｔＲｉｃｈＰｏｐｏｕｔ<<\\p>'
    resultText = replaceContentDuplicates(exampleText)
    assert resultText == \
        '<p>ｆｉｌｅｐｏｐｏｕｔ＝' + \
        'ＴｅｍｐｌａｔｅＡｔｔａｃｈｍｅｎｔＲｉｃｈＰｏｐｏｕｔ'


def testAddEmoji():
    print('testAddEmoji')
    content = "Emoji :lemon: :strawberry: :banana:"
    httpPrefix = 'http'
    nickname = 'testuser'
    domain = 'testdomain.net'
    port = 3682
    recipients = []
    hashtags = {}
    baseDir = os.getcwd()
    baseDirOriginal = os.getcwd()
    path = baseDir + '/.tests'
    if not os.path.isdir(path):
        os.mkdir(path)
    path = baseDir + '/.tests/emoji'
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.mkdir(path)
    baseDir = path
    path = baseDir + '/emoji'
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.mkdir(path)
    copytree(baseDirOriginal + '/emoji', baseDir + '/emoji')
    os.chdir(baseDir)
    privateKeyPem, publicKeyPem, person, wfEndpoint = \
        createPerson(baseDir, nickname, domain, port,
                     httpPrefix, True, 'password')
    contentModified = \
        addHtmlTags(baseDir, httpPrefix,
                    nickname, domain, content,
                    recipients, hashtags, True)
    assert ':lemon:' in contentModified
    assert contentModified.startswith('<p>')
    assert contentModified.endswith('</p>')
    tags = []
    for tagName, tag in hashtags.items():
        tags.append(tag)
    content = contentModified
    contentModified = replaceEmojiFromTags(content, tags, 'content')
    # print('contentModified: '+contentModified)
    assert contentModified == '<p>Emoji 🍋 🍓 🍌</p>'

    os.chdir(baseDirOriginal)
    shutil.rmtree(baseDirOriginal + '/.tests')


def testGetStatusNumber():
    print('testGetStatusNumber')
    prevStatusNumber = None
    for i in range(1, 20):
        statusNumber, published = getStatusNumber()
        if prevStatusNumber:
            assert len(statusNumber) == 18
            assert int(statusNumber) > prevStatusNumber
        prevStatusNumber = int(statusNumber)


def testCommentJson() -> None:
    print('testCommentJson')
    filename = '/tmp/test.json'
    messageStr = "Crème brûlée यह एक परीक्षण ह"
    testJson = {
        "content": messageStr
    }
    assert saveJson(testJson, filename)
    receivedJson = loadJson(filename, 0)
    assert receivedJson
    assert receivedJson['content'] == messageStr
    encodedStr = json.dumps(testJson, ensure_ascii=False)
    assert messageStr in encodedStr


def testSaveLoadJson():
    print('testSaveLoadJson')
    testJson = {
        "param1": 3,
        "param2": '"Crème brûlée यह एक परीक्षण ह"'
    }
    testFilename = '/tmp/.epicyonTestSaveLoadJson.json'
    if os.path.isfile(testFilename):
        os.remove(testFilename)
    assert saveJson(testJson, testFilename)
    assert os.path.isfile(testFilename)
    testLoadJson = loadJson(testFilename)
    assert(testLoadJson)
    assert testLoadJson.get('param1')
    assert testLoadJson.get('param2')
    assert testLoadJson['param1'] == 3
    assert testLoadJson['param2'] == '"Crème brûlée यह एक परीक्षण ह"'
    os.remove(testFilename)


def testTheme():
    print('testTheme')
    css = 'somestring --background-value: 24px; --foreground-value: 24px;'
    result = setCSSparam(css, 'background-value', '32px')
    assert result == \
        'somestring --background-value: 32px; --foreground-value: 24px;'
    css = \
        'somestring --background-value: 24px; --foreground-value: 24px; ' + \
        '--background-value: 24px;'
    result = setCSSparam(css, 'background-value', '32px')
    assert result == \
        'somestring --background-value: 32px; --foreground-value: 24px; ' + \
        '--background-value: 32px;'
    css = '--background-value: 24px; --foreground-value: 24px;'
    result = setCSSparam(css, 'background-value', '32px')
    assert result == '--background-value: 32px; --foreground-value: 24px;'


def testRecentPostsCache():
    print('testRecentPostsCache')
    recentPostsCache = {}
    maxRecentPosts = 3
    htmlStr = '<html></html>'
    for i in range(5):
        postJsonObject = {
            "id": "https://somesite.whatever/users/someuser/statuses/"+str(i)
        }
        updateRecentPostsCache(recentPostsCache, maxRecentPosts,
                               postJsonObject, htmlStr)
    assert len(recentPostsCache['index']) == maxRecentPosts
    assert len(recentPostsCache['json'].items()) == maxRecentPosts
    assert len(recentPostsCache['html'].items()) == maxRecentPosts


def runAllTests():
    print('Running tests...')
    testWebLinks()
    testRecentPostsCache()
    testTheme()
    testSaveLoadJson()
    testCommentJson()
    testGetStatusNumber()
    testAddEmoji()
    testActorParsing()
    testHttpsig()
    testCache()
    testThreads()
    testCreatePerson()
    testAuthentication()
    testFollowersOfPerson()
    testNoOfFollowersOnDomain()
    testFollows()
    testGroupFollowers()
    testDelegateRoles()
    print('Tests succeeded\n')
