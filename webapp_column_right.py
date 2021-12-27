__filename__ = "webapp_column_right.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Web Interface Columns"

import os
from datetime import datetime
from content import removeLongWords
from content import limitRepeatedWords
from utils import get_fav_filename_from_url
from utils import get_base_content_from_post
from utils import remove_html
from utils import locate_post
from utils import load_json
from utils import votesOnNewswireItem
from utils import get_nickname_from_actor
from utils import is_editor
from utils import get_config_param
from utils import remove_domain_port
from utils import acct_dir
from posts import isModerator
from newswire import getNewswireFaviconUrl
from webapp_utils import getRightImageFile
from webapp_utils import htmlHeaderWithExternalStyle
from webapp_utils import htmlFooter
from webapp_utils import getBannerFile
from webapp_utils import htmlPostSeparator
from webapp_utils import headerButtonsFrontScreen
from webapp_utils import editTextField


def _votesIndicator(totalVotes: int, positive_voting: bool) -> str:
    """Returns an indicator of the number of votes on a newswire item
    """
    if totalVotes <= 0:
        return ''
    totalVotesStr = ' '
    for v in range(totalVotes):
        if positive_voting:
            totalVotesStr += '✓'
        else:
            totalVotesStr += '✗'
    return totalVotesStr


def getRightColumnContent(base_dir: str, nickname: str, domain_full: str,
                          http_prefix: str, translate: {},
                          moderator: bool, editor: bool,
                          newswire: {}, positive_voting: bool,
                          showBackButton: bool, timelinePath: str,
                          showPublishButton: bool,
                          show_publish_as_icon: bool,
                          rss_icon_at_top: bool,
                          publish_button_at_top: bool,
                          authorized: bool,
                          showHeaderImage: bool,
                          theme: str,
                          defaultTimeline: str,
                          accessKeys: {}) -> str:
    """Returns html content for the right column
    """
    htmlStr = ''

    domain = remove_domain_port(domain_full)

    if authorized:
        # only show the publish button if logged in, otherwise replace it with
        # a login button
        titleStr = translate['Publish a blog article']
        if defaultTimeline == 'tlfeatures':
            titleStr = translate['Publish a news article']
        publishButtonStr = \
            '        <a href="' + \
            '/users/' + nickname + '/newblog?nodropdown" ' + \
            'title="' + titleStr + '" ' + \
            'accesskey="' + accessKeys['menuNewPost'] + '">' + \
            '<button class="publishbtn">' + \
            translate['Publish'] + '</button></a>\n'
    else:
        # if not logged in then replace the publish button with
        # a login button
        publishButtonStr = \
            '        <a href="/login"><button class="publishbtn">' + \
            translate['Login'] + '</button></a>\n'

    # show publish button at the top if needed
    if publish_button_at_top:
        htmlStr += '<center>' + publishButtonStr + '</center>'

    # show a column header image, eg. title of the theme or newswire banner
    editImageClass = ''
    if showHeaderImage:
        rightImageFile, rightColumnImageFilename = \
            getRightImageFile(base_dir, nickname, domain, theme)

        # show the image at the top of the column
        editImageClass = 'rightColEdit'
        if os.path.isfile(rightColumnImageFilename):
            editImageClass = 'rightColEditImage'
            htmlStr += \
                '\n      <center>\n' + \
                '          <img class="rightColImg" ' + \
                'alt="" loading="lazy" src="/users/' + \
                nickname + '/' + rightImageFile + '" />\n' + \
                '      </center>\n'

    if showPublishButton or editor or rss_icon_at_top:
        if not showHeaderImage:
            htmlStr += '<div class="columnIcons">'

    if editImageClass == 'rightColEdit':
        htmlStr += '\n      <center>\n'

    # whether to show a back icon
    # This is probably going to be osolete soon
    if showBackButton:
        htmlStr += \
            '      <a href="' + timelinePath + '">' + \
            '<button class="cancelbtn">' + \
            translate['Go Back'] + '</button></a>\n'

    if showPublishButton and not publish_button_at_top:
        if not show_publish_as_icon:
            htmlStr += publishButtonStr

    # show the edit icon
    if editor:
        if os.path.isfile(base_dir + '/accounts/newswiremoderation.txt'):
            # show the edit icon highlighted
            htmlStr += \
                '        <a href="' + \
                '/users/' + nickname + '/editnewswire" ' + \
                'accesskey="' + accessKeys['menuEdit'] + '">' + \
                '<img class="' + editImageClass + \
                '" loading="lazy" alt="' + \
                translate['Edit newswire'] + ' | " title="' + \
                translate['Edit newswire'] + '" src="/' + \
                'icons/edit_notify.png" /></a>\n'
        else:
            # show the edit icon
            htmlStr += \
                '        <a href="' + \
                '/users/' + nickname + '/editnewswire" ' + \
                'accesskey="' + accessKeys['menuEdit'] + '">' + \
                '<img class="' + editImageClass + \
                '" loading="lazy" alt="' + \
                translate['Edit newswire'] + ' | " title="' + \
                translate['Edit newswire'] + '" src="/' + \
                'icons/edit.png" /></a>\n'

    # show the RSS icons
    rssIconStr = \
        '        <a href="/categories.xml">' + \
        '<img class="' + editImageClass + \
        '" loading="lazy" alt="' + \
        translate['Hashtag Categories RSS Feed'] + ' | " title="' + \
        translate['Hashtag Categories RSS Feed'] + '" src="/' + \
        'icons/categoriesrss.png" /></a>\n'
    rssIconStr += \
        '        <a href="/newswire.xml">' + \
        '<img class="' + editImageClass + \
        '" loading="lazy" alt="' + \
        translate['Newswire RSS Feed'] + ' | " title="' + \
        translate['Newswire RSS Feed'] + '" src="/' + \
        'icons/logorss.png" /></a>\n'
    if rss_icon_at_top:
        htmlStr += rssIconStr

    # show publish icon at top
    if showPublishButton:
        if show_publish_as_icon:
            titleStr = translate['Publish a blog article']
            if defaultTimeline == 'tlfeatures':
                titleStr = translate['Publish a news article']
            htmlStr += \
                '        <a href="' + \
                '/users/' + nickname + '/newblog?nodropdown" ' + \
                'accesskey="' + accessKeys['menuNewPost'] + '">' + \
                '<img class="' + editImageClass + \
                '" loading="lazy" alt="' + \
                titleStr + '" title="' + \
                titleStr + '" src="/' + \
                'icons/publish.png" /></a>\n'

    if editImageClass == 'rightColEdit':
        htmlStr += '      </center>\n'
    else:
        if showHeaderImage:
            htmlStr += '      <br>\n'

    if showPublishButton or editor or rss_icon_at_top:
        if not showHeaderImage:
            htmlStr += '</div><br>'

    # show the newswire lines
    newswireContentStr = \
        _htmlNewswire(base_dir, newswire, nickname, moderator, translate,
                      positive_voting)
    htmlStr += newswireContentStr

    # show the rss icon at the bottom, typically on the right hand side
    if newswireContentStr and not rss_icon_at_top:
        htmlStr += '<br><div class="columnIcons">' + rssIconStr + '</div>'
    return htmlStr


