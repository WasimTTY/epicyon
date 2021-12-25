__filename__ = "like.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "ActivityPub"

import os
from pprint import pprint
from utils import hasObjectString
from utils import hasObjectStringObject
from utils import hasObjectStringType
from utils import removeDomainPort
from utils import hasObjectDict
from utils import hasUsersPath
from utils import getFullDomain
from utils import removeIdEnding
from utils import urlPermitted
from utils import getNicknameFromActor
from utils import getDomainFromActor
from utils import locatePost
from utils import undoLikesCollectionEntry
from utils import hasGroupType
from utils import localActorUrl
from utils import loadJson
from utils import saveJson
from utils import removePostFromCache
from utils import getCachedPostFilename
from posts import sendSignedJson
from session import postJson
from webfinger import webfingerHandle
from auth import createBasicAuthHeader
from posts import getPersonBox


def noOfLikes(postJsonObject: {}) -> int:
    """Returns the number of likes ona  given post
    """
    obj = postJsonObject
    if hasObjectDict(postJsonObject):
        obj = postJsonObject['object']
    if not obj.get('likes'):
        return 0
    if not isinstance(obj['likes'], dict):
        return 0
    if not obj['likes'].get('items'):
        obj['likes']['items'] = []
        obj['likes']['totalItems'] = 0
    return len(obj['likes']['items'])


def likedByPerson(postJsonObject: {}, nickname: str, domain: str) -> bool:
    """Returns True if the given post is liked by the given person
    """
    if noOfLikes(postJsonObject) == 0:
        return False
    actorMatch = domain + '/users/' + nickname

    obj = postJsonObject
    if hasObjectDict(postJsonObject):
        obj = postJsonObject['object']

    for item in obj['likes']['items']:
        if item['actor'].endswith(actorMatch):
            return True
    return False


def _like(recentPostsCache: {},
          session, base_dir: str, federationList: [],
          nickname: str, domain: str, port: int,
          ccList: [], http_prefix: str,
          objectUrl: str, actorLiked: str,
          client_to_server: bool,
          send_threads: [], postLog: [],
          personCache: {}, cachedWebfingers: {},
          debug: bool, project_version: str,
          signingPrivateKeyPem: str) -> {}:
    """Creates a like
    actor is the person doing the liking
    'to' might be a specific person (actor) whose post was liked
    object is typically the url of the message which was liked
    """
    if not urlPermitted(objectUrl, federationList):
        return None

    fullDomain = getFullDomain(domain, port)

    newLikeJson = {
        "@context": "https://www.w3.org/ns/activitystreams",
        'type': 'Like',
        'actor': localActorUrl(http_prefix, nickname, fullDomain),
        'object': objectUrl
    }
    if ccList:
        if len(ccList) > 0:
            newLikeJson['cc'] = ccList

    # Extract the domain and nickname from a statuses link
    likedPostNickname = None
    likedPostDomain = None
    likedPostPort = None
    groupAccount = False
    if actorLiked:
        likedPostNickname = getNicknameFromActor(actorLiked)
        likedPostDomain, likedPostPort = getDomainFromActor(actorLiked)
        groupAccount = hasGroupType(base_dir, actorLiked, personCache)
    else:
        if hasUsersPath(objectUrl):
            likedPostNickname = getNicknameFromActor(objectUrl)
            likedPostDomain, likedPostPort = getDomainFromActor(objectUrl)
            if '/' + str(likedPostNickname) + '/' in objectUrl:
                actorLiked = \
                    objectUrl.split('/' + likedPostNickname + '/')[0] + \
                    '/' + likedPostNickname
                groupAccount = hasGroupType(base_dir, actorLiked, personCache)

    if likedPostNickname:
        postFilename = locatePost(base_dir, nickname, domain, objectUrl)
        if not postFilename:
            print('DEBUG: like base_dir: ' + base_dir)
            print('DEBUG: like nickname: ' + nickname)
            print('DEBUG: like domain: ' + domain)
            print('DEBUG: like objectUrl: ' + objectUrl)
            return None

        updateLikesCollection(recentPostsCache,
                              base_dir, postFilename, objectUrl,
                              newLikeJson['actor'],
                              nickname, domain, debug, None)

        sendSignedJson(newLikeJson, session, base_dir,
                       nickname, domain, port,
                       likedPostNickname, likedPostDomain, likedPostPort,
                       'https://www.w3.org/ns/activitystreams#Public',
                       http_prefix, True, client_to_server, federationList,
                       send_threads, postLog, cachedWebfingers, personCache,
                       debug, project_version, None, groupAccount,
                       signingPrivateKeyPem, 7367374)

    return newLikeJson


