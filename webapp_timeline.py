__filename__ = "webapp_timeline.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Timeline"

import os
import time
from shutil import copyfile
from utils import is_artist
from utils import dangerous_markup
from utils import get_config_param
from utils import get_full_domain
from utils import is_editor
from utils import remove_id_ending
from utils import acct_dir
from utils import is_float
from utils import local_actor_url
from follow import follower_approval_active
from person import is_person_snoozed
from markdown import markdown_to_html
from webapp_utils import html_keyboard_navigation
from webapp_utils import html_hide_from_screen_reader
from webapp_utils import html_post_separator
from webapp_utils import get_banner_file
from webapp_utils import html_header_with_external_style
from webapp_utils import html_footer
from webapp_utils import shares_timeline_json
from webapp_utils import html_highlight_label
from webapp_post import prepare_post_from_html_cache
from webapp_post import individual_post_as_html
from webapp_column_left import get_left_column_content
from webapp_column_right import get_right_column_content
from webapp_headerbuttons import header_buttons_timeline
from posts import is_moderator
from announce import is_self_announce


def _log_timeline_timing(enableTimingLog: bool, timelineStartTime,
                         boxName: str, debugId: str) -> None:
    """Create a log of timings for performance tuning
    """
    if not enableTimingLog:
        return
    timeDiff = int((time.time() - timelineStartTime) * 1000)
    if timeDiff > 100:
        print('TIMELINE TIMING ' +
              boxName + ' ' + debugId + ' = ' + str(timeDiff))


def _get_help_for_timeline(base_dir: str, boxName: str) -> str:
    """Shows help text for the given timeline
    """
    # get the filename for help for this timeline
    helpFilename = base_dir + '/accounts/help_' + boxName + '.md'
    if not os.path.isfile(helpFilename):
        language = \
            get_config_param(base_dir, 'language')
        if not language:
            language = 'en'
        theme_name = \
            get_config_param(base_dir, 'theme')
        defaultFilename = None
        if theme_name:
            defaultFilename = \
                base_dir + '/theme/' + theme_name + '/welcome/' + \
                'help_' + boxName + '_' + language + '.md'
            if not os.path.isfile(defaultFilename):
                defaultFilename = None
        if not defaultFilename:
            defaultFilename = \
                base_dir + '/defaultwelcome/' + \
                'help_' + boxName + '_' + language + '.md'
        if not os.path.isfile(defaultFilename):
            defaultFilename = \
                base_dir + '/defaultwelcome/help_' + boxName + '_en.md'
        if os.path.isfile(defaultFilename):
            copyfile(defaultFilename, helpFilename)

    # show help text
    if os.path.isfile(helpFilename):
        instanceTitle = \
            get_config_param(base_dir, 'instanceTitle')
        if not instanceTitle:
            instanceTitle = 'Epicyon'
        with open(helpFilename, 'r') as helpFile:
            helpText = helpFile.read()
            if dangerous_markup(helpText, False):
                return ''
            helpText = helpText.replace('INSTANCE', instanceTitle)
            return '<div class="container">\n' + \
                markdown_to_html(helpText) + '\n' + \
                '</div>\n'
    return ''


def _html_timeline_new_post(manuallyApproveFollowers: bool,
                            boxName: str, icons_as_buttons: bool,
                            usersPath: str, translate: {}) -> str:
    """Returns html for the new post button
    """
    newPostButtonStr = ''
    if boxName == 'dm':
        if not icons_as_buttons:
            newPostButtonStr += \
                '<a class="imageAnchor" href="' + usersPath + \
                '/newdm?nodropdown"><img loading="lazy" src="/' + \
                'icons/newpost.png" title="' + \
                translate['Create a new DM'] + \
                '" alt="| ' + translate['Create a new DM'] + \
                '" class="timelineicon"/></a>\n'
        else:
            newPostButtonStr += \
                '<a href="' + usersPath + '/newdm?nodropdown">' + \
                '<button class="button"><span>' + \
                translate['Post'] + ' </span></button></a>'
    elif (boxName == 'tlblogs' or
          boxName == 'tlnews' or
          boxName == 'tlfeatures'):
        if not icons_as_buttons:
            newPostButtonStr += \
                '<a class="imageAnchor" href="' + usersPath + \
                '/newblog"><img loading="lazy" src="/' + \
                'icons/newpost.png" title="' + \
                translate['Create a new post'] + '" alt="| ' + \
                translate['Create a new post'] + \
                '" class="timelineicon"/></a>\n'
        else:
            newPostButtonStr += \
                '<a href="' + usersPath + '/newblog">' + \
                '<button class="button"><span>' + \
                translate['Post'] + '</span></button></a>'
    elif boxName == 'tlshares':
        if not icons_as_buttons:
            newPostButtonStr += \
                '<a class="imageAnchor" href="' + usersPath + \
                '/newshare?nodropdown"><img loading="lazy" src="/' + \
                'icons/newpost.png" title="' + \
                translate['Create a new shared item'] + '" alt="| ' + \
                translate['Create a new shared item'] + \
                '" class="timelineicon"/></a>\n'
        else:
            newPostButtonStr += \
                '<a href="' + usersPath + '/newshare?nodropdown">' + \
                '<button class="button"><span>' + \
                translate['Post'] + '</span></button></a>'
    elif boxName == 'tlwanted':
        if not icons_as_buttons:
            newPostButtonStr += \
                '<a class="imageAnchor" href="' + usersPath + \
                '/newwanted?nodropdown"><img loading="lazy" src="/' + \
                'icons/newpost.png" title="' + \
                translate['Create a new wanted item'] + '" alt="| ' + \
                translate['Create a new wanted item'] + \
                '" class="timelineicon"/></a>\n'
        else:
            newPostButtonStr += \
                '<a href="' + usersPath + '/newwanted?nodropdown">' + \
                '<button class="button"><span>' + \
                translate['Post'] + '</span></button></a>'
    else:
        if not manuallyApproveFollowers:
            if not icons_as_buttons:
                newPostButtonStr += \
                    '<a class="imageAnchor" href="' + usersPath + \
                    '/newpost"><img loading="lazy" src="/' + \
                    'icons/newpost.png" title="' + \
                    translate['Create a new post'] + '" alt="| ' + \
                    translate['Create a new post'] + \
                    '" class="timelineicon"/></a>\n'
            else:
                newPostButtonStr += \
                    '<a href="' + usersPath + '/newpost">' + \
                    '<button class="button"><span>' + \
                    translate['Post'] + '</span></button></a>'
        else:
            if not icons_as_buttons:
                newPostButtonStr += \
                    '<a class="imageAnchor" href="' + usersPath + \
                    '/newfollowers"><img loading="lazy" src="/' + \
                    'icons/newpost.png" title="' + \
                    translate['Create a new post'] + \
                    '" alt="| ' + translate['Create a new post'] + \
                    '" class="timelineicon"/></a>\n'
            else:
                newPostButtonStr += \
                    '<a href="' + usersPath + '/newfollowers">' + \
                    '<button class="button"><span>' + \
                    translate['Post'] + '</span></button></a>'
    return newPostButtonStr