def _getBrokenFavSubstitute() -> str:
    """Substitute link used if a favicon is not available
    """
    return " onerror=\"this.onerror=null; this.src='/newswire_favicon.ico'\""


def _htmlNewswire(base_dir: str, newswire: {}, nickname: str, moderator: bool,
                  translate: {}, positive_voting: bool) -> str:
    """Converts a newswire dict into html
    """
    separatorStr = htmlPostSeparator(base_dir, 'right')
    htmlStr = ''
    for dateStr, item in newswire.items():
        item[0] = remove_html(item[0]).strip()
        if not item[0]:
            continue
        # remove any CDATA
        if 'CDATA[' in item[0]:
            item[0] = item[0].split('CDATA[')[1]
            if ']' in item[0]:
                item[0] = item[0].split(']')[0]
        try:
            publishedDate = \
                datetime.strptime(dateStr, "%Y-%m-%d %H:%M:%S%z")
        except BaseException:
            print('EX: _htmlNewswire bad date format ' + dateStr)
            continue
        dateShown = publishedDate.strftime("%Y-%m-%d %H:%M")

        dateStrLink = dateStr.replace('T', ' ')
        dateStrLink = dateStrLink.replace('Z', '')
        url = item[1]
        faviconUrl = getNewswireFaviconUrl(url)
        faviconLink = ''
        if faviconUrl:
            cachedFaviconFilename = \
                get_fav_filename_from_url(base_dir, faviconUrl)
            if os.path.isfile(cachedFaviconFilename):
                faviconUrl = \
                    cachedFaviconFilename.replace(base_dir, '')
            else:
                extensions = ('png', 'jpg', 'gif', 'avif', 'svg', 'webp')
                for ext in extensions:
                    cachedFaviconFilename = \
                        get_fav_filename_from_url(base_dir, faviconUrl)
                    cachedFaviconFilename = \
                        cachedFaviconFilename.replace('.ico', '.' + ext)
                    if os.path.isfile(cachedFaviconFilename):
                        faviconUrl = \
                            cachedFaviconFilename.replace(base_dir, '')

            faviconLink = \
                '<img loading="lazy" src="' + faviconUrl + '" ' + \
                'alt="" ' + _getBrokenFavSubstitute() + '/>'
        moderatedItem = item[5]
        htmlStr += separatorStr
        if moderatedItem and 'vote:' + nickname in item[2]:
            totalVotesStr = ''
            totalVotes = 0
            if moderator:
                totalVotes = votesOnNewswireItem(item[2])
                totalVotesStr = \
                    _votesIndicator(totalVotes, positive_voting)

            title = removeLongWords(item[0], 16, []).replace('\n', '<br>')
            title = limitRepeatedWords(title, 6)
            htmlStr += '<p class="newswireItemVotedOn">' + \
                '<a href="' + url + '" target="_blank" ' + \
                'rel="nofollow noopener noreferrer">' + \
                '<span class="newswireItemVotedOn">' + \
                faviconLink + title + '</span></a>' + totalVotesStr
            if moderator:
                htmlStr += \
                    ' ' + dateShown + '<a href="/users/' + nickname + \
                    '/newswireunvote=' + dateStrLink + '" ' + \
                    'title="' + translate['Remove Vote'] + '">'
                htmlStr += '<img loading="lazy" class="voteicon" src="/' + \
                    'alt="' + translate['Remove Vote'] + '" ' + \
                    'icons/vote.png" /></a></p>\n'
            else:
                htmlStr += ' <span class="newswireDateVotedOn">'
                htmlStr += dateShown + '</span></p>\n'
        else:
            totalVotesStr = ''
            totalVotes = 0
            if moderator:
                if moderatedItem:
                    totalVotes = votesOnNewswireItem(item[2])
                    # show a number of ticks or crosses for how many
                    # votes for or against
                    totalVotesStr = \
                        _votesIndicator(totalVotes, positive_voting)

            title = removeLongWords(item[0], 16, []).replace('\n', '<br>')
            title = limitRepeatedWords(title, 6)
            if moderator and moderatedItem:
                htmlStr += '<p class="newswireItemModerated">' + \
                    '<a href="' + url + '" target="_blank" ' + \
                    'rel="nofollow noopener noreferrer">' + \
                    faviconLink + title + '</a>' + totalVotesStr
                htmlStr += ' ' + dateShown
                htmlStr += '<a href="/users/' + nickname + \
                    '/newswirevote=' + dateStrLink + '" ' + \
                    'title="' + translate['Vote'] + '">'
                htmlStr += '<img class="voteicon" ' + \
                    'alt="' + translate['Vote'] + '" ' + \
                    'src="/icons/vote.png" /></a>'
                htmlStr += '</p>\n'
            else:
                htmlStr += '<p class="newswireItem">' + \
                    '<a href="' + url + '" target="_blank" ' + \
                    'rel="nofollow noopener noreferrer">' + \
                    faviconLink + title + '</a>' + totalVotesStr
                htmlStr += ' <span class="newswireDate">'
                htmlStr += dateShown + '</span></p>\n'

    if htmlStr:
        htmlStr = '<nav>\n' + htmlStr + '</nav>\n'
    return htmlStr


