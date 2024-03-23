__filename__ = "daemon_post_person_options.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.5.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Core POST"

import os
import errno
import urllib.parse
from socket import error as SocketError
from utils import get_nickname_from_actor
from httpcodes import write2
from httpcodes import http_404
from httpheaders import login_headers
from httpheaders import redirect_headers
from httpheaders import set_headers
from utils import refresh_newswire
from utils import acct_dir
from utils import get_config_param
from utils import get_domain_from_actor
from utils import get_full_domain
from utils import remove_eol
from session import establish_session
from webapp_profile import html_profile_after_search
from petnames import set_pet_name
from person import person_snooze
from person import person_unsnooze
from person import set_person_notes
from followingCalendar import add_person_to_calendar
from followingCalendar import remove_person_from_calendar
from webapp_person_options import person_minimize_images
from webapp_person_options import person_undo_minimize_images
from webapp_confirm import html_confirm_block
from webapp_confirm import html_confirm_unblock
from webapp_confirm import html_confirm_follow
from webapp_confirm import html_confirm_unfollow
from webapp_create_post import html_new_post
from webapp_moderation import html_account_info
from languages import get_understood_languages
from blocking import allowed_announce_add
from blocking import allowed_announce_remove
from notifyOnPost import add_notify_on_post
from notifyOnPost import remove_notify_on_post
from posts import is_moderator


