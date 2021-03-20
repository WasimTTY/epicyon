__filename__ = "bookmarks.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@freedombone.net"
__status__ = "Production"

import os
from pprint import pprint
from webfinger import webfingerHandle
from auth import createBasicAuthHeader
from utils import hasUsersPath
from utils import getFullDomain
from utils import removeIdEnding
from utils import removePostFromCache
from utils import urlPermitted
from utils import getNicknameFromActor
from utils import getDomainFromActor
from utils import locatePost
from utils import getCachedPostFilename
from utils import loadJson
from utils import saveJson
from posts import getPersonBox
from session import postJson


def undoBookmarksCollectionEntry(recentPostsCache: {},
                                 baseDir: str, postFilename: str,
                                 objectUrl: str,
                                 actor: str, domain: str, debug: bool) -> None:
    """Undoes a bookmark for a particular actor
    """
    postJsonObject = loadJson(postFilename)
    if not postJsonObject:
        return

    # remove any cached version of this post so that the
    # bookmark icon is changed
    nickname = getNicknameFromActor(actor)
    cachedPostFilename = getCachedPostFilename(baseDir, nickname,
                                               domain, postJsonObject)
    if cachedPostFilename:
        if os.path.isfile(cachedPostFilename):
            os.remove(cachedPostFilename)
    removePostFromCache(postJsonObject, recentPostsCache)

    # remove from the index
    bookmarksIndexFilename = baseDir + '/accounts/' + \
        nickname + '@' + domain + '/bookmarks.index'
    if not os.path.isfile(bookmarksIndexFilename):
        return
    if '/' in postFilename:
        bookmarkIndex = postFilename.split('/')[-1].strip()
    else:
        bookmarkIndex = postFilename.strip()
    bookmarkIndex = bookmarkIndex.replace('\n', '').replace('\r', '')
    if bookmarkIndex not in open(bookmarksIndexFilename).read():
        return
    indexStr = ''
    with open(bookmarksIndexFilename, 'r') as indexFile:
        indexStr = indexFile.read().replace(bookmarkIndex + '\n', '')
        bookmarksIndexFile = open(bookmarksIndexFilename, 'w+')
        if bookmarksIndexFile:
            bookmarksIndexFile.write(indexStr)
            bookmarksIndexFile.close()

    if not postJsonObject.get('type'):
        return
    if postJsonObject['type'] != 'Create':
        return
    if not postJsonObject.get('object'):
        if debug:
            print('DEBUG: bookmarked post has no object ' +
                  str(postJsonObject))
        return
    if not isinstance(postJsonObject['object'], dict):
        return
    if not postJsonObject['object'].get('bookmarks'):
        return
    if not isinstance(postJsonObject['object']['bookmarks'], dict):
        return
    if not postJsonObject['object']['bookmarks'].get('items'):
        return
    totalItems = 0
    if postJsonObject['object']['bookmarks'].get('totalItems'):
        totalItems = postJsonObject['object']['bookmarks']['totalItems']
        itemFound = False
    for bookmarkItem in postJsonObject['object']['bookmarks']['items']:
        if bookmarkItem.get('actor'):
            if bookmarkItem['actor'] == actor:
                if debug:
                    print('DEBUG: bookmark was removed for ' + actor)
                bmIt = bookmarkItem
                postJsonObject['object']['bookmarks']['items'].remove(bmIt)
                itemFound = True
                break

    if not itemFound:
        return

    if totalItems == 1:
        if debug:
            print('DEBUG: bookmarks was removed from post')
        del postJsonObject['object']['bookmarks']
    else:
        bmItLen = len(postJsonObject['object']['bookmarks']['items'])
        postJsonObject['object']['bookmarks']['totalItems'] = bmItLen
    saveJson(postJsonObject, postFilename)


def bookmarkedByPerson(postJsonObject: {}, nickname: str, domain: str) -> bool:
    """Returns True if the given post is bookmarked by the given person
    """
    if _noOfBookmarks(postJsonObject) == 0:
        return False
    actorMatch = domain + '/users/' + nickname
    for item in postJsonObject['object']['bookmarks']['items']:
        if item['actor'].endswith(actorMatch):
            return True
    return False