def _html_timeline_moderation_buttons(moderator: bool, boxName: str,
                                      nickname: str, moderationActionStr: str,
                                      translate: {}) -> str:
    """Returns html for the moderation screen buttons
    """
    tlStr = ''
    if moderator and boxName == 'moderation':
        tlStr += \
            '<form id="modtimeline" method="POST" action="/users/' + \
            nickname + '/moderationaction">'
        tlStr += '<div class="container">\n'
        idx = 'Nickname or URL. Block using *@domain or nickname@domain'
        tlStr += \
            '    <b>' + translate[idx] + '</b><br>\n'
        if moderationActionStr:
            tlStr += '    <input type="text" ' + \
                'name="moderationAction" value="' + \
                moderationActionStr + '" autofocus><br>\n'
        else:
            tlStr += '    <input type="text" ' + \
                'name="moderationAction" value="" autofocus><br>\n'

        tlStr += \
            '    <input type="submit" title="' + \
            translate['Information about current blocks/suspensions'] + \
            '" alt="' + \
            translate['Information about current blocks/suspensions'] + \
            ' | " ' + \
            'name="submitInfo" value="' + translate['Info'] + '">\n'
        tlStr += \
            '    <input type="submit" title="' + \
            translate['Remove the above item'] + '" ' + \
            'alt="' + translate['Remove the above item'] + ' | " ' + \
            'name="submitRemove" value="' + \
            translate['Remove'] + '">\n'

        tlStr += \
            '    <input type="submit" title="' + \
            translate['Suspend the above account nickname'] + '" ' + \
            'alt="' + \
            translate['Suspend the above account nickname'] + ' | " ' + \
            'name="submitSuspend" value="' + translate['Suspend'] + '">\n'
        tlStr += \
            '    <input type="submit" title="' + \
            translate['Remove a suspension for an account nickname'] + '" ' + \
            'alt="' + \
            translate['Remove a suspension for an account nickname'] + \
            ' | " ' + \
            'name="submitUnsuspend" value="' + \
            translate['Unsuspend'] + '">\n'

        tlStr += \
            '    <input type="submit" title="' + \
            translate['Block an account on another instance'] + '" ' + \
            'alt="' + \
            translate['Block an account on another instance'] + ' | " ' + \
            'name="submitBlock" value="' + translate['Block'] + '">\n'
        tlStr += \
            '    <input type="submit" title="' + \
            translate['Unblock an account on another instance'] + '" ' + \
            'alt="' + \
            translate['Unblock an account on another instance'] + ' | " ' + \
            'name="submitUnblock" value="' + translate['Unblock'] + '">\n'

        tlStr += \
            '    <input type="submit" title="' + \
            translate['Filter out words'] + '" ' + \
            'alt="' + \
            translate['Filter out words'] + ' | " ' + \
            'name="submitFilter" value="' + translate['Filter'] + '">\n'
        tlStr += \
            '    <input type="submit" title="' + \
            translate['Unfilter words'] + '" ' + \
            'alt="' + \
            translate['Unfilter words'] + ' | " ' + \
            'name="submitUnfilter" value="' + translate['Unfilter'] + '">\n'

        tlStr += '</div>\n</form>\n'
    return tlStr


def _html_timeline_keyboard(moderator: bool, text_mode_banner: str,
                            usersPath: str,
                            nickname: str, newCalendarEvent: bool,
                            newDM: bool, newReply: bool,
                            newShare: bool, newWanted: bool,
                            followApprovals: bool,
                            accessKeys: {}, translate: {}) -> str:
    """Returns html for timeline keyboard navigation
    """
    calendarStr = translate['Calendar']
    if newCalendarEvent:
        calendarStr = '<strong>' + calendarStr + '</strong>'
    dmStr = translate['DM']
    if newDM:
        dmStr = '<strong>' + dmStr + '</strong>'
    repliesStr = translate['Replies']
    if newReply:
        repliesStr = '<strong>' + repliesStr + '</strong>'
    sharesStr = translate['Shares']
    if newShare:
        sharesStr = '<strong>' + sharesStr + '</strong>'
    wantedStr = translate['Wanted']
    if newWanted:
        wantedStr = '<strong>' + wantedStr + '</strong>'
    menuProfile = \
        html_hide_from_screen_reader('👤') + ' ' + \
        translate['Switch to profile view']
    menuInbox = \
        html_hide_from_screen_reader('📥') + ' ' + translate['Inbox']
    menuOutbox = \
        html_hide_from_screen_reader('📤') + ' ' + translate['Sent']
    menuSearch = \
        html_hide_from_screen_reader('🔍') + ' ' + \
        translate['Search and follow']
    menuCalendar = \
        html_hide_from_screen_reader('📅') + ' ' + calendarStr
    menuDM = \
        html_hide_from_screen_reader('📩') + ' ' + dmStr
    menuReplies = \
        html_hide_from_screen_reader('📨') + ' ' + repliesStr
    menuBookmarks = \
        html_hide_from_screen_reader('🔖') + ' ' + translate['Bookmarks']
    menuShares = \
        html_hide_from_screen_reader('🤝') + ' ' + sharesStr
    menuWanted = \
        html_hide_from_screen_reader('⛱') + ' ' + wantedStr
    menuBlogs = \
        html_hide_from_screen_reader('📝') + ' ' + translate['Blogs']
    menuNewswire = \
        html_hide_from_screen_reader('📰') + ' ' + translate['Newswire']
    menuLinks = \
        html_hide_from_screen_reader('🔗') + ' ' + translate['Links']
    menuNewPost = \
        html_hide_from_screen_reader('➕') + ' ' + \
        translate['Create a new post']
    menuModeration = \
        html_hide_from_screen_reader('⚡️') + ' ' + translate['Mod']
    navLinks = {
        menuProfile: '/users/' + nickname,
        menuInbox: usersPath + '/inbox#timelineposts',
        menuSearch: usersPath + '/search',
        menuNewPost: usersPath + '/newpost',
        menuCalendar: usersPath + '/calendar',
        menuDM: usersPath + '/dm#timelineposts',
        menuReplies: usersPath + '/tlreplies#timelineposts',
        menuOutbox: usersPath + '/outbox#timelineposts',
        menuBookmarks: usersPath + '/tlbookmarks#timelineposts',
        menuShares: usersPath + '/tlshares#timelineposts',
        menuWanted: usersPath + '/tlwanted#timelineposts',
        menuBlogs: usersPath + '/tlblogs#timelineposts',
        menuNewswire: usersPath + '/newswiremobile',
        menuLinks: usersPath + '/linksmobile'
    }
    navAccessKeys = {}
    for variableName, key in accessKeys.items():
        if not locals().get(variableName):
            continue
        navAccessKeys[locals()[variableName]] = key
    if moderator:
        navLinks[menuModeration] = usersPath + '/moderation#modtimeline'
    return html_keyboard_navigation(text_mode_banner, navLinks, navAccessKeys,
                                    None, usersPath, translate,
                                    followApprovals)


def _html_timeline_end(base_dir: str, nickname: str, domain_full: str,
                       http_prefix: str, translate: {},
                       moderator: bool, editor: bool,
                       newswire: {}, positive_voting: bool,
                       show_publish_as_icon: bool,
                       rss_icon_at_top: bool, publish_button_at_top: bool,
                       authorized: bool, theme: str,
                       defaultTimeline: str, accessKeys: {},
                       boxName: str,
                       enableTimingLog: bool, timelineStartTime) -> str:
    """Ending of the timeline, containing the right column
    """
    # end of timeline-posts
    tlStr = '  </div>\n'

    # end of column-center
    tlStr += '  </td>\n'

    # right column
    rightColumnStr = get_right_column_content(base_dir, nickname, domain_full,
                                              http_prefix, translate,
                                              moderator, editor,
                                              newswire, positive_voting,
                                              False, None, True,
                                              show_publish_as_icon,
                                              rss_icon_at_top,
                                              publish_button_at_top,
                                              authorized, True, theme,
                                              defaultTimeline, accessKeys)
    tlStr += '  <td valign="top" class="col-right" ' + \
        'id="newswire" tabindex="-1">' + \
        rightColumnStr + '  </td>\n'
    tlStr += '  </tr>\n'

    _log_timeline_timing(enableTimingLog, timelineStartTime, boxName, '9')

    tlStr += '  </tbody>\n'
    tlStr += '</table>\n'
    return tlStr


def _page_number_buttons(usersPath: str, boxName: str, pageNumber: int) -> str:
    """Shows selactable page numbers at the bottom of the screen
    """
    pagesWidth = 3
    minPageNumber = pageNumber - pagesWidth
    if minPageNumber < 1:
        minPageNumber = 1
    maxPageNumber = minPageNumber + 1 + (pagesWidth * 2)
    numStr = ''
    for page in range(minPageNumber, maxPageNumber):
        if numStr:
            numStr += ' ⸻ '
        pageStr = str(page)
        if page == pageNumber:
            pageStr = '<mark>' + str(page) + '</mark>'
        numStr += \
            '<a href="' + usersPath + '/' + boxName + '?page=' + \
            str(page) + '" class="pageslist">' + pageStr + '</a>'
    return '<center>' + numStr + '</center>'