def htmlCitations(base_dir: str, nickname: str, domain: str,
                  http_prefix: str, defaultTimeline: str,
                  translate: {}, newswire: {}, cssCache: {},
                  blogTitle: str, blogContent: str,
                  blogImageFilename: str,
                  blogImageAttachmentMediaType: str,
                  blogImageDescription: str,
                  theme: str) -> str:
    """Show the citations screen when creating a blog
    """
    htmlStr = ''

    # create a list of dates for citations
    # these can then be used to re-select checkboxes later
    citationsFilename = \
        acct_dir(base_dir, nickname, domain) + '/.citations.txt'
    citationsSelected = []
    if os.path.isfile(citationsFilename):
        citationsSeparator = '#####'
        with open(citationsFilename, 'r') as f:
            citations = f.readlines()
            for line in citations:
                if citationsSeparator not in line:
                    continue
                sections = line.strip().split(citationsSeparator)
                if len(sections) != 3:
                    continue
                dateStr = sections[0]
                citationsSelected.append(dateStr)

    # the css filename
    cssFilename = base_dir + '/epicyon-profile.css'
    if os.path.isfile(base_dir + '/epicyon.css'):
        cssFilename = base_dir + '/epicyon.css'

    instanceTitle = \
        get_config_param(base_dir, 'instanceTitle')
    htmlStr = htmlHeaderWithExternalStyle(cssFilename, instanceTitle, None)

    # top banner
    bannerFile, bannerFilename = \
        getBannerFile(base_dir, nickname, domain, theme)
    htmlStr += \
        '<a href="/users/' + nickname + '/newblog" title="' + \
        translate['Go Back'] + '" alt="' + \
        translate['Go Back'] + '">\n'
    htmlStr += '<img loading="lazy" class="timeline-banner" ' + \
        'alt="" src="' + \
        '/users/' + nickname + '/' + bannerFile + '" /></a>\n'

    htmlStr += \
        '<form enctype="multipart/form-data" method="POST" ' + \
        'accept-charset="UTF-8" action="/users/' + nickname + \
        '/citationsdata">\n'
    htmlStr += '  <center>\n'
    htmlStr += translate['Choose newswire items ' +
                         'referenced in your article'] + '<br>'
    if blogTitle is None:
        blogTitle = ''
    htmlStr += \
        '    <input type="hidden" name="blogTitle" value="' + \
        blogTitle + '">\n'
    if blogContent is None:
        blogContent = ''
    htmlStr += \
        '    <input type="hidden" name="blogContent" value="' + \
        blogContent + '">\n'
    # submit button
    htmlStr += \
        '    <input type="submit" name="submitCitations" value="' + \
        translate['Submit'] + '">\n'
    htmlStr += '  </center>\n'

    citationsSeparator = '#####'

    # list of newswire items
    if newswire:
        ctr = 0
        for dateStr, item in newswire.items():
            item[0] = remove_html(item[0]).strip()
            if not item[0]:
                continue
            # remove any CDATA
            if 'CDATA[' in item[0]:
                item[0] = item[0].split('CDATA[')[1]
                if ']' in item[0]:
                    item[0] = item[0].split(']')[0]
            # should this checkbox be selected?
            selectedStr = ''
            if dateStr in citationsSelected:
                selectedStr = ' checked'

            publishedDate = \
                datetime.strptime(dateStr, "%Y-%m-%d %H:%M:%S%z")
            dateShown = publishedDate.strftime("%Y-%m-%d %H:%M")

            title = removeLongWords(item[0], 16, []).replace('\n', '<br>')
            title = limitRepeatedWords(title, 6)
            link = item[1]

            citationValue = \
                dateStr + citationsSeparator + \
                title + citationsSeparator + \
                link
            htmlStr += \
                '<input type="checkbox" name="newswire' + str(ctr) + \
                '" value="' + citationValue + '"' + selectedStr + '/>' + \
                '<a href="' + link + '"><cite>' + title + '</cite></a> '
            htmlStr += '<span class="newswireDate">' + \
                dateShown + '</span><br>\n'
            ctr += 1

    htmlStr += '</form>\n'
    return htmlStr + htmlFooter()


