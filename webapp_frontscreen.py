__filename__ = "webapp_frontscreen.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Timeline"

import os
from utils import isSystemAccount
from utils import getDomainFromActor
from utils import getConfigParam
from person import personBoxJson
from webapp_utils import htmlHeaderWithExternalStyle
from webapp_utils import htmlFooter
from webapp_utils import getBannerFile
from webapp_utils import htmlPostSeparator
from webapp_utils import headerButtonsFrontScreen
from webapp_column_left import getLeftColumnContent
from webapp_column_right import getRightColumnContent
from webapp_post import individualPostAsHtml


def _htmlFrontScreenPosts(recentPostsCache: {}, max_recent_posts: int,
                          translate: {},
                          base_dir: str, http_prefix: str,
                          nickname: str, domain: str, port: int,
                          session, cachedWebfingers: {}, personCache: {},
                          project_version: str,
                          yt_replace_domain: str,
                          twitterReplacementDomain: str,
                          show_published_date_only: bool,
                          peertubeInstances: [],
                          allow_local_network_access: bool,
                          themeName: str, systemLanguage: str,
                          max_like_count: int,
                          signingPrivateKeyPem: str, CWlists: {},
                          lists_enabled: str) -> str:
    """Shows posts on the front screen of a news instance
    These should only be public blog posts from the features timeline
    which is the blog timeline of the news actor
    """
    separatorStr = htmlPostSeparator(base_dir, None)
    profileStr = ''
    maxItems = 4
    ctr = 0
    currPage = 1
    boxName = 'tlfeatures'
    authorized = True
    while ctr < maxItems and currPage < 4:
        outboxFeedPathStr = \
            '/users/' + nickname + '/' + boxName + \
            '?page=' + str(currPage)
        outboxFeed = \
            personBoxJson({}, session, base_dir, domain, port,
                          outboxFeedPathStr,
                          http_prefix, 10, boxName,
                          authorized, 0, False, 0)
        if not outboxFeed:
            break
        if len(outboxFeed['orderedItems']) == 0:
            break
        for item in outboxFeed['orderedItems']:
            if item['type'] == 'Create':
                postStr = \
                    individualPostAsHtml(signingPrivateKeyPem,
                                         True, recentPostsCache,
                                         max_recent_posts,
                                         translate, None,
                                         base_dir, session,
                                         cachedWebfingers,
                                         personCache,
                                         nickname, domain, port, item,
                                         None, True, False,
                                         http_prefix, project_version, 'inbox',
                                         yt_replace_domain,
                                         twitterReplacementDomain,
                                         show_published_date_only,
                                         peertubeInstances,
                                         allow_local_network_access,
                                         themeName, systemLanguage,
                                         max_like_count,
                                         False, False, False,
                                         True, False, False,
                                         CWlists, lists_enabled)
                if postStr:
                    profileStr += postStr + separatorStr
                    ctr += 1
                    if ctr >= maxItems:
                        break
        currPage += 1
    return profileStr


def htmlFrontScreen(signingPrivateKeyPem: str,
                    rss_icon_at_top: bool,
                    cssCache: {}, icons_as_buttons: bool,
                    defaultTimeline: str,
                    recentPostsCache: {}, max_recent_posts: int,
                    translate: {}, project_version: str,
                    base_dir: str, http_prefix: str, authorized: bool,
                    profileJson: {}, selected: str,
                    session, cachedWebfingers: {}, personCache: {},
                    yt_replace_domain: str,
                    twitterReplacementDomain: str,
                    show_published_date_only: bool,
                    newswire: {}, theme: str,
                    peertubeInstances: [],
                    allow_local_network_access: bool,
                    accessKeys: {},
                    systemLanguage: str, max_like_count: int,
                    shared_items_federated_domains: [],
                    extraJson: {},
                    pageNumber: int,
                    maxItemsPerPage: int,
                    CWlists: {}, lists_enabled: str) -> str:
    """Show the news instance front screen
    """
    nickname = profileJson['preferredUsername']
    if not nickname:
        return ""
    if not isSystemAccount(nickname):
        return ""
    domain, port = getDomainFromActor(profileJson['id'])
    if not domain:
        return ""
    domainFull = domain
    if port:
        domainFull = domain + ':' + str(port)

    loginButton = headerButtonsFrontScreen(translate, nickname,
                                           'features', authorized,
                                           icons_as_buttons)

    # If this is the news account then show a different banner
    bannerFile, bannerFilename = \
        getBannerFile(base_dir, nickname, domain, theme)
    profileHeaderStr = \
        '<img loading="lazy" class="timeline-banner" ' + \
        'src="/users/' + nickname + '/' + bannerFile + '" />\n'
    if loginButton:
        profileHeaderStr += '<center>' + loginButton + '</center>\n'

    profileHeaderStr += \
        '<table class="timeline">\n' + \
        '  <colgroup>\n' + \
        '    <col span="1" class="column-left">\n' + \
        '    <col span="1" class="column-center">\n' + \
        '    <col span="1" class="column-right">\n' + \
        '  </colgroup>\n' + \
        '  <tbody>\n' + \
        '    <tr>\n' + \
        '      <td valign="top" class="col-left">\n'
    profileHeaderStr += \
        getLeftColumnContent(base_dir, 'news', domainFull,
                             http_prefix, translate,
                             False, False,
                             False, None, rss_icon_at_top, True,
                             True, theme, accessKeys,
                             shared_items_federated_domains)
    profileHeaderStr += \
        '      </td>\n' + \
        '      <td valign="top" class="col-center">\n'

    profileStr = profileHeaderStr

    cssFilename = base_dir + '/epicyon-profile.css'
    if os.path.isfile(base_dir + '/epicyon.css'):
        cssFilename = base_dir + '/epicyon.css'

    licenseStr = ''
    bannerFile, bannerFilename = \
        getBannerFile(base_dir, nickname, domain, theme)
    profileStr += \
        _htmlFrontScreenPosts(recentPostsCache, max_recent_posts,
                              translate,
                              base_dir, http_prefix,
                              nickname, domain, port,
                              session, cachedWebfingers, personCache,
                              project_version,
                              yt_replace_domain,
                              twitterReplacementDomain,
                              show_published_date_only,
                              peertubeInstances,
                              allow_local_network_access,
                              theme, systemLanguage,
                              max_like_count,
                              signingPrivateKeyPem,
                              CWlists, lists_enabled) + licenseStr

    # Footer which is only used for system accounts
    profileFooterStr = '      </td>\n'
    profileFooterStr += '      <td valign="top" class="col-right">\n'
    profileFooterStr += \
        getRightColumnContent(base_dir, 'news', domainFull,
                              http_prefix, translate,
                              False, False, newswire, False,
                              False, None, False, False,
                              False, True, authorized, True, theme,
                              defaultTimeline, accessKeys)
    profileFooterStr += \
        '      </td>\n' + \
        '  </tr>\n' + \
        '  </tbody>\n' + \
        '</table>\n'

    instanceTitle = \
        getConfigParam(base_dir, 'instanceTitle')
    profileStr = \
        htmlHeaderWithExternalStyle(cssFilename, instanceTitle, None) + \
        profileStr + profileFooterStr + htmlFooter()
    return profileStr