def html_timeline(css_cache: {}, defaultTimeline: str,
                  recent_posts_cache: {}, max_recent_posts: int,
                  translate: {}, pageNumber: int,
                  itemsPerPage: int, session, base_dir: str,
                  cached_webfingers: {}, person_cache: {},
                  nickname: str, domain: str, port: int, timelineJson: {},
                  boxName: str, allow_deletion: bool,
                  http_prefix: str, project_version: str,
                  manuallyApproveFollowers: bool,
                  minimal: bool,
                  yt_replace_domain: str,
                  twitter_replacement_domain: str,
                  show_published_date_only: bool,
                  newswire: {}, moderator: bool,
                  editor: bool, artist: bool,
                  positive_voting: bool,
                  show_publish_as_icon: bool,
                  full_width_tl_button_header: bool,
                  icons_as_buttons: bool,
                  rss_icon_at_top: bool,
                  publish_button_at_top: bool,
                  authorized: bool,
                  moderationActionStr: str,
                  theme: str,
                  peertube_instances: [],
                  allow_local_network_access: bool,
                  text_mode_banner: str,
                  accessKeys: {}, system_language: str,
                  max_like_count: int,
                  shared_items_federated_domains: [],
                  signing_priv_key_pem: str,
                  cw_lists: {}, lists_enabled: str) -> str:
    """Show the timeline as html
    """
    enableTimingLog = False

    timelineStartTime = time.time()

    accountDir = acct_dir(base_dir, nickname, domain)

    # should the calendar icon be highlighted?
    newCalendarEvent = False
    calendarImage = 'calendar.png'
    calendarPath = '/calendar'
    calendarFile = accountDir + '/.newCalendar'
    if os.path.isfile(calendarFile):
        newCalendarEvent = True
        calendarImage = 'calendar_notify.png'
        with open(calendarFile, 'r') as calfile:
            calendarPath = calfile.read().replace('##sent##', '')
            calendarPath = calendarPath.replace('\n', '').replace('\r', '')

    # should the DM button be highlighted?
    newDM = False
    dmFile = accountDir + '/.newDM'
    if os.path.isfile(dmFile):
        newDM = True
        if boxName == 'dm':
            try:
                os.remove(dmFile)
            except OSError:
                print('EX: html_timeline unable to delete ' + dmFile)

    # should the Replies button be highlighted?
    newReply = False
    replyFile = accountDir + '/.newReply'
    if os.path.isfile(replyFile):
        newReply = True
        if boxName == 'tlreplies':
            try:
                os.remove(replyFile)
            except OSError:
                print('EX: html_timeline unable to delete ' + replyFile)

    # should the Shares button be highlighted?
    newShare = False
    newShareFile = accountDir + '/.newShare'
    if os.path.isfile(newShareFile):
        newShare = True
        if boxName == 'tlshares':
            try:
                os.remove(newShareFile)
            except OSError:
                print('EX: html_timeline unable to delete ' + newShareFile)

    # should the Wanted button be highlighted?
    newWanted = False
    newWantedFile = accountDir + '/.newWanted'
    if os.path.isfile(newWantedFile):
        newWanted = True
        if boxName == 'tlwanted':
            try:
                os.remove(newWantedFile)
            except OSError:
                print('EX: html_timeline unable to delete ' + newWantedFile)

    # should the Moderation/reports button be highlighted?
    newReport = False
    newReportFile = accountDir + '/.newReport'
    if os.path.isfile(newReportFile):
        newReport = True
        if boxName == 'moderation':
            try:
                os.remove(newReportFile)
            except OSError:
                print('EX: html_timeline unable to delete ' + newReportFile)

    separatorStr = ''
    if boxName != 'tlmedia':
        separatorStr = html_post_separator(base_dir, None)

    # the css filename
    cssFilename = base_dir + '/epicyon-profile.css'
    if os.path.isfile(base_dir + '/epicyon.css'):
        cssFilename = base_dir + '/epicyon.css'

    # filename of the banner shown at the top
    bannerFile, bannerFilename = \
        get_banner_file(base_dir, nickname, domain, theme)

    _log_timeline_timing(enableTimingLog, timelineStartTime, boxName, '1')

    # is the user a moderator?
    if not moderator:
        moderator = is_moderator(base_dir, nickname)

    # is the user a site editor?
    if not editor:
        editor = is_editor(base_dir, nickname)

    _log_timeline_timing(enableTimingLog, timelineStartTime, boxName, '2')

    # the appearance of buttons - highlighted or not
    inboxButton = 'button'
    blogsButton = 'button'
    featuresButton = 'button'
    newsButton = 'button'
    dmButton = 'button'
    if newDM:
        dmButton = 'buttonhighlighted'
    repliesButton = 'button'
    if newReply:
        repliesButton = 'buttonhighlighted'
    mediaButton = 'button'
    bookmarksButton = 'button'