def htmlNewswireMobile(cssCache: {}, base_dir: str, nickname: str,
                       domain: str, domain_full: str,
                       http_prefix: str, translate: {},
                       newswire: {},
                       positive_voting: bool,
                       timelinePath: str,
                       show_publish_as_icon: bool,
                       authorized: bool,
                       rss_icon_at_top: bool,
                       icons_as_buttons: bool,
                       defaultTimeline: str,
                       theme: str,
                       accessKeys: {}) -> str:
    """Shows the mobile version of the newswire right column
    """
    htmlStr = ''

    # the css filename
    cssFilename = base_dir + '/epicyon-profile.css'
    if os.path.isfile(base_dir + '/epicyon.css'):
        cssFilename = base_dir + '/epicyon.css'

    if nickname == 'news':
        editor = False
        moderator = False
    else:
        # is the user a moderator?
        moderator = isModerator(base_dir, nickname)

        # is the user a site editor?
        editor = is_editor(base_dir, nickname)

    showPublishButton = editor

    instanceTitle = \
        get_config_param(base_dir, 'instanceTitle')
    htmlStr = htmlHeaderWithExternalStyle(cssFilename, instanceTitle, None)

    bannerFile, bannerFilename = \
        getBannerFile(base_dir, nickname, domain, theme)
    htmlStr += \
        '<a href="/users/' + nickname + '/' + defaultTimeline + '" ' + \
        'accesskey="' + accessKeys['menuTimeline'] + '">' + \
        '<img loading="lazy" class="timeline-banner" ' + \
        'alt="' + translate['Timeline banner image'] + '" ' + \
        'src="/users/' + nickname + '/' + bannerFile + '" /></a>\n'

    htmlStr += '<div class="col-right-mobile">\n'

    htmlStr += '<center>' + \
        headerButtonsFrontScreen(translate, nickname,
                                 'newswire', authorized,
                                 icons_as_buttons) + '</center>'
    htmlStr += \
        getRightColumnContent(base_dir, nickname, domain_full,
                              http_prefix, translate,
                              moderator, editor,
                              newswire, positive_voting,
                              False, timelinePath, showPublishButton,
                              show_publish_as_icon, rss_icon_at_top, False,
                              authorized, False, theme,
                              defaultTimeline, accessKeys)
    if editor and not newswire:
        htmlStr += '<br><br><br>\n'
        htmlStr += '<center>\n  '
        htmlStr += translate['Select the edit icon to add RSS feeds']
        htmlStr += '\n</center>\n'
    # end of col-right-mobile
    htmlStr += '</div\n>'

    htmlStr += htmlFooter()
    return htmlStr


