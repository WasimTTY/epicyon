__filename__ = "outbox.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.1.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@freedombone.net"
__status__ = "Production"

import os
from session import createSession
from auth import createPassword
from posts import outboxMessageCreateWrap
from posts import savePostToBox
from posts import sendToFollowersThread
from posts import sendToNamedAddresses
from utils import getDomainFromActor
from blocking import isBlockedDomain
from blocking import outboxBlock
from blocking import outboxUndoBlock
from media import replaceYouTube
from media import getMediaPath
from media import createMediaDirs
from inbox import inboxUpdateIndex
from announce import outboxAnnounce
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


def postMessageToOutbox(messageJson: {}, postToNickname: str,
                        server, baseDir: str, httpPrefix: str,
                        domain: str, domainFull: str,
                        onionDomain: str, i2pDomain: str,
                        port: int,
                        recentPostsCache: {}, followersThreads: [],
                        federationList: [], sendThreads: [],
                        postLog: [], cachedWebfingers: {},
                        personCache: {}, allowDeletion: bool,
                        useTor: bool, version: str, debug: bool) -> bool:
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
        testDomain, testPort = getDomainFromActor(messageJson['actor'])
        if testPort:
            if testPort != 80 and testPort != 443:
                testDomain = testDomain + ':' + str(testPort)
        if isBlockedDomain(baseDir, testDomain):
            if debug:
                print('DEBUG: domain is blocked: ' + messageJson['actor'])
            return False
        # replace youtube, so that google gets less tracking data
        replaceYouTube(messageJson)
        # https://www.w3.org/TR/activitypub/#create-activity-outbox
        messageJson['object']['attributedTo'] = messageJson['actor']
        if messageJson['object'].get('attachment'):
            attachmentIndex = 0
            attach = messageJson['object']['attachment'][attachmentIndex]
            if attach.get('mediaType'):
                fileExtension = 'png'
                mediaTypeStr = \
                    attach['mediaType']
                if mediaTypeStr.endswith('jpeg'):
                    fileExtension = 'jpg'
                elif mediaTypeStr.endswith('gif'):
                    fileExtension = 'gif'
                elif mediaTypeStr.endswith('webp'):
                    fileExtension = 'webp'
                elif mediaTypeStr.endswith('audio/mpeg'):
                    fileExtension = 'mp3'
                elif mediaTypeStr.endswith('ogg'):
                    fileExtension = 'ogg'
                elif mediaTypeStr.endswith('mp4'):
                    fileExtension = 'mp4'
                elif mediaTypeStr.endswith('webm'):
                    fileExtension = 'webm'
                elif mediaTypeStr.endswith('ogv'):
                    fileExtension = 'ogv'
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
                            'Delegate', 'Skill', 'Bookmark')
    if messageJson['type'] not in permittedOutboxTypes:
        if debug:
            print('DEBUG: POST to outbox - ' + messageJson['type'] +
                  ' is not a permitted activity type')
        return False
    if messageJson.get('id'):
        postId = \
            messageJson['id'].replace('/activity', '').replace('/undo', '')
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

        # if this is a blog post then save to its own box
        if messageJson['type'] == 'Create':
            if messageJson.get('object'):
                if isinstance(messageJson['object'], dict):
                    if messageJson['object'].get('type'):
                        if messageJson['object']['type'] == 'Article':
                            outboxName = 'tlblogs'

        savedFilename = \
            savePostToBox(baseDir,
                          httpPrefix,
                          postId,
                          postToNickname,
                          domainFull, messageJson, outboxName)
        if messageJson['type'] == 'Create' or \
           messageJson['type'] == 'Question' or \
           messageJson['type'] == 'Note' or \
           messageJson['type'] == 'Article' or \
           messageJson['type'] == 'Patch' or \
           messageJson['type'] == 'Announce':
            indexes = [outboxName, "inbox"]
            for boxNameIndex in indexes:
                if boxNameIndex == 'inbox' and outboxName == 'tlblogs':
                    continue
                selfActor = \
                    httpPrefix + '://' + domainFull + \
                    '/users/' + postToNickname
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
        if debug:
            print('DEBUG: creating new session for c2s')
        server.session = createSession(useTor)
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
                 allowDeletion)

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
