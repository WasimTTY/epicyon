__filename__ = "blog.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.1.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@freedombone.net"
__status__ = "Production"

import os
from datetime import datetime

from content import replaceEmojiFromTags
from webinterface import contentWarningScriptOpen
from webinterface import getIconsDir
from webinterface import getPostAttachmentsAsHtml
from webinterface import htmlHeader
from webinterface import htmlFooter
from webinterface import addEmbeddedElements
from utils import getNicknameFromActor
from utils import getDomainFromActor
from utils import locatePost
from utils import loadJson
from posts import createBlogsTimeline


def noOfBlogReplies(baseDir: str, httpPrefix: str, translate: {},
                    nickname: str, domain: str, domainFull: str,
                    postId: str, depth=0) -> int:
    """Returns the number of replies on the post
    This is recursive, so can handle replies to replies
    """
    if depth > 4:
        return 0
    if not postId:
        return 0

    tryPostBox = ('tlblogs', 'inbox', 'outbox')
    boxFound = False
    for postBox in tryPostBox:
        postFilename = baseDir + '/accounts/' + \
            nickname + '@' + domain + '/' + postBox + '/' + \
            postId.replace('/', '#') + '.replies'
        if os.path.isfile(postFilename):
            boxFound = True
            break
    if not boxFound:
        # post may exist but has no replies
        for postBox in tryPostBox:
            postFilename = baseDir + '/accounts/' + \
                nickname + '@' + domain + '/' + postBox + '/' + \
                postId.replace('/', '#')
            if os.path.isfile(postFilename):
                return 1
        return 0

    removals = []
    replies = 0
    lines = []
    with open(postFilename, "r") as f:
        lines = f.readlines()
        for replyPostId in lines:
            replyPostId = replyPostId.replace('\n', '').replace('\r', '')
            replyPostId = replyPostId.replace('.json', '')
            if locatePost(baseDir, nickname, domain, replyPostId):
                replyPostId = replyPostId.replace('.replies', '')
                replies += 1 + noOfBlogReplies(baseDir, httpPrefix, translate,
                                               nickname, domain, domainFull,
                                               replyPostId, depth+1)
            else:
                # remove post which no longer exists
                removals.append(replyPostId)

    # remove posts from .replies file if they don't exist
    if lines and removals:
        print('Rewriting ' + postFilename + ' to remove ' +
              str(len(removals)) + ' entries')
        with open(postFilename, "w") as f:
            for replyPostId in lines:
                replyPostId = replyPostId.replace('\n', '').replace('\r', '')
                if replyPostId not in removals:
                    f.write(replyPostId + '\n')

    return replies


def getBlogReplies(baseDir: str, httpPrefix: str, translate: {},
                   nickname: str, domain: str, domainFull: str,
                   postId: str, depth=0) -> str:
    """Returns a string containing html blog posts
    """
    if depth > 4:
        return ''
    if not postId:
        return ''

    tryPostBox = ('tlblogs', 'inbox', 'outbox')
    boxFound = False
    for postBox in tryPostBox:
        postFilename = baseDir + '/accounts/' + \
            nickname + '@' + domain + '/' + postBox + '/' + \
            postId.replace('/', '#') + '.replies'
        if os.path.isfile(postFilename):
            boxFound = True
            break
    if not boxFound:
        # post may exist but has no replies
        for postBox in tryPostBox:
            postFilename = baseDir + '/accounts/' + \
                nickname + '@' + domain + '/' + postBox + '/' + \
                postId.replace('/', '#') + '.json'
            if os.path.isfile(postFilename):
                postFilename = baseDir + '/accounts/' + \
                    nickname + '@' + domain + \
                    '/postcache/' + \
                    postId.replace('/', '#') + '.html'
                if os.path.isfile(postFilename):
                    with open(postFilename, "r") as postFile:
                        return postFile.read() + '\n'
        return ''

    with open(postFilename, "r") as f:
        lines = f.readlines()
        repliesStr = ''
        for replyPostId in lines:
            replyPostId = replyPostId.replace('\n', '').replace('\r', '')
            replyPostId = replyPostId.replace('.json', '')
            replyPostId = replyPostId.replace('.replies', '')
            postFilename = baseDir + '/accounts/' + \
                nickname + '@' + domain + \
                '/postcache/' + \
                replyPostId.replace('/', '#') + '.html'
            if not os.path.isfile(postFilename):
                continue
            with open(postFilename, "r") as postFile:
                repliesStr += postFile.read() + '\n'
            rply = getBlogReplies(baseDir, httpPrefix, translate,
                                  nickname, domain, domainFull,
                                  replyPostId, depth+1)
            if rply not in repliesStr:
                repliesStr += rply

        # indicate the reply indentation level
        indentStr = '>'
        for indentLevel in range(depth):
            indentStr += ' >'

        repliesStr = repliesStr.replace(translate['SHOW MORE'], indentStr)
        return repliesStr.replace('?tl=outbox', '?tl=tlblogs')
    return ''


