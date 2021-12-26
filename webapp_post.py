__filename__ = "webapp_post.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Web Interface"

import os
import time
import urllib.parse
from dateutil.parser import parse
from auth import createPassword
from git import isGitPatch
from datetime import datetime
from cache import getPersonFromCache
from bookmarks import bookmarkedByPerson
from like import likedByPerson
from like import noOfLikes
from follow import isFollowingActor
from posts import postIsMuted
from posts import getPersonBox
from posts import downloadAnnounce
from posts import populateRepliesJson
from utils import removeHashFromPostId
from utils import removeHtml
from utils import get_actor_languages_list
from utils import getBaseContentFromPost
from utils import get_content_from_post
from utils import has_object_dict
from utils import updateAnnounceCollection
from utils import isPGPEncrypted
from utils import isDM
from utils import rejectPostId
from utils import isRecentPost
from utils import getConfigParam
from utils import getFullDomain
from utils import isEditor
from utils import locatePost
from utils import loadJson
from utils import getCachedPostDirectory
from utils import getCachedPostFilename
from utils import getProtocolPrefixes
from utils import isNewsPost
from utils import isBlogPost
from utils import getDisplayName
from utils import isPublicPost
from utils import updateRecentPostsCache
from utils import removeIdEnding
from utils import getNicknameFromActor
from utils import getDomainFromActor
from utils import acctDir
from utils import local_actor_url
from content import limitRepeatedWords
from content import replaceEmojiFromTags
from content import htmlReplaceQuoteMarks
from content import htmlReplaceEmailQuote
from content import removeTextFormatting
from content import removeLongWords
from content import getMentionsFromHtml
from content import switchWords
from person import isPersonSnoozed
from person import getPersonAvatarUrl
from announce import announcedByPerson
from webapp_utils import getBannerFile
from webapp_utils import getAvatarImageUrl
from webapp_utils import updateAvatarImageCache
from webapp_utils import loadIndividualPostAsHtmlFromCache
from webapp_utils import addEmojiToDisplayName
from webapp_utils import postContainsPublic
from webapp_utils import getContentWarningButton
from webapp_utils import getPostAttachmentsAsHtml
from webapp_utils import htmlHeaderWithExternalStyle
from webapp_utils import htmlFooter
from webapp_utils import getBrokenLinkSubstitute
from webapp_media import addEmbeddedElements
from webapp_question import insertQuestion
from devices import E2EEdecryptMessageFromDevice
from webfinger import webfingerHandle
from speaker import updateSpeaker
from languages import autoTranslatePost
from blocking import isBlocked
from blocking import addCWfromLists
from reaction import htmlEmojiReactions


def _htmlPostMetadataOpenGraph(domain: str, post_json_object: {}) -> str:
    """Returns html OpenGraph metadata for a post
    """
    metadata = \
        "    <meta content=\"" + domain + "\" property=\"og:site_name\" />\n"
    metadata += \
        "    <meta content=\"article\" property=\"og:type\" />\n"
    objJson = post_json_object
    if has_object_dict(post_json_object):
        objJson = post_json_object['object']
    if objJson.get('attributedTo'):
        if isinstance(objJson['attributedTo'], str):
            attrib = objJson['attributedTo']
            actorNick = getNicknameFromActor(attrib)
            actorDomain, _ = getDomainFromActor(attrib)
            actorHandle = actorNick + '@' + actorDomain
            metadata += \
                "    <meta content=\"@" + actorHandle + \
                "\" property=\"og:title\" />\n"
    if objJson.get('url'):
        metadata += \
            "    <meta content=\"" + objJson['url'] + \
            "\" property=\"og:url\" />\n"
    if objJson.get('published'):
        metadata += \
            "    <meta content=\"" + objJson['published'] + \
            "\" property=\"og:published_time\" />\n"
    if not objJson.get('attachment') or objJson.get('sensitive'):
        if objJson.get('content') and not objJson.get('sensitive'):
            description = removeHtml(objJson['content'])
            metadata += \
                "    <meta content=\"" + description + \
                "\" name=\"description\">\n"
            metadata += \
                "    <meta content=\"" + description + \
                "\" name=\"og:description\">\n"
        return metadata

    # metadata for attachment
    for attachJson in objJson['attachment']:
        if not isinstance(attachJson, dict):
            continue
        if not attachJson.get('mediaType'):
            continue
        if not attachJson.get('url'):
            continue
        if not attachJson.get('name'):
            continue
        description = None
        if attachJson['mediaType'].startswith('image/'):
            description = 'Attached: 1 image'
        elif attachJson['mediaType'].startswith('video/'):
            description = 'Attached: 1 video'
        elif attachJson['mediaType'].startswith('audio/'):
            description = 'Attached: 1 audio'
        if description:
            if objJson.get('content') and not objJson.get('sensitive'):
                description += '\n\n' + removeHtml(objJson['content'])
            metadata += \
                "    <meta content=\"" + description + \
                "\" name=\"description\">\n"
            metadata += \
                "    <meta content=\"" + description + \
                "\" name=\"og:description\">\n"
            metadata += \
                "    <meta content=\"" + attachJson['url'] + \
                "\" property=\"og:image\" />\n"
            metadata += \
                "    <meta content=\"" + attachJson['mediaType'] + \
                "\" property=\"og:image:type\" />\n"
            if attachJson.get('width'):
                metadata += \
                    "    <meta content=\"" + str(attachJson['width']) + \
                    "\" property=\"og:image:width\" />\n"
            if attachJson.get('height'):
                metadata += \
                    "    <meta content=\"" + str(attachJson['height']) + \
                    "\" property=\"og:image:height\" />\n"
            metadata += \
                "    <meta content=\"" + attachJson['name'] + \
                "\" property=\"og:image:alt\" />\n"
            if attachJson['mediaType'].startswith('image/'):
                metadata += \
                    "    <meta content=\"summary_large_image\" " + \
                    "property=\"twitter:card\" />\n"
    return metadata


def _logPostTiming(enableTimingLog: bool, postStartTime, debugId: str) -> None:
    """Create a log of timings for performance tuning
    """
    if not enableTimingLog:
        return
    timeDiff = int((time.time() - postStartTime) * 1000)
    if timeDiff > 100:
        print('TIMING INDIV ' + debugId + ' = ' + str(timeDiff))


def prepareHtmlPostNickname(nickname: str, postHtml: str) -> str:
    """html posts stored in memory are for all accounts on the instance
    and they're indexed by id. However, some incoming posts may be
    destined for multiple accounts (followers). This creates a problem
    where the icon links whose urls begin with href="/users/nickname?
    need to be changed for different nicknames to display correctly
    within their timelines.
    This function changes the nicknames for the icon links.
    """
    # replace the nickname
    usersStr = ' href="/users/'
    if usersStr not in postHtml:
        return postHtml

    userFound = True
    postStr = postHtml
    newPostStr = ''
    while userFound:
        if usersStr not in postStr:
            newPostStr += postStr
            break

        # the next part, after href="/users/nickname?
        nextStr = postStr.split(usersStr, 1)[1]
        if '?' in nextStr:
            nextStr = nextStr.split('?', 1)[1]
        else:
            newPostStr += postStr
            break

        # append the previous text to the result
        newPostStr += postStr.split(usersStr)[0]
        newPostStr += usersStr + nickname + '?'

        # post is now the next part
        postStr = nextStr
    return newPostStr


def preparePostFromHtmlCache(nickname: str, postHtml: str, boxName: str,
                             pageNumber: int) -> str:
    """Sets the page number on a cached html post
    """
    # if on the bookmarks timeline then remain there
    if boxName == 'tlbookmarks' or boxName == 'bookmarks':
        postHtml = postHtml.replace('?tl=inbox', '?tl=tlbookmarks')
        if '?page=' in postHtml:
            pageNumberStr = postHtml.split('?page=')[1]
            if '?' in pageNumberStr:
                pageNumberStr = pageNumberStr.split('?')[0]
            postHtml = postHtml.replace('?page=' + pageNumberStr, '?page=-999')

    withPageNumber = postHtml.replace(';-999;', ';' + str(pageNumber) + ';')
    withPageNumber = withPageNumber.replace('?page=-999',
                                            '?page=' + str(pageNumber))
    return prepareHtmlPostNickname(nickname, withPageNumber)


def _saveIndividualPostAsHtmlToCache(base_dir: str,
                                     nickname: str, domain: str,
                                     post_json_object: {},
                                     postHtml: str) -> bool:
    """Saves the given html for a post to a cache file
    This is so that it can be quickly reloaded on subsequent
    refresh of the timeline
    """
    htmlPostCacheDir = \
        getCachedPostDirectory(base_dir, nickname, domain)
    cachedPostFilename = \
        getCachedPostFilename(base_dir, nickname, domain, post_json_object)

    # create the cache directory if needed
    if not os.path.isdir(htmlPostCacheDir):
        os.mkdir(htmlPostCacheDir)

    try:
        with open(cachedPostFilename, 'w+') as fp:
            fp.write(postHtml)
            return True
    except Exception as ex:
        print('ERROR: saving post to cache, ' + str(ex))
    return False