#    eventsButton = 'button'
    sentButton = 'button'
    sharesButton = 'button'
    if newShare:
        sharesButton = 'buttonhighlighted'
    wantedButton = 'button'
    if newWanted:
        wantedButton = 'buttonhighlighted'
    moderationButton = 'button'
    if newReport:
        moderationButton = 'buttonhighlighted'
    if boxName == 'inbox':
        inboxButton = 'buttonselected'
    elif boxName == 'tlblogs':
        blogsButton = 'buttonselected'
    elif boxName == 'tlfeatures':
        featuresButton = 'buttonselected'
    elif boxName == 'tlnews':
        newsButton = 'buttonselected'
    elif boxName == 'dm':
        dmButton = 'buttonselected'
        if newDM:
            dmButton = 'buttonselectedhighlighted'
    elif boxName == 'tlreplies':
        repliesButton = 'buttonselected'
        if newReply:
            repliesButton = 'buttonselectedhighlighted'
    elif boxName == 'tlmedia':
        mediaButton = 'buttonselected'
    elif boxName == 'outbox':
        sentButton = 'buttonselected'
    elif boxName == 'moderation':
        moderationButton = 'buttonselected'
        if newReport:
            moderationButton = 'buttonselectedhighlighted'
    elif boxName == 'tlshares':
        sharesButton = 'buttonselected'
        if newShare:
            sharesButton = 'buttonselectedhighlighted'
    elif boxName == 'tlwanted':
        wantedButton = 'buttonselected'
        if newWanted:
            wantedButton = 'buttonselectedhighlighted'
    elif boxName == 'tlbookmarks' or boxName == 'bookmarks':
        bookmarksButton = 'buttonselected'

    # get the full domain, including any port number
    fullDomain = get_full_domain(domain, port)

    usersPath = '/users/' + nickname
    actor = http_prefix + '://' + fullDomain + usersPath

    showIndividualPostIcons = True

    # show an icon for new follow approvals
    followApprovals = ''
    followRequestsFilename = \
        acct_dir(base_dir, nickname, domain) + '/followrequests.txt'
    if os.path.isfile(followRequestsFilename):
        with open(followRequestsFilename, 'r') as f:
            for line in f:
                if len(line) > 0:
                    # show follow approvals icon
                    followApprovals = \
                        '<a href="' + usersPath + \
                        '/followers#buttonheader" ' + \
                        'accesskey="' + accessKeys['followButton'] + '">' + \
                        '<img loading="lazy" ' + \
                        'class="timelineicon" alt="' + \
                        translate['Approve follow requests'] + \
                        '" title="' + translate['Approve follow requests'] + \
                        '" src="/icons/person.png"/></a>\n'
                    break

    _log_timeline_timing(enableTimingLog, timelineStartTime, boxName, '3')

    # moderation / reports button
    moderationButtonStr = ''
    if moderator and not minimal:
        moderationButtonStr = \
            '<a href="' + usersPath + \
            '/moderation"><button class="' + \
            moderationButton + '"><span>' + \
            html_highlight_label(translate['Mod'], newReport) + \
            ' </span></button></a>'

    # shares, bookmarks and events buttons
    sharesButtonStr = ''
    wantedButtonStr = ''
    bookmarksButtonStr = ''
    eventsButtonStr = ''
    if not minimal:
        sharesButtonStr = \
            '<a href="' + usersPath + '/tlshares"><button class="' + \
            sharesButton + '"><span>' + \
            html_highlight_label(translate['Shares'], newShare) + \
            '</span></button></a>'

        wantedButtonStr = \
            '<a href="' + usersPath + '/tlwanted"><button class="' + \
            wantedButton + '"><span>' + \
            html_highlight_label(translate['Wanted'], newWanted) + \
            '</span></button></a>'

        bookmarksButtonStr = \
            '<a href="' + usersPath + '/tlbookmarks"><button class="' + \
            bookmarksButton + '"><span>' + translate['Bookmarks'] + \
            '</span></button></a>'

    instanceTitle = \
        get_config_param(base_dir, 'instanceTitle')
    tlStr = html_header_with_external_style(cssFilename, instanceTitle, None)

    _log_timeline_timing(enableTimingLog, timelineStartTime, boxName, '4')

    # if this is a news instance and we are viewing the news timeline
    newsHeader = False
    if defaultTimeline == 'tlfeatures' and boxName == 'tlfeatures':
        newsHeader = True

    newPostButtonStr = ''
    # start of headericons div
    if not newsHeader:
        if not icons_as_buttons:
            newPostButtonStr += '<div class="headericons">'

    # what screen to go to when a new post is created
    newPostButtonStr += \
        _html_timeline_new_post(manuallyApproveFollowers, boxName,
                                icons_as_buttons, usersPath, translate)

    # keyboard navigation
    tlStr += \
        _html_timeline_keyboard(moderator, text_mode_banner,
                                usersPath, nickname,
                                newCalendarEvent, newDM, newReply,
                                newShare, newWanted,
                                followApprovals, accessKeys, translate)

    # banner and row of buttons
    tlStr += \
        '<header>\n' + \
        '<a href="/users/' + nickname + '" title="' + \
        translate['Switch to profile view'] + '" alt="' + \
        translate['Switch to profile view'] + '">\n'
    tlStr += '<img loading="lazy" class="timeline-banner" ' + \
        'alt="" ' + \
        'src="' + usersPath + '/' + bannerFile + '" /></a>\n' + \
        '</header>\n'

    if full_width_tl_button_header:
        tlStr += \
            header_buttons_timeline(defaultTimeline, boxName, pageNumber,
                                    translate, usersPath, mediaButton,
                                    blogsButton, featuresButton,
                                    newsButton, inboxButton,
                                    dmButton, newDM, repliesButton,
                                    newReply, minimal, sentButton,
                                    sharesButtonStr, wantedButtonStr,
                                    bookmarksButtonStr,
                                    eventsButtonStr, moderationButtonStr,
                                    newPostButtonStr, base_dir, nickname,
                                    domain, timelineStartTime,
                                    newCalendarEvent, calendarPath,
                                    calendarImage, followApprovals,
                                    icons_as_buttons, accessKeys)

    # start the timeline
    tlStr += \
        '<table class="timeline">\n' + \
        '  <colgroup>\n' + \
        '    <col span="1" class="column-left">\n' + \
        '    <col span="1" class="column-center">\n' + \
        '    <col span="1" class="column-right">\n' + \
        '  </colgroup>\n' + \
        '  <tbody>\n' + \
        '    <tr>\n'

    domain_full = get_full_domain(domain, port)

    # left column
    leftColumnStr = \
        get_left_column_content(base_dir, nickname, domain_full,
                                http_prefix, translate,
                                editor, artist, False, None, rss_icon_at_top,
                                True, False, theme, accessKeys,
                                shared_items_federated_domains)
    tlStr += '  <td valign="top" class="col-left" ' + \
        'id="links" tabindex="-1">' + \
        leftColumnStr + '  </td>\n'
    # center column containing posts
    tlStr += '  <td valign="top" class="col-center">\n'

    if not full_width_tl_button_header:
        tlStr += \
            header_buttons_timeline(defaultTimeline, boxName, pageNumber,
                                    translate, usersPath, mediaButton,
                                    blogsButton, featuresButton,
                                    newsButton, inboxButton,
                                    dmButton, newDM, repliesButton,
                                    newReply, minimal, sentButton,
                                    sharesButtonStr, wantedButtonStr,
                                    bookmarksButtonStr,
                                    eventsButtonStr, moderationButtonStr,
                                    newPostButtonStr, base_dir, nickname,
                                    domain, timelineStartTime,
                                    newCalendarEvent, calendarPath,
                                    calendarImage, followApprovals,
                                    icons_as_buttons, accessKeys)

    tlStr += '  <div id="timelineposts" class="timeline-posts">\n'

    # second row of buttons for moderator actions
    tlStr += \
        _html_timeline_moderation_buttons(moderator, boxName, nickname,
                                          moderationActionStr, translate)

    _log_timeline_timing(enableTimingLog, timelineStartTime, boxName, '6')

    if boxName == 'tlshares':
        maxSharesPerAccount = itemsPerPage
        return (tlStr +
                _html_shares_timeline(translate, pageNumber, itemsPerPage,
                                      base_dir, actor, nickname, domain, port,
                                      maxSharesPerAccount, http_prefix,
                                      shared_items_federated_domains,
                                      'shares') +
                _html_timeline_end(base_dir, nickname, domain_full,
                                   http_prefix, translate,
                                   moderator, editor,
                                   newswire, positive_voting,
                                   show_publish_as_icon,
                                   rss_icon_at_top, publish_button_at_top,
                                   authorized, theme,
                                   defaultTimeline, accessKeys,
                                   boxName,
                                   enableTimingLog, timelineStartTime) +
                html_footer())
    elif boxName == 'tlwanted':
        maxSharesPerAccount = itemsPerPage
        return (tlStr +
                _html_shares_timeline(translate, pageNumber, itemsPerPage,
                                      base_dir, actor, nickname, domain, port,
                                      maxSharesPerAccount, http_prefix,
                                      shared_items_federated_domains,
                                      'wanted') +
                _html_timeline_end(base_dir, nickname, domain_full,
                                   http_prefix, translate,
                                   moderator, editor,
                                   newswire, positive_voting,
                                   show_publish_as_icon,
                                   rss_icon_at_top, publish_button_at_top,
                                   authorized, theme,
                                   defaultTimeline, accessKeys,
                                   boxName,
                                   enableTimingLog, timelineStartTime) +
                html_footer())

    _log_timeline_timing(enableTimingLog, timelineStartTime, boxName, '7')

    # separator between posts which only appears in shell browsers
    # such as Lynx and is not read by screen readers
    if boxName != 'tlmedia':
        textModeSeparator = \
            '<div class="transparent"><hr></div>'
    else:
        textModeSeparator = ''

    # page up arrow
    if pageNumber > 1:
        tlStr += textModeSeparator
        tlStr += '<br>' + _page_number_buttons(usersPath, boxName, pageNumber)
        tlStr += \
            '  <center>\n' + \
            '    <a href="' + usersPath + '/' + boxName + \
            '?page=' + str(pageNumber - 1) + \
            '" accesskey="' + accessKeys['Page up'] + '">' + \
            '<img loading="lazy" class="pageicon" src="/' + \
            'icons/pageup.png" title="' + \
            translate['Page up'] + '" alt="' + \
            translate['Page up'] + '"></a>\n' + \
            '  </center>\n'

    # show the posts
    itemCtr = 0
    if timelineJson:
        if 'orderedItems' not in timelineJson:
            print('ERROR: no orderedItems in timeline for '
                  + boxName + ' ' + str(timelineJson))
            return ''

    useCacheOnly = False
    if boxName == 'inbox':
        useCacheOnly = True

    if timelineJson:
        # if this is the media timeline then add an extra gallery container
        if boxName == 'tlmedia':
            if pageNumber > 1:
                tlStr += '<br>'
            tlStr += '<div class="galleryContainer">\n'

        # show each post in the timeline
        for item in timelineJson['orderedItems']:
            if item['type'] == 'Create' or \
               item['type'] == 'Announce':
                # is the actor who sent this post snoozed?
                if is_person_snoozed(base_dir, nickname, domain,
                                     item['actor']):
                    continue
                if is_self_announce(item):
                    continue

                # is the post in the memory cache of recent ones?
                currTlStr = None
                if boxName != 'tlmedia' and recent_posts_cache.get('html'):
                    post_id = remove_id_ending(item['id']).replace('/', '#')
                    if recent_posts_cache['html'].get(post_id):
                        currTlStr = recent_posts_cache['html'][post_id]
                        currTlStr = \
                            prepare_post_from_html_cache(nickname,
                                                         currTlStr,
                                                         boxName,
                                                         pageNumber)
                        _log_timeline_timing(enableTimingLog,
                                             timelineStartTime,
                                             boxName, '10')

                if not currTlStr:
                    _log_timeline_timing(enableTimingLog,
                                         timelineStartTime,
                                         boxName, '11')

                    # read the post from disk
                    currTlStr = \
                        individual_post_as_html(signing_priv_key_pem,
                                                False, recent_posts_cache,
                                                max_recent_posts,
                                                translate, pageNumber,
                                                base_dir, session,
                                                cached_webfingers,
                                                person_cache,
                                                nickname, domain, port,
                                                item, None, True,
                                                allow_deletion,
                                                http_prefix, project_version,
                                                boxName,
                                                yt_replace_domain,
                                                twitter_replacement_domain,
                                                show_published_date_only,
                                                peertube_instances,
                                                allow_local_network_access,
                                                theme, system_language,
                                                max_like_count,
                                                boxName != 'dm',
                                                showIndividualPostIcons,
                                                manuallyApproveFollowers,
                                                False, True, useCacheOnly,
                                                cw_lists, lists_enabled)
                    _log_timeline_timing(enableTimingLog,
                                         timelineStartTime, boxName, '12')

                if currTlStr:
                    if currTlStr not in tlStr:
                        itemCtr += 1
                        tlStr += textModeSeparator + currTlStr
                        if separatorStr:
                            tlStr += separatorStr
        if boxName == 'tlmedia':
            tlStr += '</div>\n'

    if itemCtr < 3:
        print('Items added to html timeline ' + boxName + ': ' +
              str(itemCtr) + ' ' + str(timelineJson['orderedItems']))

    # page down arrow
    if itemCtr > 0:
        tlStr += textModeSeparator
        tlStr += \
            '      <br>\n' + \
            '      <center>\n' + \
            '        <a href="' + usersPath + '/' + boxName + '?page=' + \
            str(pageNumber + 1) + \
            '" accesskey="' + accessKeys['Page down'] + '">' + \
            '<img loading="lazy" class="pageicon" src="/' + \
            'icons/pagedown.png" title="' + \
            translate['Page down'] + '" alt="' + \
            translate['Page down'] + '"></a>\n' + \
            '      </center>\n'
        tlStr += _page_number_buttons(usersPath, boxName, pageNumber)
        tlStr += textModeSeparator
    elif itemCtr == 0:
        tlStr += _get_help_for_timeline(base_dir, boxName)

    tlStr += \
        _html_timeline_end(base_dir, nickname, domain_full,
                           http_prefix, translate,
                           moderator, editor,
                           newswire, positive_voting,
                           show_publish_as_icon,
                           rss_icon_at_top, publish_button_at_top,
                           authorized, theme,
                           defaultTimeline, accessKeys,
                           boxName,
                           enableTimingLog, timelineStartTime)
    tlStr += html_footer()
    return tlStr