def htmlBlogPostContent(authorized: bool,
                        baseDir: str, httpPrefix: str, translate: {},
                        nickname: str, domain: str, domainFull: str,
                        postJsonObject: {},
                        handle: str, restrictToDomain: bool,
                        blogSeparator='<hr>') -> str:
    """Returns the content for a single blog post
    """
    linkedAuthor = False
    actor = ''
    blogStr = ''
    messageLink = ''
    if postJsonObject['object'].get('id'):
        messageLink = postJsonObject['object']['id'].replace('/statuses/', '/')
    titleStr = ''
    if postJsonObject['object'].get('summary'):
        titleStr = postJsonObject['object']['summary']
        blogStr += '<h1><a href="' + messageLink + '">' + \
            titleStr + '</a></h1>\n'

    # get the handle of the author
    if postJsonObject['object'].get('attributedTo'):
        actor = postJsonObject['object']['attributedTo']
        authorNickname = getNicknameFromActor(actor)
        if authorNickname:
            authorDomain, authorPort = getDomainFromActor(actor)
            if authorDomain:
                # author must be from the given domain
                if restrictToDomain and authorDomain != domain:
                    return ''
                handle = authorNickname + '@' + authorDomain
    else:
        # posts from the domain are expected to have an attributedTo field
        if restrictToDomain:
            return ''

    if postJsonObject['object'].get('published'):
        if 'T' in postJsonObject['object']['published']:
            blogStr += '<h3>' + \
                postJsonObject['object']['published'].split('T')[0]
            if handle:
                if handle.startswith(nickname + '@' + domain):
                    blogStr += ' <a href="' + httpPrefix + '://' + \
                        domainFull + \
                        '/users/' + nickname + '">' + handle + '</a>'
                    linkedAuthor = True
                else:
                    if actor:
                        blogStr += ' <a href="' + actor + '">' + \
                            handle + '</a>'
                        linkedAuthor = True
                    else:
                        blogStr += ' ' + handle
            blogStr += '</h3>\n'

    avatarLink = ''
    replyStr = ''
    announceStr = ''
    likeStr = ''
    bookmarkStr = ''
    deleteStr = ''
    muteStr = ''
    isMuted = False
    attachmentStr, galleryStr = getPostAttachmentsAsHtml(postJsonObject,
                                                         'tlblogs', translate,
                                                         isMuted, avatarLink,
                                                         replyStr, announceStr,
                                                         likeStr, bookmarkStr,
                                                         deleteStr, muteStr)
    if attachmentStr:
        blogStr += '<br><center>' + attachmentStr + '</center>'

    if postJsonObject['object'].get('content'):
        contentStr = addEmbeddedElements(translate,
                                         postJsonObject['object']['content'])
        if postJsonObject['object'].get('tag'):
            contentStr = replaceEmojiFromTags(contentStr,
                                              postJsonObject['object']['tag'],
                                              'content')
        blogStr += '<br>' + contentStr + '\n'

    blogStr += '<br>\n'

    if not linkedAuthor:
        blogStr += '<p class="about"><a class="about" href="' + \
            httpPrefix + '://' + domainFull + \
            '/users/' + nickname + '">' + translate['About the author'] + \
            '</a></p>\n'

    replies = noOfBlogReplies(baseDir, httpPrefix, translate,
                              nickname, domain, domainFull,
                              postJsonObject['object']['id'])

    # separator between blogs should be centered
    if '<center>' not in blogSeparator:
        blogSeparator = '<center>' + blogSeparator + '</center>'

    if replies == 0:
        blogStr += blogSeparator + '\n'
        return blogStr

    if not authorized:
        blogStr += '<p class="blogreplies">' + \
            translate['Replies'].lower() + ': ' + str(replies) + '</p>'
        blogStr += '<br><br><br>' + blogSeparator + '\n'
    else:
        blogStr += blogSeparator + '<h1>' + translate['Replies'] + '</h1>\n'
        blogStr += '<script>' + contentWarningScriptOpen() + '</script>\n'
        if not titleStr:
            blogStr += getBlogReplies(baseDir, httpPrefix, translate,
                                      nickname, domain, domainFull,
                                      postJsonObject['object']['id'])
        else:
            blogRepliesStr = getBlogReplies(baseDir, httpPrefix, translate,
                                            nickname, domain, domainFull,
                                            postJsonObject['object']['id'])
            blogStr += blogRepliesStr.replace('>' + titleStr + '<', '')

    return blogStr