def _noOfBookmarks(postJsonObject: {}) -> int:
    """Returns the number of bookmarks ona  given post
    """
    if not postJsonObject.get('object'):
        return 0
    if not isinstance(postJsonObject['object'], dict):
        return 0
    if not postJsonObject['object'].get('bookmarks'):
        return 0
    if not isinstance(postJsonObject['object']['bookmarks'], dict):
        return 0
    if not postJsonObject['object']['bookmarks'].get('items'):
        postJsonObject['object']['bookmarks']['items'] = []
        postJsonObject['object']['bookmarks']['totalItems'] = 0
    return len(postJsonObject['object']['bookmarks']['items'])


def updateBookmarksCollection(recentPostsCache: {},
                              baseDir: str, postFilename: str,
                              objectUrl: str,
                              actor: str, domain: str, debug: bool) -> None:
    """Updates the bookmarks collection within a post
    """
    postJsonObject = loadJson(postFilename)
    if postJsonObject:
        # remove any cached version of this post so that the
        # bookmark icon is changed
        nickname = getNicknameFromActor(actor)
        cachedPostFilename = getCachedPostFilename(baseDir, nickname,
                                                   domain, postJsonObject)
        if cachedPostFilename:
            if os.path.isfile(cachedPostFilename):
                os.remove(cachedPostFilename)
        removePostFromCache(postJsonObject, recentPostsCache)

        if not postJsonObject.get('object'):
            if debug:
                print('DEBUG: no object in bookmarked post ' +
                      str(postJsonObject))
            return
        if not objectUrl.endswith('/bookmarks'):
            objectUrl = objectUrl + '/bookmarks'
        # does this post have bookmarks on it from differenent actors?
        if not postJsonObject['object'].get('bookmarks'):
            if debug:
                print('DEBUG: Adding initial bookmarks to ' + objectUrl)
            bookmarksJson = {
                "@context": "https://www.w3.org/ns/activitystreams",
                'id': objectUrl,
                'type': 'Collection',
                "totalItems": 1,
                'items': [{
                    'type': 'Bookmark',
                    'actor': actor
                }]
            }
            postJsonObject['object']['bookmarks'] = bookmarksJson
        else:
            if not postJsonObject['object']['bookmarks'].get('items'):
                postJsonObject['object']['bookmarks']['items'] = []
            for bookmarkItem in postJsonObject['object']['bookmarks']['items']:
                if bookmarkItem.get('actor'):
                    if bookmarkItem['actor'] == actor:
                        return
                    newBookmark = {
                        'type': 'Bookmark',
                        'actor': actor
                    }
                    nb = newBookmark
                    bmIt = len(postJsonObject['object']['bookmarks']['items'])
                    postJsonObject['object']['bookmarks']['items'].append(nb)
                    postJsonObject['object']['bookmarks']['totalItems'] = bmIt

        if debug:
            print('DEBUG: saving post with bookmarks added')
            pprint(postJsonObject)

        saveJson(postJsonObject, postFilename)

        # prepend to the index
        bookmarksIndexFilename = baseDir + '/accounts/' + \
            nickname + '@' + domain + '/bookmarks.index'
        bookmarkIndex = postFilename.split('/')[-1]
        if os.path.isfile(bookmarksIndexFilename):
            if bookmarkIndex not in open(bookmarksIndexFilename).read():
                try:
                    with open(bookmarksIndexFilename, 'r+') as bmIndexFile:
                        content = bmIndexFile.read()
                        if bookmarkIndex + '\n' not in content:
                            bmIndexFile.seek(0, 0)
                            bmIndexFile.write(bookmarkIndex + '\n' + content)
                            if debug:
                                print('DEBUG: bookmark added to index')
                except Exception as e:
                    print('WARN: Failed to write entry to bookmarks index ' +
                          bookmarksIndexFilename + ' ' + str(e))
        else:
            bookmarksIndexFile = open(bookmarksIndexFilename, 'w+')
            if bookmarksIndexFile:
                bookmarksIndexFile.write(bookmarkIndex + '\n')
                bookmarksIndexFile.close()


