__filename__ = "outbox.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@freedombone.net"
__status__ = "Production"

import os
from shutil import copyfile
from session import createSession
from auth import createPassword
from posts import isImageMedia
from posts import outboxMessageCreateWrap
from posts import savePostToBox
from posts import sendToFollowersThread
from posts import sendToNamedAddresses
from utils import getLocalNetworkAddresses
from utils import getFullDomain
from utils import removeIdEnding
from utils import getDomainFromActor
from utils import dangerousMarkup
from utils import isFeaturedWriter
from utils import loadJson
from utils import saveJson
from blocking import isBlockedDomain
from blocking import outboxBlock
from blocking import outboxUndoBlock
from blocking import outboxMute
from blocking import outboxUndoMute
from media import replaceYouTube
from media import getMediaPath
from media import createMediaDirs
from inbox import inboxUpdateIndex
from announce import outboxAnnounce
from announce import outboxUndoAnnounce
from follow import outboxUndoFollow
from roles import outboxDelegate
from skills import outboxSkills
from availability import outboxAvailability
from like import outboxLike
from like import outboxUndoLike
from bookmarks import outboxBookmark
from bookmarks import outboxUndoBookmark
from delete import outboxDelete
from shares import outboxShareUpload
from shares import outboxUndoShareUpload


def _outboxPersonReceiveUpdate(recentPostsCache: {},
                               baseDir: str, httpPrefix: str,
                               nickname: str, domain: str, port: int,
                               messageJson: {}, debug: bool) -> None:
    """ Receive an actor update from c2s
    For example, setting the PGP key from the desktop client
    """
    # these attachments are updatable via c2s
    updatableAttachments = ('PGP', 'OpenPGP', 'Email')

    if not messageJson.get('type'):
        return
    print("messageJson['type'] " + messageJson['type'])
    if messageJson['type'] != 'Update':
        return
    if not messageJson.get('object'):
        return
    if not isinstance(messageJson['object'], dict):
        if debug:
            print('DEBUG: c2s actor update object is not dict')
        return
    if not messageJson['object'].get('type'):
        if debug:
            print('DEBUG: c2s actor update - no type')
        return
    if messageJson['object']['type'] != 'Person':
        if debug:
            print('DEBUG: not a c2s actor update')
        return
    if not messageJson.get('to'):
        if debug:
            print('DEBUG: c2s actor update has no "to" field')
        return
    if not messageJson.get('actor'):
        if debug:
            print('DEBUG: c2s actor update has no actor field')
        return
    if not messageJson.get('id'):
        if debug:
            print('DEBUG: c2s actor update has no id field')
        return
    actor = \
        httpPrefix + '://' + getFullDomain(domain, port) + '/users/' + nickname
    if len(messageJson['to']) != 1:
        if debug:
            print('DEBUG: c2s actor update - to does not contain one actor ' +
                  messageJson['to'])
        return
    if messageJson['to'][0] != actor:
        if debug:
            print('DEBUG: c2s actor update - to does not contain actor ' +
                  messageJson['to'] + ' ' + actor)
        return
    if not messageJson['id'].startswith(actor + '#updates/'):
        if debug:
            print('DEBUG: c2s actor update - unexpected id ' +
                  messageJson['id'])
        return
    updatedActorJson = messageJson['object']
    # load actor from file
    actorFilename = baseDir + '/accounts/' + nickname + '@' + domain + '.json'
    if not os.path.isfile(actorFilename):
        print('actorFilename not found: ' + actorFilename)
        return
    actorJson = loadJson(actorFilename)
    if not actorJson:
        return
    actorChanged = False
    # update fields within actor
    if 'attachment' in updatedActorJson:
        for newPropertyValue in updatedActorJson['attachment']:
            if not newPropertyValue.get('name'):
                continue
            if newPropertyValue['name'] not in updatableAttachments:
                continue
            if not newPropertyValue.get('type'):
                continue
            if not newPropertyValue.get('value'):
                continue
            if newPropertyValue['type'] != 'PropertyValue':
                continue
            if 'attachment' in actorJson:
                found = False
                for attachIdx in range(len(actorJson['attachment'])):
                    if actorJson['attachment'][attachIdx]['type'] != \
                       'PropertyValue':
                        continue
                    if actorJson['attachment'][attachIdx]['name'] != \
                       newPropertyValue['name']:
                        continue
                    else:
                        if actorJson['attachment'][attachIdx]['value'] != \
                           newPropertyValue['value']:
                            actorJson['attachment'][attachIdx]['value'] = \
                                newPropertyValue['value']
                            actorChanged = True
                        found = True
                        break
                if not found:
                    actorJson['attachment'].append({
                        "name": newPropertyValue['name'],
                        "type": "PropertyValue",
                        "value": newPropertyValue['value']
                    })
                    actorChanged = True
    # save actor to file
    if actorChanged:
        saveJson(actorJson, actorFilename)
        if debug:
            print('actor saved: ' + actorFilename)
    if debug:
        print('New attachment: ' + str(actorJson['attachment']))
    messageJson['object'] = actorJson
    if debug:
        print('DEBUG: actor update via c2s - ' + nickname + '@' + domain)