def html_individual_share(domain: str, shareId: str,
                          actor: str, sharedItem: {}, translate: {},
                          showContact: bool, removeButton: bool,
                          sharesFileType: str) -> str:
    """Returns an individual shared item as html
    """
    profileStr = '<div class="container">\n'
    profileStr += \
        '<p class="share-title">' + sharedItem['displayName'] + '</p>\n'
    if sharedItem.get('imageUrl'):
        profileStr += '<a href="' + sharedItem['imageUrl'] + '">\n'
        profileStr += \
            '<img loading="lazy" src="' + sharedItem['imageUrl'] + \
            '" alt="' + translate['Item image'] + '">\n</a>\n'
    profileStr += '<p>' + sharedItem['summary'] + '</p>\n<p>'
    if sharedItem.get('itemQty'):
        if sharedItem['itemQty'] > 1:
            profileStr += \
                '<b>' + translate['Quantity'] + ':</b> ' + \
                str(sharedItem['itemQty']) + '<br>'
    profileStr += \
        '<b>' + translate['Type'] + ':</b> ' + sharedItem['itemType'] + '<br>'
    profileStr += \
        '<b>' + translate['Category'] + ':</b> ' + \
        sharedItem['category'] + '<br>'
    if sharedItem.get('location'):
        profileStr += \
            '<b>' + translate['Location'] + ':</b> ' + \
            sharedItem['location'] + '<br>'
    contactTitleStr = translate['Contact']
    if sharedItem.get('itemPrice') and sharedItem.get('itemCurrency'):
        if is_float(sharedItem['itemPrice']):
            if float(sharedItem['itemPrice']) > 0:
                profileStr += ' ' + \
                    '<b>' + translate['Price'] + ':</b> ' + \
                    sharedItem['itemPrice'] + ' ' + sharedItem['itemCurrency']
                contactTitleStr = translate['Buy']
    profileStr += '</p>\n'
    sharedesc = sharedItem['displayName']
    if '<' not in sharedesc and ';' not in sharedesc:
        if showContact:
            buttonStyleStr = 'button'
            if sharedItem['category'] == 'accommodation':
                contactTitleStr = translate['Request to stay']
                buttonStyleStr = 'contactbutton'

            contactActor = sharedItem['actor']
            profileStr += \
                '<p>' + \
                '<a href="' + actor + \
                '?replydm=sharedesc:' + sharedesc + \
                '?mention=' + contactActor + '">' + \
                '<button class="' + buttonStyleStr + '">' + \
                contactTitleStr + '</button></a>\n'
            profileStr += \
                '<a href="' + contactActor + '"><button class="button">' + \
                translate['Profile'] + '</button></a>\n'
        if removeButton and domain in shareId:
            if sharesFileType == 'shares':
                profileStr += \
                    ' <a href="' + actor + '?rmshare=' + shareId + \
                    '"><button class="button">' + \
                    translate['Remove'] + '</button></a>\n'
            else:
                profileStr += \
                    ' <a href="' + actor + '?rmwanted=' + shareId + \
                    '"><button class="button">' + \
                    translate['Remove'] + '</button></a>\n'
    profileStr += '</div>\n'
    return profileStr


def _html_shares_timeline(translate: {}, pageNumber: int, itemsPerPage: int,
                          base_dir: str, actor: str,
                          nickname: str, domain: str, port: int,
                          maxSharesPerAccount: int, http_prefix: str,
                          shared_items_federated_domains: [],
                          sharesFileType: str) -> str:
    """Show shared items timeline as html
    """
    sharesJson, lastPage = \
        shares_timeline_json(actor, pageNumber, itemsPerPage,
                             base_dir, domain, nickname, maxSharesPerAccount,
                             shared_items_federated_domains, sharesFileType)
    domain_full = get_full_domain(domain, port)
    actor = local_actor_url(http_prefix, nickname, domain_full)
    adminNickname = get_config_param(base_dir, 'admin')
    adminActor = ''
    if adminNickname:
        adminActor = \
            local_actor_url(http_prefix, adminNickname, domain_full)
    timelineStr = ''

    if pageNumber > 1:
        timelineStr += '<br>' + \
            _page_number_buttons(actor, 'tl' + sharesFileType, pageNumber)
        timelineStr += \
            '  <center>\n' + \
            '    <a href="' + actor + '/tl' + sharesFileType + '?page=' + \
            str(pageNumber - 1) + \
            '"><img loading="lazy" class="pageicon" src="/' + \
            'icons/pageup.png" title="' + translate['Page up'] + \
            '" alt="' + translate['Page up'] + '"></a>\n' + \
            '  </center>\n'

    separatorStr = html_post_separator(base_dir, None)
    ctr = 0

    isAdminAccount = False
    if adminActor and actor == adminActor:
        isAdminAccount = True
    is_moderatorAccount = False
    if is_moderator(base_dir, nickname):
        is_moderatorAccount = True

    for published, sharedItem in sharesJson.items():
        showContactButton = False
        if sharedItem['actor'] != actor:
            showContactButton = True
        showRemoveButton = False
        if '___' + domain in sharedItem['shareId']:
            if sharedItem['actor'] == actor or \
               isAdminAccount or is_moderatorAccount:
                showRemoveButton = True
        timelineStr += \
            html_individual_share(domain, sharedItem['shareId'],
                                  actor, sharedItem, translate,
                                  showContactButton, showRemoveButton,
                                  sharesFileType)
        timelineStr += separatorStr
        ctr += 1

    if ctr == 0:
        timelineStr += _get_help_for_timeline(base_dir, 'tl' + sharesFileType)

    if not lastPage:
        timelineStr += \
            '  <center>\n' + \
            '    <a href="' + actor + '/tl' + sharesFileType + '?page=' + \
            str(pageNumber + 1) + \
            '"><img loading="lazy" class="pageicon" src="/' + \
            'icons/pagedown.png" title="' + translate['Page down'] + \
            '" alt="' + translate['Page down'] + '"></a>\n' + \
            '  </center>\n'
        timelineStr += \
            _page_number_buttons(actor, 'tl' + sharesFileType, pageNumber)

    return timelineStr