def person_options2(self, path: str,
                    calling_domain: str, cookie: str,
                    base_dir: str, http_prefix: str,
                    domain: str, domain_full: str, port: int,
                    onion_domain: str, i2p_domain: str,
                    debug: bool, curr_session,
                    authorized: bool) -> None:
    """Receive POST from person options screen
    """
    page_number = 1
    users_path = path.split('/personoptions')[0]
    origin_path_str = http_prefix + '://' + domain_full + users_path

    chooser_nickname = get_nickname_from_actor(origin_path_str)
    if not chooser_nickname:
        if calling_domain.endswith('.onion') and onion_domain:
            origin_path_str = 'http://' + onion_domain + users_path
        elif (calling_domain.endswith('.i2p') and i2p_domain):
            origin_path_str = 'http://' + i2p_domain + users_path
        print('WARN: unable to find nickname in ' + origin_path_str)
        redirect_headers(self, origin_path_str, cookie, calling_domain)
        self.server.postreq_busy = False
        return

    length = int(self.headers['Content-length'])

    try:
        options_confirm_params = self.rfile.read(length).decode('utf-8')
    except SocketError as ex:
        if ex.errno == errno.ECONNRESET:
            print('EX: POST options_confirm_params ' +
                  'connection reset by peer')
        else:
            print('EX: POST options_confirm_params socket error')
        self.send_response(400)
        self.end_headers()
        self.server.postreq_busy = False
        return
    except ValueError as ex:
        print('EX: ' +
              'POST options_confirm_params rfile.read failed, ' + str(ex))
        self.send_response(400)
        self.end_headers()
        self.server.postreq_busy = False
        return
    options_confirm_params = \
        urllib.parse.unquote_plus(options_confirm_params)

    # page number to return to
    if 'pageNumber=' in options_confirm_params:
        page_number_str = options_confirm_params.split('pageNumber=')[1]
        if '&' in page_number_str:
            page_number_str = page_number_str.split('&')[0]
        if len(page_number_str) < 5:
            if page_number_str.isdigit():
                page_number = int(page_number_str)

    # actor for the person
    options_actor = options_confirm_params.split('actor=')[1]
    if '&' in options_actor:
        options_actor = options_actor.split('&')[0]

    # actor for the movedTo
    options_actor_moved = None
    if 'movedToActor=' in options_confirm_params:
        options_actor_moved = \
            options_confirm_params.split('movedToActor=')[1]
        if '&' in options_actor_moved:
            options_actor_moved = options_actor_moved.split('&')[0]

    # url of the avatar
    options_avatar_url = options_confirm_params.split('avatarUrl=')[1]
    if '&' in options_avatar_url:
        options_avatar_url = options_avatar_url.split('&')[0]

    # link to a post, which can then be included in reports
    post_url = None
    if 'postUrl' in options_confirm_params:
        post_url = options_confirm_params.split('postUrl=')[1]
        if '&' in post_url:
            post_url = post_url.split('&')[0]

    # petname for this person
    petname = None
    if 'optionpetname' in options_confirm_params:
        petname = options_confirm_params.split('optionpetname=')[1]
        if '&' in petname:
            petname = petname.split('&')[0]
        # Limit the length of the petname
        if len(petname) > 20 or \
           ' ' in petname or '/' in petname or \
           '?' in petname or '#' in petname:
            petname = None

    # notes about this person
    person_notes = None
    if 'optionnotes' in options_confirm_params:
        person_notes = options_confirm_params.split('optionnotes=')[1]
        if '&' in person_notes:
            person_notes = person_notes.split('&')[0]
        person_notes = urllib.parse.unquote_plus(person_notes.strip())
        # Limit the length of the notes
        if len(person_notes) > 64000:
            person_notes = None

    # get the nickname
    options_nickname = get_nickname_from_actor(options_actor)
    if not options_nickname:
        if calling_domain.endswith('.onion') and onion_domain:
            origin_path_str = 'http://' + onion_domain + users_path
        elif (calling_domain.endswith('.i2p') and i2p_domain):
            origin_path_str = 'http://' + i2p_domain + users_path
        print('WARN: unable to find nickname in ' + options_actor)
        redirect_headers(self, origin_path_str, cookie, calling_domain)
        self.server.postreq_busy = False
        return

    options_domain, options_port = get_domain_from_actor(options_actor)
    if not options_domain:
        if calling_domain.endswith('.onion') and onion_domain:
            origin_path_str = 'http://' + onion_domain + users_path
        elif (calling_domain.endswith('.i2p') and i2p_domain):
            origin_path_str = 'http://' + i2p_domain + users_path
        print('WARN: unable to find domain in ' + options_actor)
        redirect_headers(self, origin_path_str, cookie, calling_domain)
        self.server.postreq_busy = False
        return

    options_domain_full = get_full_domain(options_domain, options_port)
    if chooser_nickname == options_nickname and \
       options_domain == domain and \
       options_port == port:
        if debug:
            print('You cannot perform an option action on yourself')

    # person options screen, view button
    # See html_person_options
    if '&submitView=' in options_confirm_params:
        if debug:
            print('Viewing ' + options_actor)

        show_published_date_only = \
            self.server.show_published_date_only
        allow_local_network_access = \
            self.server.allow_local_network_access

        access_keys = self.server.access_keys
        if self.server.key_shortcuts.get(chooser_nickname):
            access_keys = self.server.key_shortcuts[chooser_nickname]

        signing_priv_key_pem = \
            self.server.signing_priv_key_pem
        twitter_replacement_domain = \
            self.server.twitter_replacement_domain
        peertube_instances = \
            self.server.peertube_instances
        yt_replace_domain = \
            self.server.yt_replace_domain
        cached_webfingers = \
            self.server.cached_webfingers
        recent_posts_cache = \
            self.server.recent_posts_cache
        timezone = None
        if self.server.account_timezone.get(chooser_nickname):
            timezone = \
                self.server.account_timezone.get(chooser_nickname)

        profile_handle = remove_eol(options_actor).strip()

        # establish the session
        curr_proxy_type = self.server.proxy_type
        if '.onion/' in profile_handle or \
           profile_handle.endswith('.onion'):
            curr_proxy_type = 'tor'
            curr_session = self.server.session_onion
        elif ('.i2p/' in profile_handle or
              profile_handle.endswith('.i2p')):
            curr_proxy_type = 'i2p'
            curr_session = self.server.session_i2p

        curr_session = \
            establish_session("handle search",
                              curr_session,
                              curr_proxy_type,
                              self.server)
        if not curr_session:
            self.server.postreq_busy = False
            return

        bold_reading = False
        if self.server.bold_reading.get(chooser_nickname):
            bold_reading = True

        min_images_for_accounts = \
            self.server.min_images_for_accounts
        max_shares_on_profile = \
            self.server.max_shares_on_profile
        profile_str = \
            html_profile_after_search(authorized,
                                      recent_posts_cache,
                                      self.server.max_recent_posts,
                                      self.server.translate,
                                      base_dir,
                                      users_path,
                                      http_prefix,
                                      chooser_nickname,
                                      domain,
                                      port,
                                      profile_handle,
                                      curr_session,
                                      cached_webfingers,
                                      self.server.person_cache,
                                      self.server.debug,
                                      self.server.project_version,
                                      yt_replace_domain,
                                      twitter_replacement_domain,
                                      show_published_date_only,
                                      self.server.default_timeline,
                                      peertube_instances,
                                      allow_local_network_access,
                                      self.server.theme_name,
                                      access_keys,
                                      self.server.system_language,
                                      self.server.max_like_count,
                                      signing_priv_key_pem,
                                      self.server.cw_lists,
                                      self.server.lists_enabled,
                                      timezone,
                                      self.server.onion_domain,
                                      self.server.i2p_domain,
                                      bold_reading,
                                      self.server.dogwhistles,
                                      min_images_for_accounts,
                                      self.server.buy_sites,
                                      max_shares_on_profile,
                                      self.server.no_of_books,
                                      self.server.auto_cw_cache)
        if profile_str:
            msg = profile_str.encode('utf-8')
            msglen = len(msg)
            login_headers(self, 'text/html',
                          msglen, calling_domain)
            write2(self, msg)
            self.server.postreq_busy = False
            return
        redirect_headers(self, options_actor,
                         cookie, calling_domain)
        self.server.postreq_busy = False
        return

    # person options screen, petname submit button
    # See html_person_options
    if '&submitPetname=' in options_confirm_params and petname:
        if debug:
            print('Change petname to ' + petname)
        handle = options_nickname + '@' + options_domain_full
        set_pet_name(base_dir,
                     chooser_nickname,
                     domain,
                     handle, petname)
        users_path_str = \
            users_path + '/' + self.server.default_timeline + \
            '?page=' + str(page_number)
        redirect_headers(self, users_path_str, cookie,
                         calling_domain)
        self.server.postreq_busy = False
        return

    # person options screen, person notes submit button
    # See html_person_options
    if '&submitPersonNotes=' in options_confirm_params:
        if debug:
            print('Change person notes')
        handle = options_nickname + '@' + options_domain_full
        if not person_notes:
            person_notes = ''
        set_person_notes(base_dir,
                         chooser_nickname,
                         domain,
                         handle, person_notes)
        users_path_str = \
            users_path + '/' + self.server.default_timeline + \
            '?page=' + str(page_number)
        redirect_headers(self, users_path_str, cookie,
                         calling_domain)
        self.server.postreq_busy = False
        return

    # person options screen, on calendar checkbox
    # See html_person_options
    if '&submitOnCalendar=' in options_confirm_params:
        on_calendar = None
        if 'onCalendar=' in options_confirm_params:
            on_calendar = options_confirm_params.split('onCalendar=')[1]
            if '&' in on_calendar:
                on_calendar = on_calendar.split('&')[0]
        if on_calendar == 'on':
            add_person_to_calendar(base_dir,
                                   chooser_nickname,
                                   domain,
                                   options_nickname,
                                   options_domain_full)
        else:
            remove_person_from_calendar(base_dir,
                                        chooser_nickname,
                                        domain,
                                        options_nickname,
                                        options_domain_full)
        users_path_str = \
            users_path + '/' + self.server.default_timeline + \
            '?page=' + str(page_number)
        redirect_headers(self, users_path_str, cookie,
                         calling_domain)
        self.server.postreq_busy = False
        return

    # person options screen, minimize images checkbox
    # See html_person_options
    if '&submitMinimizeImages=' in options_confirm_params:
        minimize_images = None
        if 'minimizeImages=' in options_confirm_params:
            minimize_images = \
                options_confirm_params.split('minimizeImages=')[1]
            if '&' in minimize_images:
                minimize_images = minimize_images.split('&')[0]
        if minimize_images == 'on':
            person_minimize_images(base_dir,
                                   chooser_nickname,
                                   domain,
                                   options_nickname,
                                   options_domain_full)
        else:
            person_undo_minimize_images(base_dir,
                                        chooser_nickname,
                                        domain,
                                        options_nickname,
                                        options_domain_full)
        users_path_str = \
            users_path + '/' + self.server.default_timeline + \
            '?page=' + str(page_number)
        redirect_headers(self, users_path_str, cookie,
                         calling_domain)
        self.server.postreq_busy = False
        return

    # person options screen, allow announces checkbox
    # See html_person_options
    if '&submitAllowAnnounce=' in options_confirm_params:
        allow_announce = None
        if 'allowAnnounce=' in options_confirm_params:
            allow_announce = \
                options_confirm_params.split('allowAnnounce=')[1]
            if '&' in allow_announce:
                allow_announce = allow_announce.split('&')[0]
        if allow_announce == 'on':
            allowed_announce_add(base_dir,
                                 chooser_nickname,
                                 domain,
                                 options_nickname,
                                 options_domain_full)
        else:
            allowed_announce_remove(base_dir,
                                    chooser_nickname,
                                    domain,
                                    options_nickname,
                                    options_domain_full)
        users_path_str = \
            users_path + '/' + self.server.default_timeline + \
            '?page=' + str(page_number)
        redirect_headers(self, users_path_str, cookie,
                         calling_domain)
        self.server.postreq_busy = False
        return

    # person options screen, on notify checkbox
    # See html_person_options
    if '&submitNotifyOnPost=' in options_confirm_params:
        notify = None
        if 'notifyOnPost=' in options_confirm_params:
            notify = options_confirm_params.split('notifyOnPost=')[1]
            if '&' in notify:
                notify = notify.split('&')[0]
        if notify == 'on':
            add_notify_on_post(base_dir,
                               chooser_nickname,
                               domain,
                               options_nickname,
                               options_domain_full)
        else:
            remove_notify_on_post(base_dir,
                                  chooser_nickname,
                                  domain,
                                  options_nickname,
                                  options_domain_full)
        users_path_str = \
            users_path + '/' + self.server.default_timeline + \
            '?page=' + str(page_number)
        redirect_headers(self, users_path_str, cookie,
                         calling_domain)
        self.server.postreq_busy = False
        return

    # person options screen, permission to post to newswire
    # See html_person_options
    if '&submitPostToNews=' in options_confirm_params:
        admin_nickname = get_config_param(self.server.base_dir, 'admin')
        if (chooser_nickname != options_nickname and
            (chooser_nickname == admin_nickname or
             (is_moderator(self.server.base_dir, chooser_nickname) and
              not is_moderator(self.server.base_dir, options_nickname)))):
            posts_to_news = None
            if 'postsToNews=' in options_confirm_params:
                posts_to_news = \
                    options_confirm_params.split('postsToNews=')[1]
                if '&' in posts_to_news:
                    posts_to_news = posts_to_news.split('&')[0]
            account_dir = acct_dir(self.server.base_dir,
                                   options_nickname, options_domain)
            newswire_blocked_filename = account_dir + '/.nonewswire'
            if posts_to_news == 'on':
                if os.path.isfile(newswire_blocked_filename):
                    try:
                        os.remove(newswire_blocked_filename)
                    except OSError:
                        print('EX: _person_options unable to delete ' +
                              newswire_blocked_filename)
                    refresh_newswire(self.server.base_dir)
            else:
                if os.path.isdir(account_dir):
                    nw_filename = newswire_blocked_filename
                    nw_written = False
                    try:
                        with open(nw_filename, 'w+',
                                  encoding='utf-8') as nofile:
                            nofile.write('\n')
                            nw_written = True
                    except OSError as ex:
                        print('EX: unable to write ' + nw_filename +
                              ' ' + str(ex))
                    if nw_written:
                        refresh_newswire(self.server.base_dir)
        users_path_str = \
            users_path + '/' + self.server.default_timeline + \
            '?page=' + str(page_number)
        redirect_headers(self, users_path_str, cookie,
                         calling_domain)
        self.server.postreq_busy = False
        return

    # person options screen, permission to post to featured articles
    # See html_person_options
    if '&submitPostToFeatures=' in options_confirm_params:
        admin_nickname = get_config_param(self.server.base_dir, 'admin')
        if (chooser_nickname != options_nickname and
            (chooser_nickname == admin_nickname or
             (is_moderator(self.server.base_dir, chooser_nickname) and
              not is_moderator(self.server.base_dir, options_nickname)))):
            posts_to_features = None
            if 'postsToFeatures=' in options_confirm_params:
                posts_to_features = \
                    options_confirm_params.split('postsToFeatures=')[1]
                if '&' in posts_to_features:
                    posts_to_features = posts_to_features.split('&')[0]
            account_dir = acct_dir(self.server.base_dir,
                                   options_nickname, options_domain)
            features_blocked_filename = account_dir + '/.nofeatures'
            if posts_to_features == 'on':
                if os.path.isfile(features_blocked_filename):
                    try:
                        os.remove(features_blocked_filename)
                    except OSError:
                        print('EX: _person_options unable to delete ' +
                              features_blocked_filename)
                    refresh_newswire(self.server.base_dir)
            else:
                if os.path.isdir(account_dir):
                    feat_filename = features_blocked_filename
                    feat_written = False
                    try:
                        with open(feat_filename, 'w+',
                                  encoding='utf-8') as nofile:
                            nofile.write('\n')
                            feat_written = True
                    except OSError as ex:
                        print('EX: unable to write ' + feat_filename +
                              ' ' + str(ex))
                    if feat_written:
                        refresh_newswire(self.server.base_dir)
        users_path_str = \
            users_path + '/' + self.server.default_timeline + \
            '?page=' + str(page_number)
        redirect_headers(self, users_path_str, cookie,
                         calling_domain)
        self.server.postreq_busy = False
        return

    # person options screen, permission to post to newswire
    # See html_person_options
    if '&submitModNewsPosts=' in options_confirm_params:
        admin_nickname = get_config_param(self.server.base_dir, 'admin')
        if (chooser_nickname != options_nickname and
            (chooser_nickname == admin_nickname or
             (is_moderator(self.server.base_dir, chooser_nickname) and
              not is_moderator(self.server.base_dir, options_nickname)))):
            mod_posts_to_news = None
            if 'modNewsPosts=' in options_confirm_params:
                mod_posts_to_news = \
                    options_confirm_params.split('modNewsPosts=')[1]
                if '&' in mod_posts_to_news:
                    mod_posts_to_news = mod_posts_to_news.split('&')[0]
            account_dir = acct_dir(self.server.base_dir,
                                   options_nickname, options_domain)
            newswire_mod_filename = account_dir + '/.newswiremoderated'
            if mod_posts_to_news != 'on':
                if os.path.isfile(newswire_mod_filename):
                    try:
                        os.remove(newswire_mod_filename)
                    except OSError:
                        print('EX: _person_options unable to delete ' +
                              newswire_mod_filename)
            else:
                if os.path.isdir(account_dir):
                    nw_filename = newswire_mod_filename
                    try:
                        with open(nw_filename, 'w+',
                                  encoding='utf-8') as modfile:
                            modfile.write('\n')
                    except OSError:
                        print('EX: unable to write ' + nw_filename)
        users_path_str = \
            users_path + '/' + self.server.default_timeline + \
            '?page=' + str(page_number)
        redirect_headers(self, users_path_str, cookie,
                         calling_domain)
        self.server.postreq_busy = False
        return

    # person options screen, block button
    # See html_person_options
    if '&submitBlock=' in options_confirm_params:
        if debug:
            print('Blocking ' + options_actor)
        msg = \
            html_confirm_block(self.server.translate,
                               base_dir,
                               users_path,
                               options_actor,
                               options_avatar_url).encode('utf-8')
        msglen = len(msg)
        set_headers(self, 'text/html', msglen,
                    cookie, calling_domain, False)
        write2(self, msg)
        self.server.postreq_busy = False
        return

    # person options screen, unblock button
    # See html_person_options
    if '&submitUnblock=' in options_confirm_params:
        if debug:
            print('Unblocking ' + options_actor)
        msg = \
            html_confirm_unblock(self.server.translate,
                                 base_dir,
                                 users_path,
                                 options_actor,
                                 options_avatar_url).encode('utf-8')
        msglen = len(msg)
        set_headers(self, 'text/html', msglen,
                    cookie, calling_domain, False)
        write2(self, msg)
        self.server.postreq_busy = False
        return

    # person options screen, follow button
    # See html_person_options followStr
    if '&submitFollow=' in options_confirm_params or \
       '&submitJoin=' in options_confirm_params:
        if debug:
            print('Following ' + options_actor)
        msg = \
            html_confirm_follow(self.server.translate,
                                base_dir,
                                users_path,
                                options_actor,
                                options_avatar_url,
                                chooser_nickname,
                                domain).encode('utf-8')
        msglen = len(msg)
        set_headers(self, 'text/html', msglen,
                    cookie, calling_domain, False)
        write2(self, msg)
        self.server.postreq_busy = False
        return

    # person options screen, move button
    # See html_person_options followStr
    if '&submitMove=' in options_confirm_params and options_actor_moved:
        if debug:
            print('Moving ' + options_actor_moved)
        msg = \
            html_confirm_follow(self.server.translate,
                                base_dir,
                                users_path,
                                options_actor_moved,
                                options_avatar_url,
                                chooser_nickname,
                                domain).encode('utf-8')
        if msg:
            msglen = len(msg)
            set_headers(self, 'text/html', msglen,
                        cookie, calling_domain, False)
            write2(self, msg)
        self.server.postreq_busy = False
        return

    # person options screen, unfollow button
    # See html_person_options followStr
    if '&submitUnfollow=' in options_confirm_params or \
       '&submitLeave=' in options_confirm_params:
        print('Unfollowing ' + options_actor)
        msg = \
            html_confirm_unfollow(self.server.translate,
                                  base_dir,
                                  users_path,
                                  options_actor,
                                  options_avatar_url).encode('utf-8')
        msglen = len(msg)
        set_headers(self, 'text/html', msglen,
                    cookie, calling_domain, False)
        write2(self, msg)
        self.server.postreq_busy = False
        return

    # person options screen, DM button
    # See html_person_options
    if '&submitDM=' in options_confirm_params:
        if debug:
            print('Sending DM to ' + options_actor)
        report_path = path.replace('/personoptions', '') + '/newdm'

        access_keys = self.server.access_keys
        if '/users/' in path:
            nickname = path.split('/users/')[1]
            if '/' in nickname:
                nickname = nickname.split('/')[0]
            if self.server.key_shortcuts.get(nickname):
                access_keys = self.server.key_shortcuts[nickname]

        custom_submit_text = get_config_param(base_dir, 'customSubmitText')
        conversation_id = None
        reply_is_chat = False

        bold_reading = False
        if self.server.bold_reading.get(chooser_nickname):
            bold_reading = True

        languages_understood = \
            get_understood_languages(base_dir,
                                     http_prefix,
                                     chooser_nickname,
                                     self.server.domain_full,
                                     self.server.person_cache)

        default_post_language = self.server.system_language
        if self.server.default_post_language.get(nickname):
            default_post_language = \
                self.server.default_post_language[nickname]
        default_buy_site = ''
        msg = \
            html_new_post({}, False, self.server.translate,
                          base_dir,
                          http_prefix,
                          report_path, None,
                          [options_actor], None, None,
                          page_number, '',
                          chooser_nickname,
                          domain,
                          domain_full,
                          self.server.default_timeline,
                          self.server.newswire,
                          self.server.theme_name,
                          True, access_keys,
                          custom_submit_text,
                          conversation_id,
                          self.server.recent_posts_cache,
                          self.server.max_recent_posts,
                          curr_session,
                          self.server.cached_webfingers,
                          self.server.person_cache,
                          self.server.port,
                          None,
                          self.server.project_version,
                          self.server.yt_replace_domain,
                          self.server.twitter_replacement_domain,
                          self.server.show_published_date_only,
                          self.server.peertube_instances,
                          self.server.allow_local_network_access,
                          self.server.system_language,
                          languages_understood,
                          self.server.max_like_count,
                          self.server.signing_priv_key_pem,
                          self.server.cw_lists,
                          self.server.lists_enabled,
                          self.server.default_timeline,
                          reply_is_chat,
                          bold_reading,
                          self.server.dogwhistles,
                          self.server.min_images_for_accounts,
                          None, None, default_post_language,
                          self.server.buy_sites,
                          default_buy_site,
                          self.server.auto_cw_cache)
        if msg:
            msg = msg.encode('utf-8')
            msglen = len(msg)
            set_headers(self, 'text/html', msglen,
                        cookie, calling_domain, False)
            write2(self, msg)
        self.server.postreq_busy = False
        return

    # person options screen, Info button
    # See html_person_options
    if '&submitPersonInfo=' in options_confirm_params:
        if is_moderator(self.server.base_dir, chooser_nickname):
            if debug:
                print('Showing info for ' + options_actor)
            signing_priv_key_pem = self.server.signing_priv_key_pem
            msg = \
                html_account_info(self.server.translate,
                                  base_dir,
                                  http_prefix,
                                  chooser_nickname,
                                  domain,
                                  options_actor,
                                  self.server.debug,
                                  self.server.system_language,
                                  signing_priv_key_pem,
                                  None,
                                  self.server.block_federated)
            if msg:
                msg = msg.encode('utf-8')
                msglen = len(msg)
                set_headers(self, 'text/html', msglen,
                            cookie, calling_domain, False)
                write2(self, msg)
            self.server.postreq_busy = False
            return
        http_404(self, 11)
        return

    # person options screen, snooze button
    # See html_person_options
    if '&submitSnooze=' in options_confirm_params:
        users_path = path.split('/personoptions')[0]
        this_actor = http_prefix + '://' + domain_full + users_path
        if debug:
            print('Snoozing ' + options_actor + ' ' + this_actor)
        if '/users/' in this_actor:
            nickname = this_actor.split('/users/')[1]
            person_snooze(base_dir, nickname,
                          domain, options_actor)
            if calling_domain.endswith('.onion') and onion_domain:
                this_actor = 'http://' + onion_domain + users_path
            elif (calling_domain.endswith('.i2p') and i2p_domain):
                this_actor = 'http://' + i2p_domain + users_path
            actor_path_str = \
                this_actor + '/' + self.server.default_timeline + \
                '?page=' + str(page_number)
            redirect_headers(self, actor_path_str, cookie,
                             calling_domain)
            self.server.postreq_busy = False
            return

    # person options screen, unsnooze button
    # See html_person_options
    if '&submitUnsnooze=' in options_confirm_params:
        users_path = path.split('/personoptions')[0]
        this_actor = http_prefix + '://' + domain_full + users_path
        if debug:
            print('Unsnoozing ' + options_actor + ' ' + this_actor)
        if '/users/' in this_actor:
            nickname = this_actor.split('/users/')[1]
            person_unsnooze(base_dir, nickname,
                            domain, options_actor)
            if calling_domain.endswith('.onion') and onion_domain:
                this_actor = 'http://' + onion_domain + users_path
            elif (calling_domain.endswith('.i2p') and i2p_domain):
                this_actor = 'http://' + i2p_domain + users_path
            actor_path_str = \
                this_actor + '/' + self.server.default_timeline + \
                '?page=' + str(page_number)
            redirect_headers(self, actor_path_str, cookie,
                             calling_domain)
            self.server.postreq_busy = False
            return

    # person options screen, report button
    # See html_person_options
    if '&submitReport=' in options_confirm_params:
        if debug:
            print('Reporting ' + options_actor)
        report_path = \
            path.replace('/personoptions', '') + '/newreport'

        access_keys = self.server.access_keys
        if '/users/' in path:
            nickname = path.split('/users/')[1]
            if '/' in nickname:
                nickname = nickname.split('/')[0]
            if self.server.key_shortcuts.get(nickname):
                access_keys = self.server.key_shortcuts[nickname]

        custom_submit_text = get_config_param(base_dir, 'customSubmitText')
        conversation_id = None
        reply_is_chat = False

        bold_reading = False
        if self.server.bold_reading.get(chooser_nickname):
            bold_reading = True

        languages_understood = \
            get_understood_languages(base_dir,
                                     http_prefix,
                                     chooser_nickname,
                                     self.server.domain_full,
                                     self.server.person_cache)

        default_post_language = self.server.system_language
        if self.server.default_post_language.get(nickname):
            default_post_language = \
                self.server.default_post_language[nickname]
        default_buy_site = ''
        msg = \
            html_new_post({}, False, self.server.translate,
                          base_dir,
                          http_prefix,
                          report_path, None, [],
                          None, post_url, page_number, '',
                          chooser_nickname,
                          domain,
                          domain_full,
                          self.server.default_timeline,
                          self.server.newswire,
                          self.server.theme_name,
                          True, access_keys,
                          custom_submit_text,
                          conversation_id,
                          self.server.recent_posts_cache,
                          self.server.max_recent_posts,
                          curr_session,
                          self.server.cached_webfingers,
                          self.server.person_cache,
                          self.server.port,
                          None,
                          self.server.project_version,
                          self.server.yt_replace_domain,
                          self.server.twitter_replacement_domain,
                          self.server.show_published_date_only,
                          self.server.peertube_instances,
                          self.server.allow_local_network_access,
                          self.server.system_language,
                          languages_understood,
                          self.server.max_like_count,
                          self.server.signing_priv_key_pem,
                          self.server.cw_lists,
                          self.server.lists_enabled,
                          self.server.default_timeline,
                          reply_is_chat,
                          bold_reading,
                          self.server.dogwhistles,
                          self.server.min_images_for_accounts,
                          None, None, default_post_language,
                          self.server.buy_sites,
                          default_buy_site,
                          self.server.auto_cw_cache)
        if msg:
            msg = msg.encode('utf-8')
            msglen = len(msg)
            set_headers(self, 'text/html', msglen,
                        cookie, calling_domain, False)
            write2(self, msg)
        self.server.postreq_busy = False
        return

    # redirect back from person options screen
    if calling_domain.endswith('.onion') and onion_domain:
        origin_path_str = 'http://' + onion_domain + users_path
    elif calling_domain.endswith('.i2p') and i2p_domain:
        origin_path_str = 'http://' + i2p_domain + users_path
    redirect_headers(self, origin_path_str, cookie, calling_domain)
    self.server.postreq_busy = False
    return