def htmlBlogPostRSS(authorized: bool,
                    baseDir: str, httpPrefix: str, translate: {},
                    nickname: str, domain: str, domainFull: str,
                    postJsonObject: {},
                    handle: str, restrictToDomain: bool) -> str:
    """Returns the RSS feed for a single blog post
    """
    messageLink = ''
    if postJsonObject['object'].get('id'):
        messageLink = postJsonObject['object']['id'].replace('/statuses/', '/')
        if not restrictToDomain or \
           (restrictToDomain and '/' + domain in messageLink):
            if postJsonObject['object'].get('summary'):
                published = postJsonObject['object']['published']
                pubDate = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
                titleStr = postJsonObject['object']['summary']
                rssDateStr = pubDate.strftime("%a, %d %b %Y %H:%M:%S UT")
                rssStr = '     <item>'
                rssStr += '         <title>' + titleStr + '</title>'
                rssStr += '         <link>' + messageLink + '</link>'
                rssStr += '         <pubDate>' + rssDateStr + '</pubDate>'
                rssStr += '     </item>'
    return rssStr


def htmlBlogPost(authorized: bool,
                 baseDir: str, httpPrefix: str, translate: {},
                 nickname: str, domain: str, domainFull: str,
                 postJsonObject: {}) -> str:
    """Returns a html blog post
    """
    blogStr = ''

    cssFilename = baseDir + '/epicyon-blog.css'
    if os.path.isfile(baseDir + '/blog.css'):
        cssFilename = baseDir + '/blog.css'
    with open(cssFilename, 'r') as cssFile:
        blogCSS = cssFile.read()
        blogStr = htmlHeader(cssFilename, blogCSS)
        blogStr = blogStr.replace('.cwText', '.cwTextInactive')

        blogStr += htmlBlogPostContent(authorized, baseDir,
                                       httpPrefix, translate,
                                       nickname, domain,
                                       domainFull, postJsonObject,
                                       None, False)

        # show rss link
        iconsDir = getIconsDir(baseDir)
        blogStr += '<p class="rssfeed">'
        blogStr += '<a href="' + httpPrefix + '://' + \
            domainFull + '/blog/' + nickname + '/rss.xml">'
        blogStr += '<img loading="lazy" alt="RSS" title="RSS" src="/' + \
            iconsDir + '/rss.png" />'
        blogStr += '</a></p>'

        return blogStr + htmlFooter()
    return None