def _getPostFromRecentCache(session,
                            base_dir: str,
                            http_prefix: str,
                            nickname: str, domain: str,
                            post_json_object: {},
                            postActor: str,
                            person_cache: {},
                            allowDownloads: bool,
                            showPublicOnly: bool,
                            storeToCache: bool,
                            boxName: str,
                            avatarUrl: str,
                            enableTimingLog: bool,
                            postStartTime,
                            pageNumber: int,
                            recentPostsCache: {},
                            max_recent_posts: int,
                            signing_priv_key_pem: str) -> str:
    """Attempts to get the html post from the recent posts cache in memory
    """
    if boxName == 'tlmedia':
        return None

    if showPublicOnly:
        return None

    tryCache = False
    bmTimeline = boxName == 'bookmarks' or boxName == 'tlbookmarks'
    if storeToCache or bmTimeline:
        tryCache = True

    if not tryCache:
        return None

    # update avatar if needed
    if not avatarUrl:
        avatarUrl = \
            getPersonAvatarUrl(base_dir, postActor, person_cache,
                               allowDownloads)

        _logPostTiming(enableTimingLog, postStartTime, '2.1')

    updateAvatarImageCache(signing_priv_key_pem,
                           session, base_dir, http_prefix,
                           postActor, avatarUrl, person_cache,
                           allowDownloads)

    _logPostTiming(enableTimingLog, postStartTime, '2.2')

    postHtml = \
        loadIndividualPostAsHtmlFromCache(base_dir, nickname, domain,
                                          post_json_object)
    if not postHtml:
        return None

    postHtml = \
        preparePostFromHtmlCache(nickname, postHtml, boxName, pageNumber)
    updateRecentPostsCache(recentPostsCache, max_recent_posts,
                           post_json_object, postHtml)
    _logPostTiming(enableTimingLog, postStartTime, '3')
    return postHtml


def _getAvatarImageHtml(showAvatarOptions: bool,
                        nickname: str, domain_full: str,
                        avatarUrl: str, postActor: str,
                        translate: {}, avatarPosition: str,
                        pageNumber: int, messageIdStr: str) -> str:
    """Get html for the avatar image
    """
    avatarLink = ''
    if '/users/news/' not in avatarUrl:
        avatarLink = '        <a class="imageAnchor" href="' + postActor + '">'
        showProfileStr = 'Show profile'
        if translate.get(showProfileStr):
            showProfileStr = translate[showProfileStr]
        avatarLink += \
            '<img loading="lazy" src="' + avatarUrl + '" title="' + \
            showProfileStr + '" alt=" "' + avatarPosition + \
            getBrokenLinkSubstitute() + '/></a>\n'

    if showAvatarOptions and \
       domain_full + '/users/' + nickname not in postActor:
        showOptionsForThisPersonStr = 'Show options for this person'
        if translate.get(showOptionsForThisPersonStr):
            showOptionsForThisPersonStr = \
                translate[showOptionsForThisPersonStr]
        if '/users/news/' not in avatarUrl:
            avatarLink = \
                '        <a class="imageAnchor" href="/users/' + \
                nickname + '?options=' + postActor + \
                ';' + str(pageNumber) + ';' + avatarUrl + messageIdStr + '">\n'
            avatarLink += \
                '        <img loading="lazy" title="' + \
                showOptionsForThisPersonStr + '" ' + \
                'alt="👤 ' + \
                showOptionsForThisPersonStr + '" ' + \
                'src="' + avatarUrl + '" ' + avatarPosition + \
                getBrokenLinkSubstitute() + '/></a>\n'
        else:
            # don't link to the person options for the news account
            avatarLink += \
                '        <img loading="lazy" title="' + \
                showOptionsForThisPersonStr + '" ' + \
                'alt="👤 ' + \
                showOptionsForThisPersonStr + '" ' + \
                'src="' + avatarUrl + '" ' + avatarPosition + \
                getBrokenLinkSubstitute() + '/>\n'
    return avatarLink.strip()


def _getReplyIconHtml(base_dir: str, nickname: str, domain: str,
                      isPublicRepeat: bool,
                      showIcons: bool, commentsEnabled: bool,
                      post_json_object: {}, pageNumberParam: str,
                      translate: {}, system_language: str,
                      conversationId: str) -> str:
    """Returns html for the reply icon/button
    """
    replyStr = ''
    if not (showIcons and commentsEnabled):
        return replyStr

    # reply is permitted - create reply icon
    replyToLink = removeHashFromPostId(post_json_object['object']['id'])
    replyToLink = removeIdEnding(replyToLink)

    # see Mike MacGirvin's replyTo suggestion
    if post_json_object['object'].get('replyTo'):
        # check that the alternative replyTo url is not blocked
        blockNickname = \
            getNicknameFromActor(post_json_object['object']['replyTo'])
        blockDomain, _ = \
            getDomainFromActor(post_json_object['object']['replyTo'])
        if not isBlocked(base_dir, nickname, domain,
                         blockNickname, blockDomain, {}):
            replyToLink = post_json_object['object']['replyTo']

    if post_json_object['object'].get('attributedTo'):
        if isinstance(post_json_object['object']['attributedTo'], str):
            replyToLink += \
                '?mention=' + post_json_object['object']['attributedTo']
    content = getBaseContentFromPost(post_json_object, system_language)
    if content:
        mentionedActors = getMentionsFromHtml(content)
        if mentionedActors:
            for actorUrl in mentionedActors:
                if '?mention=' + actorUrl not in replyToLink:
                    replyToLink += '?mention=' + actorUrl
                    if len(replyToLink) > 500:
                        break
    replyToLink += pageNumberParam

    replyStr = ''
    replyToThisPostStr = 'Reply to this post'
    if translate.get(replyToThisPostStr):
        replyToThisPostStr = translate[replyToThisPostStr]
    conversationStr = ''
    if conversationId:
        conversationStr = '?conversationId=' + conversationId
    if isPublicRepeat:
        replyStr += \
            '        <a class="imageAnchor" href="/users/' + \
            nickname + '?replyto=' + replyToLink + \
            '?actor=' + post_json_object['actor'] + \
            conversationStr + \
            '" title="' + replyToThisPostStr + '">\n'
    else:
        if isDM(post_json_object):
            replyStr += \
                '        ' + \
                '<a class="imageAnchor" href="/users/' + nickname + \
                '?replydm=' + replyToLink + \
                '?actor=' + post_json_object['actor'] + \
                conversationStr + \
                '" title="' + replyToThisPostStr + '">\n'
        else:
            replyStr += \
                '        ' + \
                '<a class="imageAnchor" href="/users/' + nickname + \
                '?replyfollowers=' + replyToLink + \
                '?actor=' + post_json_object['actor'] + \
                conversationStr + \
                '" title="' + replyToThisPostStr + '">\n'

    replyStr += \
        '        ' + \
        '<img loading="lazy" title="' + \
        replyToThisPostStr + '" alt="' + replyToThisPostStr + \
        ' |" src="/icons/reply.png"/></a>\n'
    return replyStr


def _getEditIconHtml(base_dir: str, nickname: str, domain_full: str,
                     post_json_object: {}, actorNickname: str,
                     translate: {}, isEvent: bool) -> str:
    """Returns html for the edit icon/button
    """
    editStr = ''
    actor = post_json_object['actor']
    # This should either be a post which you created,
    # or it could be generated from the newswire (see
    # _addBlogsToNewswire) in which case anyone with
    # editor status should be able to alter it
    if (actor.endswith('/' + domain_full + '/users/' + nickname) or
        (isEditor(base_dir, nickname) and
         actor.endswith('/' + domain_full + '/users/news'))):

        postId = removeIdEnding(post_json_object['object']['id'])

        if '/statuses/' not in postId:
            return editStr

        if isBlogPost(post_json_object):
            editBlogPostStr = 'Edit blog post'
            if translate.get(editBlogPostStr):
                editBlogPostStr = translate[editBlogPostStr]
            if not isNewsPost(post_json_object):
                editStr += \
                    '        ' + \
                    '<a class="imageAnchor" href="/users/' + \
                    nickname + \
                    '/tlblogs?editblogpost=' + \
                    postId.split('/statuses/')[1] + \
                    ';actor=' + actorNickname + \
                    '" title="' + editBlogPostStr + '">' + \
                    '<img loading="lazy" title="' + \
                    editBlogPostStr + '" alt="' + editBlogPostStr + \
                    ' |" src="/icons/edit.png"/></a>\n'
            else:
                editStr += \
                    '        ' + \
                    '<a class="imageAnchor" href="/users/' + \
                    nickname + '/editnewspost=' + \
                    postId.split('/statuses/')[1] + \
                    '?actor=' + actorNickname + \
                    '" title="' + editBlogPostStr + '">' + \
                    '<img loading="lazy" title="' + \
                    editBlogPostStr + '" alt="' + editBlogPostStr + \
                    ' |" src="/icons/edit.png"/></a>\n'
        elif isEvent:
            editEventStr = 'Edit event'
            if translate.get(editEventStr):
                editEventStr = translate[editEventStr]
            editStr += \
                '        ' + \
                '<a class="imageAnchor" href="/users/' + nickname + \
                '/tlblogs?editeventpost=' + \
                postId.split('/statuses/')[1] + \
                '?actor=' + actorNickname + \
                '" title="' + editEventStr + '">' + \
                '<img loading="lazy" title="' + \
                editEventStr + '" alt="' + editEventStr + \
                ' |" src="/icons/edit.png"/></a>\n'
    return editStr


def _getAnnounceIconHtml(isAnnounced: bool,
                         postActor: str,
                         nickname: str, domain_full: str,
                         announceJsonObject: {},
                         post_json_object: {},
                         isPublicRepeat: bool,
                         isModerationPost: bool,
                         showRepeatIcon: bool,
                         translate: {},
                         pageNumberParam: str,
                         timelinePostBookmark: str,
                         boxName: str) -> str:
    """Returns html for announce icon/button
    """
    announceStr = ''

    if not showRepeatIcon:
        return announceStr

    if isModerationPost:
        return announceStr

    # don't allow announce/repeat of your own posts
    announceIcon = 'repeat_inactive.png'
    announceLink = 'repeat'
    announceEmoji = ''
    if not isPublicRepeat:
        announceLink = 'repeatprivate'
    repeatThisPostStr = 'Repeat this post'
    if translate.get(repeatThisPostStr):
        repeatThisPostStr = translate[repeatThisPostStr]
    announceTitle = repeatThisPostStr
    unannounceLinkStr = ''

    if announcedByPerson(isAnnounced,
                         postActor, nickname, domain_full):
        announceIcon = 'repeat.png'
        announceEmoji = '🔁 '
        announceLink = 'unrepeat'
        if not isPublicRepeat:
            announceLink = 'unrepeatprivate'
        undoTheRepeatStr = 'Undo the repeat'
        if translate.get(undoTheRepeatStr):
            undoTheRepeatStr = translate[undoTheRepeatStr]
        announceTitle = undoTheRepeatStr
        if announceJsonObject:
            unannounceLinkStr = '?unannounce=' + \
                removeIdEnding(announceJsonObject['id'])

    announcePostId = removeHashFromPostId(post_json_object['object']['id'])
    announcePostId = removeIdEnding(announcePostId)
    announceLinkStr = '?' + \
        announceLink + '=' + announcePostId + pageNumberParam
    announceStr = \
        '        <a class="imageAnchor" href="/users/' + \
        nickname + announceLinkStr + unannounceLinkStr + \
        '?actor=' + post_json_object['actor'] + \
        '?bm=' + timelinePostBookmark + \
        '?tl=' + boxName + '" title="' + announceTitle + '">\n'

    announceStr += \
        '          ' + \
        '<img loading="lazy" title="' + announceTitle + \
        '" alt="' + announceEmoji + announceTitle + \
        ' |" src="/icons/' + announceIcon + '"/></a>\n'
    return announceStr