def html_shares(css_cache: {}, defaultTimeline: str,
                recent_posts_cache: {}, max_recent_posts: int,
                translate: {}, pageNumber: int, itemsPerPage: int,
                session, base_dir: str,
                cached_webfingers: {}, person_cache: {},
                nickname: str, domain: str, port: int,
                allow_deletion: bool,
                http_prefix: str, project_version: str,
                yt_replace_domain: str,
                twitter_replacement_domain: str,
                show_published_date_only: bool,
                newswire: {}, positive_voting: bool,
                show_publish_as_icon: bool,
                full_width_tl_button_header: bool,
                icons_as_buttons: bool,
                rss_icon_at_top: bool,
                publish_button_at_top: bool,
                authorized: bool, theme: str,
                peertube_instances: [],
                allow_local_network_access: bool,
                text_mode_banner: str,
                accessKeys: {}, system_language: str,
                max_like_count: int,
                shared_items_federated_domains: [],
                signing_priv_key_pem: str,
                cw_lists: {}, lists_enabled: str) -> str:
    """Show the shares timeline as html
    """
    manuallyApproveFollowers = \
        follower_approval_active(base_dir, nickname, domain)
    artist = is_artist(base_dir, nickname)

    return html_timeline(css_cache, defaultTimeline,
                         recent_posts_cache, max_recent_posts,
                         translate, pageNumber,
                         itemsPerPage, session, base_dir,
                         cached_webfingers, person_cache,
                         nickname, domain, port, None,
                         'tlshares', allow_deletion,
                         http_prefix, project_version,
                         manuallyApproveFollowers,
                         False,
                         yt_replace_domain,
                         twitter_replacement_domain,
                         show_published_date_only,
                         newswire, False, False, artist,
                         positive_voting, show_publish_as_icon,
                         full_width_tl_button_header,
                         icons_as_buttons, rss_icon_at_top,
                         publish_button_at_top,
                         authorized, None, theme, peertube_instances,
                         allow_local_network_access, text_mode_banner,
                         accessKeys, system_language, max_like_count,
                         shared_items_federated_domains,
                         signing_priv_key_pem,
                         cw_lists, lists_enabled)


def html_wanted(css_cache: {}, defaultTimeline: str,
                recent_posts_cache: {}, max_recent_posts: int,
                translate: {}, pageNumber: int, itemsPerPage: int,
                session, base_dir: str,
                cached_webfingers: {}, person_cache: {},
                nickname: str, domain: str, port: int,
                allow_deletion: bool,
                http_prefix: str, project_version: str,
                yt_replace_domain: str,
                twitter_replacement_domain: str,
                show_published_date_only: bool,
                newswire: {}, positive_voting: bool,
                show_publish_as_icon: bool,
                full_width_tl_button_header: bool,
                icons_as_buttons: bool,
                rss_icon_at_top: bool,
                publish_button_at_top: bool,
                authorized: bool, theme: str,
                peertube_instances: [],
                allow_local_network_access: bool,
                text_mode_banner: str,
                accessKeys: {}, system_language: str,
                max_like_count: int,
                shared_items_federated_domains: [],
                signing_priv_key_pem: str,
                cw_lists: {}, lists_enabled: str) -> str:
    """Show the wanted timeline as html
    """
    manuallyApproveFollowers = \
        follower_approval_active(base_dir, nickname, domain)
    artist = is_artist(base_dir, nickname)

    return html_timeline(css_cache, defaultTimeline,
                         recent_posts_cache, max_recent_posts,
                         translate, pageNumber,
                         itemsPerPage, session, base_dir,
                         cached_webfingers, person_cache,
                         nickname, domain, port, None,
                         'tlwanted', allow_deletion,
                         http_prefix, project_version,
                         manuallyApproveFollowers,
                         False,
                         yt_replace_domain,
                         twitter_replacement_domain,
                         show_published_date_only,
                         newswire, False, False, artist,
                         positive_voting, show_publish_as_icon,
                         full_width_tl_button_header,
                         icons_as_buttons, rss_icon_at_top,
                         publish_button_at_top,
                         authorized, None, theme, peertube_instances,
                         allow_local_network_access, text_mode_banner,
                         accessKeys, system_language, max_like_count,
                         shared_items_federated_domains,
                         signing_priv_key_pem,
                         cw_lists, lists_enabled)


def html_inbox(css_cache: {}, defaultTimeline: str,
               recent_posts_cache: {}, max_recent_posts: int,
               translate: {}, pageNumber: int, itemsPerPage: int,
               session, base_dir: str,
               cached_webfingers: {}, person_cache: {},
               nickname: str, domain: str, port: int, inboxJson: {},
               allow_deletion: bool,
               http_prefix: str, project_version: str,
               minimal: bool,
               yt_replace_domain: str,
               twitter_replacement_domain: str,
               show_published_date_only: bool,
               newswire: {}, positive_voting: bool,
               show_publish_as_icon: bool,
               full_width_tl_button_header: bool,
               icons_as_buttons: bool,
               rss_icon_at_top: bool,
               publish_button_at_top: bool,
               authorized: bool, theme: str,
               peertube_instances: [],
               allow_local_network_access: bool,
               text_mode_banner: str,
               accessKeys: {}, system_language: str,
               max_like_count: int,
               shared_items_federated_domains: [],
               signing_priv_key_pem: str,
               cw_lists: {}, lists_enabled: str) -> str:
    """Show the inbox as html
    """
    manuallyApproveFollowers = \
        follower_approval_active(base_dir, nickname, domain)
    artist = is_artist(base_dir, nickname)

    return html_timeline(css_cache, defaultTimeline,
                         recent_posts_cache, max_recent_posts,
                         translate, pageNumber,
                         itemsPerPage, session, base_dir,
                         cached_webfingers, person_cache,
                         nickname, domain, port, inboxJson,
                         'inbox', allow_deletion,
                         http_prefix, project_version,
                         manuallyApproveFollowers,
                         minimal,
                         yt_replace_domain,
                         twitter_replacement_domain,
                         show_published_date_only,
                         newswire, False, False, artist,
                         positive_voting, show_publish_as_icon,
                         full_width_tl_button_header,
                         icons_as_buttons, rss_icon_at_top,
                         publish_button_at_top,
                         authorized, None, theme, peertube_instances,
                         allow_local_network_access, text_mode_banner,
                         accessKeys, system_language, max_like_count,
                         shared_items_federated_domains,
                         signing_priv_key_pem,
                         cw_lists, lists_enabled)