def htmlBlogPage(authorized: bool, session,
                 baseDir: str, httpPrefix: str, translate: {},
                 nickname: str, domain: str, port: int,
                 noOfItems: int, pageNumber: int) -> str:
    """Returns a html blog page containing posts
    """
    if ' ' in nickname or '@' in nickname or \
       '\n' in nickname or '\r' in nickname:
        return None
    blogStr = ''

    cssFilename = baseDir + '/epicyon-profile.css'
    if os.path.isfile(baseDir + '/epicyon.css'):
        cssFilename = baseDir + '/epicyon.css'
    with open(cssFilename, 'r') as cssFile:
        blogCSS = cssFile.read()
        blogStr = htmlHeader(cssFilename, blogCSS)
        blogStr = blogStr.replace('.cwText', '.cwTextInactive')

        blogsIndex = baseDir + '/accounts/' + \
            nickname + '@' + domain + '/tlblogs.index'
        if not os.path.isfile(blogsIndex):
            return blogStr + htmlFooter()

        timelineJson = createBlogsTimeline(session, baseDir,
                                           nickname, domain, port,
                                           httpPrefix,
                                           noOfItems, False, False,
                                           pageNumber)

        if not timelineJson:
            return blogStr + htmlFooter()

        domainFull = domain
        if port:
            if port != 80 and port != 443:
                domainFull = domain + ':' + str(port)

        # show previous and next buttons
        if pageNumber is not None:
            iconsDir = getIconsDir(baseDir)
            navigateStr = '<p>'
            if pageNumber > 1:
                # show previous button
                navigateStr += '<a href="' + httpPrefix + '://' + \
                    domainFull + '/blog/' + \
                    nickname + '?page=' + str(pageNumber-1) + '">' + \
                    '<img loading="lazy" alt="<" title="<" ' + \
                    'src="/' + iconsDir + \
                    '/prev.png" class="buttonprev"/></a>\n'
            if len(timelineJson['orderedItems']) >= noOfItems:
                # show next button
                navigateStr += '<a href="' + httpPrefix + '://' + \
                    domainFull + '/blog/' + nickname + \
                    '?page=' + str(pageNumber + 1) + '">' + \
                    '<img loading="lazy" alt=">" title=">" ' + \
                    'src="/' + iconsDir + \
                    '/prev.png" class="buttonnext"/></a>\n'
            navigateStr += '</p>'
            blogStr += navigateStr

        for item in timelineJson['orderedItems']:
            if item['type'] != 'Create':
                continue

            blogStr += htmlBlogPostContent(authorized, baseDir,
                                           httpPrefix, translate,
                                           nickname, domain,
                                           domainFull, item,
                                           None, True)

        if len(timelineJson['orderedItems']) >= noOfItems:
            blogStr += navigateStr

        # show rss link
        blogStr += '<p class="rssfeed">'
        blogStr += '<a href="' + httpPrefix + '://' + \
            domainFull + '/blog/' + nickname + '/rss.xml">'
        blogStr += '<img loading="lazy" alt="RSS" title="RSS" src="/' + \
            iconsDir + '/rss.png" />'
        blogStr += '</a></p>'

        return blogStr + htmlFooter()
    return None


def rssHeader(httpPrefix: str,
              nickname: str, domainFull: str, translate: {}) -> str:
    rssStr = "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>"
    rssStr += "<rss version=\"2.0\">"
    rssStr += '<channel>'
    rssStr += '    <title>' + translate['Blog'] + '</title>'
    rssStr += '    <link>' + httpPrefix + '://' + domainFull + \
        '/users/' + nickname + '/rss.xml' + '</link>'
    return rssStr


def rssFooter() -> str:
    rssStr = '</channel>'
    rssStr += '</rss>'
    return rssStr


def htmlBlogPageRSS(authorized: bool, session,
                    baseDir: str, httpPrefix: str, translate: {},
                    nickname: str, domain: str, port: int,
                    noOfItems: int, pageNumber: int) -> str:
    """Returns an rss feed containing posts
    """
    if ' ' in nickname or '@' in nickname or \
       '\n' in nickname or '\r' in nickname:
        return None

    domainFull = domain
    if port:
        if port != 80 and port != 443:
            domainFull = domain + ':' + str(port)

    blogRSS = rssHeader(httpPrefix, nickname, domainFull, translate)

    blogsIndex = baseDir + '/accounts/' + \
        nickname + '@' + domain + '/tlblogs.index'
    if not os.path.isfile(blogsIndex):
        return blogRSS + rssFooter()

    timelineJson = createBlogsTimeline(session, baseDir,
                                       nickname, domain, port,
                                       httpPrefix,
                                       noOfItems, False, False,
                                       pageNumber)

    if not timelineJson:
        return blogRSS + rssFooter()

    if pageNumber is not None:
        for item in timelineJson['orderedItems']:
            if item['type'] != 'Create':
                continue

            blogRSS += htmlBlogPostRSS(authorized, baseDir,
                                       httpPrefix, translate,
                                       nickname, domain,
                                       domainFull, item,
                                       None, True)

    return blogRSS + rssFooter()


def getBlogIndexesForAccounts(baseDir: str) -> {}:
    """ Get the index files for blogs for each account
    and add them to a dict
    """
    blogIndexes = {}
    for subdir, dirs, files in os.walk(baseDir + '/accounts'):
        for acct in dirs:
            if '@' not in acct:
                continue
            if 'inbox@' in acct:
                continue
            accountDir = os.path.join(baseDir + '/accounts', acct)
            blogsIndex = accountDir + '/tlblogs.index'
            if os.path.isfile(blogsIndex):
                blogIndexes[acct] = blogsIndex
    return blogIndexes