def bookmark(recentPostsCache: {},
             session, baseDir: str, federationList: [],
             nickname: str, domain: str, port: int,
             ccList: [], httpPrefix: str,
             objectUrl: str, actorBookmarked: str,
             clientToServer: bool,
             sendThreads: [], postLog: [],
             personCache: {}, cachedWebfingers: {},
             debug: bool, projectVersion: str) -> {}:
    """Creates a bookmark
    actor is the person doing the bookmarking
    'to' might be a specific person (actor) whose post was bookmarked
    object is typically the url of the message which was bookmarked
    """
    if not urlPermitted(objectUrl, federationList):
        return None

    fullDomain = getFullDomain(domain, port)

    newBookmarkJson = {
        "@context": "https://www.w3.org/ns/activitystreams",
        'type': 'Bookmark',
        'actor': httpPrefix+'://'+fullDomain+'/users/'+nickname,
        'object': objectUrl
    }
    if ccList:
        if len(ccList) > 0:
            newBookmarkJson['cc'] = ccList

    # Extract the domain and nickname from a statuses link
    bookmarkedPostNickname = None
    bookmarkedPostDomain = None
    bookmarkedPostPort = None
    if actorBookmarked:
        acBm = actorBookmarked
        bookmarkedPostNickname = getNicknameFromActor(acBm)
        bookmarkedPostDomain, bookmarkedPostPort = getDomainFromActor(acBm)
    else:
        if hasUsersPath(objectUrl):
            ou = objectUrl
            bookmarkedPostNickname = getNicknameFromActor(ou)
            bookmarkedPostDomain, bookmarkedPostPort = getDomainFromActor(ou)

    if bookmarkedPostNickname:
        postFilename = locatePost(baseDir, nickname, domain, objectUrl)
        if not postFilename:
            print('DEBUG: bookmark baseDir: ' + baseDir)
            print('DEBUG: bookmark nickname: ' + nickname)
            print('DEBUG: bookmark domain: ' + domain)
            print('DEBUG: bookmark objectUrl: ' + objectUrl)
            return None

        updateBookmarksCollection(recentPostsCache,
                                  baseDir, postFilename, objectUrl,
                                  newBookmarkJson['actor'], domain, debug)

    return newBookmarkJson


def undoBookmark(recentPostsCache: {},
                 session, baseDir: str, federationList: [],
                 nickname: str, domain: str, port: int,
                 ccList: [], httpPrefix: str,
                 objectUrl: str, actorBookmarked: str,
                 clientToServer: bool,
                 sendThreads: [], postLog: [],
                 personCache: {}, cachedWebfingers: {},
                 debug: bool, projectVersion: str) -> {}:
    """Removes a bookmark
    actor is the person doing the bookmarking
    'to' might be a specific person (actor) whose post was bookmarked
    object is typically the url of the message which was bookmarked
    """
    if not urlPermitted(objectUrl, federationList):
        return None

    fullDomain = getFullDomain(domain, port)

    newUndoBookmarkJson = {
        "@context": "https://www.w3.org/ns/activitystreams",
        'type': 'Undo',
        'actor': httpPrefix+'://'+fullDomain+'/users/'+nickname,
        'object': {
            'type': 'Bookmark',
            'actor': httpPrefix+'://'+fullDomain+'/users/'+nickname,
            'object': objectUrl
        }
    }
    if ccList:
        if len(ccList) > 0:
            newUndoBookmarkJson['cc'] = ccList
            newUndoBookmarkJson['object']['cc'] = ccList

    # Extract the domain and nickname from a statuses link
    bookmarkedPostNickname = None
    bookmarkedPostDomain = None
    bookmarkedPostPort = None
    if actorBookmarked:
        acBm = actorBookmarked
        bookmarkedPostNickname = getNicknameFromActor(acBm)
        bookmarkedPostDomain, bookmarkedPostPort = getDomainFromActor(acBm)
    else:
        if hasUsersPath(objectUrl):
            ou = objectUrl
            bookmarkedPostNickname = getNicknameFromActor(ou)
            bookmarkedPostDomain, bookmarkedPostPort = getDomainFromActor(ou)

    if bookmarkedPostNickname:
        postFilename = locatePost(baseDir, nickname, domain, objectUrl)
        if not postFilename:
            return None

        undoBookmarksCollectionEntry(recentPostsCache,
                                     baseDir, postFilename, objectUrl,
                                     newUndoBookmarkJson['actor'],
                                     domain, debug)
    else:
        return None

    return newUndoBookmarkJson