def htmlEditNewswire(cssCache: {}, translate: {}, base_dir: str, path: str,
                     domain: str, port: int, http_prefix: str,
                     defaultTimeline: str, theme: str,
                     accessKeys: {}) -> str:
    """Shows the edit newswire screen
    """
    if '/users/' not in path:
        return ''
    path = path.replace('/inbox', '').replace('/outbox', '')
    path = path.replace('/shares', '').replace('/wanted', '')

    nickname = get_nickname_from_actor(path)
    if not nickname:
        return ''

    # is the user a moderator?
    if not isModerator(base_dir, nickname):
        return ''

    cssFilename = base_dir + '/epicyon-links.css'
    if os.path.isfile(base_dir + '/links.css'):
        cssFilename = base_dir + '/links.css'

    # filename of the banner shown at the top
    bannerFile, bannerFilename = \
        getBannerFile(base_dir, nickname, domain, theme)

    instanceTitle = \
        get_config_param(base_dir, 'instanceTitle')
    editNewswireForm = \
        htmlHeaderWithExternalStyle(cssFilename, instanceTitle, None)

    # top banner
    editNewswireForm += \
        '<header>' + \
        '<a href="/users/' + nickname + '/' + defaultTimeline + '" title="' + \
        translate['Switch to timeline view'] + '" alt="' + \
        translate['Switch to timeline view'] + '" ' + \
        'accesskey="' + accessKeys['menuTimeline'] + '">\n'
    editNewswireForm += '<img loading="lazy" class="timeline-banner" src="' + \
        '/users/' + nickname + '/' + bannerFile + '" ' + \
        'alt="" /></a>\n</header>'

    editNewswireForm += \
        '<form enctype="multipart/form-data" method="POST" ' + \
        'accept-charset="UTF-8" action="' + path + '/newswiredata">\n'
    editNewswireForm += \
        '  <div class="vertical-center">\n'
    editNewswireForm += \
        '    <h1>' + translate['Edit newswire'] + '</h1>'
    editNewswireForm += \
        '    <div class="containerSubmitNewPost">\n'
    editNewswireForm += \
        '      <input type="submit" name="submitNewswire" value="' + \
        translate['Submit'] + '" ' + \
        'accesskey="' + accessKeys['submitButton'] + '">\n'
    editNewswireForm += \
        '    </div>\n'

    newswireFilename = base_dir + '/accounts/newswire.txt'
    newswireStr = ''
    if os.path.isfile(newswireFilename):
        with open(newswireFilename, 'r') as fp:
            newswireStr = fp.read()

    editNewswireForm += \
        '<div class="container">'

    editNewswireForm += \
        '  ' + \
        translate['Add RSS feed links below.'] + \
        '<br>'
    newFeedStr = translate['New feed URL']
    editNewswireForm += editTextField(None, 'newNewswireFeed', '', newFeedStr)
    editNewswireForm += \
        '  <textarea id="message" name="editedNewswire" ' + \
        'style="height:80vh" spellcheck="false">' + \
        newswireStr + '</textarea>'

    filterStr = ''
    filterFilename = \
        base_dir + '/accounts/news@' + domain + '/filters.txt'
    if os.path.isfile(filterFilename):
        with open(filterFilename, 'r') as filterfile:
            filterStr = filterfile.read()

    editNewswireForm += \
        '      <br><b><label class="labels">' + \
        translate['Filtered words'] + '</label></b>\n'
    editNewswireForm += '      <br><label class="labels">' + \
        translate['One per line'] + '</label>'
    editNewswireForm += '      <textarea id="message" ' + \
        'name="filteredWordsNewswire" style="height:50vh" ' + \
        'spellcheck="true">' + filterStr + '</textarea>\n'

    hashtagRulesStr = ''
    hashtagRulesFilename = \
        base_dir + '/accounts/hashtagrules.txt'
    if os.path.isfile(hashtagRulesFilename):
        with open(hashtagRulesFilename, 'r') as rulesfile:
            hashtagRulesStr = rulesfile.read()

    editNewswireForm += \
        '      <br><b><label class="labels">' + \
        translate['News tagging rules'] + '</label></b>\n'
    editNewswireForm += '      <br><label class="labels">' + \
        translate['One per line'] + '.</label>\n'
    editNewswireForm += \
        '      <a href="' + \
        'https://gitlab.com/bashrc2/epicyon/-/raw/main/hashtagrules.txt' + \
        '">' + translate['See instructions'] + '</a>\n'
    editNewswireForm += '      <textarea id="message" ' + \
        'name="hashtagRulesList" style="height:80vh" spellcheck="false">' + \
        hashtagRulesStr + '</textarea>\n'

    editNewswireForm += \
        '</div>'

    editNewswireForm += htmlFooter()
    return editNewswireForm