def noOfBlogAccounts(baseDir: str) -> int:
    """Returns the number of blog accounts
    """
    ctr = 0
    for subdir, dirs, files in os.walk(baseDir + '/accounts'):
        for acct in dirs:
            if '@' not in acct:
                continue
            if 'inbox@' in acct:
                continue
            accountDir = os.path.join(baseDir + '/accounts', acct)
            blogsIndex = accountDir + '/tlblogs.index'
            if os.path.isfile(blogsIndex):
                ctr += 1
    return ctr


def singleBlogAccountNickname(baseDir: str) -> str:
    """Returns the nickname of a single blog account
    """
    for subdir, dirs, files in os.walk(baseDir + '/accounts'):
        for acct in dirs:
            if '@' not in acct:
                continue
            if 'inbox@' in acct:
                continue
            accountDir = os.path.join(baseDir + '/accounts', acct)
            blogsIndex = accountDir + '/tlblogs.index'
            if os.path.isfile(blogsIndex):
                return acct.split('@')[0]
    return None


def htmlBlogView(authorized: bool,
                 session, baseDir: str, httpPrefix: str,
                 translate: {}, domain: str, port: int,
                 noOfItems: int) -> str:
    """Show the blog main page
    """
    blogStr = ''

    cssFilename = baseDir + '/epicyon-profile.css'
    if os.path.isfile(baseDir + '/epicyon.css'):
        cssFilename = baseDir + '/epicyon.css'
    with open(cssFilename, 'r') as cssFile:
        blogCSS = cssFile.read()
        blogStr = htmlHeader(cssFilename, blogCSS)

        if noOfBlogAccounts(baseDir) <= 1:
            nickname = singleBlogAccountNickname(baseDir)
            if nickname:
                return htmlBlogPage(authorized, session,
                                    baseDir, httpPrefix, translate,
                                    nickname, domain, port,
                                    noOfItems, 1)

        domainFull = domain
        if port:
            if port != 80 and port != 443:
                domainFull = domain + ':' + str(port)

        for subdir, dirs, files in os.walk(baseDir + '/accounts'):
            for acct in dirs:
                if '@' not in acct:
                    continue
                if 'inbox@' in acct:
                    continue
                accountDir = os.path.join(baseDir + '/accounts', acct)
                blogsIndex = accountDir + '/tlblogs.index'
                if os.path.isfile(blogsIndex):
                    blogStr += '<p class="blogaccount">'
                    blogStr += '<a href="' + \
                        httpPrefix + '://' + domainFull + '/blog/' + \
                        acct.split('@')[0] + '">' + acct + '</a>'
                    blogStr += '</p>'

        return blogStr + htmlFooter()
    return None


