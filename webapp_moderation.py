__filename__ = "webapp_moderation.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.3.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Moderation"

import os
from utils import is_artist
from utils import is_account_dir
from utils import get_full_domain
from utils import is_editor
from utils import load_json
from utils import get_nickname_from_actor
from utils import get_domain_from_actor
from utils import get_config_param
from utils import local_actor_url
from posts import download_follow_collection
from posts import get_public_post_info
from posts import is_moderator
from webapp_timeline import html_timeline
# from webapp_utils import get_person_avatar_url
from webapp_utils import get_content_warning_button
from webapp_utils import html_header_with_external_style
from webapp_utils import html_footer
from blocking import is_blocked_domain
from blocking import is_blocked
from session import create_session


def html_moderation(css_cache: {}, default_timeline: str,
                    recent_posts_cache: {}, max_recent_posts: int,
                    translate: {}, page_number: int, items_per_page: int,
                    session, base_dir: str, wf_request: {}, person_cache: {},
                    nickname: str, domain: str, port: int, inbox_json: {},
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
                    authorized: bool, moderation_action_str: str,
                    theme: str, peertube_instances: [],
                    allow_local_network_access: bool,
                    text_mode_banner: str,
                    access_keys: {}, system_language: str,
                    max_like_count: int,
                    shared_items_federated_domains: [],
                    signing_priv_key_pem: str,
                    cw_lists: {}, lists_enabled: str,
                    timezone: str) -> str:
    """Show the moderation feed as html
    This is what you see when selecting the "mod" timeline
    """
    artist = is_artist(base_dir, nickname)
    return html_timeline(css_cache, default_timeline,
                         recent_posts_cache, max_recent_posts,
                         translate, page_number,
                         items_per_page, session, base_dir,
                         wf_request, person_cache,
                         nickname, domain, port, inbox_json, 'moderation',
                         allow_deletion, http_prefix,
                         project_version, True, False,
                         yt_replace_domain,
                         twitter_replacement_domain,
                         show_published_date_only,
                         newswire, False, False, artist, positive_voting,
                         show_publish_as_icon,
                         full_width_tl_button_header,
                         icons_as_buttons, rss_icon_at_top,
                         publish_button_at_top,
                         authorized, moderation_action_str, theme,
                         peertube_instances, allow_local_network_access,
                         text_mode_banner, access_keys, system_language,
                         max_like_count, shared_items_federated_domains,
                         signing_priv_key_pem, cw_lists, lists_enabled,
                         timezone)


