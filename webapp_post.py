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
from auth import create_password
from git import is_git_patch
from datetime import datetime
from cache import get_person_from_cache
from bookmarks import bookmarked_by_person
from like import liked_by_person
from like import no_of_likes
from follow import is_following_actor
from posts import post_is_muted
from posts import get_person_box
from posts import download_announce
from posts import populate_replies_json
from utils import remove_hash_from_post_id
from utils import remove_html
from utils import get_actor_languages_list
from utils import get_base_content_from_post
from utils import get_content_from_post
from utils import has_object_dict
from utils import update_announce_collection
from utils import is_pgp_encrypted
from utils import is_dm
from utils import reject_post_id
from utils import is_recent_post
from utils import get_config_param
from utils import get_full_domain
from utils import is_editor
from utils import locate_post
from utils import load_json
from utils import get_cached_post_directory
from utils import get_cached_post_filename
from utils import get_protocol_prefixes
from utils import is_news_post
from utils import is_blog_post
from utils import get_display_name
from utils import is_public_post
from utils import update_recent_posts_cache
from utils import remove_id_ending
from utils import get_nickname_from_actor
from utils import get_domain_from_actor
from utils import acct_dir
from utils import local_actor_url
from content import limit_repeated_words
from content import replace_emoji_from_tags
from content import html_replace_quote_marks
from content import html_replace_email_quote
from content import remove_text_formatting
from content import remove_long_words
from content import get_mentions_from_html
from content import switch_words
from person import is_person_snoozed
from person import get_person_avatar_url
from announce import announced_by_person
from webapp_utils import get_banner_file
from webapp_utils import get_avatar_image_url
from webapp_utils import update_avatar_image_cache
from webapp_utils import load_individual_post_as_html_from_cache
from webapp_utils import add_emoji_to_display_name
from webapp_utils import post_contains_public
from webapp_utils import get_content_warning_button
from webapp_utils import get_post_attachments_as_html
from webapp_utils import html_header_with_external_style
from webapp_utils import html_footer
from webapp_utils import get_broken_link_substitute
from webapp_media import add_embedded_elements
from webapp_question import insert_question
from devices import e2e_edecrypt_message_from_device
from webfinger import webfinger_handle
from speaker import update_speaker
from languages import auto_translate_post
from blocking import is_blocked
from blocking import add_cw_from_lists
from reaction import html_emoji_reactions


def _html_post_metadata_open_graph(domain: str, post_json_object: {}) -> str:
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
            actorNick = get_nickname_from_actor(attrib)
            actorDomain, _ = get_domain_from_actor(attrib)
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
            description = remove_html(objJson['content'])
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
                description += '\n\n' + remove_html(objJson['content'])
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


def _log_post_timing(enableTimingLog: bool, postStartTime,
                     debugId: str) -> None:
    """Create a log of timings for performance tuning
    """
    if not enableTimingLog:
        return
    timeDiff = int((time.time() - postStartTime) * 1000)
    if timeDiff > 100:
        print('TIMING INDIV ' + debugId + ' = ' + str(timeDiff))


def prepare_html_post_nickname(nickname: str, postHtml: str) -> str:
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