def html_bookmarks(css_cache: {}, defaultTimeline: str,
                   recent_posts_cache: {}, max_recent_posts: int,
                   translate: {}, pageNumber: int, itemsPerPage: int,
                   session, base_dir: str,
                   cached_webfingers: {}, person_cache: {},
                   nickname: str, domain: str, port: int, bookmarksJson: {},
                   allow_deletion: bool,
                   http_prefix: str, project_version: str,
                   minimal: bool,
                   yt_replace_domain: str,
                   twitter_replacement_domain: str,
                   show_published_date_only: bool,
                   newswire: {}, positive_voting: bool,
                   show_publish_as_icon: bool,
                   full_width_tl_button_header: bool,
                   icons_as_buttons: bool,
                   rss_icon_at_top: bool,
                   publish_button_at_top: bool,
                   authorized: bool, theme: str,
                   peertube_instances: [],
                   allow_local_network_access: bool,
                   text_mode_banner: str,
                   accessKeys: {}, system_language: str,
                   max_like_count: int,
                   shared_items_federated_domains: [],
                   signing_priv_key_pem: str,
                   cw_lists: {}, lists_enabled: str) -> str:
    """Show the bookmarks as html
    """
    manuallyApproveFollowers = \
        follower_approval_active(base_dir, nickname, domain)
    artist = is_artist(base_dir, nickname)

    return html_timeline(css_cache, defaultTimeline,
                         recent_posts_cache, max_recent_posts,
                         translate, pageNumber,
                         itemsPerPage, session, base_dir,
                         cached_webfingers, person_cache,
                         nickname, domain, port, bookmarksJson,
                         'tlbookmarks', allow_deletion,
                         http_prefix, project_version,
                         manuallyApproveFollowers,
                         minimal,
                         yt_replace_domain,
                         twitter_replacement_domain,
                         show_published_date_only,
                         newswire, False, False, artist,
                         positive_voting, show_publish_as_icon,
                         full_width_tl_button_header,
                         icons_as_buttons, rss_icon_at_top,
                         publish_button_at_top,
                         authorized, None, theme, peertube_instances,
                         allow_local_network_access, text_mode_banner,
                         accessKeys, system_language, max_like_count,
                         shared_items_federated_domains, signing_priv_key_pem,
                         cw_lists, lists_enabled)


def html_inbox_d_ms(css_cache: {}, defaultTimeline: str,
                    recent_posts_cache: {}, max_recent_posts: int,
                    translate: {}, pageNumber: int, itemsPerPage: int,
                    session, base_dir: str,
                    cached_webfingers: {}, person_cache: {},
                    nickname: str, domain: str, port: int, inboxJson: {},
                    allow_deletion: bool,
                    http_prefix: str, project_version: str,
                    minimal: bool,
                    yt_replace_domain: str,
                    twitter_replacement_domain: str,
                    show_published_date_only: bool,
                    newswire: {}, positive_voting: bool,
                    show_publish_as_icon: bool,
                    full_width_tl_button_header: bool,
                    icons_as_buttons: bool,
                    rss_icon_at_top: bool,
                    publish_button_at_top: bool,
                    authorized: bool, theme: str,
                    peertube_instances: [],
                    allow_local_network_access: bool,
                    text_mode_banner: str,
                    accessKeys: {}, system_language: str,
                    max_like_count: int,
                    shared_items_federated_domains: [],
                    signing_priv_key_pem: str,
                    cw_lists: {}, lists_enabled: str) -> str:
    """Show the DM timeline as html
    """
    artist = is_artist(base_dir, nickname)
    return html_timeline(css_cache, defaultTimeline,
                         recent_posts_cache, max_recent_posts,
                         translate, pageNumber,
                         itemsPerPage, session, base_dir,
                         cached_webfingers, person_cache,
                         nickname, domain, port, inboxJson,
                         'dm', allow_deletion,
                         http_prefix, project_version, False, minimal,
                         yt_replace_domain,
                         twitter_replacement_domain,
                         show_published_date_only,
                         newswire, False, False, artist, positive_voting,
                         show_publish_as_icon,
                         full_width_tl_button_header,
                         icons_as_buttons, rss_icon_at_top,
                         publish_button_at_top,
                         authorized, None, theme, peertube_instances,
                         allow_local_network_access, text_mode_banner,
                         accessKeys, system_language, max_like_count,
                         shared_items_federated_domains,
                         signing_priv_key_pem,
                         cw_lists, lists_enabled)


def html_inbox_replies(css_cache: {}, defaultTimeline: str,
                       recent_posts_cache: {}, max_recent_posts: int,
                       translate: {}, pageNumber: int, itemsPerPage: int,
                       session, base_dir: str,
                       cached_webfingers: {}, person_cache: {},
                       nickname: str, domain: str, port: int, inboxJson: {},
                       allow_deletion: bool,
                       http_prefix: str, project_version: str,
                       minimal: bool,
                       yt_replace_domain: str,
                       twitter_replacement_domain: str,
                       show_published_date_only: bool,
                       newswire: {}, positive_voting: bool,
                       show_publish_as_icon: bool,
                       full_width_tl_button_header: bool,
                       icons_as_buttons: bool,
                       rss_icon_at_top: bool,
                       publish_button_at_top: bool,
                       authorized: bool, theme: str,
                       peertube_instances: [],
                       allow_local_network_access: bool,
                       text_mode_banner: str,
                       accessKeys: {}, system_language: str,
                       max_like_count: int,
                       shared_items_federated_domains: [],
                       signing_priv_key_pem: str,
                       cw_lists: {}, lists_enabled: str) -> str:
    """Show the replies timeline as html
    """
    artist = is_artist(base_dir, nickname)
    return html_timeline(css_cache, defaultTimeline,
                         recent_posts_cache, max_recent_posts,
                         translate, pageNumber,
                         itemsPerPage, session, base_dir,
                         cached_webfingers, person_cache,
                         nickname, domain, port, inboxJson, 'tlreplies',
                         allow_deletion, http_prefix, project_version, False,
                         minimal,
                         yt_replace_domain,
                         twitter_replacement_domain,
                         show_published_date_only,
                         newswire, False, False, artist,
                         positive_voting, show_publish_as_icon,
                         full_width_tl_button_header,
                         icons_as_buttons, rss_icon_at_top,
                         publish_button_at_top,
                         authorized, None, theme, peertube_instances,
                         allow_local_network_access, text_mode_banner,
                         accessKeys, system_language, max_like_count,
                         shared_items_federated_domains, signing_priv_key_pem,
                         cw_lists, lists_enabled)


def html_inbox_media(css_cache: {}, defaultTimeline: str,
                     recent_posts_cache: {}, max_recent_posts: int,
                     translate: {}, pageNumber: int, itemsPerPage: int,
                     session, base_dir: str,
                     cached_webfingers: {}, person_cache: {},
                     nickname: str, domain: str, port: int, inboxJson: {},
                     allow_deletion: bool,
                     http_prefix: str, project_version: str,
                     minimal: bool,
                     yt_replace_domain: str,
                     twitter_replacement_domain: str,
                     show_published_date_only: bool,
                     newswire: {}, positive_voting: bool,
                     show_publish_as_icon: bool,
                     full_width_tl_button_header: bool,
                     icons_as_buttons: bool,
                     rss_icon_at_top: bool,
                     publish_button_at_top: bool,
                     authorized: bool, theme: str,
                     peertube_instances: [],
                     allow_local_network_access: bool,
                     text_mode_banner: str,
                     accessKeys: {}, system_language: str,
                     max_like_count: int,
                     shared_items_federated_domains: [],
                     signing_priv_key_pem: str,
                     cw_lists: {}, lists_enabled: str) -> str:
    """Show the media timeline as html
    """
    artist = is_artist(base_dir, nickname)
    return html_timeline(css_cache, defaultTimeline,
                         recent_posts_cache, max_recent_posts,
                         translate, pageNumber,
                         itemsPerPage, session, base_dir,
                         cached_webfingers, person_cache,
                         nickname, domain, port, inboxJson, 'tlmedia',
                         allow_deletion, http_prefix, project_version, False,
                         minimal,
                         yt_replace_domain,
                         twitter_replacement_domain,
                         show_published_date_only,
                         newswire, False, False, artist,
                         positive_voting, show_publish_as_icon,
                         full_width_tl_button_header,
                         icons_as_buttons, rss_icon_at_top,
                         publish_button_at_top,
                         authorized, None, theme, peertube_instances,
                         allow_local_network_access, text_mode_banner,
                         accessKeys, system_language, max_like_count,
                         shared_items_federated_domains, signing_priv_key_pem,
                         cw_lists, lists_enabled)