def _getLikeIconHtml(nickname: str, domain_full: str,
                     isModerationPost: bool,
                     showLikeButton: bool,
                     post_json_object: {},
                     enableTimingLog: bool,
                     postStartTime,
                     translate: {}, pageNumberParam: str,
                     timelinePostBookmark: str,
                     boxName: str,
                     max_like_count: int) -> str:
    """Returns html for like icon/button
    """
    if not showLikeButton or isModerationPost:
        return ''
    likeStr = ''
    likeIcon = 'like_inactive.png'
    likeLink = 'like'
    likeTitle = 'Like this post'
    if translate.get(likeTitle):
        likeTitle = translate[likeTitle]
    likeEmoji = ''
    likeCount = noOfLikes(post_json_object)

    _logPostTiming(enableTimingLog, postStartTime, '12.1')

    likeCountStr = ''
    if likeCount > 0:
        if likeCount <= max_like_count:
            likeCountStr = ' (' + str(likeCount) + ')'
        else:
            likeCountStr = ' (' + str(max_like_count) + '+)'
        if likedByPerson(post_json_object, nickname, domain_full):
            if likeCount == 1:
                # liked by the reader only
                likeCountStr = ''
            likeIcon = 'like.png'
            likeLink = 'unlike'
            likeTitle = 'Undo the like'
            if translate.get(likeTitle):
                likeTitle = translate[likeTitle]
            likeEmoji = '👍 '

    _logPostTiming(enableTimingLog, postStartTime, '12.2')

    likeStr = ''
    if likeCountStr:
        # show the number of likes next to icon
        likeStr += '<label class="likesCount">'
        likeStr += likeCountStr.replace('(', '').replace(')', '').strip()
        likeStr += '</label>\n'
    likePostId = removeHashFromPostId(post_json_object['id'])
    likePostId = removeIdEnding(likePostId)
    likeStr += \
        '        <a class="imageAnchor" href="/users/' + nickname + '?' + \
        likeLink + '=' + likePostId + \
        pageNumberParam + \
        '?actor=' + post_json_object['actor'] + \
        '?bm=' + timelinePostBookmark + \
        '?tl=' + boxName + '" title="' + \
        likeTitle + likeCountStr + '">\n'
    likeStr += \
        '          ' + \
        '<img loading="lazy" title="' + likeTitle + likeCountStr + \
        '" alt="' + likeEmoji + likeTitle + \
        ' |" src="/icons/' + likeIcon + '"/></a>\n'
    return likeStr


def _getBookmarkIconHtml(nickname: str, domain_full: str,
                         post_json_object: {},
                         isModerationPost: bool,
                         translate: {},
                         enableTimingLog: bool,
                         postStartTime, boxName: str,
                         pageNumberParam: str,
                         timelinePostBookmark: str) -> str:
    """Returns html for bookmark icon/button
    """
    bookmarkStr = ''

    if isModerationPost:
        return bookmarkStr

    bookmarkIcon = 'bookmark_inactive.png'
    bookmarkLink = 'bookmark'
    bookmarkEmoji = ''
    bookmarkTitle = 'Bookmark this post'
    if translate.get(bookmarkTitle):
        bookmarkTitle = translate[bookmarkTitle]
    if bookmarkedByPerson(post_json_object, nickname, domain_full):
        bookmarkIcon = 'bookmark.png'
        bookmarkLink = 'unbookmark'
        bookmarkEmoji = '🔖 '
        bookmarkTitle = 'Undo the bookmark'
        if translate.get(bookmarkTitle):
            bookmarkTitle = translate[bookmarkTitle]
    _logPostTiming(enableTimingLog, postStartTime, '12.6')
    bookmarkPostId = removeHashFromPostId(post_json_object['object']['id'])
    bookmarkPostId = removeIdEnding(bookmarkPostId)
    bookmarkStr = \
        '        <a class="imageAnchor" href="/users/' + nickname + '?' + \
        bookmarkLink + '=' + bookmarkPostId + \
        pageNumberParam + \
        '?actor=' + post_json_object['actor'] + \
        '?bm=' + timelinePostBookmark + \
        '?tl=' + boxName + '" title="' + bookmarkTitle + '">\n'
    bookmarkStr += \
        '        ' + \
        '<img loading="lazy" title="' + bookmarkTitle + '" alt="' + \
        bookmarkEmoji + bookmarkTitle + ' |" src="/icons' + \
        '/' + bookmarkIcon + '"/></a>\n'
    return bookmarkStr


def _getReactionIconHtml(nickname: str, domain_full: str,
                         post_json_object: {},
                         isModerationPost: bool,
                         showReactionButton: bool,
                         translate: {},
                         enableTimingLog: bool,
                         postStartTime, boxName: str,
                         pageNumberParam: str,
                         timelinePostReaction: str) -> str:
    """Returns html for reaction icon/button
    """
    reactionStr = ''

    if not showReactionButton or isModerationPost:
        return reactionStr

    reactionIcon = 'reaction.png'
    reactionTitle = 'Select reaction'
    if translate.get(reactionTitle):
        reactionTitle = translate[reactionTitle]
    _logPostTiming(enableTimingLog, postStartTime, '12.65')
    reactionPostId = removeHashFromPostId(post_json_object['object']['id'])
    reactionPostId = removeIdEnding(reactionPostId)
    reactionStr = \
        '        <a class="imageAnchor" href="/users/' + nickname + \
        '?selreact=' + reactionPostId + pageNumberParam + \
        '?actor=' + post_json_object['actor'] + \
        '?bm=' + timelinePostReaction + \
        '?tl=' + boxName + '" title="' + reactionTitle + '">\n'
    reactionStr += \
        '        ' + \
        '<img loading="lazy" title="' + reactionTitle + '" alt="' + \
        reactionTitle + ' |" src="/icons' + \
        '/' + reactionIcon + '"/></a>\n'
    return reactionStr


def _getMuteIconHtml(isMuted: bool,
                     postActor: str,
                     messageId: str,
                     nickname: str, domain_full: str,
                     allow_deletion: bool,
                     pageNumberParam: str,
                     boxName: str,
                     timelinePostBookmark: str,
                     translate: {}) -> str:
    """Returns html for mute icon/button
    """
    muteStr = ''
    if (allow_deletion or
        ('/' + domain_full + '/' in postActor and
         messageId.startswith(postActor))):
        return muteStr

    if not isMuted:
        muteThisPostStr = 'Mute this post'
        if translate.get('Mute this post'):
            muteThisPostStr = translate[muteThisPostStr]
        muteStr = \
            '        <a class="imageAnchor" href="/users/' + nickname + \
            '?mute=' + messageId + pageNumberParam + '?tl=' + boxName + \
            '?bm=' + timelinePostBookmark + \
            '" title="' + muteThisPostStr + '">\n'
        muteStr += \
            '          ' + \
            '<img loading="lazy" alt="' + \
            muteThisPostStr + \
            ' |" title="' + muteThisPostStr + \
            '" src="/icons/mute.png"/></a>\n'
    else:
        undoMuteStr = 'Undo mute'
        if translate.get(undoMuteStr):
            undoMuteStr = translate[undoMuteStr]
        muteStr = \
            '        <a class="imageAnchor" href="/users/' + \
            nickname + '?unmute=' + messageId + \
            pageNumberParam + '?tl=' + boxName + '?bm=' + \
            timelinePostBookmark + '" title="' + undoMuteStr + '">\n'
        muteStr += \
            '          ' + \
            '<img loading="lazy" alt="🔇 ' + undoMuteStr + \
            ' |" title="' + undoMuteStr + \
            '" src="/icons/unmute.png"/></a>\n'
    return muteStr


def _getDeleteIconHtml(nickname: str, domain_full: str,
                       allow_deletion: bool,
                       postActor: str,
                       messageId: str,
                       post_json_object: {},
                       pageNumberParam: str,
                       translate: {}) -> str:
    """Returns html for delete icon/button
    """
    deleteStr = ''
    if (allow_deletion or
        ('/' + domain_full + '/' in postActor and
         messageId.startswith(postActor))):
        if '/users/' + nickname + '/' in messageId:
            if not isNewsPost(post_json_object):
                deleteThisPostStr = 'Delete this post'
                if translate.get(deleteThisPostStr):
                    deleteThisPostStr = translate[deleteThisPostStr]
                deleteStr = \
                    '        <a class="imageAnchor" href="/users/' + \
                    nickname + \
                    '?delete=' + messageId + pageNumberParam + \
                    '" title="' + deleteThisPostStr + '">\n'
                deleteStr += \
                    '          ' + \
                    '<img loading="lazy" alt="' + \
                    deleteThisPostStr + \
                    ' |" title="' + deleteThisPostStr + \
                    '" src="/icons/delete.png"/></a>\n'
    return deleteStr