def likePost(recentPostsCache: {},
             session, base_dir: str, federationList: [],
             nickname: str, domain: str, port: int, http_prefix: str,
             likeNickname: str, likeDomain: str, likePort: int,
             ccList: [],
             likeStatusNumber: int, client_to_server: bool,
             send_threads: [], postLog: [],
             personCache: {}, cachedWebfingers: {},
             debug: bool, project_version: str,
             signingPrivateKeyPem: str) -> {}:
    """Likes a given status post. This is only used by unit tests
    """
    likeDomain = getFullDomain(likeDomain, likePort)

    actorLiked = localActorUrl(http_prefix, likeNickname, likeDomain)
    objectUrl = actorLiked + '/statuses/' + str(likeStatusNumber)

    return _like(recentPostsCache,
                 session, base_dir, federationList, nickname, domain, port,
                 ccList, http_prefix, objectUrl, actorLiked, client_to_server,
                 send_threads, postLog, personCache, cachedWebfingers,
                 debug, project_version, signingPrivateKeyPem)


def sendLikeViaServer(base_dir: str, session,
                      fromNickname: str, password: str,
                      fromDomain: str, fromPort: int,
                      http_prefix: str, likeUrl: str,
                      cachedWebfingers: {}, personCache: {},
                      debug: bool, project_version: str,
                      signingPrivateKeyPem: str) -> {}:
    """Creates a like via c2s
    """
    if not session:
        print('WARN: No session for sendLikeViaServer')
        return 6

    fromDomainFull = getFullDomain(fromDomain, fromPort)

    actor = localActorUrl(http_prefix, fromNickname, fromDomainFull)

    newLikeJson = {
        "@context": "https://www.w3.org/ns/activitystreams",
        'type': 'Like',
        'actor': actor,
        'object': likeUrl
    }

    handle = http_prefix + '://' + fromDomainFull + '/@' + fromNickname

    # lookup the inbox for the To handle
    wfRequest = webfingerHandle(session, handle, http_prefix,
                                cachedWebfingers,
                                fromDomain, project_version, debug, False,
                                signingPrivateKeyPem)
    if not wfRequest:
        if debug:
            print('DEBUG: like webfinger failed for ' + handle)
        return 1
    if not isinstance(wfRequest, dict):
        print('WARN: like webfinger for ' + handle +
              ' did not return a dict. ' + str(wfRequest))
        return 1

    postToBox = 'outbox'

    # get the actor inbox for the To handle
    originDomain = fromDomain
    (inboxUrl, pubKeyId, pubKey, fromPersonId, sharedInbox, avatarUrl,
     displayName, _) = getPersonBox(signingPrivateKeyPem,
                                    originDomain,
                                    base_dir, session, wfRequest,
                                    personCache,
                                    project_version, http_prefix,
                                    fromNickname, fromDomain,
                                    postToBox, 72873)

    if not inboxUrl:
        if debug:
            print('DEBUG: like no ' + postToBox + ' was found for ' + handle)
        return 3
    if not fromPersonId:
        if debug:
            print('DEBUG: like no actor was found for ' + handle)
        return 4

    authHeader = createBasicAuthHeader(fromNickname, password)

    headers = {
        'host': fromDomain,
        'Content-type': 'application/json',
        'Authorization': authHeader
    }
    postResult = postJson(http_prefix, fromDomainFull,
                          session, newLikeJson, [], inboxUrl,
                          headers, 3, True)
    if not postResult:
        if debug:
            print('WARN: POST like failed for c2s to ' + inboxUrl)
        return 5

    if debug:
        print('DEBUG: c2s POST like success')

    return newLikeJson


def sendUndoLikeViaServer(base_dir: str, session,
                          fromNickname: str, password: str,
                          fromDomain: str, fromPort: int,
                          http_prefix: str, likeUrl: str,
                          cachedWebfingers: {}, personCache: {},
                          debug: bool, project_version: str,
                          signingPrivateKeyPem: str) -> {}:
    """Undo a like via c2s
    """
    if not session:
        print('WARN: No session for sendUndoLikeViaServer')
        return 6

    fromDomainFull = getFullDomain(fromDomain, fromPort)

    actor = localActorUrl(http_prefix, fromNickname, fromDomainFull)

    newUndoLikeJson = {
        "@context": "https://www.w3.org/ns/activitystreams",
        'type': 'Undo',
        'actor': actor,
        'object': {
            'type': 'Like',
            'actor': actor,
            'object': likeUrl
        }
    }

    handle = http_prefix + '://' + fromDomainFull + '/@' + fromNickname

    # lookup the inbox for the To handle
    wfRequest = webfingerHandle(session, handle, http_prefix,
                                cachedWebfingers,
                                fromDomain, project_version, debug, False,
                                signingPrivateKeyPem)
    if not wfRequest:
        if debug:
            print('DEBUG: unlike webfinger failed for ' + handle)
        return 1
    if not isinstance(wfRequest, dict):
        if debug:
            print('WARN: unlike webfinger for ' + handle +
                  ' did not return a dict. ' + str(wfRequest))
        return 1

    postToBox = 'outbox'

    # get the actor inbox for the To handle
    originDomain = fromDomain
    (inboxUrl, pubKeyId, pubKey, fromPersonId, sharedInbox, avatarUrl,
     displayName, _) = getPersonBox(signingPrivateKeyPem,
                                    originDomain,
                                    base_dir, session, wfRequest,
                                    personCache, project_version,
                                    http_prefix, fromNickname,
                                    fromDomain, postToBox,
                                    72625)

    if not inboxUrl:
        if debug:
            print('DEBUG: unlike no ' + postToBox + ' was found for ' + handle)
        return 3
    if not fromPersonId:
        if debug:
            print('DEBUG: unlike no actor was found for ' + handle)
        return 4

    authHeader = createBasicAuthHeader(fromNickname, password)

    headers = {
        'host': fromDomain,
        'Content-type': 'application/json',
        'Authorization': authHeader
    }
    postResult = postJson(http_prefix, fromDomainFull,
                          session, newUndoLikeJson, [], inboxUrl,
                          headers, 3, True)
    if not postResult:
        if debug:
            print('WARN: POST unlike failed for c2s to ' + inboxUrl)
        return 5

    if debug:
        print('DEBUG: c2s POST unlike success')

    return newUndoLikeJson