def sendBookmarkViaServer(baseDir: str, session,
                          nickname: str, password: str,
                          domain: str, fromPort: int,
                          httpPrefix: str, bookmarkUrl: str,
                          cachedWebfingers: {}, personCache: {},
                          debug: bool, projectVersion: str) -> {}:
    """Creates a bookmark via c2s
    """
    if not session:
        print('WARN: No session for sendBookmarkViaServer')
        return 6

    domainFull = getFullDomain(domain, fromPort)

    actor = httpPrefix + '://' + domainFull + '/users/' + nickname

    newBookmarkJson = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Add",
        "actor": actor,
        "to": [actor],
        "object": {
            "type": "Document",
            "url": bookmarkUrl,
            "to": [actor]
        },
        "target": actor + "/tlbookmarks"
    }

    handle = httpPrefix + '://' + domainFull + '/@' + nickname

    # lookup the inbox for the To handle
    wfRequest = webfingerHandle(session, handle, httpPrefix,
                                cachedWebfingers,
                                domain, projectVersion, debug)
    if not wfRequest:
        if debug:
            print('DEBUG: bookmark webfinger failed for ' + handle)
        return 1
    if not isinstance(wfRequest, dict):
        print('WARN: bookmark webfinger for ' + handle +
              ' did not return a dict. ' + str(wfRequest))
        return 1

    postToBox = 'outbox'

    # get the actor inbox for the To handle
    (inboxUrl, pubKeyId, pubKey, fromPersonId, sharedInbox,
     avatarUrl, displayName) = getPersonBox(baseDir, session, wfRequest,
                                            personCache,
                                            projectVersion, httpPrefix,
                                            nickname, domain,
                                            postToBox, 52594)

    if not inboxUrl:
        if debug:
            print('DEBUG: bookmark no ' + postToBox +
                  ' was found for ' + handle)
        return 3
    if not fromPersonId:
        if debug:
            print('DEBUG: bookmark no actor was found for ' + handle)
        return 4

    authHeader = createBasicAuthHeader(nickname, password)

    headers = {
        'host': domain,
        'Content-type': 'application/json',
        'Authorization': authHeader
    }
    postResult = postJson(session, newBookmarkJson, [], inboxUrl,
                          headers, 30, True)
    if not postResult:
        if debug:
            print('WARN: POST bookmark failed for c2s to ' + inboxUrl)
        return 5

    if debug:
        print('DEBUG: c2s POST bookmark success')

    return newBookmarkJson


def sendUndoBookmarkViaServer(baseDir: str, session,
                              nickname: str, password: str,
                              domain: str, fromPort: int,
                              httpPrefix: str, bookmarkUrl: str,
                              cachedWebfingers: {}, personCache: {},
                              debug: bool, projectVersion: str) -> {}:
    """Removes a bookmark via c2s
    """
    if not session:
        print('WARN: No session for sendUndoBookmarkViaServer')
        return 6

    domainFull = getFullDomain(domain, fromPort)

    actor = httpPrefix + '://' + domainFull + '/users/' + nickname

    newBookmarkJson = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Remove",
        "actor": actor,
        "object": {
            "type": "Document",
            "url": bookmarkUrl
        },
        "target": actor + "/tlbookmarks"
    }

    handle = httpPrefix + '://' + domainFull + '/@' + nickname

    # lookup the inbox for the To handle
    wfRequest = webfingerHandle(session, handle, httpPrefix,
                                cachedWebfingers,
                                domain, projectVersion, debug)
    if not wfRequest:
        if debug:
            print('DEBUG: unbookmark webfinger failed for ' + handle)
        return 1
    if not isinstance(wfRequest, dict):
        print('WARN: unbookmark webfinger for ' + handle +
              ' did not return a dict. ' + str(wfRequest))
        return 1

    postToBox = 'outbox'

    # get the actor inbox for the To handle
    (inboxUrl, pubKeyId, pubKey, fromPersonId, sharedInbox,
     avatarUrl, displayName) = getPersonBox(baseDir, session, wfRequest,
                                            personCache,
                                            projectVersion, httpPrefix,
                                            nickname, domain,
                                            postToBox, 52594)

    if not inboxUrl:
        if debug:
            print('DEBUG: unbookmark no ' + postToBox +
                  ' was found for ' + handle)
        return 3
    if not fromPersonId:
        if debug:
            print('DEBUG: unbookmark no actor was found for ' + handle)
        return 4

    authHeader = createBasicAuthHeader(nickname, password)

    headers = {
        'host': domain,
        'Content-type': 'application/json',
        'Authorization': authHeader
    }
    postResult = postJson(session, newBookmarkJson, [], inboxUrl,
                          headers, 30, True)
    if not postResult:
        if debug:
            print('WARN: POST unbookmark failed for c2s to ' + inboxUrl)
        return 5

    if debug:
        print('DEBUG: c2s POST unbookmark success')

    return newBookmarkJson