def _getPublishedDateStr(post_json_object: {},
                         show_published_date_only: bool) -> str:
    """Return the html for the published date on a post
    """
    publishedStr = ''

    if not post_json_object['object'].get('published'):
        return publishedStr

    publishedStr = post_json_object['object']['published']
    if '.' not in publishedStr:
        if '+' not in publishedStr:
            datetimeObject = \
                datetime.strptime(publishedStr, "%Y-%m-%dT%H:%M:%SZ")
        else:
            datetimeObject = \
                datetime.strptime(publishedStr.split('+')[0] + 'Z',
                                  "%Y-%m-%dT%H:%M:%SZ")
    else:
        publishedStr = \
            publishedStr.replace('T', ' ').split('.')[0]
        datetimeObject = parse(publishedStr)
    if not show_published_date_only:
        publishedStr = datetimeObject.strftime("%a %b %d, %H:%M")
    else:
        publishedStr = datetimeObject.strftime("%a %b %d")

    # if the post has replies then append a symbol to indicate this
    if post_json_object.get('hasReplies'):
        if post_json_object['hasReplies'] is True:
            publishedStr = '[' + publishedStr + ']'
    return publishedStr


def _getBlogCitationsHtml(boxName: str,
                          post_json_object: {},
                          translate: {}) -> str:
    """Returns blog citations as html
    """
    # show blog citations
    citationsStr = ''
    if not (boxName == 'tlblogs' or boxName == 'tlfeatures'):
        return citationsStr

    if not post_json_object['object'].get('tag'):
        return citationsStr

    for tagJson in post_json_object['object']['tag']:
        if not isinstance(tagJson, dict):
            continue
        if not tagJson.get('type'):
            continue
        if tagJson['type'] != 'Article':
            continue
        if not tagJson.get('name'):
            continue
        if not tagJson.get('url'):
            continue
        citationsStr += \
            '<li><a href="' + tagJson['url'] + '">' + \
            '<cite>' + tagJson['name'] + '</cite></a></li>\n'

    if citationsStr:
        translatedCitationsStr = 'Citations'
        if translate.get(translatedCitationsStr):
            translatedCitationsStr = translate[translatedCitationsStr]
        citationsStr = '<p><b>' + translatedCitationsStr + ':</b></p>' + \
            '<ul>\n' + citationsStr + '</ul>\n'
    return citationsStr


def _boostOwnPostHtml(translate: {}) -> str:
    """The html title for announcing your own post
    """
    announcesStr = 'announces'
    if translate.get(announcesStr):
        announcesStr = translate[announcesStr]
    return '        <img loading="lazy" title="' + \
        announcesStr + \
        '" alt="' + announcesStr + \
        '" src="/icons' + \
        '/repeat_inactive.png" class="announceOrReply"/>\n'


def _announceUnattributedHtml(translate: {},
                              post_json_object: {}) -> str:
    """Returns the html for an announce title where there
    is no attribution on the announced post
    """
    announcesStr = 'announces'
    if translate.get(announcesStr):
        announcesStr = translate[announcesStr]
    postId = removeIdEnding(post_json_object['object']['id'])
    return '    <img loading="lazy" title="' + \
        announcesStr + '" alt="' + \
        announcesStr + '" src="/icons' + \
        '/repeat_inactive.png" ' + \
        'class="announceOrReply"/>\n' + \
        '      <a href="' + postId + \
        '" class="announceOrReply">@unattributed</a>\n'


def _announceWithDisplayNameHtml(translate: {},
                                 post_json_object: {},
                                 announceDisplayName: str) -> str:
    """Returns html for an announce having a display name
    """
    announcesStr = 'announces'
    if translate.get(announcesStr):
        announcesStr = translate[announcesStr]
    postId = removeIdEnding(post_json_object['object']['id'])
    return '          <img loading="lazy" title="' + \
        announcesStr + '" alt="' + \
        announcesStr + '" src="/' + \
        'icons/repeat_inactive.png" ' + \
        'class="announceOrReply"/>\n' + \
        '        <a href="' + postId + '" ' + \
        'class="announceOrReply">' + announceDisplayName + '</a>\n'


def _getPostTitleAnnounceHtml(base_dir: str,
                              http_prefix: str,
                              nickname: str, domain: str,
                              showRepeatIcon: bool,
                              isAnnounced: bool,
                              post_json_object: {},
                              postActor: str,
                              translate: {},
                              enableTimingLog: bool,
                              postStartTime,
                              boxName: str,
                              person_cache: {},
                              allowDownloads: bool,
                              avatarPosition: str,
                              pageNumber: int,
                              messageIdStr: str,
                              containerClassIcons: str,
                              containerClass: str) -> (str, str, str, str):
    """Returns the announce title of a post containing names of participants
    x announces y
    """
    titleStr = ''
    replyAvatarImageInPost = ''
    objJson = post_json_object['object']

    # has no attribution
    if not objJson.get('attributedTo'):
        titleStr += _announceUnattributedHtml(translate, post_json_object)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    attributedTo = ''
    if isinstance(objJson['attributedTo'], str):
        attributedTo = objJson['attributedTo']

    # boosting your own post
    if attributedTo.startswith(postActor):
        titleStr += _boostOwnPostHtml(translate)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    # boosting another person's post
    _logPostTiming(enableTimingLog, postStartTime, '13.2')
    announceNickname = None
    if attributedTo:
        announceNickname = getNicknameFromActor(attributedTo)
    if not announceNickname:
        titleStr += _announceUnattributedHtml(translate, post_json_object)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    announceDomain, announcePort = getDomainFromActor(attributedTo)
    getPersonFromCache(base_dir, attributedTo, person_cache, allowDownloads)
    announceDisplayName = getDisplayName(base_dir, attributedTo, person_cache)
    if not announceDisplayName:
        announceDisplayName = announceNickname + '@' + announceDomain

    _logPostTiming(enableTimingLog, postStartTime, '13.3')

    # add any emoji to the display name
    if ':' in announceDisplayName:
        announceDisplayName = \
            addEmojiToDisplayName(None, base_dir, http_prefix,
                                  nickname, domain,
                                  announceDisplayName, False)
    _logPostTiming(enableTimingLog, postStartTime, '13.3.1')
    titleStr += \
        _announceWithDisplayNameHtml(translate, post_json_object,
                                     announceDisplayName)
    # show avatar of person replied to
    announceActor = attributedTo
    announceAvatarUrl = \
        getPersonAvatarUrl(base_dir, announceActor,
                           person_cache, allowDownloads)

    _logPostTiming(enableTimingLog, postStartTime, '13.4')

    if not announceAvatarUrl:
        announceAvatarUrl = ''

    idx = 'Show options for this person'
    if '/users/news/' not in announceAvatarUrl:
        showOptionsForThisPersonStr = idx
        if translate.get(idx):
            showOptionsForThisPersonStr = translate[idx]
        replyAvatarImageInPost = \
            '        <div class="timeline-avatar-reply">\n' \
            '            <a class="imageAnchor" ' + \
            'href="/users/' + nickname + '?options=' + \
            announceActor + ';' + str(pageNumber) + \
            ';' + announceAvatarUrl + messageIdStr + '">' \
            '<img loading="lazy" src="' + announceAvatarUrl + '" ' + \
            'title="' + showOptionsForThisPersonStr + \
            '" alt=" "' + avatarPosition + \
            getBrokenLinkSubstitute() + '/></a>\n    </div>\n'

    return (titleStr, replyAvatarImageInPost,
            containerClassIcons, containerClass)


def _replyToYourselfHtml(translate: {}) -> str:
    """Returns html for a title which is a reply to yourself
    """
    replyingToThemselvesStr = 'replying to themselves'
    if translate.get(replyingToThemselvesStr):
        replyingToThemselvesStr = translate[replyingToThemselvesStr]
    return '    <img loading="lazy" title="' + \
        replyingToThemselvesStr + \
        '" alt="' + replyingToThemselvesStr + \
        '" src="/icons' + \
        '/reply.png" class="announceOrReply"/>\n'


def _replyToUnknownHtml(translate: {},
                        post_json_object: {}) -> str:
    """Returns the html title for a reply to an unknown handle
    """
    replyingToStr = 'replying to'
    if translate.get(replyingToStr):
        replyingToStr = translate[replyingToStr]
    return '        <img loading="lazy" title="' + \
        replyingToStr + '" alt="' + \
        replyingToStr + '" src="/icons' + \
        '/reply.png" class="announceOrReply"/>\n' + \
        '        <a href="' + \
        post_json_object['object']['inReplyTo'] + \
        '" class="announceOrReply">@unknown</a>\n'


def _replyWithUnknownPathHtml(translate: {},
                              post_json_object: {},
                              postDomain: str) -> str:
    """Returns html title for a reply with an unknown path
    eg. does not contain /statuses/
    """
    replyingToStr = 'replying to'
    if translate.get(replyingToStr):
        replyingToStr = translate[replyingToStr]
    return '        <img loading="lazy" title="' + \
        replyingToStr + \
        '" alt="' + replyingToStr + \
        '" src="/icons/reply.png" ' + \
        'class="announceOrReply"/>\n' + \
        '        <a href="' + \
        post_json_object['object']['inReplyTo'] + \
        '" class="announceOrReply">' + \
        postDomain + '</a>\n'


def _getReplyHtml(translate: {},
                  inReplyTo: str, replyDisplayName: str) -> str:
    """Returns html title for a reply
    """
    replyingToStr = 'replying to'
    if translate.get(replyingToStr):
        replyingToStr = translate[replyingToStr]
    return '        ' + \
        '<img loading="lazy" title="' + \
        replyingToStr + '" alt="' + \
        replyingToStr + '" src="/' + \
        'icons/reply.png" ' + \
        'class="announceOrReply"/>\n' + \
        '        <a href="' + inReplyTo + \
        '" class="announceOrReply">' + \
        replyDisplayName + '</a>\n'