def html_inbox_blogs(css_cache: {}, defaultTimeline: str,
                     recent_posts_cache: {}, max_recent_posts: int,
                     translate: {}, pageNumber: int, itemsPerPage: int,
                     session, base_dir: str,
                     cached_webfingers: {}, person_cache: {},
                     nickname: str, domain: str, port: int, inboxJson: {},
                     allow_deletion: bool,
                     http_prefix: str, project_version: str,
                     minimal: bool,
                     yt_replace_domain: str,
                     twitter_replacement_domain: str,
                     show_published_date_only: bool,
                     newswire: {}, positive_voting: bool,
                     show_publish_as_icon: bool,
                     full_width_tl_button_header: bool,
                     icons_as_buttons: bool,
                     rss_icon_at_top: bool,
                     publish_button_at_top: bool,
                     authorized: bool, theme: str,
                     peertube_instances: [],
                     allow_local_network_access: bool,
                     text_mode_banner: str,
                     accessKeys: {}, system_language: str,
                     max_like_count: int,
                     shared_items_federated_domains: [],
                     signing_priv_key_pem: str,
                     cw_lists: {}, lists_enabled: str) -> str:
    """Show the blogs timeline as html
    """
    artist = is_artist(base_dir, nickname)
    return html_timeline(css_cache, defaultTimeline,
                         recent_posts_cache, max_recent_posts,
                         translate, pageNumber,
                         itemsPerPage, session, base_dir,
                         cached_webfingers, person_cache,
                         nickname, domain, port, inboxJson, 'tlblogs',
                         allow_deletion, http_prefix, project_version, False,
                         minimal,
                         yt_replace_domain,
                         twitter_replacement_domain,
                         show_published_date_only,
                         newswire, False, False, artist,
                         positive_voting, show_publish_as_icon,
                         full_width_tl_button_header,
                         icons_as_buttons, rss_icon_at_top,
                         publish_button_at_top,
                         authorized, None, theme, peertube_instances,
                         allow_local_network_access, text_mode_banner,
                         accessKeys, system_language, max_like_count,
                         shared_items_federated_domains, signing_priv_key_pem,
                         cw_lists, lists_enabled)


def html_inbox_features(css_cache: {}, defaultTimeline: str,
                        recent_posts_cache: {}, max_recent_posts: int,
                        translate: {}, pageNumber: int, itemsPerPage: int,
                        session, base_dir: str,
                        cached_webfingers: {}, person_cache: {},
                        nickname: str, domain: str, port: int, inboxJson: {},
                        allow_deletion: bool,
                        http_prefix: str, project_version: str,
                        minimal: bool,
                        yt_replace_domain: str,
                        twitter_replacement_domain: str,
                        show_published_date_only: bool,
                        newswire: {}, positive_voting: bool,
                        show_publish_as_icon: bool,
                        full_width_tl_button_header: bool,
                        icons_as_buttons: bool,
                        rss_icon_at_top: bool,
                        publish_button_at_top: bool,
                        authorized: bool,
                        theme: str,
                        peertube_instances: [],
                        allow_local_network_access: bool,
                        text_mode_banner: str,
                        accessKeys: {}, system_language: str,
                        max_like_count: int,
                        shared_items_federated_domains: [],
                        signing_priv_key_pem: str,
                        cw_lists: {}, lists_enabled: str) -> str:
    """Show the features timeline as html
    """
    return html_timeline(css_cache, defaultTimeline,
                         recent_posts_cache, max_recent_posts,
                         translate, pageNumber,
                         itemsPerPage, session, base_dir,
                         cached_webfingers, person_cache,
                         nickname, domain, port, inboxJson, 'tlfeatures',
                         allow_deletion, http_prefix, project_version, False,
                         minimal,
                         yt_replace_domain,
                         twitter_replacement_domain,
                         show_published_date_only,
                         newswire, False, False, False,
                         positive_voting, show_publish_as_icon,
                         full_width_tl_button_header,
                         icons_as_buttons, rss_icon_at_top,
                         publish_button_at_top,
                         authorized, None, theme, peertube_instances,
                         allow_local_network_access, text_mode_banner,
                         accessKeys, system_language, max_like_count,
                         shared_items_federated_domains, signing_priv_key_pem,
                         cw_lists, lists_enabled)


def html_inbox_news(css_cache: {}, defaultTimeline: str,
                    recent_posts_cache: {}, max_recent_posts: int,
                    translate: {}, pageNumber: int, itemsPerPage: int,
                    session, base_dir: str,
                    cached_webfingers: {}, person_cache: {},
                    nickname: str, domain: str, port: int, inboxJson: {},
                    allow_deletion: bool,
                    http_prefix: str, project_version: str,
                    minimal: bool,
                    yt_replace_domain: str,
                    twitter_replacement_domain: str,
                    show_published_date_only: bool,
                    newswire: {}, moderator: bool, editor: bool, artist: bool,
                    positive_voting: bool, show_publish_as_icon: bool,
                    full_width_tl_button_header: bool,
                    icons_as_buttons: bool,
                    rss_icon_at_top: bool,
                    publish_button_at_top: bool,
                    authorized: bool, theme: str,
                    peertube_instances: [],
                    allow_local_network_access: bool,
                    text_mode_banner: str,
                    accessKeys: {}, system_language: str,
                    max_like_count: int,
                    shared_items_federated_domains: [],
                    signing_priv_key_pem: str,
                    cw_lists: {}, lists_enabled: str) -> str:
    """Show the news timeline as html
    """
    return html_timeline(css_cache, defaultTimeline,
                         recent_posts_cache, max_recent_posts,
                         translate, pageNumber,
                         itemsPerPage, session, base_dir,
                         cached_webfingers, person_cache,
                         nickname, domain, port, inboxJson, 'tlnews',
                         allow_deletion, http_prefix, project_version, False,
                         minimal,
                         yt_replace_domain,
                         twitter_replacement_domain,
                         show_published_date_only,
                         newswire, moderator, editor, artist,
                         positive_voting, show_publish_as_icon,
                         full_width_tl_button_header,
                         icons_as_buttons, rss_icon_at_top,
                         publish_button_at_top,
                         authorized, None, theme, peertube_instances,
                         allow_local_network_access, text_mode_banner,
                         accessKeys, system_language, max_like_count,
                         shared_items_federated_domains, signing_priv_key_pem,
                         cw_lists, lists_enabled)


def html_outbox(css_cache: {}, defaultTimeline: str,
                recent_posts_cache: {}, max_recent_posts: int,
                translate: {}, pageNumber: int, itemsPerPage: int,
                session, base_dir: str,
                cached_webfingers: {}, person_cache: {},
                nickname: str, domain: str, port: int, outboxJson: {},
                allow_deletion: bool,
                http_prefix: str, project_version: str,
                minimal: bool,
                yt_replace_domain: str,
                twitter_replacement_domain: str,
                show_published_date_only: bool,
                newswire: {}, positive_voting: bool,
                show_publish_as_icon: bool,
                full_width_tl_button_header: bool,
                icons_as_buttons: bool,
                rss_icon_at_top: bool,
                publish_button_at_top: bool,
                authorized: bool, theme: str,
                peertube_instances: [],
                allow_local_network_access: bool,
                text_mode_banner: str,
                accessKeys: {}, system_language: str,
                max_like_count: int,
                shared_items_federated_domains: [],
                signing_priv_key_pem: str,
                cw_lists: {}, lists_enabled: str) -> str:
    """Show the Outbox as html
    """
    manuallyApproveFollowers = \
        follower_approval_active(base_dir, nickname, domain)
    artist = is_artist(base_dir, nickname)
    return html_timeline(css_cache, defaultTimeline,
                         recent_posts_cache, max_recent_posts,
                         translate, pageNumber,
                         itemsPerPage, session, base_dir,
                         cached_webfingers, person_cache,
                         nickname, domain, port, outboxJson, 'outbox',
                         allow_deletion, http_prefix, project_version,
                         manuallyApproveFollowers, minimal,
                         yt_replace_domain,
                         twitter_replacement_domain,
                         show_published_date_only,
                         newswire, False, False, artist, positive_voting,
                         show_publish_as_icon,
                         full_width_tl_button_header,
                         icons_as_buttons, rss_icon_at_top,
                         publish_button_at_top,
                         authorized, None, theme, peertube_instances,
                         allow_local_network_access, text_mode_banner,
                         accessKeys, system_language, max_like_count,
                         shared_items_federated_domains, signing_priv_key_pem,
                         cw_lists, lists_enabled)