def htmlEditBlog(mediaInstance: bool, translate: {},
                 baseDir: str, httpPrefix: str,
                 path: str,
                 pageNumber: int,
                 nickname: str, domain: str,
                 postUrl: str) -> str:
    """Edit a blog post after it was created
    """
    postFilename = locatePost(baseDir, nickname, domain, postUrl)
    if not postFilename:
        print('Edit blog: Filename not found for ' + postUrl)
        return None

    postJsonObject = loadJson(postFilename)
    if not postJsonObject:
        print('Edit blog: json not loaded for ' + postFilename)
        return None

    iconsDir = getIconsDir(baseDir)

    editBlogText = '<p class="new-post-text">' + \
        translate['Write your post text below.'] + '</p>'

    if os.path.isfile(baseDir + '/accounts/newpost.txt'):
        with open(baseDir + '/accounts/newpost.txt', 'r') as file:
            editBlogText = '<p class="new-post-text">' + file.read() + '</p>'

    cssFilename = baseDir + '/epicyon-profile.css'
    if os.path.isfile(baseDir + '/epicyon.css'):
        cssFilename = baseDir + '/epicyon.css'
    with open(cssFilename, 'r') as cssFile:
        editBlogCSS = cssFile.read()
        if httpPrefix != 'https':
            editBlogCSS = editBlogCSS.replace('https://', httpPrefix+'://')

    if '?' in path:
        path = path.split('?')[0]
    pathBase = path

    editBlogImageSection = '    <div class="container">'
    editBlogImageSection += '      <label class="labels">' + \
        translate['Image description'] + '</label>'
    editBlogImageSection += '      <input type="text" name="imageDescription">'
    editBlogImageSection += \
        '      <input type="file" id="attachpic" name="attachpic"'
    editBlogImageSection += \
        '            accept=".png, .jpg, .jpeg, .gif, .webp, ' + \
        '.mp4, .webm, .ogv, .mp3, .ogg">'
    editBlogImageSection += '    </div>'

    placeholderMessage = translate['Write something'] + '...'
    endpoint = 'editblogpost'
    placeholderSubject = translate['Title']
    scopeIcon = 'scope_blog.png'
    scopeDescription = translate['Blog']

    dateAndLocation = ''
    dateAndLocation = '<div class="container">'

    dateAndLocation += \
        '<p><input type="checkbox" class="profilecheckbox" ' + \
        'name="schedulePost"><label class="labels">' + \
        translate['This is a scheduled post.'] + '</label></p>'

    dateAndLocation += \
        '<p><img loading="lazy" alt="" title="" ' + \
        'class="emojicalendar" src="/' + \
        iconsDir + '/calendar.png"/>'
    dateAndLocation += \
        '<label class="labels">' + translate['Date'] + ': </label>'
    dateAndLocation += '<input type="date" name="eventDate">'
    dateAndLocation += '<label class="labelsright">' + translate['Time'] + ':'
    dateAndLocation += '<input type="time" name="eventTime"></label></p>'
    dateAndLocation += '</div>'
    dateAndLocation += '<div class="container">'
    dateAndLocation += \
        '<br><label class="labels">' + translate['Location'] + ': </label>'
    dateAndLocation += '<input type="text" name="location">'
    dateAndLocation += '</div>'

    editBlogForm = htmlHeader(cssFilename, editBlogCSS)

    editBlogForm += \
        '<form enctype="multipart/form-data" method="POST" ' + \
        'accept-charset="UTF-8" action="' + \
        pathBase + '?' + endpoint + '?page=' + str(pageNumber) + '">'
    editBlogForm += \
        '  <input type="hidden" name="postUrl" value="' + postUrl + '">'
    editBlogForm += \
        '  <input type="hidden" name="pageNumber" value="' + \
        str(pageNumber) + '">'
    editBlogForm += '  <div class="vertical-center">'
    editBlogForm += \
        '    <label for="nickname"><b>' + editBlogText + '</b></label>'
    editBlogForm += '    <div class="container">'

    editBlogForm += '      <div class="dropbtn">'
    editBlogForm += \
        '        <img loading="lazy" alt="" title="" src="/' + iconsDir + \
        '/' + scopeIcon + '"/><b class="scope-desc">' + \
        scopeDescription + '</b>'
    editBlogForm += '      </div>'

    editBlogForm += '      <a href="' + pathBase + \
        '/searchemoji"><img loading="lazy" ' + \
        'class="emojisearch" src="/emoji/1F601.png" title="' + \
        translate['Search for emoji'] + '" alt="' + \
        translate['Search for emoji'] + '"/></a>'
    editBlogForm += '    </div>'
    editBlogForm += '    <div class="container"><center>'
    editBlogForm += '      <a href="' + pathBase + \
        '/inbox"><button class="cancelbtn">' + \
        translate['Cancel'] + '</button></a>'
    editBlogForm += '      <input type="submit" name="submitPost" value="' + \
        translate['Submit'] + '">'
    editBlogForm += '    </center></div>'
    if mediaInstance:
        editBlogForm += editBlogImageSection
    editBlogForm += \
        '    <label class="labels">' + placeholderSubject + '</label><br>'
    titleStr = ''
    if postJsonObject['object'].get('summary'):
        titleStr = postJsonObject['object']['summary']
    editBlogForm += \
        '    <input type="text" name="subject" value="' + titleStr + '">'
    editBlogForm += ''
    editBlogForm += '    <br><label class="labels">' + \
        placeholderMessage + '</label>'
    messageBoxHeight = 800

    contentStr = postJsonObject['object']['content']
    contentStr = contentStr.replace('<p>', '').replace('</p>', '\n')

    editBlogForm += \
        '    <textarea id="message" name="message" style="height:' + \
        str(messageBoxHeight) + 'px">' + contentStr + '</textarea>'
    editBlogForm += dateAndLocation
    if not mediaInstance:
        editBlogForm += editBlogImageSection
    editBlogForm += '  </div>'
    editBlogForm += '</form>'

    editBlogForm = editBlogForm.replace('<body>',
                                        '<body onload="focusOnMessage()">')

    editBlogForm += htmlFooter()
    return editBlogForm