def _getPostTitleReplyHtml(base_dir: str,
                           http_prefix: str,
                           nickname: str, domain: str,
                           showRepeatIcon: bool,
                           isAnnounced: bool,
                           post_json_object: {},
                           postActor: str,
                           translate: {},
                           enableTimingLog: bool,
                           postStartTime,
                           boxName: str,
                           person_cache: {},
                           allowDownloads: bool,
                           avatarPosition: str,
                           pageNumber: int,
                           messageIdStr: str,
                           containerClassIcons: str,
                           containerClass: str) -> (str, str, str, str):
    """Returns the reply title of a post containing names of participants
    x replies to y
    """
    titleStr = ''
    replyAvatarImageInPost = ''
    objJson = post_json_object['object']

    # not a reply
    if not objJson.get('inReplyTo'):
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    containerClassIcons = 'containericons darker'
    containerClass = 'container darker'

    # reply to self
    if objJson['inReplyTo'].startswith(postActor):
        titleStr += _replyToYourselfHtml(translate)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    # has a reply
    if '/statuses/' not in objJson['inReplyTo']:
        postDomain = objJson['inReplyTo']
        prefixes = getProtocolPrefixes()
        for prefix in prefixes:
            postDomain = postDomain.replace(prefix, '')
        if '/' in postDomain:
            postDomain = postDomain.split('/', 1)[0]
        if postDomain:
            titleStr += \
                _replyWithUnknownPathHtml(translate,
                                          post_json_object, postDomain)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    inReplyTo = objJson['inReplyTo']
    replyActor = inReplyTo.split('/statuses/')[0]
    replyNickname = getNicknameFromActor(replyActor)
    if not replyNickname:
        titleStr += _replyToUnknownHtml(translate, post_json_object)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    replyDomain, replyPort = getDomainFromActor(replyActor)
    if not (replyNickname and replyDomain):
        titleStr += _replyToUnknownHtml(translate, post_json_object)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    getPersonFromCache(base_dir, replyActor, person_cache, allowDownloads)
    replyDisplayName = getDisplayName(base_dir, replyActor, person_cache)
    if not replyDisplayName:
        replyDisplayName = replyNickname + '@' + replyDomain

    # add emoji to the display name
    if ':' in replyDisplayName:
        _logPostTiming(enableTimingLog, postStartTime, '13.5')

        replyDisplayName = \
            addEmojiToDisplayName(None, base_dir, http_prefix,
                                  nickname, domain,
                                  replyDisplayName, False)
        _logPostTiming(enableTimingLog, postStartTime, '13.6')

    titleStr += _getReplyHtml(translate, inReplyTo, replyDisplayName)

    _logPostTiming(enableTimingLog, postStartTime, '13.7')

    # show avatar of person replied to
    replyAvatarUrl = \
        getPersonAvatarUrl(base_dir, replyActor, person_cache, allowDownloads)

    _logPostTiming(enableTimingLog, postStartTime, '13.8')

    if replyAvatarUrl:
        showProfileStr = 'Show profile'
        if translate.get(showProfileStr):
            showProfileStr = translate[showProfileStr]
        replyAvatarImageInPost = \
            '        <div class="timeline-avatar-reply">\n' + \
            '          <a class="imageAnchor" ' + \
            'href="/users/' + nickname + '?options=' + replyActor + \
            ';' + str(pageNumber) + ';' + replyAvatarUrl + \
            messageIdStr + '">\n' + \
            '          <img loading="lazy" src="' + replyAvatarUrl + '" ' + \
            'title="' + showProfileStr + \
            '" alt=" "' + avatarPosition + getBrokenLinkSubstitute() + \
            '/></a>\n        </div>\n'

    return (titleStr, replyAvatarImageInPost,
            containerClassIcons, containerClass)


def _getPostTitleHtml(base_dir: str,
                      http_prefix: str,
                      nickname: str, domain: str,
                      showRepeatIcon: bool,
                      isAnnounced: bool,
                      post_json_object: {},
                      postActor: str,
                      translate: {},
                      enableTimingLog: bool,
                      postStartTime,
                      boxName: str,
                      person_cache: {},
                      allowDownloads: bool,
                      avatarPosition: str,
                      pageNumber: int,
                      messageIdStr: str,
                      containerClassIcons: str,
                      containerClass: str) -> (str, str, str, str):
    """Returns the title of a post containing names of participants
    x replies to y, x announces y, etc
    """
    if not isAnnounced and boxName == 'search' and \
       post_json_object.get('object'):
        if post_json_object['object'].get('attributedTo'):
            if post_json_object['object']['attributedTo'] != postActor:
                isAnnounced = True

    if isAnnounced:
        return _getPostTitleAnnounceHtml(base_dir,
                                         http_prefix,
                                         nickname, domain,
                                         showRepeatIcon,
                                         isAnnounced,
                                         post_json_object,
                                         postActor,
                                         translate,
                                         enableTimingLog,
                                         postStartTime,
                                         boxName,
                                         person_cache,
                                         allowDownloads,
                                         avatarPosition,
                                         pageNumber,
                                         messageIdStr,
                                         containerClassIcons,
                                         containerClass)

    return _getPostTitleReplyHtml(base_dir,
                                  http_prefix,
                                  nickname, domain,
                                  showRepeatIcon,
                                  isAnnounced,
                                  post_json_object,
                                  postActor,
                                  translate,
                                  enableTimingLog,
                                  postStartTime,
                                  boxName,
                                  person_cache,
                                  allowDownloads,
                                  avatarPosition,
                                  pageNumber,
                                  messageIdStr,
                                  containerClassIcons,
                                  containerClass)


def _getFooterWithIcons(showIcons: bool,
                        containerClassIcons: str,
                        replyStr: str, announceStr: str,
                        likeStr: str, reactionStr: str,
                        bookmarkStr: str,
                        deleteStr: str, muteStr: str, editStr: str,
                        post_json_object: {}, publishedLink: str,
                        timeClass: str, publishedStr: str) -> str:
    """Returns the html for a post footer containing icons
    """
    if not showIcons:
        return None

    footerStr = '\n      <nav>\n'
    footerStr += '      <div class="' + containerClassIcons + '">\n'
    footerStr += replyStr + announceStr + likeStr + bookmarkStr + reactionStr
    footerStr += deleteStr + muteStr + editStr
    if not isNewsPost(post_json_object):
        footerStr += '        <a href="' + publishedLink + '" class="' + \
            timeClass + '">' + publishedStr + '</a>\n'
    else:
        footerStr += '        <a href="' + \
            publishedLink.replace('/news/', '/news/statuses/') + \
            '" class="' + timeClass + '">' + publishedStr + '</a>\n'
    footerStr += '      </div>\n'
    footerStr += '      </nav>\n'
    return footerStr