def html_account_info(css_cache: {}, translate: {},
                      base_dir: str, http_prefix: str,
                      nickname: str, domain: str, port: int,
                      search_handle: str, debug: bool,
                      system_language: str, signing_priv_key_pem: str) -> str:
    """Shows which domains a search handle interacts with.
    This screen is shown if a moderator enters a handle and selects info
    on the moderation screen
    """
    signing_priv_key_pem = None
    msg_str1 = 'This account interacts with the following instances'

    info_form = ''
    css_filename = base_dir + '/epicyon-profile.css'
    if os.path.isfile(base_dir + '/epicyon.css'):
        css_filename = base_dir + '/epicyon.css'

    instance_title = \
        get_config_param(base_dir, 'instanceTitle')
    info_form = \
        html_header_with_external_style(css_filename, instance_title, None)

    search_nickname = get_nickname_from_actor(search_handle)
    search_domain, search_port = get_domain_from_actor(search_handle)

    search_handle = search_nickname + '@' + search_domain
    search_actor = \
        local_actor_url(http_prefix, search_nickname, search_domain)
    info_form += \
        '<center><h1><a href="/users/' + nickname + '/moderation">' + \
        translate['Account Information'] + ':</a> <a href="' + search_actor + \
        '">' + search_handle + '</a></h1><br>\n'

    info_form += translate[msg_str1] + '</center><br><br>\n'

    proxy_type = 'tor'
    if not os.path.isfile('/usr/bin/tor'):
        proxy_type = None
    if domain.endswith('.i2p'):
        proxy_type = None

    session = create_session(proxy_type)

    word_frequency = {}
    origin_domain = None
    domain_dict = get_public_post_info(session, base_dir,
                                       search_nickname, search_domain,
                                       origin_domain,
                                       proxy_type, search_port,
                                       http_prefix, debug,
                                       __version__, word_frequency,
                                       system_language,
                                       signing_priv_key_pem)

    # get a list of any blocked followers
    followers_list = \
        download_follow_collection(signing_priv_key_pem,
                                   'followers', session,
                                   http_prefix, search_actor, 1, 5, debug)
    blocked_followers = []
    for follower_actor in followers_list:
        follower_nickname = get_nickname_from_actor(follower_actor)
        follower_domain, follower_port = get_domain_from_actor(follower_actor)
        follower_domain_full = get_full_domain(follower_domain, follower_port)
        if is_blocked(base_dir, nickname, domain,
                      follower_nickname, follower_domain_full):
            blocked_followers.append(follower_actor)

    # get a list of any blocked following
    following_list = \
        download_follow_collection(signing_priv_key_pem,
                                   'following', session,
                                   http_prefix, search_actor, 1, 5, debug)
    blocked_following = []
    for following_actor in following_list:
        following_nickname = get_nickname_from_actor(following_actor)
        following_domain, following_port = \
            get_domain_from_actor(following_actor)
        following_domain_full = \
            get_full_domain(following_domain, following_port)
        if is_blocked(base_dir, nickname, domain,
                      following_nickname, following_domain_full):
            blocked_following.append(following_actor)

    info_form += '<div class="accountInfoDomains">\n'
    users_path = '/users/' + nickname + '/accountinfo'
    ctr = 1
    for post_domain, blocked_post_urls in domain_dict.items():
        info_form += '<a href="' + \
            http_prefix + '://' + post_domain + '" ' + \
            'target="_blank" rel="nofollow noopener noreferrer">' + \
            post_domain + '</a> '
        if is_blocked_domain(base_dir, post_domain):
            blocked_posts_links = ''
            url_ctr = 0
            for url in blocked_post_urls:
                if url_ctr > 0:
                    blocked_posts_links += '<br>'
                blocked_posts_links += \
                    '<a href="' + url + '" ' + \
                    'target="_blank" rel="nofollow noopener noreferrer">' + \
                    url + '</a>'
                url_ctr += 1
            blocked_posts_html = ''
            if blocked_posts_links:
                block_no_str = 'blockNumber' + str(ctr)
                blocked_posts_html = \
                    get_content_warning_button(block_no_str,
                                               translate,
                                               blocked_posts_links)
                ctr += 1

            info_form += \
                '<a href="' + users_path + '?unblockdomain=' + post_domain + \
                '?handle=' + search_handle + '">'
            info_form += '<button class="buttonhighlighted"><span>' + \
                translate['Unblock'] + '</span></button></a> ' + \
                blocked_posts_html + '\n'
        else:
            info_form += \
                '<a href="' + users_path + '?blockdomain=' + post_domain + \
                '?handle=' + search_handle + '">'
            if post_domain != domain:
                info_form += '<button class="button"><span>' + \
                    translate['Block'] + '</span></button>'
            info_form += '</a>\n'
        info_form += '<br>\n'

    info_form += '</div>\n'

    if blocked_following:
        blocked_following.sort()
        info_form += '<div class="accountInfoDomains">\n'
        info_form += '<h1>' + translate['Blocked following'] + '</h1>\n'
        info_form += \
            '<p>' + \
            translate['Receives posts from the following accounts'] + \
            ':</p>\n'
        for actor in blocked_following:
            following_nickname = get_nickname_from_actor(actor)
            following_domain, following_port = get_domain_from_actor(actor)
            following_domain_full = \
                get_full_domain(following_domain, following_port)
            info_form += '<a href="' + actor + '" ' + \
                'target="_blank" rel="nofollow noopener noreferrer">' + \
                following_nickname + '@' + following_domain_full + \
                '</a><br><br>\n'
        info_form += '</div>\n'

    if blocked_followers:
        blocked_followers.sort()
        info_form += '<div class="accountInfoDomains">\n'
        info_form += '<h1>' + translate['Blocked followers'] + '</h1>\n'
        info_form += \
            '<p>' + \
            translate['Sends out posts to the following accounts'] + \
            ':</p>\n'
        for actor in blocked_followers:
            follower_nickname = get_nickname_from_actor(actor)
            follower_domain, follower_port = get_domain_from_actor(actor)
            follower_domain_full = \
                get_full_domain(follower_domain, follower_port)
            info_form += '<a href="' + actor + '" ' + \
                'target="_blank" rel="nofollow noopener noreferrer">' + \
                follower_nickname + '@' + \
                follower_domain_full + '</a><br><br>\n'
        info_form += '</div>\n'

    if word_frequency:
        max_count = 1
        for word, count in word_frequency.items():
            if count > max_count:
                max_count = count
        minimum_word_count = int(max_count / 2)
        if minimum_word_count >= 3:
            info_form += '<div class="accountInfoDomains">\n'
            info_form += '<h1>' + translate['Word frequencies'] + '</h1>\n'
            word_swarm = ''
            ctr = 0
            for word, count in word_frequency.items():
                if count >= minimum_word_count:
                    if ctr > 0:
                        word_swarm += ' '
                    if count < max_count - int(max_count / 4):
                        word_swarm += word
                    else:
                        if count != max_count:
                            word_swarm += '<b>' + word + '</b>'
                        else:
                            word_swarm += '<b><i>' + word + '</i></b>'
                    ctr += 1
            info_form += word_swarm
            info_form += '</div>\n'

    info_form += html_footer()
    return info_form