def htmlEditNewsPost(cssCache: {}, translate: {}, base_dir: str, path: str,
                     domain: str, port: int,
                     http_prefix: str, postUrl: str,
                     system_language: str) -> str:
    """Edits a news post on the news/features timeline
    """
    if '/users/' not in path:
        return ''
    pathOriginal = path

    nickname = get_nickname_from_actor(path)
    if not nickname:
        return ''

    # is the user an editor?
    if not is_editor(base_dir, nickname):
        return ''

    postUrl = postUrl.replace('/', '#')
    post_filename = locate_post(base_dir, nickname, domain, postUrl)
    if not post_filename:
        return ''
    post_json_object = load_json(post_filename)
    if not post_json_object:
        return ''

    cssFilename = base_dir + '/epicyon-links.css'
    if os.path.isfile(base_dir + '/links.css'):
        cssFilename = base_dir + '/links.css'

    instanceTitle = \
        get_config_param(base_dir, 'instanceTitle')
    editNewsPostForm = \
        htmlHeaderWithExternalStyle(cssFilename, instanceTitle, None)
    editNewsPostForm += \
        '<form enctype="multipart/form-data" method="POST" ' + \
        'accept-charset="UTF-8" action="' + path + '/newseditdata">\n'
    editNewsPostForm += \
        '  <div class="vertical-center">\n'
    editNewsPostForm += \
        '    <h1>' + translate['Edit News Post'] + '</h1>'
    editNewsPostForm += \
        '    <div class="container">\n'
    editNewsPostForm += \
        '      <a href="' + pathOriginal + '/tlnews">' + \
        '<button class="cancelbtn">' + translate['Go Back'] + '</button></a>\n'
    editNewsPostForm += \
        '      <input type="submit" name="submitEditedNewsPost" value="' + \
        translate['Submit'] + '">\n'
    editNewsPostForm += \
        '    </div>\n'

    editNewsPostForm += \
        '<div class="container">'

    editNewsPostForm += \
        '  <input type="hidden" name="newsPostUrl" value="' + \
        postUrl + '">\n'

    newsPostTitle = post_json_object['object']['summary']
    editNewsPostForm += \
        '  <input type="text" name="newsPostTitle" value="' + \
        newsPostTitle + '"><br>\n'

    newsPostContent = get_base_content_from_post(post_json_object,
                                                 system_language)
    editNewsPostForm += \
        '  <textarea id="message" name="editedNewsPost" ' + \
        'style="height:600px" spellcheck="true">' + \
        newsPostContent + '</textarea>'

    editNewsPostForm += \
        '</div>'

    editNewsPostForm += htmlFooter()
    return editNewsPostForm