def outboxLike(recentPostsCache: {},
               base_dir: str, http_prefix: str,
               nickname: str, domain: str, port: int,
               messageJson: {}, debug: bool) -> None:
    """ When a like request is received by the outbox from c2s
    """
    if not messageJson.get('type'):
        if debug:
            print('DEBUG: like - no type')
        return
    if not messageJson['type'] == 'Like':
        if debug:
            print('DEBUG: not a like')
        return
    if not hasObjectString(messageJson, debug):
        return
    if debug:
        print('DEBUG: c2s like request arrived in outbox')

    messageId = removeIdEnding(messageJson['object'])
    domain = removeDomainPort(domain)
    postFilename = locatePost(base_dir, nickname, domain, messageId)
    if not postFilename:
        if debug:
            print('DEBUG: c2s like post not found in inbox or outbox')
            print(messageId)
        return True
    updateLikesCollection(recentPostsCache,
                          base_dir, postFilename, messageId,
                          messageJson['actor'],
                          nickname, domain, debug, None)
    if debug:
        print('DEBUG: post liked via c2s - ' + postFilename)


def outboxUndoLike(recentPostsCache: {},
                   base_dir: str, http_prefix: str,
                   nickname: str, domain: str, port: int,
                   messageJson: {}, debug: bool) -> None:
    """ When an undo like request is received by the outbox from c2s
    """
    if not messageJson.get('type'):
        return
    if not messageJson['type'] == 'Undo':
        return
    if not hasObjectStringType(messageJson, debug):
        return
    if not messageJson['object']['type'] == 'Like':
        if debug:
            print('DEBUG: not a undo like')
        return
    if not hasObjectStringObject(messageJson, debug):
        return
    if debug:
        print('DEBUG: c2s undo like request arrived in outbox')

    messageId = removeIdEnding(messageJson['object']['object'])
    domain = removeDomainPort(domain)
    postFilename = locatePost(base_dir, nickname, domain, messageId)
    if not postFilename:
        if debug:
            print('DEBUG: c2s undo like post not found in inbox or outbox')
            print(messageId)
        return True
    undoLikesCollectionEntry(recentPostsCache, base_dir, postFilename,
                             messageId, messageJson['actor'],
                             domain, debug, None)
    if debug:
        print('DEBUG: post undo liked via c2s - ' + postFilename)


def updateLikesCollection(recentPostsCache: {},
                          base_dir: str, postFilename: str,
                          objectUrl: str, actor: str,
                          nickname: str, domain: str, debug: bool,
                          postJsonObject: {}) -> None:
    """Updates the likes collection within a post
    """
    if not postJsonObject:
        postJsonObject = loadJson(postFilename)
    if not postJsonObject:
        return

    # remove any cached version of this post so that the
    # like icon is changed
    removePostFromCache(postJsonObject, recentPostsCache)
    cachedPostFilename = getCachedPostFilename(base_dir, nickname,
                                               domain, postJsonObject)
    if cachedPostFilename:
        if os.path.isfile(cachedPostFilename):
            try:
                os.remove(cachedPostFilename)
            except OSError:
                print('EX: updateLikesCollection unable to delete ' +
                      cachedPostFilename)

    obj = postJsonObject
    if hasObjectDict(postJsonObject):
        obj = postJsonObject['object']

    if not objectUrl.endswith('/likes'):
        objectUrl = objectUrl + '/likes'
    if not obj.get('likes'):
        if debug:
            print('DEBUG: Adding initial like to ' + objectUrl)
        likesJson = {
            "@context": "https://www.w3.org/ns/activitystreams",
            'id': objectUrl,
            'type': 'Collection',
            "totalItems": 1,
            'items': [{
                'type': 'Like',
                'actor': actor
            }]
        }
        obj['likes'] = likesJson
    else:
        if not obj['likes'].get('items'):
            obj['likes']['items'] = []
        for likeItem in obj['likes']['items']:
            if likeItem.get('actor'):
                if likeItem['actor'] == actor:
                    # already liked
                    return
        newLike = {
            'type': 'Like',
            'actor': actor
        }
        obj['likes']['items'].append(newLike)
        itlen = len(obj['likes']['items'])
        obj['likes']['totalItems'] = itlen

    if debug:
        print('DEBUG: saving post with likes added')
        pprint(postJsonObject)
    saveJson(postJsonObject, postFilename)