def html_moderation_info(css_cache: {}, translate: {},
                         base_dir: str, http_prefix: str,
                         nickname: str) -> str:
    msg_str1 = \
        'These are globally blocked for all accounts on this instance'
    msg_str2 = \
        'Any blocks or suspensions made by moderators will be shown here.'

    info_form = ''
    css_filename = base_dir + '/epicyon-profile.css'
    if os.path.isfile(base_dir + '/epicyon.css'):
        css_filename = base_dir + '/epicyon.css'

    instance_title = \
        get_config_param(base_dir, 'instanceTitle')
    info_form = html_header_with_external_style(css_filename,
                                                instance_title, None)

    info_form += \
        '<center><h1><a href="/users/' + nickname + '/moderation">' + \
        translate['Moderation Information'] + \
        '</a></h1></center><br>'

    info_shown = False

    accounts = []
    for _, dirs, _ in os.walk(base_dir + '/accounts'):
        for acct in dirs:
            if not is_account_dir(acct):
                continue
            accounts.append(acct)
        break
    accounts.sort()

    cols = 5
    if len(accounts) > 10:
        info_form += '<details><summary><b>' + translate['Show Accounts']
        info_form += '</b></summary>\n'
    info_form += '<div class="container">\n'
    info_form += '<table class="accountsTable">\n'
    info_form += '  <colgroup>\n'
    for col in range(cols):
        info_form += '    <col span="1" class="accountsTableCol">\n'
    info_form += '  </colgroup>\n'
    info_form += '<tr>\n'

    col = 0
    for acct in accounts:
        acct_nickname = acct.split('@')[0]
        account_dir = os.path.join(base_dir + '/accounts', acct)
        actor_json = load_json(account_dir + '.json')
        if not actor_json:
            continue
        actor = actor_json['id']
        avatar_url = ''
        ext = ''
        if actor_json.get('icon'):
            if actor_json['icon'].get('url'):
                avatar_url = actor_json['icon']['url']
                if '.' in avatar_url:
                    ext = '.' + avatar_url.split('.')[-1]
        acct_url = \
            '/users/' + nickname + '?options=' + actor + ';1;' + \
            '/members/' + acct_nickname + ext
        info_form += '<td>\n<a href="' + acct_url + '">'
        info_form += '<img loading="lazy" style="width:90%" '
        info_form += 'src="' + avatar_url + '" />'
        info_form += '<br><center>'
        if is_moderator(base_dir, acct_nickname):
            info_form += '<b><u>' + acct_nickname + '</u></b>'
        else:
            info_form += acct_nickname
        if is_editor(base_dir, acct_nickname):
            info_form += ' ✍'
        info_form += '</center></a>\n</td>\n'
        col += 1
        if col == cols:
            # new row of accounts
            info_form += '</tr>\n<tr>\n'
    info_form += '</tr>\n</table>\n'
    info_form += '</div>\n'
    if len(accounts) > 10:
        info_form += '</details>\n'

    suspended_filename = base_dir + '/accounts/suspended.txt'
    if os.path.isfile(suspended_filename):
        with open(suspended_filename, 'r') as fp_sus:
            suspended_str = fp_sus.read()
            info_form += '<div class="container">\n'
            info_form += '  <br><b>' + \
                translate['Suspended accounts'] + '</b>'
            info_form += '  <br>' + \
                translate['These are currently suspended']
            info_form += \
                '  <textarea id="message" ' + \
                'name="suspended" style="height:200px" spellcheck="false">' + \
                suspended_str + '</textarea>\n'
            info_form += '</div>\n'
            info_shown = True

    blocking_filename = base_dir + '/accounts/blocking.txt'
    if os.path.isfile(blocking_filename):
        with open(blocking_filename, 'r') as fp_block:
            blocked_str = fp_block.read()
            info_form += '<div class="container">\n'
            info_form += \
                '  <br><b>' + \
                translate['Blocked accounts and hashtags'] + '</b>'
            info_form += \
                '  <br>' + \
                translate[msg_str1]
            info_form += \
                '  <textarea id="message" ' + \
                'name="blocked" style="height:700px" spellcheck="false">' + \
                blocked_str + '</textarea>\n'
            info_form += '</div>\n'
            info_shown = True

    filters_filename = base_dir + '/accounts/filters.txt'
    if os.path.isfile(filters_filename):
        with open(filters_filename, 'r') as fp_filt:
            filtered_str = fp_filt.read()
            info_form += '<div class="container">\n'
            info_form += \
                '  <br><b>' + \
                translate['Filtered words'] + '</b>'
            info_form += \
                '  <textarea id="message" ' + \
                'name="filtered" style="height:700px" spellcheck="true">' + \
                filtered_str + '</textarea>\n'
            info_form += '</div>\n'
            info_shown = True

    if not info_shown:
        info_form += \
            '<center><p>' + \
            translate[msg_str2] + \
            '</p></center>\n'
    info_form += html_footer()
    return info_form