def individualPostAsHtml(signing_priv_key_pem: str,
                         allowDownloads: bool,
                         recentPostsCache: {}, max_recent_posts: int,
                         translate: {},
                         pageNumber: int, base_dir: str,
                         session, cached_webfingers: {}, person_cache: {},
                         nickname: str, domain: str, port: int,
                         post_json_object: {},
                         avatarUrl: str, showAvatarOptions: bool,
                         allow_deletion: bool,
                         http_prefix: str, project_version: str,
                         boxName: str,
                         yt_replace_domain: str,
                         twitter_replacement_domain: str,
                         show_published_date_only: bool,
                         peertube_instances: [],
                         allow_local_network_access: bool,
                         theme_name: str, system_language: str,
                         max_like_count: int,
                         showRepeats: bool,
                         showIcons: bool,
                         manuallyApprovesFollowers: bool,
                         showPublicOnly: bool,
                         storeToCache: bool,
                         useCacheOnly: bool,
                         cw_lists: {},
                         lists_enabled: str) -> str:
    """ Shows a single post as html
    """
    if not post_json_object:
        return ''

    # maximum number of different emoji reactions which can be added to a post
    maxReactionTypes = 5

    # benchmark
    postStartTime = time.time()

    postActor = post_json_object['actor']

    # ZZZzzz
    if isPersonSnoozed(base_dir, nickname, domain, postActor):
        return ''

    # if downloads of avatar images aren't enabled then we can do more
    # accurate timing of different parts of the code
    enableTimingLog = not allowDownloads

    _logPostTiming(enableTimingLog, postStartTime, '1')

    avatarPosition = ''
    messageId = ''
    if post_json_object.get('id'):
        messageId = removeHashFromPostId(post_json_object['id'])
        messageId = removeIdEnding(messageId)

    _logPostTiming(enableTimingLog, postStartTime, '2')

    messageIdStr = ''
    if messageId:
        messageIdStr = ';' + messageId

    domain_full = getFullDomain(domain, port)

    pageNumberParam = ''
    if pageNumber:
        pageNumberParam = '?page=' + str(pageNumber)

    # get the html post from the recent posts cache if it exists there
    postHtml = \
        _getPostFromRecentCache(session, base_dir,
                                http_prefix, nickname, domain,
                                post_json_object,
                                postActor,
                                person_cache,
                                allowDownloads,
                                showPublicOnly,
                                storeToCache,
                                boxName,
                                avatarUrl,
                                enableTimingLog,
                                postStartTime,
                                pageNumber,
                                recentPostsCache,
                                max_recent_posts,
                                signing_priv_key_pem)
    if postHtml:
        return postHtml
    if useCacheOnly and post_json_object['type'] != 'Announce':
        return ''

    _logPostTiming(enableTimingLog, postStartTime, '4')

    avatarUrl = \
        getAvatarImageUrl(session,
                          base_dir, http_prefix,
                          postActor, person_cache,
                          avatarUrl, allowDownloads,
                          signing_priv_key_pem)

    _logPostTiming(enableTimingLog, postStartTime, '5')

    # get the display name
    if domain_full not in postActor:
        # lookup the correct webfinger for the postActor
        postActorNickname = getNicknameFromActor(postActor)
        postActorDomain, postActorPort = getDomainFromActor(postActor)
        postActorDomainFull = getFullDomain(postActorDomain, postActorPort)
        postActorHandle = postActorNickname + '@' + postActorDomainFull
        postActorWf = \
            webfingerHandle(session, postActorHandle, http_prefix,
                            cached_webfingers,
                            domain, __version__, False, False,
                            signing_priv_key_pem)

        avatarUrl2 = None
        displayName = None
        if postActorWf:
            originDomain = domain
            (inboxUrl, pubKeyId, pubKey, fromPersonId, sharedInbox, avatarUrl2,
             displayName, _) = getPersonBox(signing_priv_key_pem,
                                            originDomain,
                                            base_dir, session,
                                            postActorWf,
                                            person_cache,
                                            project_version,
                                            http_prefix,
                                            nickname, domain,
                                            'outbox', 72367)

        _logPostTiming(enableTimingLog, postStartTime, '6')

        if avatarUrl2:
            avatarUrl = avatarUrl2
        if displayName:
            # add any emoji to the display name
            if ':' in displayName:
                displayName = \
                    addEmojiToDisplayName(session, base_dir, http_prefix,
                                          nickname, domain,
                                          displayName, False)

    _logPostTiming(enableTimingLog, postStartTime, '7')

    avatarLink = \
        _getAvatarImageHtml(showAvatarOptions,
                            nickname, domain_full,
                            avatarUrl, postActor,
                            translate, avatarPosition,
                            pageNumber, messageIdStr)

    avatarImageInPost = \
        '      <div class="timeline-avatar">' + avatarLink + '</div>\n'

    timelinePostBookmark = removeIdEnding(post_json_object['id'])
    timelinePostBookmark = timelinePostBookmark.replace('://', '-')
    timelinePostBookmark = timelinePostBookmark.replace('/', '-')

    # If this is the inbox timeline then don't show the repeat icon on any DMs
    showRepeatIcon = showRepeats
    isPublicRepeat = False
    postIsDM = isDM(post_json_object)
    if showRepeats:
        if postIsDM:
            showRepeatIcon = False
        else:
            if not isPublicPost(post_json_object):
                isPublicRepeat = True

    titleStr = ''
    galleryStr = ''
    isAnnounced = False
    announceJsonObject = None
    if post_json_object['type'] == 'Announce':
        announceJsonObject = post_json_object.copy()
        blockedCache = {}
        postJsonAnnounce = \
            downloadAnnounce(session, base_dir, http_prefix,
                             nickname, domain, post_json_object,
                             project_version, translate,
                             yt_replace_domain,
                             twitter_replacement_domain,
                             allow_local_network_access,
                             recentPostsCache, False,
                             system_language,
                             domain_full, person_cache,
                             signing_priv_key_pem,
                             blockedCache)
        if not postJsonAnnounce:
            # if the announce could not be downloaded then mark it as rejected
            announcedPostId = removeIdEnding(post_json_object['id'])
            rejectPostId(base_dir, nickname, domain, announcedPostId,
                         recentPostsCache)
            return ''
        post_json_object = postJsonAnnounce

        # is the announced post in the html cache?
        postHtml = \
            _getPostFromRecentCache(session, base_dir,
                                    http_prefix, nickname, domain,
                                    post_json_object,
                                    postActor,
                                    person_cache,
                                    allowDownloads,
                                    showPublicOnly,
                                    storeToCache,
                                    boxName,
                                    avatarUrl,
                                    enableTimingLog,
                                    postStartTime,
                                    pageNumber,
                                    recentPostsCache,
                                    max_recent_posts,
                                    signing_priv_key_pem)
        if postHtml:
            return postHtml

        announceFilename = \
            locatePost(base_dir, nickname, domain, post_json_object['id'])
        if announceFilename:
            updateAnnounceCollection(recentPostsCache,
                                     base_dir, announceFilename,
                                     postActor, nickname, domain_full, False)

            # create a file for use by text-to-speech
            if isRecentPost(post_json_object, 3):
                if post_json_object.get('actor'):
                    if not os.path.isfile(announceFilename + '.tts'):
                        updateSpeaker(base_dir, http_prefix,
                                      nickname, domain, domain_full,
                                      post_json_object, person_cache,
                                      translate, post_json_object['actor'],
                                      theme_name)
                        with open(announceFilename + '.tts', 'w+') as ttsFile:
                            ttsFile.write('\n')

        isAnnounced = True

    _logPostTiming(enableTimingLog, postStartTime, '8')

    if not has_object_dict(post_json_object):
        return ''

    # if this post should be public then check its recipients
    if showPublicOnly:
        if not postContainsPublic(post_json_object):
            return ''

    isModerationPost = False
    if post_json_object['object'].get('moderationStatus'):
        isModerationPost = True
    containerClass = 'container'
    containerClassIcons = 'containericons'
    timeClass = 'time-right'
    actorNickname = getNicknameFromActor(postActor)
    if not actorNickname:
        # single user instance
        actorNickname = 'dev'
    actorDomain, actorPort = getDomainFromActor(postActor)

    displayName = getDisplayName(base_dir, postActor, person_cache)
    if displayName:
        if ':' in displayName:
            displayName = \
                addEmojiToDisplayName(session, base_dir, http_prefix,
                                      nickname, domain,
                                      displayName, False)
        titleStr += \
            '        <a class="imageAnchor" href="/users/' + \
            nickname + '?options=' + postActor + \
            ';' + str(pageNumber) + ';' + avatarUrl + messageIdStr + \
            '">' + displayName + '</a>\n'
    else:
        if not messageId:
            # pprint(post_json_object)
            print('ERROR: no messageId')
        if not actorNickname:
            # pprint(post_json_object)
            print('ERROR: no actorNickname')
        if not actorDomain:
            # pprint(post_json_object)
            print('ERROR: no actorDomain')
        titleStr += \
            '        <a class="imageAnchor" href="/users/' + \
            nickname + '?options=' + postActor + \
            ';' + str(pageNumber) + ';' + avatarUrl + messageIdStr + \
            '">@' + actorNickname + '@' + actorDomain + '</a>\n'

    # benchmark 9
    _logPostTiming(enableTimingLog, postStartTime, '9')

    # Show a DM icon for DMs in the inbox timeline
    if postIsDM:
        titleStr = \
            titleStr + ' <img loading="lazy" src="/' + \
            'icons/dm.png" class="DMicon"/>\n'

    # check if replying is permitted
    commentsEnabled = True
    if isinstance(post_json_object['object'], dict) and \
       'commentsEnabled' in post_json_object['object']:
        if post_json_object['object']['commentsEnabled'] is False:
            commentsEnabled = False
        elif 'rejectReplies' in post_json_object['object']:
            if post_json_object['object']['rejectReplies']:
                commentsEnabled = False

    conversationId = None
    if isinstance(post_json_object['object'], dict) and \
       'conversation' in post_json_object['object']:
        if post_json_object['object']['conversation']:
            conversationId = post_json_object['object']['conversation']

    publicReply = False
    if isPublicPost(post_json_object):
        publicReply = True
    replyStr = _getReplyIconHtml(base_dir, nickname, domain,
                                 publicReply,
                                 showIcons, commentsEnabled,
                                 post_json_object, pageNumberParam,
                                 translate, system_language,
                                 conversationId)

    _logPostTiming(enableTimingLog, postStartTime, '10')

    editStr = _getEditIconHtml(base_dir, nickname, domain_full,
                               post_json_object, actorNickname,
                               translate, False)

    _logPostTiming(enableTimingLog, postStartTime, '11')

    announceStr = \
        _getAnnounceIconHtml(isAnnounced,
                             postActor,
                             nickname, domain_full,
                             announceJsonObject,
                             post_json_object,
                             isPublicRepeat,
                             isModerationPost,
                             showRepeatIcon,
                             translate,
                             pageNumberParam,
                             timelinePostBookmark,
                             boxName)

    _logPostTiming(enableTimingLog, postStartTime, '12')

    # whether to show a like button
    hideLikeButtonFile = \
        acctDir(base_dir, nickname, domain) + '/.hideLikeButton'
    showLikeButton = True
    if os.path.isfile(hideLikeButtonFile):
        showLikeButton = False

    # whether to show a reaction button
    hideReactionButtonFile = \
        acctDir(base_dir, nickname, domain) + '/.hideReactionButton'
    showReactionButton = True
    if os.path.isfile(hideReactionButtonFile):
        showReactionButton = False

    likeJsonObject = post_json_object
    if announceJsonObject:
        likeJsonObject = announceJsonObject
    likeStr = _getLikeIconHtml(nickname, domain_full,
                               isModerationPost,
                               showLikeButton,
                               likeJsonObject,
                               enableTimingLog,
                               postStartTime,
                               translate, pageNumberParam,
                               timelinePostBookmark,
                               boxName, max_like_count)

    _logPostTiming(enableTimingLog, postStartTime, '12.5')

    bookmarkStr = \
        _getBookmarkIconHtml(nickname, domain_full,
                             post_json_object,
                             isModerationPost,
                             translate,
                             enableTimingLog,
                             postStartTime, boxName,
                             pageNumberParam,
                             timelinePostBookmark)

    _logPostTiming(enableTimingLog, postStartTime, '12.9')

    reactionStr = \
        _getReactionIconHtml(nickname, domain_full,
                             post_json_object,
                             isModerationPost,
                             showReactionButton,
                             translate,
                             enableTimingLog,
                             postStartTime, boxName,
                             pageNumberParam,
                             timelinePostBookmark)

    _logPostTiming(enableTimingLog, postStartTime, '12.10')

    isMuted = postIsMuted(base_dir, nickname, domain,
                          post_json_object, messageId)

    _logPostTiming(enableTimingLog, postStartTime, '13')

    muteStr = \
        _getMuteIconHtml(isMuted,
                         postActor,
                         messageId,
                         nickname, domain_full,
                         allow_deletion,
                         pageNumberParam,
                         boxName,
                         timelinePostBookmark,
                         translate)

    deleteStr = \
        _getDeleteIconHtml(nickname, domain_full,
                           allow_deletion,
                           postActor,
                           messageId,
                           post_json_object,
                           pageNumberParam,
                           translate)

    _logPostTiming(enableTimingLog, postStartTime, '13.1')

    # get the title: x replies to y, x announces y, etc
    (titleStr2,
     replyAvatarImageInPost,
     containerClassIcons,
     containerClass) = _getPostTitleHtml(base_dir,
                                         http_prefix,
                                         nickname, domain,
                                         showRepeatIcon,
                                         isAnnounced,
                                         post_json_object,
                                         postActor,
                                         translate,
                                         enableTimingLog,
                                         postStartTime,
                                         boxName,
                                         person_cache,
                                         allowDownloads,
                                         avatarPosition,
                                         pageNumber,
                                         messageIdStr,
                                         containerClassIcons,
                                         containerClass)
    titleStr += titleStr2

    _logPostTiming(enableTimingLog, postStartTime, '14')

    attachmentStr, galleryStr = \
        getPostAttachmentsAsHtml(post_json_object, boxName, translate,
                                 isMuted, avatarLink,
                                 replyStr, announceStr, likeStr,
                                 bookmarkStr, deleteStr, muteStr)

    publishedStr = \
        _getPublishedDateStr(post_json_object, show_published_date_only)

    _logPostTiming(enableTimingLog, postStartTime, '15')

    publishedLink = messageId
    # blog posts should have no /statuses/ in their link
    if isBlogPost(post_json_object):
        # is this a post to the local domain?
        if '://' + domain in messageId:
            publishedLink = messageId.replace('/statuses/', '/')
    # if this is a local link then make it relative so that it works
    # on clearnet or onion address
    if domain + '/users/' in publishedLink or \
       domain + ':' + str(port) + '/users/' in publishedLink:
        publishedLink = '/users/' + publishedLink.split('/users/')[1]

    if not isNewsPost(post_json_object):
        footerStr = '<a href="' + publishedLink + \
            '" class="' + timeClass + '">' + publishedStr + '</a>\n'
    else:
        footerStr = '<a href="' + \
            publishedLink.replace('/news/', '/news/statuses/') + \
            '" class="' + timeClass + '">' + publishedStr + '</a>\n'

    # change the background color for DMs in inbox timeline
    if postIsDM:
        containerClassIcons = 'containericons dm'
        containerClass = 'container dm'

    newFooterStr = _getFooterWithIcons(showIcons,
                                       containerClassIcons,
                                       replyStr, announceStr,
                                       likeStr, reactionStr, bookmarkStr,
                                       deleteStr, muteStr, editStr,
                                       post_json_object, publishedLink,
                                       timeClass, publishedStr)
    if newFooterStr:
        footerStr = newFooterStr

    # add any content warning from the cwlists directory
    addCWfromLists(post_json_object, cw_lists, translate, lists_enabled)

    postIsSensitive = False
    if post_json_object['object'].get('sensitive'):
        # sensitive posts should have a summary
        if post_json_object['object'].get('summary'):
            postIsSensitive = post_json_object['object']['sensitive']
        else:
            # add a generic summary if none is provided
            sensitiveStr = 'Sensitive'
            if translate.get(sensitiveStr):
                sensitiveStr = translate[sensitiveStr]
            post_json_object['object']['summary'] = sensitiveStr

    # add an extra line if there is a content warning,
    # for better vertical spacing on mobile
    if postIsSensitive:
        footerStr = '<br>' + footerStr

    if not post_json_object['object'].get('summary'):
        post_json_object['object']['summary'] = ''

    if post_json_object['object'].get('cipherText'):
        post_json_object['object']['content'] = \
            E2EEdecryptMessageFromDevice(post_json_object['object'])
        post_json_object['object']['contentMap'][system_language] = \
            post_json_object['object']['content']

    domain_full = getFullDomain(domain, port)
    personUrl = local_actor_url(http_prefix, nickname, domain_full)
    actor_json = \
        getPersonFromCache(base_dir, personUrl, person_cache, False)
    languages_understood = []
    if actor_json:
        languages_understood = get_actor_languages_list(actor_json)
    contentStr = get_content_from_post(post_json_object, system_language,
                                       languages_understood)
    if not contentStr:
        contentStr = \
            autoTranslatePost(base_dir, post_json_object,
                              system_language, translate)
        if not contentStr:
            return ''

    isPatch = isGitPatch(base_dir, nickname, domain,
                         post_json_object['object']['type'],
                         post_json_object['object']['summary'],
                         contentStr)

    _logPostTiming(enableTimingLog, postStartTime, '16')

    if not isPGPEncrypted(contentStr):
        if not isPatch:
            objectContent = \
                removeLongWords(contentStr, 40, [])
            objectContent = removeTextFormatting(objectContent)
            objectContent = limitRepeatedWords(objectContent, 6)
            objectContent = \
                switchWords(base_dir, nickname, domain, objectContent)
            objectContent = htmlReplaceEmailQuote(objectContent)
            objectContent = htmlReplaceQuoteMarks(objectContent)
        else:
            objectContent = contentStr
    else:
        encryptedStr = 'Encrypted'
        if translate.get(encryptedStr):
            encryptedStr = translate[encryptedStr]
        objectContent = '🔒 ' + encryptedStr

    objectContent = '<article>' + objectContent + '</article>'

    if not postIsSensitive:
        contentStr = objectContent + attachmentStr
        contentStr = addEmbeddedElements(translate, contentStr,
                                         peertube_instances)
        contentStr = insertQuestion(base_dir, translate,
                                    nickname, domain, port,
                                    contentStr, post_json_object,
                                    pageNumber)
    else:
        postID = 'post' + str(createPassword(8))
        contentStr = ''
        if post_json_object['object'].get('summary'):
            cwStr = str(post_json_object['object']['summary'])
            cwStr = \
                addEmojiToDisplayName(session, base_dir, http_prefix,
                                      nickname, domain,
                                      cwStr, False)
            contentStr += \
                '<label class="cw">' + cwStr + '</label>\n '
            if isModerationPost:
                containerClass = 'container report'
        # get the content warning text
        cwContentStr = objectContent + attachmentStr
        if not isPatch:
            cwContentStr = addEmbeddedElements(translate, cwContentStr,
                                               peertube_instances)
            cwContentStr = \
                insertQuestion(base_dir, translate, nickname, domain, port,
                               cwContentStr, post_json_object, pageNumber)
            cwContentStr = \
                switchWords(base_dir, nickname, domain, cwContentStr)
        if not isBlogPost(post_json_object):
            # get the content warning button
            contentStr += \
                getContentWarningButton(postID, translate, cwContentStr)
        else:
            contentStr += cwContentStr

    _logPostTiming(enableTimingLog, postStartTime, '17')

    if post_json_object['object'].get('tag') and not isPatch:
        contentStr = \
            replaceEmojiFromTags(session, base_dir, contentStr,
                                 post_json_object['object']['tag'],
                                 'content', False)

    if isMuted:
        contentStr = ''
    else:
        if not isPatch:
            contentStr = '      <div class="message">' + \
                contentStr + \
                '      </div>\n'
        else:
            contentStr = \
                '<div class="gitpatch"><pre><code>' + contentStr + \
                '</code></pre></div>\n'

    # show blog citations
    citationsStr = \
        _getBlogCitationsHtml(boxName, post_json_object, translate)

    postHtml = ''
    if boxName != 'tlmedia':
        reactionStr = ''
        if showIcons:
            reactionStr = \
                htmlEmojiReactions(post_json_object, True, personUrl,
                                   maxReactionTypes,
                                   boxName, pageNumber)
            if postIsSensitive and reactionStr:
                reactionStr = '<br>' + reactionStr
        postHtml = '    <div id="' + timelinePostBookmark + \
            '" class="' + containerClass + '">\n'
        postHtml += avatarImageInPost
        postHtml += '      <div class="post-title">\n' + \
            '        ' + titleStr + \
            replyAvatarImageInPost + '      </div>\n'
        postHtml += contentStr + citationsStr + reactionStr + footerStr + '\n'
        postHtml += '    </div>\n'
    else:
        postHtml = galleryStr

    _logPostTiming(enableTimingLog, postStartTime, '18')

    # save the created html to the recent posts cache
    if not showPublicOnly and storeToCache and \
       boxName != 'tlmedia' and boxName != 'tlbookmarks' and \
       boxName != 'bookmarks':
        _saveIndividualPostAsHtmlToCache(base_dir, nickname, domain,
                                         post_json_object, postHtml)
        updateRecentPostsCache(recentPostsCache, max_recent_posts,
                               post_json_object, postHtml)

    _logPostTiming(enableTimingLog, postStartTime, '19')

    return postHtml