def outboxBookmark(recentPostsCache: {},
                   baseDir: str, httpPrefix: str,
                   nickname: str, domain: str, port: int,
                   messageJson: {}, debug: bool) -> None:
    """ When a bookmark request is received by the outbox from c2s
    """
    if not messageJson.get('type'):
        return
    if messageJson['type'] != 'Add':
        return
    if not messageJson.get('actor'):
        if debug:
            print('DEBUG: no actor in bookmark Add')
        return
    if not messageJson.get('object'):
        if debug:
            print('DEBUG: no object in bookmark Add')
        return
    if not messageJson.get('target'):
        if debug:
            print('DEBUG: no target in bookmark Add')
        return
    if not isinstance(messageJson['object'], str):
        if debug:
            print('DEBUG: bookmark Add object is not string')
        return
    if not isinstance(messageJson['target'], str):
        if debug:
            print('DEBUG: bookmark Add target is not string')
        return
    domainFull = getFullDomain(domain, port)
    if not messageJson['target'].endswith('://' + domainFull +
                                          '/users/' + nickname +
                                          '/tlbookmarks'):
        if debug:
            print('DEBUG: bookmark Add target invalid ' +
                  messageJson['target'])
        return
    if messageJson['object']['type'] != 'Document':
        if debug:
            print('DEBUG: bookmark Add type is not Document')
        return
    if not messageJson['object'].get('url'):
        if debug:
            print('DEBUG: bookmark Add missing url')
        return
    if debug:
        print('DEBUG: c2s bookmark Add request arrived in outbox')

    messageUrl = removeIdEnding(messageJson['object']['url'])
    if ':' in domain:
        domain = domain.split(':')[0]
    postFilename = locatePost(baseDir, nickname, domain, messageUrl)
    if not postFilename:
        if debug:
            print('DEBUG: c2s like post not found in inbox or outbox')
            print(messageUrl)
        return True
    updateBookmarksCollection(recentPostsCache,
                              baseDir, postFilename, messageUrl,
                              messageJson['actor'], domain, debug)
    if debug:
        print('DEBUG: post bookmarked via c2s - ' + postFilename)


def outboxUndoBookmark(recentPostsCache: {},
                       baseDir: str, httpPrefix: str,
                       nickname: str, domain: str, port: int,
                       messageJson: {}, debug: bool) -> None:
    """ When an undo bookmark request is received by the outbox from c2s
    """
    if not messageJson.get('type'):
        return
    if messageJson['type'] != 'Remove':
        return
    if not messageJson.get('actor'):
        if debug:
            print('DEBUG: no actor in unbookmark Remove')
        return
    if not messageJson.get('object'):
        if debug:
            print('DEBUG: no object in unbookmark Remove')
        return
    if not messageJson.get('target'):
        if debug:
            print('DEBUG: no target in unbookmark Remove')
        return
    if not isinstance(messageJson['object'], str):
        if debug:
            print('DEBUG: unbookmark Remove object is not string')
        return
    if not isinstance(messageJson['target'], str):
        if debug:
            print('DEBUG: unbookmark Remove target is not string')
        return
    domainFull = getFullDomain(domain, port)
    if not messageJson['target'].endswith('://' + domainFull +
                                          '/users/' + nickname +
                                          '/tlbookmarks'):
        if debug:
            print('DEBUG: unbookmark Remove target invalid ' +
                  messageJson['target'])
        return
    if messageJson['object']['type'] != 'Document':
        if debug:
            print('DEBUG: unbookmark Remove type is not Document')
        return
    if not messageJson['object'].get('url'):
        if debug:
            print('DEBUG: unbookmark Remove missing url')
        return
    if debug:
        print('DEBUG: c2s unbookmark Remove request arrived in outbox')

    messageUrl = removeIdEnding(messageJson['object']['url'])
    if ':' in domain:
        domain = domain.split(':')[0]
    postFilename = locatePost(baseDir, nickname, domain, messageUrl)
    if not postFilename:
        if debug:
            print('DEBUG: c2s unbookmark post not found in inbox or outbox')
            print(messageUrl)
        return True
    updateBookmarksCollection(recentPostsCache,
                              baseDir, postFilename, messageUrl,
                              messageJson['actor'], domain, debug)
    if debug:
        print('DEBUG: post unbookmarked via c2s - ' + postFilename)