def postMessageToOutbox(session, translate: {},
                        messageJson: {}, postToNickname: str,
                        server, baseDir: str, httpPrefix: str,
                        domain: str, domainFull: str,
                        onionDomain: str, i2pDomain: str, port: int,
                        recentPostsCache: {}, followersThreads: [],
                        federationList: [], sendThreads: [],
                        postLog: [], cachedWebfingers: {},
                        personCache: {}, allowDeletion: bool,
                        proxyType: str, version: str, debug: bool,
                        YTReplacementDomain: str,
                        showPublishedDateOnly: bool,
                        allowLocalNetworkAccess: bool) -> bool:
    """post is received by the outbox
    Client to server message post
    https://www.w3.org/TR/activitypub/#client-to-server-outbox-delivery
    """
    if not messageJson.get('type'):
        if debug:
            print('DEBUG: POST to outbox has no "type" parameter')
        return False
    if not messageJson.get('object') and messageJson.get('content'):
        if messageJson['type'] != 'Create':
            # https://www.w3.org/TR/activitypub/#object-without-create
            if debug:
                print('DEBUG: POST to outbox - adding Create wrapper')
            messageJson = \
                outboxMessageCreateWrap(httpPrefix,
                                        postToNickname,
                                        domain, port,
                                        messageJson)

    # check that the outgoing post doesn't contain any markup
    # which can be used to implement exploits
    if messageJson.get('object'):
        if isinstance(messageJson['object'], dict):
            if messageJson['object'].get('content'):
                if dangerousMarkup(messageJson['object']['content'],
                                   allowLocalNetworkAccess):
                    print('POST to outbox contains dangerous markup: ' +
                          str(messageJson))
                    return False

    if messageJson['type'] == 'Create':
        if not (messageJson.get('id') and
                messageJson.get('type') and
                messageJson.get('actor') and
                messageJson.get('object') and
                messageJson.get('to')):
            if not messageJson.get('id'):
                if debug:
                    print('DEBUG: POST to outbox - ' +
                          'Create does not have the id parameter ' +
                          str(messageJson))
            elif not messageJson.get('id'):
                if debug:
                    print('DEBUG: POST to outbox - ' +
                          'Create does not have the type parameter ' +
                          str(messageJson))
            elif not messageJson.get('id'):
                if debug:
                    print('DEBUG: POST to outbox - ' +
                          'Create does not have the actor parameter ' +
                          str(messageJson))
            elif not messageJson.get('id'):
                if debug:
                    print('DEBUG: POST to outbox - ' +
                          'Create does not have the object parameter ' +
                          str(messageJson))
            else:
                if debug:
                    print('DEBUG: POST to outbox - ' +
                          'Create does not have the "to" parameter ' +
                          str(messageJson))
            return False

        # actor should be a string
        if not isinstance(messageJson['actor'], str):
            return False

        # actor should look like a url
        if '://' not in messageJson['actor'] or \
           '.' not in messageJson['actor']:
            return False

        # sent by an actor on a local network address?
        if not allowLocalNetworkAccess:
            localNetworkPatternList = getLocalNetworkAddresses()
            for localNetworkPattern in localNetworkPatternList:
                if localNetworkPattern in messageJson['actor']:
                    return False

        testDomain, testPort = getDomainFromActor(messageJson['actor'])
        testDomain = getFullDomain(testDomain, testPort)
        if isBlockedDomain(baseDir, testDomain):
            if debug:
                print('DEBUG: domain is blocked: ' + messageJson['actor'])
            return False
        # replace youtube, so that google gets less tracking data
        replaceYouTube(messageJson, YTReplacementDomain)
        # https://www.w3.org/TR/activitypub/#create-activity-outbox
        messageJson['object']['attributedTo'] = messageJson['actor']
        if messageJson['object'].get('attachment'):
            attachmentIndex = 0
            attach = messageJson['object']['attachment'][attachmentIndex]
            if attach.get('mediaType'):
                fileExtension = 'png'
                mediaTypeStr = \
                    attach['mediaType']

                extensions = {
                    "jpeg": "jpg",
                    "gif": "gif",
                    "svg": "svg",
                    "webp": "webp",
                    "avif": "avif",
                    "audio/mpeg": "mp3",
                    "ogg": "ogg",
                    "mp4": "mp4",
                    "webm": "webm",
                    "ogv": "ogv"
                }
                for matchExt, ext in extensions.items():
                    if mediaTypeStr.endswith(matchExt):
                        fileExtension = ext
                        break

                mediaDir = \
                    baseDir + '/accounts/' + \
                    postToNickname + '@' + domain
                uploadMediaFilename = mediaDir + '/upload.' + fileExtension
                if not os.path.isfile(uploadMediaFilename):
                    del messageJson['object']['attachment']
                else:
                    # generate a path for the uploaded image
                    mPath = getMediaPath()
                    mediaPath = mPath + '/' + \
                        createPassword(32) + '.' + fileExtension
                    createMediaDirs(baseDir, mPath)
                    mediaFilename = baseDir + '/' + mediaPath
                    # move the uploaded image to its new path
                    os.rename(uploadMediaFilename, mediaFilename)
                    # change the url of the attachment
                    attach['url'] = \
                        httpPrefix + '://' + domainFull + '/' + mediaPath

    permittedOutboxTypes = ('Create', 'Announce', 'Like', 'Follow', 'Undo',
                            'Update', 'Add', 'Remove', 'Block', 'Delete',
                            'Delegate', 'Skill', 'Add', 'Remove', 'Event',
                            'Ignore')
    if messageJson['type'] not in permittedOutboxTypes:
        if debug:
            print('DEBUG: POST to outbox - ' + messageJson['type'] +
                  ' is not a permitted activity type')
        return False
    if messageJson.get('id'):
        postId = removeIdEnding(messageJson['id'])
        if debug:
            print('DEBUG: id attribute exists within POST to outbox')
    else:
        if debug:
            print('DEBUG: No id attribute within POST to outbox')
        postId = None
    if debug:
        print('DEBUG: savePostToBox')
    if messageJson['type'] != 'Upgrade':
        outboxName = 'outbox'

        # if this is a blog post or an event then save to its own box
        if messageJson['type'] == 'Create':
            if messageJson.get('object'):
                if isinstance(messageJson['object'], dict):
                    if messageJson['object'].get('type'):
                        if messageJson['object']['type'] == 'Article':
                            outboxName = 'tlblogs'
                        elif messageJson['object']['type'] == 'Event':
                            outboxName = 'tlevents'

        savedFilename = \
            savePostToBox(baseDir,
                          httpPrefix,
                          postId,
                          postToNickname, domainFull,
                          messageJson, outboxName)
        if not savedFilename:
            print('WARN: post not saved to outbox ' + outboxName)
            return False

        # save all instance blogs to the news actor
        if postToNickname != 'news' and outboxName == 'tlblogs':
            if '/' in savedFilename:
                if isFeaturedWriter(baseDir, postToNickname, domain):
                    savedPostId = savedFilename.split('/')[-1]
                    blogsDir = \
                        baseDir + '/accounts/news@' + domain + '/tlblogs'
                    if not os.path.isdir(blogsDir):
                        os.mkdir(blogsDir)
                    copyfile(savedFilename, blogsDir + '/' + savedPostId)
                    inboxUpdateIndex('tlblogs', baseDir,
                                     'news@' + domain,
                                     savedFilename, debug)

                # clear the citations file if it exists
                citationsFilename = \
                    baseDir + '/accounts/' + \
                    postToNickname + '@' + domain + '/.citations.txt'
                if os.path.isfile(citationsFilename):
                    os.remove(citationsFilename)

        if messageJson['type'] == 'Create' or \
           messageJson['type'] == 'Question' or \
           messageJson['type'] == 'Note' or \
           messageJson['type'] == 'EncryptedMessage' or \
           messageJson['type'] == 'Article' or \
           messageJson['type'] == 'Event' or \
           messageJson['type'] == 'Patch' or \
           messageJson['type'] == 'Announce':
            indexes = [outboxName, "inbox"]
            selfActor = \
                httpPrefix + '://' + domainFull + '/users/' + postToNickname
            for boxNameIndex in indexes:
                if not boxNameIndex:
                    continue

                # should this also go to the media timeline?
                if boxNameIndex == 'inbox':
                    if isImageMedia(session, baseDir, httpPrefix,
                                    postToNickname, domain,
                                    messageJson,
                                    translate, YTReplacementDomain,
                                    allowLocalNetworkAccess,
                                    recentPostsCache, debug):
                        inboxUpdateIndex('tlmedia', baseDir,
                                         postToNickname + '@' + domain,
                                         savedFilename, debug)

                if boxNameIndex == 'inbox' and outboxName == 'tlblogs':
                    continue
                # avoid duplicates of the message if already going
                # back to the inbox of the same account
                if selfActor not in messageJson['to']:
                    # show sent post within the inbox,
                    # as is the typical convention
                    inboxUpdateIndex(boxNameIndex, baseDir,
                                     postToNickname + '@' + domain,
                                     savedFilename, debug)
    if outboxAnnounce(recentPostsCache,
                      baseDir, messageJson, debug):
        if debug:
            print('DEBUG: Updated announcements (shares) collection ' +
                  'for the post associated with the Announce activity')
    if not server.session:
        print('DEBUG: creating new session for c2s')
        server.session = createSession(proxyType)
        if not server.session:
            print('ERROR: Failed to create session for postMessageToOutbox')
            return False
    if debug:
        print('DEBUG: sending c2s post to followers')
    # remove inactive threads
    inactiveFollowerThreads = []
    for th in followersThreads:
        if not th.is_alive():
            inactiveFollowerThreads.append(th)
    for th in inactiveFollowerThreads:
        followersThreads.remove(th)
    if debug:
        print('DEBUG: ' + str(len(followersThreads)) +
              ' followers threads active')
    # retain up to 200 threads
    if len(followersThreads) > 200:
        # kill the thread if it is still alive
        if followersThreads[0].is_alive():
            followersThreads[0].kill()
        # remove it from the list
        followersThreads.pop(0)
    # create a thread to send the post to followers
    followersThread = \
        sendToFollowersThread(server.session,
                              baseDir,
                              postToNickname,
                              domain, onionDomain, i2pDomain,
                              port, httpPrefix,
                              federationList,
                              sendThreads,
                              postLog,
                              cachedWebfingers,
                              personCache,
                              messageJson, debug,
                              version)
    followersThreads.append(followersThread)

    if debug:
        print('DEBUG: handle any unfollow requests')
    outboxUndoFollow(baseDir, messageJson, debug)

    if debug:
        print('DEBUG: handle delegation requests')
    outboxDelegate(baseDir, postToNickname, messageJson, debug)

    if debug:
        print('DEBUG: handle skills changes requests')
    outboxSkills(baseDir, postToNickname, messageJson, debug)

    if debug:
        print('DEBUG: handle availability changes requests')
    outboxAvailability(baseDir, postToNickname, messageJson, debug)

    if debug:
        print('DEBUG: handle any like requests')
    outboxLike(recentPostsCache,
               baseDir, httpPrefix,
               postToNickname, domain, port,
               messageJson, debug)
    if debug:
        print('DEBUG: handle any undo like requests')
    outboxUndoLike(recentPostsCache,
                   baseDir, httpPrefix,
                   postToNickname, domain, port,
                   messageJson, debug)
    if debug:
        print('DEBUG: handle any undo announce requests')
    outboxUndoAnnounce(recentPostsCache,
                       baseDir, httpPrefix,
                       postToNickname, domain, port,
                       messageJson, debug)

    if debug:
        print('DEBUG: handle any bookmark requests')
    outboxBookmark(recentPostsCache,
                   baseDir, httpPrefix,
                   postToNickname, domain, port,
                   messageJson, debug)
    if debug:
        print('DEBUG: handle any undo bookmark requests')
    outboxUndoBookmark(recentPostsCache,
                       baseDir, httpPrefix,
                       postToNickname, domain, port,
                       messageJson, debug)

    if debug:
        print('DEBUG: handle delete requests')
    outboxDelete(baseDir, httpPrefix,
                 postToNickname, domain,
                 messageJson, debug,
                 allowDeletion,
                 recentPostsCache)

    if debug:
        print('DEBUG: handle block requests')
    outboxBlock(baseDir, httpPrefix,
                postToNickname, domain,
                port,
                messageJson, debug)

    if debug:
        print('DEBUG: handle undo block requests')
    outboxUndoBlock(baseDir, httpPrefix,
                    postToNickname, domain,
                    port, messageJson, debug)

    if debug:
        print('DEBUG: handle mute requests')
    outboxMute(baseDir, httpPrefix,
               postToNickname, domain,
               port,
               messageJson, debug,
               recentPostsCache)

    if debug:
        print('DEBUG: handle undo mute requests')
    outboxUndoMute(baseDir, httpPrefix,
                   postToNickname, domain,
                   port,
                   messageJson, debug,
                   recentPostsCache)

    if debug:
        print('DEBUG: handle share uploads')
    outboxShareUpload(baseDir, httpPrefix,
                      postToNickname, domain,
                      port, messageJson, debug)

    if debug:
        print('DEBUG: handle undo share uploads')
    outboxUndoShareUpload(baseDir, httpPrefix,
                          postToNickname, domain,
                          port, messageJson, debug)

    if debug:
        print('DEBUG: handle actor updates from c2s')
    _outboxPersonReceiveUpdate(recentPostsCache,
                               baseDir, httpPrefix,
                               postToNickname, domain, port,
                               messageJson, debug)

    if debug:
        print('DEBUG: sending c2s post to named addresses')
        if messageJson.get('to'):
            print('c2s sender: ' +
                  postToNickname + '@' + domain + ':' + str(port) +
                  ' recipient: ' + str(messageJson['to']))
        else:
            print('c2s sender: ' +
                  postToNickname + '@' + domain + ':' + str(port))
    sendToNamedAddresses(server.session, baseDir,
                         postToNickname,
                         domain, onionDomain, i2pDomain, port,
                         httpPrefix,
                         federationList,
                         sendThreads,
                         postLog,
                         cachedWebfingers,
                         personCache,
                         messageJson, debug,
                         version)
    return True