def htmlIndividualPost(cssCache: {},
                       recentPostsCache: {}, max_recent_posts: int,
                       translate: {},
                       base_dir: str, session, cached_webfingers: {},
                       person_cache: {},
                       nickname: str, domain: str, port: int, authorized: bool,
                       post_json_object: {}, http_prefix: str,
                       project_version: str, likedBy: str,
                       reactBy: str, reactEmoji: str,
                       yt_replace_domain: str,
                       twitter_replacement_domain: str,
                       show_published_date_only: bool,
                       peertube_instances: [],
                       allow_local_network_access: bool,
                       theme_name: str, system_language: str,
                       max_like_count: int, signing_priv_key_pem: str,
                       cw_lists: {}, lists_enabled: str) -> str:
    """Show an individual post as html
    """
    originalPostJson = post_json_object
    postStr = ''
    byStr = ''
    byText = ''
    byTextExtra = ''
    if likedBy:
        byStr = likedBy
        byText = 'Liked by'
    elif reactBy and reactEmoji:
        byStr = reactBy
        byText = 'Reaction by'
        byTextExtra = ' ' + reactEmoji

    if byStr:
        byStrNickname = getNicknameFromActor(byStr)
        byStrDomain, byStrPort = getDomainFromActor(byStr)
        byStrDomain = getFullDomain(byStrDomain, byStrPort)
        byStrHandle = byStrNickname + '@' + byStrDomain
        if translate.get(byText):
            byText = translate[byText]
        postStr += \
            '<p>' + byText + ' <a href="' + byStr + '">@' + \
            byStrHandle + '</a>' + byTextExtra + '\n'

        domain_full = getFullDomain(domain, port)
        actor = '/users/' + nickname
        followStr = '  <form method="POST" ' + \
            'accept-charset="UTF-8" action="' + actor + '/searchhandle">\n'
        followStr += \
            '    <input type="hidden" name="actor" value="' + actor + '">\n'
        followStr += \
            '    <input type="hidden" name="searchtext" value="' + \
            byStrHandle + '">\n'
        if not isFollowingActor(base_dir, nickname, domain_full, byStr):
            translateFollowStr = 'Follow'
            if translate.get(translateFollowStr):
                translateFollowStr = translate[translateFollowStr]
            followStr += '    <button type="submit" class="button" ' + \
                'name="submitSearch">' + translateFollowStr + '</button>\n'
        goBackStr = 'Go Back'
        if translate.get(goBackStr):
            goBackStr = translate[goBackStr]
        followStr += '    <button type="submit" class="button" ' + \
            'name="submitBack">' + goBackStr + '</button>\n'
        followStr += '  </form>\n'
        postStr += followStr + '</p>\n'

    postStr += \
        individualPostAsHtml(signing_priv_key_pem,
                             True, recentPostsCache, max_recent_posts,
                             translate, None,
                             base_dir, session,
                             cached_webfingers, person_cache,
                             nickname, domain, port, post_json_object,
                             None, True, False,
                             http_prefix, project_version, 'inbox',
                             yt_replace_domain,
                             twitter_replacement_domain,
                             show_published_date_only,
                             peertube_instances,
                             allow_local_network_access, theme_name,
                             system_language, max_like_count,
                             False, authorized, False, False, False, False,
                             cw_lists, lists_enabled)
    messageId = removeIdEnding(post_json_object['id'])

    # show the previous posts
    if has_object_dict(post_json_object):
        while post_json_object['object'].get('inReplyTo'):
            postFilename = \
                locatePost(base_dir, nickname, domain,
                           post_json_object['object']['inReplyTo'])
            if not postFilename:
                break
            post_json_object = loadJson(postFilename)
            if post_json_object:
                postStr = \
                    individualPostAsHtml(signing_priv_key_pem,
                                         True, recentPostsCache,
                                         max_recent_posts,
                                         translate, None,
                                         base_dir, session, cached_webfingers,
                                         person_cache,
                                         nickname, domain, port,
                                         post_json_object,
                                         None, True, False,
                                         http_prefix, project_version, 'inbox',
                                         yt_replace_domain,
                                         twitter_replacement_domain,
                                         show_published_date_only,
                                         peertube_instances,
                                         allow_local_network_access,
                                         theme_name, system_language,
                                         max_like_count,
                                         False, authorized,
                                         False, False, False, False,
                                         cw_lists, lists_enabled) + postStr

    # show the following posts
    postFilename = locatePost(base_dir, nickname, domain, messageId)
    if postFilename:
        # is there a replies file for this post?
        repliesFilename = postFilename.replace('.json', '.replies')
        if os.path.isfile(repliesFilename):
            # get items from the replies file
            repliesJson = {
                'orderedItems': []
            }
            populateRepliesJson(base_dir, nickname, domain,
                                repliesFilename, authorized, repliesJson)
            # add items to the html output
            for item in repliesJson['orderedItems']:
                postStr += \
                    individualPostAsHtml(signing_priv_key_pem,
                                         True, recentPostsCache,
                                         max_recent_posts,
                                         translate, None,
                                         base_dir, session, cached_webfingers,
                                         person_cache,
                                         nickname, domain, port, item,
                                         None, True, False,
                                         http_prefix, project_version, 'inbox',
                                         yt_replace_domain,
                                         twitter_replacement_domain,
                                         show_published_date_only,
                                         peertube_instances,
                                         allow_local_network_access,
                                         theme_name, system_language,
                                         max_like_count,
                                         False, authorized,
                                         False, False, False, False,
                                         cw_lists, lists_enabled)
    cssFilename = base_dir + '/epicyon-profile.css'
    if os.path.isfile(base_dir + '/epicyon.css'):
        cssFilename = base_dir + '/epicyon.css'

    instanceTitle = \
        getConfigParam(base_dir, 'instanceTitle')
    metadataStr = _htmlPostMetadataOpenGraph(domain, originalPostJson)
    headerStr = htmlHeaderWithExternalStyle(cssFilename,
                                            instanceTitle, metadataStr)
    return headerStr + postStr + htmlFooter()