def prepare_post_from_html_cache(nickname: str, postHtml: str, boxName: str,
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
    return prepare_html_post_nickname(nickname, withPageNumber)


def _save_individual_post_as_html_to_cache(base_dir: str,
                                           nickname: str, domain: str,
                                           post_json_object: {},
                                           postHtml: str) -> bool:
    """Saves the given html for a post to a cache file
    This is so that it can be quickly reloaded on subsequent
    refresh of the timeline
    """
    htmlPostCacheDir = \
        get_cached_post_directory(base_dir, nickname, domain)
    cachedPostFilename = \
        get_cached_post_filename(base_dir, nickname, domain, post_json_object)

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


def _get_post_from_recent_cache(session,
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
                                recent_posts_cache: {},
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
            get_person_avatar_url(base_dir, postActor, person_cache,
                                  allowDownloads)

        _log_post_timing(enableTimingLog, postStartTime, '2.1')

    update_avatar_image_cache(signing_priv_key_pem,
                              session, base_dir, http_prefix,
                              postActor, avatarUrl, person_cache,
                              allowDownloads)

    _log_post_timing(enableTimingLog, postStartTime, '2.2')

    postHtml = \
        load_individual_post_as_html_from_cache(base_dir, nickname, domain,
                                                post_json_object)
    if not postHtml:
        return None

    postHtml = \
        prepare_post_from_html_cache(nickname, postHtml, boxName, pageNumber)
    update_recent_posts_cache(recent_posts_cache, max_recent_posts,
                              post_json_object, postHtml)
    _log_post_timing(enableTimingLog, postStartTime, '3')
    return postHtml


def _get_avatar_image_html(showAvatarOptions: bool,
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
            get_broken_link_substitute() + '/></a>\n'

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
                get_broken_link_substitute() + '/></a>\n'
        else:
            # don't link to the person options for the news account
            avatarLink += \
                '        <img loading="lazy" title="' + \
                showOptionsForThisPersonStr + '" ' + \
                'alt="👤 ' + \
                showOptionsForThisPersonStr + '" ' + \
                'src="' + avatarUrl + '" ' + avatarPosition + \
                get_broken_link_substitute() + '/>\n'
    return avatarLink.strip()


def _get_reply_icon_html(base_dir: str, nickname: str, domain: str,
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
    replyToLink = remove_hash_from_post_id(post_json_object['object']['id'])
    replyToLink = remove_id_ending(replyToLink)

    # see Mike MacGirvin's replyTo suggestion
    if post_json_object['object'].get('replyTo'):
        # check that the alternative replyTo url is not blocked
        blockNickname = \
            get_nickname_from_actor(post_json_object['object']['replyTo'])
        blockDomain, _ = \
            get_domain_from_actor(post_json_object['object']['replyTo'])
        if not is_blocked(base_dir, nickname, domain,
                          blockNickname, blockDomain, {}):
            replyToLink = post_json_object['object']['replyTo']

    if post_json_object['object'].get('attributedTo'):
        if isinstance(post_json_object['object']['attributedTo'], str):
            replyToLink += \
                '?mention=' + post_json_object['object']['attributedTo']
    content = get_base_content_from_post(post_json_object, system_language)
    if content:
        mentionedActors = \
            get_mentions_from_html(content,
                                   "<span class=\"h-card\"><a href=\"")
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
        if is_dm(post_json_object):
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


def _get_edit_icon_html(base_dir: str, nickname: str, domain_full: str,
                        post_json_object: {}, actorNickname: str,
                        translate: {}, isEvent: bool) -> str:
    """Returns html for the edit icon/button
    """
    editStr = ''
    actor = post_json_object['actor']
    # This should either be a post which you created,
    # or it could be generated from the newswire (see
    # _add_blogs_to_newswire) in which case anyone with
    # editor status should be able to alter it
    if (actor.endswith('/' + domain_full + '/users/' + nickname) or
        (is_editor(base_dir, nickname) and
         actor.endswith('/' + domain_full + '/users/news'))):

        post_id = remove_id_ending(post_json_object['object']['id'])

        if '/statuses/' not in post_id:
            return editStr

        if is_blog_post(post_json_object):
            editBlogPostStr = 'Edit blog post'
            if translate.get(editBlogPostStr):
                editBlogPostStr = translate[editBlogPostStr]
            if not is_news_post(post_json_object):
                editStr += \
                    '        ' + \
                    '<a class="imageAnchor" href="/users/' + \
                    nickname + \
                    '/tlblogs?editblogpost=' + \
                    post_id.split('/statuses/')[1] + \
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
                    post_id.split('/statuses/')[1] + \
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
                post_id.split('/statuses/')[1] + \
                '?actor=' + actorNickname + \
                '" title="' + editEventStr + '">' + \
                '<img loading="lazy" title="' + \
                editEventStr + '" alt="' + editEventStr + \
                ' |" src="/icons/edit.png"/></a>\n'
    return editStr


def _get_announce_icon_html(isAnnounced: bool,
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

    if announced_by_person(isAnnounced,
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
                remove_id_ending(announceJsonObject['id'])

    announcePostId = remove_hash_from_post_id(post_json_object['object']['id'])
    announcePostId = remove_id_ending(announcePostId)
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


def _get_like_icon_html(nickname: str, domain_full: str,
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
    likeCount = no_of_likes(post_json_object)

    _log_post_timing(enableTimingLog, postStartTime, '12.1')

    likeCountStr = ''
    if likeCount > 0:
        if likeCount <= max_like_count:
            likeCountStr = ' (' + str(likeCount) + ')'
        else:
            likeCountStr = ' (' + str(max_like_count) + '+)'
        if liked_by_person(post_json_object, nickname, domain_full):
            if likeCount == 1:
                # liked by the reader only
                likeCountStr = ''
            likeIcon = 'like.png'
            likeLink = 'unlike'
            likeTitle = 'Undo the like'
            if translate.get(likeTitle):
                likeTitle = translate[likeTitle]
            likeEmoji = '👍 '

    _log_post_timing(enableTimingLog, postStartTime, '12.2')

    likeStr = ''
    if likeCountStr:
        # show the number of likes next to icon
        likeStr += '<label class="likesCount">'
        likeStr += likeCountStr.replace('(', '').replace(')', '').strip()
        likeStr += '</label>\n'
    like_postId = remove_hash_from_post_id(post_json_object['id'])
    like_postId = remove_id_ending(like_postId)
    likeStr += \
        '        <a class="imageAnchor" href="/users/' + nickname + '?' + \
        likeLink + '=' + like_postId + \
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


def _get_bookmark_icon_html(nickname: str, domain_full: str,
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
    if bookmarked_by_person(post_json_object, nickname, domain_full):
        bookmarkIcon = 'bookmark.png'
        bookmarkLink = 'unbookmark'
        bookmarkEmoji = '🔖 '
        bookmarkTitle = 'Undo the bookmark'
        if translate.get(bookmarkTitle):
            bookmarkTitle = translate[bookmarkTitle]
    _log_post_timing(enableTimingLog, postStartTime, '12.6')
    bookmarkPostId = remove_hash_from_post_id(post_json_object['object']['id'])
    bookmarkPostId = remove_id_ending(bookmarkPostId)
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


def _get_reaction_icon_html(nickname: str, domain_full: str,
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
    _log_post_timing(enableTimingLog, postStartTime, '12.65')
    reaction_postId = \
        remove_hash_from_post_id(post_json_object['object']['id'])
    reaction_postId = remove_id_ending(reaction_postId)
    reactionStr = \
        '        <a class="imageAnchor" href="/users/' + nickname + \
        '?selreact=' + reaction_postId + pageNumberParam + \
        '?actor=' + post_json_object['actor'] + \
        '?bm=' + timelinePostReaction + \
        '?tl=' + boxName + '" title="' + reactionTitle + '">\n'
    reactionStr += \
        '        ' + \
        '<img loading="lazy" title="' + reactionTitle + '" alt="' + \
        reactionTitle + ' |" src="/icons' + \
        '/' + reactionIcon + '"/></a>\n'
    return reactionStr


def _get_mute_icon_html(is_muted: bool,
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

    if not is_muted:
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


def _get_delete_icon_html(nickname: str, domain_full: str,
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
            if not is_news_post(post_json_object):
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


def _get_published_date_str(post_json_object: {},
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


def _get_blog_citations_html(boxName: str,
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


def _boost_own_post_html(translate: {}) -> str:
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


def _announce_unattributed_html(translate: {},
                                post_json_object: {}) -> str:
    """Returns the html for an announce title where there
    is no attribution on the announced post
    """
    announcesStr = 'announces'
    if translate.get(announcesStr):
        announcesStr = translate[announcesStr]
    post_id = remove_id_ending(post_json_object['object']['id'])
    return '    <img loading="lazy" title="' + \
        announcesStr + '" alt="' + \
        announcesStr + '" src="/icons' + \
        '/repeat_inactive.png" ' + \
        'class="announceOrReply"/>\n' + \
        '      <a href="' + post_id + \
        '" class="announceOrReply">@unattributed</a>\n'


def _announce_with_display_name_html(translate: {},
                                     post_json_object: {},
                                     announceDisplayName: str) -> str:
    """Returns html for an announce having a display name
    """
    announcesStr = 'announces'
    if translate.get(announcesStr):
        announcesStr = translate[announcesStr]
    post_id = remove_id_ending(post_json_object['object']['id'])
    return '          <img loading="lazy" title="' + \
        announcesStr + '" alt="' + \
        announcesStr + '" src="/' + \
        'icons/repeat_inactive.png" ' + \
        'class="announceOrReply"/>\n' + \
        '        <a href="' + post_id + '" ' + \
        'class="announceOrReply">' + announceDisplayName + '</a>\n'


def _get_post_title_announce_html(base_dir: str,
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
        titleStr += _announce_unattributed_html(translate, post_json_object)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    attributedTo = ''
    if isinstance(objJson['attributedTo'], str):
        attributedTo = objJson['attributedTo']

    # boosting your own post
    if attributedTo.startswith(postActor):
        titleStr += _boost_own_post_html(translate)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    # boosting another person's post
    _log_post_timing(enableTimingLog, postStartTime, '13.2')
    announceNickname = None
    if attributedTo:
        announceNickname = get_nickname_from_actor(attributedTo)
    if not announceNickname:
        titleStr += _announce_unattributed_html(translate, post_json_object)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    announceDomain, announcePort = get_domain_from_actor(attributedTo)
    get_person_from_cache(base_dir, attributedTo, person_cache, allowDownloads)
    announceDisplayName = \
        get_display_name(base_dir, attributedTo, person_cache)
    if not announceDisplayName:
        announceDisplayName = announceNickname + '@' + announceDomain

    _log_post_timing(enableTimingLog, postStartTime, '13.3')

    # add any emoji to the display name
    if ':' in announceDisplayName:
        announceDisplayName = \
            add_emoji_to_display_name(None, base_dir, http_prefix,
                                      nickname, domain,
                                      announceDisplayName, False)
    _log_post_timing(enableTimingLog, postStartTime, '13.3.1')
    titleStr += \
        _announce_with_display_name_html(translate, post_json_object,
                                         announceDisplayName)
    # show avatar of person replied to
    announceActor = attributedTo
    announceAvatarUrl = \
        get_person_avatar_url(base_dir, announceActor,
                              person_cache, allowDownloads)

    _log_post_timing(enableTimingLog, postStartTime, '13.4')

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
            get_broken_link_substitute() + '/></a>\n    </div>\n'

    return (titleStr, replyAvatarImageInPost,
            containerClassIcons, containerClass)


def _reply_to_yourself_html(translate: {}) -> str:
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


def _reply_to_unknown_html(translate: {},
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


def _reply_with_unknown_path_html(translate: {},
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


def _get_reply_html(translate: {},
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


def _get_post_title_reply_html(base_dir: str,
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
        titleStr += _reply_to_yourself_html(translate)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    # has a reply
    if '/statuses/' not in objJson['inReplyTo']:
        postDomain = objJson['inReplyTo']
        prefixes = get_protocol_prefixes()
        for prefix in prefixes:
            postDomain = postDomain.replace(prefix, '')
        if '/' in postDomain:
            postDomain = postDomain.split('/', 1)[0]
        if postDomain:
            titleStr += \
                _reply_with_unknown_path_html(translate,
                                              post_json_object, postDomain)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    inReplyTo = objJson['inReplyTo']
    replyActor = inReplyTo.split('/statuses/')[0]
    replyNickname = get_nickname_from_actor(replyActor)
    if not replyNickname:
        titleStr += _reply_to_unknown_html(translate, post_json_object)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    replyDomain, replyPort = get_domain_from_actor(replyActor)
    if not (replyNickname and replyDomain):
        titleStr += _reply_to_unknown_html(translate, post_json_object)
        return (titleStr, replyAvatarImageInPost,
                containerClassIcons, containerClass)

    get_person_from_cache(base_dir, replyActor, person_cache, allowDownloads)
    replyDisplayName = get_display_name(base_dir, replyActor, person_cache)
    if not replyDisplayName:
        replyDisplayName = replyNickname + '@' + replyDomain

    # add emoji to the display name
    if ':' in replyDisplayName:
        _log_post_timing(enableTimingLog, postStartTime, '13.5')

        replyDisplayName = \
            add_emoji_to_display_name(None, base_dir, http_prefix,
                                      nickname, domain,
                                      replyDisplayName, False)
        _log_post_timing(enableTimingLog, postStartTime, '13.6')

    titleStr += _get_reply_html(translate, inReplyTo, replyDisplayName)

    _log_post_timing(enableTimingLog, postStartTime, '13.7')

    # show avatar of person replied to
    replyAvatarUrl = \
        get_person_avatar_url(base_dir, replyActor, person_cache,
                              allowDownloads)

    _log_post_timing(enableTimingLog, postStartTime, '13.8')

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
            '" alt=" "' + avatarPosition + get_broken_link_substitute() + \
            '/></a>\n        </div>\n'

    return (titleStr, replyAvatarImageInPost,
            containerClassIcons, containerClass)


def _get_post_title_html(base_dir: str,
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
        return _get_post_title_announce_html(base_dir,
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

    return _get_post_title_reply_html(base_dir,
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


def _get_footer_with_icons(showIcons: bool,
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
    if not is_news_post(post_json_object):
        footerStr += '        <a href="' + publishedLink + '" class="' + \
            timeClass + '">' + publishedStr + '</a>\n'
    else:
        footerStr += '        <a href="' + \
            publishedLink.replace('/news/', '/news/statuses/') + \
            '" class="' + timeClass + '">' + publishedStr + '</a>\n'
    footerStr += '      </div>\n'
    footerStr += '      </nav>\n'
    return footerStr


def individual_post_as_html(signing_priv_key_pem: str,
                            allowDownloads: bool,
                            recent_posts_cache: {}, max_recent_posts: int,
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
    if is_person_snoozed(base_dir, nickname, domain, postActor):
        return ''

    # if downloads of avatar images aren't enabled then we can do more
    # accurate timing of different parts of the code
    enableTimingLog = not allowDownloads

    _log_post_timing(enableTimingLog, postStartTime, '1')

    avatarPosition = ''
    messageId = ''
    if post_json_object.get('id'):
        messageId = remove_hash_from_post_id(post_json_object['id'])
        messageId = remove_id_ending(messageId)

    _log_post_timing(enableTimingLog, postStartTime, '2')

    messageIdStr = ''
    if messageId:
        messageIdStr = ';' + messageId

    domain_full = get_full_domain(domain, port)

    pageNumberParam = ''
    if pageNumber:
        pageNumberParam = '?page=' + str(pageNumber)

    # get the html post from the recent posts cache if it exists there
    postHtml = \
        _get_post_from_recent_cache(session, base_dir,
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
                                    recent_posts_cache,
                                    max_recent_posts,
                                    signing_priv_key_pem)
    if postHtml:
        return postHtml
    if useCacheOnly and post_json_object['type'] != 'Announce':
        return ''

    _log_post_timing(enableTimingLog, postStartTime, '4')

    avatarUrl = \
        get_avatar_image_url(session,
                             base_dir, http_prefix,
                             postActor, person_cache,
                             avatarUrl, allowDownloads,
                             signing_priv_key_pem)

    _log_post_timing(enableTimingLog, postStartTime, '5')

    # get the display name
    if domain_full not in postActor:
        # lookup the correct webfinger for the postActor
        postActorNickname = get_nickname_from_actor(postActor)
        postActorDomain, postActorPort = get_domain_from_actor(postActor)
        postActorDomainFull = get_full_domain(postActorDomain, postActorPort)
        postActorHandle = postActorNickname + '@' + postActorDomainFull
        postActorWf = \
            webfinger_handle(session, postActorHandle, http_prefix,
                             cached_webfingers,
                             domain, __version__, False, False,
                             signing_priv_key_pem)

        avatarUrl2 = None
        displayName = None
        if postActorWf:
            originDomain = domain
            (inboxUrl, pubKeyId, pubKey, fromPersonId, sharedInbox, avatarUrl2,
             displayName, _) = get_person_box(signing_priv_key_pem,
                                              originDomain,
                                              base_dir, session,
                                              postActorWf,
                                              person_cache,
                                              project_version,
                                              http_prefix,
                                              nickname, domain,
                                              'outbox', 72367)

        _log_post_timing(enableTimingLog, postStartTime, '6')

        if avatarUrl2:
            avatarUrl = avatarUrl2
        if displayName:
            # add any emoji to the display name
            if ':' in displayName:
                displayName = \
                    add_emoji_to_display_name(session, base_dir, http_prefix,
                                              nickname, domain,
                                              displayName, False)

    _log_post_timing(enableTimingLog, postStartTime, '7')

    avatarLink = \
        _get_avatar_image_html(showAvatarOptions,
                               nickname, domain_full,
                               avatarUrl, postActor,
                               translate, avatarPosition,
                               pageNumber, messageIdStr)

    avatarImageInPost = \
        '      <div class="timeline-avatar">' + avatarLink + '</div>\n'

    timelinePostBookmark = remove_id_ending(post_json_object['id'])
    timelinePostBookmark = timelinePostBookmark.replace('://', '-')
    timelinePostBookmark = timelinePostBookmark.replace('/', '-')

    # If this is the inbox timeline then don't show the repeat icon on any DMs
    showRepeatIcon = showRepeats
    isPublicRepeat = False
    postIsDM = is_dm(post_json_object)
    if showRepeats:
        if postIsDM:
            showRepeatIcon = False
        else:
            if not is_public_post(post_json_object):
                isPublicRepeat = True

    titleStr = ''
    galleryStr = ''
    isAnnounced = False
    announceJsonObject = None
    if post_json_object['type'] == 'Announce':
        announceJsonObject = post_json_object.copy()
        blockedCache = {}
        post_jsonAnnounce = \
            download_announce(session, base_dir, http_prefix,
                              nickname, domain, post_json_object,
                              project_version, translate,
                              yt_replace_domain,
                              twitter_replacement_domain,
                              allow_local_network_access,
                              recent_posts_cache, False,
                              system_language,
                              domain_full, person_cache,
                              signing_priv_key_pem,
                              blockedCache)
        if not post_jsonAnnounce:
            # if the announce could not be downloaded then mark it as rejected
            announcedPostId = remove_id_ending(post_json_object['id'])
            reject_post_id(base_dir, nickname, domain, announcedPostId,
                           recent_posts_cache)
            return ''
        post_json_object = post_jsonAnnounce

        # is the announced post in the html cache?
        postHtml = \
            _get_post_from_recent_cache(session, base_dir,
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
                                        recent_posts_cache,
                                        max_recent_posts,
                                        signing_priv_key_pem)
        if postHtml:
            return postHtml

        announceFilename = \
            locate_post(base_dir, nickname, domain, post_json_object['id'])
        if announceFilename:
            update_announce_collection(recent_posts_cache,
                                       base_dir, announceFilename,
                                       postActor, nickname,
                                       domain_full, False)

            # create a file for use by text-to-speech
            if is_recent_post(post_json_object, 3):
                if post_json_object.get('actor'):
                    if not os.path.isfile(announceFilename + '.tts'):
                        update_speaker(base_dir, http_prefix,
                                       nickname, domain, domain_full,
                                       post_json_object, person_cache,
                                       translate, post_json_object['actor'],
                                       theme_name)
                        with open(announceFilename + '.tts', 'w+') as ttsFile:
                            ttsFile.write('\n')

        isAnnounced = True

    _log_post_timing(enableTimingLog, postStartTime, '8')

    if not has_object_dict(post_json_object):
        return ''

    # if this post should be public then check its recipients
    if showPublicOnly:
        if not post_contains_public(post_json_object):
            return ''

    isModerationPost = False
    if post_json_object['object'].get('moderationStatus'):
        isModerationPost = True
    containerClass = 'container'
    containerClassIcons = 'containericons'
    timeClass = 'time-right'
    actorNickname = get_nickname_from_actor(postActor)
    if not actorNickname:
        # single user instance
        actorNickname = 'dev'
    actorDomain, actorPort = get_domain_from_actor(postActor)

    displayName = get_display_name(base_dir, postActor, person_cache)
    if displayName:
        if ':' in displayName:
            displayName = \
                add_emoji_to_display_name(session, base_dir, http_prefix,
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
    _log_post_timing(enableTimingLog, postStartTime, '9')

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
    if is_public_post(post_json_object):
        publicReply = True
    replyStr = _get_reply_icon_html(base_dir, nickname, domain,
                                    publicReply,
                                    showIcons, commentsEnabled,
                                    post_json_object, pageNumberParam,
                                    translate, system_language,
                                    conversationId)

    _log_post_timing(enableTimingLog, postStartTime, '10')

    editStr = _get_edit_icon_html(base_dir, nickname, domain_full,
                                  post_json_object, actorNickname,
                                  translate, False)

    _log_post_timing(enableTimingLog, postStartTime, '11')

    announceStr = \
        _get_announce_icon_html(isAnnounced,
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

    _log_post_timing(enableTimingLog, postStartTime, '12')

    # whether to show a like button
    hideLikeButtonFile = \
        acct_dir(base_dir, nickname, domain) + '/.hideLikeButton'
    showLikeButton = True
    if os.path.isfile(hideLikeButtonFile):
        showLikeButton = False

    # whether to show a reaction button
    hideReactionButtonFile = \
        acct_dir(base_dir, nickname, domain) + '/.hideReactionButton'
    showReactionButton = True
    if os.path.isfile(hideReactionButtonFile):
        showReactionButton = False

    likeJsonObject = post_json_object
    if announceJsonObject:
        likeJsonObject = announceJsonObject
    likeStr = _get_like_icon_html(nickname, domain_full,
                                  isModerationPost,
                                  showLikeButton,
                                  likeJsonObject,
                                  enableTimingLog,
                                  postStartTime,
                                  translate, pageNumberParam,
                                  timelinePostBookmark,
                                  boxName, max_like_count)

    _log_post_timing(enableTimingLog, postStartTime, '12.5')

    bookmarkStr = \
        _get_bookmark_icon_html(nickname, domain_full,
                                post_json_object,
                                isModerationPost,
                                translate,
                                enableTimingLog,
                                postStartTime, boxName,
                                pageNumberParam,
                                timelinePostBookmark)

    _log_post_timing(enableTimingLog, postStartTime, '12.9')

    reactionStr = \
        _get_reaction_icon_html(nickname, domain_full,
                                post_json_object,
                                isModerationPost,
                                showReactionButton,
                                translate,
                                enableTimingLog,
                                postStartTime, boxName,
                                pageNumberParam,
                                timelinePostBookmark)

    _log_post_timing(enableTimingLog, postStartTime, '12.10')

    is_muted = post_is_muted(base_dir, nickname, domain,
                             post_json_object, messageId)

    _log_post_timing(enableTimingLog, postStartTime, '13')

    muteStr = \
        _get_mute_icon_html(is_muted,
                            postActor,
                            messageId,
                            nickname, domain_full,
                            allow_deletion,
                            pageNumberParam,
                            boxName,
                            timelinePostBookmark,
                            translate)

    deleteStr = \
        _get_delete_icon_html(nickname, domain_full,
                              allow_deletion,
                              postActor,
                              messageId,
                              post_json_object,
                              pageNumberParam,
                              translate)

    _log_post_timing(enableTimingLog, postStartTime, '13.1')

    # get the title: x replies to y, x announces y, etc
    (titleStr2,
     replyAvatarImageInPost,
     containerClassIcons,
     containerClass) = _get_post_title_html(base_dir,
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

    _log_post_timing(enableTimingLog, postStartTime, '14')

    attachmentStr, galleryStr = \
        get_post_attachments_as_html(post_json_object, boxName, translate,
                                     is_muted, avatarLink,
                                     replyStr, announceStr, likeStr,
                                     bookmarkStr, deleteStr, muteStr)

    publishedStr = \
        _get_published_date_str(post_json_object, show_published_date_only)

    _log_post_timing(enableTimingLog, postStartTime, '15')

    publishedLink = messageId
    # blog posts should have no /statuses/ in their link
    if is_blog_post(post_json_object):
        # is this a post to the local domain?
        if '://' + domain in messageId:
            publishedLink = messageId.replace('/statuses/', '/')
    # if this is a local link then make it relative so that it works
    # on clearnet or onion address
    if domain + '/users/' in publishedLink or \
       domain + ':' + str(port) + '/users/' in publishedLink:
        publishedLink = '/users/' + publishedLink.split('/users/')[1]

    if not is_news_post(post_json_object):
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

    newFooterStr = _get_footer_with_icons(showIcons,
                                          containerClassIcons,
                                          replyStr, announceStr,
                                          likeStr, reactionStr, bookmarkStr,
                                          deleteStr, muteStr, editStr,
                                          post_json_object, publishedLink,
                                          timeClass, publishedStr)
    if newFooterStr:
        footerStr = newFooterStr

    # add any content warning from the cwlists directory
    add_cw_from_lists(post_json_object, cw_lists, translate, lists_enabled)

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
            e2e_edecrypt_message_from_device(post_json_object['object'])
        post_json_object['object']['contentMap'][system_language] = \
            post_json_object['object']['content']

    domain_full = get_full_domain(domain, port)
    personUrl = local_actor_url(http_prefix, nickname, domain_full)
    actor_json = \
        get_person_from_cache(base_dir, personUrl, person_cache, False)
    languages_understood = []
    if actor_json:
        languages_understood = get_actor_languages_list(actor_json)
    contentStr = get_content_from_post(post_json_object, system_language,
                                       languages_understood)
    if not contentStr:
        contentStr = \
            auto_translate_post(base_dir, post_json_object,
                                system_language, translate)
        if not contentStr:
            return ''

    isPatch = is_git_patch(base_dir, nickname, domain,
                           post_json_object['object']['type'],
                           post_json_object['object']['summary'],
                           contentStr)

    _log_post_timing(enableTimingLog, postStartTime, '16')

    if not is_pgp_encrypted(contentStr):
        if not isPatch:
            objectContent = \
                remove_long_words(contentStr, 40, [])
            objectContent = remove_text_formatting(objectContent)
            objectContent = limit_repeated_words(objectContent, 6)
            objectContent = \
                switch_words(base_dir, nickname, domain, objectContent)
            objectContent = html_replace_email_quote(objectContent)
            objectContent = html_replace_quote_marks(objectContent)
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
        contentStr = add_embedded_elements(translate, contentStr,
                                           peertube_instances)
        contentStr = insert_question(base_dir, translate,
                                     nickname, domain, port,
                                     contentStr, post_json_object,
                                     pageNumber)
    else:
        postID = 'post' + str(create_password(8))
        contentStr = ''
        if post_json_object['object'].get('summary'):
            cwStr = str(post_json_object['object']['summary'])
            cwStr = \
                add_emoji_to_display_name(session, base_dir, http_prefix,
                                          nickname, domain,
                                          cwStr, False)
            contentStr += \
                '<label class="cw">' + cwStr + '</label>\n '
            if isModerationPost:
                containerClass = 'container report'
        # get the content warning text
        cwContentStr = objectContent + attachmentStr
        if not isPatch:
            cwContentStr = add_embedded_elements(translate, cwContentStr,
                                                 peertube_instances)
            cwContentStr = \
                insert_question(base_dir, translate, nickname, domain, port,
                                cwContentStr, post_json_object, pageNumber)
            cwContentStr = \
                switch_words(base_dir, nickname, domain, cwContentStr)
        if not is_blog_post(post_json_object):
            # get the content warning button
            contentStr += \
                get_content_warning_button(postID, translate, cwContentStr)
        else:
            contentStr += cwContentStr

    _log_post_timing(enableTimingLog, postStartTime, '17')

    if post_json_object['object'].get('tag') and not isPatch:
        contentStr = \
            replace_emoji_from_tags(session, base_dir, contentStr,
                                    post_json_object['object']['tag'],
                                    'content', False)

    if is_muted:
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
        _get_blog_citations_html(boxName, post_json_object, translate)

    postHtml = ''
    if boxName != 'tlmedia':
        reactionStr = ''
        if showIcons:
            reactionStr = \
                html_emoji_reactions(post_json_object, True, personUrl,
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

    _log_post_timing(enableTimingLog, postStartTime, '18')

    # save the created html to the recent posts cache
    if not showPublicOnly and storeToCache and \
       boxName != 'tlmedia' and boxName != 'tlbookmarks' and \
       boxName != 'bookmarks':
        _save_individual_post_as_html_to_cache(base_dir, nickname, domain,
                                               post_json_object, postHtml)
        update_recent_posts_cache(recent_posts_cache, max_recent_posts,
                                  post_json_object, postHtml)

    _log_post_timing(enableTimingLog, postStartTime, '19')

    return postHtml


def html_individual_post(css_cache: {},
                         recent_posts_cache: {}, max_recent_posts: int,
                         translate: {},
                         base_dir: str, session, cached_webfingers: {},
                         person_cache: {},
                         nickname: str, domain: str, port: int,
                         authorized: bool,
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
        byStrNickname = get_nickname_from_actor(byStr)
        byStrDomain, byStrPort = get_domain_from_actor(byStr)
        byStrDomain = get_full_domain(byStrDomain, byStrPort)
        byStrHandle = byStrNickname + '@' + byStrDomain
        if translate.get(byText):
            byText = translate[byText]
        postStr += \
            '<p>' + byText + ' <a href="' + byStr + '">@' + \
            byStrHandle + '</a>' + byTextExtra + '\n'

        domain_full = get_full_domain(domain, port)
        actor = '/users/' + nickname
        followStr = '  <form method="POST" ' + \
            'accept-charset="UTF-8" action="' + actor + '/searchhandle">\n'
        followStr += \
            '    <input type="hidden" name="actor" value="' + actor + '">\n'
        followStr += \
            '    <input type="hidden" name="searchtext" value="' + \
            byStrHandle + '">\n'
        if not is_following_actor(base_dir, nickname, domain_full, byStr):
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
        individual_post_as_html(signing_priv_key_pem,
                                True, recent_posts_cache, max_recent_posts,
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
    messageId = remove_id_ending(post_json_object['id'])

    # show the previous posts
    if has_object_dict(post_json_object):
        while post_json_object['object'].get('inReplyTo'):
            post_filename = \
                locate_post(base_dir, nickname, domain,
                            post_json_object['object']['inReplyTo'])
            if not post_filename:
                break
            post_json_object = load_json(post_filename)
            if post_json_object:
                postStr = \
                    individual_post_as_html(signing_priv_key_pem,
                                            True, recent_posts_cache,
                                            max_recent_posts,
                                            translate, None,
                                            base_dir, session,
                                            cached_webfingers,
                                            person_cache,
                                            nickname, domain, port,
                                            post_json_object,
                                            None, True, False,
                                            http_prefix, project_version,
                                            'inbox',
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
    post_filename = locate_post(base_dir, nickname, domain, messageId)
    if post_filename:
        # is there a replies file for this post?
        repliesFilename = post_filename.replace('.json', '.replies')
        if os.path.isfile(repliesFilename):
            # get items from the replies file
            repliesJson = {
                'orderedItems': []
            }
            populate_replies_json(base_dir, nickname, domain,
                                  repliesFilename, authorized, repliesJson)
            # add items to the html output
            for item in repliesJson['orderedItems']:
                postStr += \
                    individual_post_as_html(signing_priv_key_pem,
                                            True, recent_posts_cache,
                                            max_recent_posts,
                                            translate, None,
                                            base_dir, session,
                                            cached_webfingers,
                                            person_cache,
                                            nickname, domain, port, item,
                                            None, True, False,
                                            http_prefix, project_version,
                                            'inbox',
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
        get_config_param(base_dir, 'instanceTitle')
    metadataStr = _html_post_metadata_open_graph(domain, originalPostJson)
    headerStr = html_header_with_external_style(cssFilename,
                                                instanceTitle, metadataStr)
    return headerStr + postStr + html_footer()


def html_post_replies(css_cache: {},
                      recent_posts_cache: {}, max_recent_posts: int,
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
                individual_post_as_html(signing_priv_key_pem,
                                        True, recent_posts_cache,
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
                                        False, False, False, False,
                                        False, False,
                                        cw_lists, lists_enabled)

    cssFilename = base_dir + '/epicyon-profile.css'
    if os.path.isfile(base_dir + '/epicyon.css'):
        cssFilename = base_dir + '/epicyon.css'

    instanceTitle = get_config_param(base_dir, 'instanceTitle')
    metadata = ''
    headerStr = \
        html_header_with_external_style(cssFilename, instanceTitle, metadata)
    return headerStr + repliesStr + html_footer()


def html_emoji_reaction_picker(css_cache: {},
                               recent_posts_cache: {}, max_recent_posts: int,
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
        individual_post_as_html(signing_priv_key_pem,
                                True, recent_posts_cache,
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
    reactionsJson = load_json(reactionsFilename)
    emojiPicksStr = ''
    baseUrl = '/users/' + nickname
    post_id = remove_id_ending(post_json_object['id'])
    for category, item in reactionsJson.items():
        emojiPicksStr += '<div class="container">\n'
        for emojiContent in item:
            emojiContentEncoded = urllib.parse.quote_plus(emojiContent)
            emojiUrl = \
                baseUrl + '?react=' + post_id + \
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
        get_banner_file(base_dir, nickname, domain, theme_name)

    instanceTitle = get_config_param(base_dir, 'instanceTitle')
    metadata = ''
    headerStr = \
        html_header_with_external_style(cssFilename, instanceTitle, metadata)

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

    return headerStr + reactedToPostStr + emojiPicksStr + html_footer()