def htmlPostReplies(cssCache: {},
                    recentPostsCache: {}, max_recent_posts: int,
                    translate: {}, base_dir: str,
                    session, cached_webfingers: {}, person_cache: {},
                    nickname: str, domain: str, port: int, repliesJson: {},
                    http_prefix: str, project_version: str,
                    yt_replace_domain: str,
                    twitter_replacement_domain: str,
                    show_published_date_only: bool,
                    peertube_instances: [],
                    allow_local_network_access: bool,
                    theme_name: str, system_language: str,
                    max_like_count: int,
                    signing_priv_key_pem: str, cw_lists: {},
                    lists_enabled: str) -> str:
    """Show the replies to an individual post as html
    """
    repliesStr = ''
    if repliesJson.get('orderedItems'):
        for item in repliesJson['orderedItems']:
            repliesStr += \
                individualPostAsHtml(signing_priv_key_pem,
                                     True, recentPostsCache,
                                     max_recent_posts,
                                     translate, None,
                                     base_dir, session, cached_webfingers,
                                     person_cache,
                                     nickname, domain, port, item,
                                     None, True, False,
                                     http_prefix, project_version, 'inbox',
                                     yt_replace_domain,
                                     twitter_replacement_domain,
                                     show_published_date_only,
                                     peertube_instances,
                                     allow_local_network_access,
                                     theme_name, system_language,
                                     max_like_count,
                                     False, False, False, False, False, False,
                                     cw_lists, lists_enabled)

    cssFilename = base_dir + '/epicyon-profile.css'
    if os.path.isfile(base_dir + '/epicyon.css'):
        cssFilename = base_dir + '/epicyon.css'

    instanceTitle = getConfigParam(base_dir, 'instanceTitle')
    metadata = ''
    headerStr = \
        htmlHeaderWithExternalStyle(cssFilename, instanceTitle, metadata)
    return headerStr + repliesStr + htmlFooter()


def htmlEmojiReactionPicker(cssCache: {},
                            recentPostsCache: {}, max_recent_posts: int,
                            translate: {},
                            base_dir: str, session, cached_webfingers: {},
                            person_cache: {},
                            nickname: str, domain: str, port: int,
                            post_json_object: {}, http_prefix: str,
                            project_version: str,
                            yt_replace_domain: str,
                            twitter_replacement_domain: str,
                            show_published_date_only: bool,
                            peertube_instances: [],
                            allow_local_network_access: bool,
                            theme_name: str, system_language: str,
                            max_like_count: int, signing_priv_key_pem: str,
                            cw_lists: {}, lists_enabled: str,
                            boxName: str, pageNumber: int) -> str:
    """Returns the emoji picker screen
    """
    reactedToPostStr = \
        '<br><center><label class="followText">' + \
        translate['Select reaction'].title() + '</label></center>\n' + \
        individualPostAsHtml(signing_priv_key_pem,
                             True, recentPostsCache,
                             max_recent_posts,
                             translate, None,
                             base_dir, session, cached_webfingers,
                             person_cache,
                             nickname, domain, port, post_json_object,
                             None, True, False,
                             http_prefix, project_version, 'inbox',
                             yt_replace_domain,
                             twitter_replacement_domain,
                             show_published_date_only,
                             peertube_instances,
                             allow_local_network_access,
                             theme_name, system_language,
                             max_like_count,
                             False, False, False, False, False, False,
                             cw_lists, lists_enabled)

    reactionsFilename = base_dir + '/emoji/reactions.json'
    if not os.path.isfile(reactionsFilename):
        reactionsFilename = base_dir + '/emoji/default_reactions.json'
    reactionsJson = loadJson(reactionsFilename)
    emojiPicksStr = ''
    baseUrl = '/users/' + nickname
    postId = removeIdEnding(post_json_object['id'])
    for category, item in reactionsJson.items():
        emojiPicksStr += '<div class="container">\n'
        for emojiContent in item:
            emojiContentEncoded = urllib.parse.quote_plus(emojiContent)
            emojiUrl = \
                baseUrl + '?react=' + postId + \
                '?actor=' + post_json_object['actor'] + \
                '?tl=' + boxName + \
                '?page=' + str(pageNumber) + \
                '?emojreact=' + emojiContentEncoded
            emojiLabel = '<label class="rlab">' + emojiContent + '</label>'
            emojiPicksStr += \
                '  <a href="' + emojiUrl + '">' + emojiLabel + '</a>\n'
        emojiPicksStr += '</div>\n'

    cssFilename = base_dir + '/epicyon-profile.css'
    if os.path.isfile(base_dir + '/epicyon.css'):
        cssFilename = base_dir + '/epicyon.css'

    # filename of the banner shown at the top
    bannerFile, _ = \
        getBannerFile(base_dir, nickname, domain, theme_name)

    instanceTitle = getConfigParam(base_dir, 'instanceTitle')
    metadata = ''
    headerStr = \
        htmlHeaderWithExternalStyle(cssFilename, instanceTitle, metadata)

    # banner
    headerStr += \
        '<header>\n' + \
        '<a href="/users/' + nickname + '/' + boxName + \
        '?page=' + str(pageNumber) + '" title="' + \
        translate['Switch to timeline view'] + '" alt="' + \
        translate['Switch to timeline view'] + '">\n'
    headerStr += '<img loading="lazy" class="timeline-banner" ' + \
        'alt="" ' + \
        'src="/users/' + nickname + '/' + bannerFile + '" /></a>\n' + \
        '</header>\n'

    return headerStr + reactedToPostStr + emojiPicksStr + htmlFooter()
