__filename__ = "utils.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Core"

import os
import re
import time
import shutil
import datetime
import json
import idna
import locale
from pprint import pprint
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from followingCalendar import add_person_to_calendar

# posts containing these strings will always get screened out,
# both incoming and outgoing.
# Could include dubious clacks or admin dogwhistles
INVALID_CHARACTERS = (
    '卐', '卍', '࿕', '࿖', '࿗', '࿘', 'ϟϟ', '🏳️‍🌈🚫', '⚡⚡'
)


def local_actor_url(http_prefix: str, nickname: str, domain_full: str) -> str:
    """Returns the url for an actor on this instance
    """
    return http_prefix + '://' + domain_full + '/users/' + nickname


def get_actor_languages_list(actor_json: {}) -> []:
    """Returns a list containing languages used by the given actor
    """
    if not actor_json.get('attachment'):
        return []
    for property_value in actor_json['attachment']:
        if not property_value.get('name'):
            continue
        if not property_value['name'].lower().startswith('languages'):
            continue
        if not property_value.get('type'):
            continue
        if not property_value.get('value'):
            continue
        if property_value['type'] != 'PropertyValue':
            continue
        if isinstance(property_value['value'], list):
            lang_list = property_value['value']
            lang_list.sort()
            return lang_list
        if isinstance(property_value['value'], str):
            lang_str = property_value['value']
            lang_list_temp = []
            if ',' in lang_str:
                lang_list_temp = lang_str.split(',')
            elif ';' in lang_str:
                lang_list_temp = lang_str.split(';')
            elif '/' in lang_str:
                lang_list_temp = lang_str.split('/')
            elif '+' in lang_str:
                lang_list_temp = lang_str.split('+')
            elif ' ' in lang_str:
                lang_list_temp = lang_str.split(' ')
            lang_list = []
            for lang in lang_list_temp:
                lang = lang.strip()
                if lang not in lang_list:
                    lang_list.append(lang)
            lang_list.sort()
            return lang_list
    return []


def get_content_from_post(post_json_object: {}, system_language: str,
                          languages_understood: []) -> str:
    """Returns the content from the post in the given language
    including searching for a matching entry within contentMap
    """
    this_post_json = post_json_object
    if has_object_dict(post_json_object):
        this_post_json = post_json_object['object']
    if not this_post_json.get('content'):
        return ''
    content = ''
    if this_post_json.get('contentMap'):
        if isinstance(this_post_json['contentMap'], dict):
            if this_post_json['contentMap'].get(system_language):
                sys_lang = this_post_json['contentMap'][system_language]
                if isinstance(sys_lang, str):
                    return this_post_json['contentMap'][system_language]
            else:
                # is there a contentMap entry for one of
                # the understood languages?
                for lang in languages_understood:
                    if this_post_json['contentMap'].get(lang):
                        return this_post_json['contentMap'][lang]
    else:
        if isinstance(this_post_json['content'], str):
            content = this_post_json['content']
    return content


def get_base_content_from_post(post_json_object: {},
                               system_language: str) -> str:
    """Returns the content from the post in the given language
    """
    this_post_json = post_json_object
    if has_object_dict(post_json_object):
        this_post_json = post_json_object['object']
    if not this_post_json.get('content'):
        return ''
    return this_post_json['content']


def acct_dir(base_dir: str, nickname: str, domain: str) -> str:
    return base_dir + '/accounts/' + nickname + '@' + domain


def is_featured_writer(base_dir: str, nickname: str, domain: str) -> bool:
    """Is the given account a featured writer, appearing in the features
    timeline on news instances?
    """
    features_blocked_filename = \
        acct_dir(base_dir, nickname, domain) + '/.nofeatures'
    return not os.path.isfile(features_blocked_filename)


def refresh_newswire(base_dir: str):
    """Causes the newswire to be updates after a change to user accounts
    """
    refresh_newswire_filename = base_dir + '/accounts/.refresh_newswire'
    if os.path.isfile(refresh_newswire_filename):
        return
    with open(refresh_newswire_filename, 'w+') as refresh_file:
        refresh_file.write('\n')


def get_sha_256(msg: str):
    """Returns a SHA256 hash of the given string
    """
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(msg)
    return digest.finalize()


def get_sha_512(msg: str):
    """Returns a SHA512 hash of the given string
    """
    digest = hashes.Hash(hashes.SHA512(), backend=default_backend())
    digest.update(msg)
    return digest.finalize()


def _local_network_host(host: str) -> bool:
    """Returns true if the given host is on the local network
    """
    if host.startswith('localhost') or \
       host.startswith('192.') or \
       host.startswith('127.') or \
       host.startswith('10.'):
        return True
    return False


def decoded_host(host: str) -> str:
    """Convert hostname to internationalized domain
    https://en.wikipedia.org/wiki/Internationalized_domain_name
    """
    if ':' not in host:
        # eg. mydomain:8000
        if not _local_network_host(host):
            if not host.endswith('.onion'):
                if not host.endswith('.i2p'):
                    return idna.decode(host)
    return host


def get_locked_account(actor_json: {}) -> bool:
    """Returns whether the given account requires follower approval
    """
    if not actor_json.get('manuallyApprovesFollowers'):
        return False
    if actor_json['manuallyApprovesFollowers'] is True:
        return True
    return False


def has_users_path(path_str: str) -> bool:
    """Whether there is a /users/ path (or equivalent) in the given string
    """
    users_list = get_user_paths()
    for users_str in users_list:
        if users_str in path_str:
            return True
    if '://' in path_str:
        domain = path_str.split('://')[1]
        if '/' in domain:
            domain = domain.split('/')[0]
        if '://' + domain + '/' not in path_str:
            return False
        nickname = path_str.split('://' + domain + '/')[1]
        if '/' in nickname or '.' in nickname:
            return False
        return True
    return False


def valid_post_date(published: str, max_age_days: int, debug: bool) -> bool:
    """Returns true if the published date is recent and is not in the future
    """
    baseline_time = datetime.datetime(1970, 1, 1)

    days_diff = datetime.datetime.utcnow() - baseline_time
    now_days_since_epoch = days_diff.days

    try:
        post_time_object = \
            datetime.datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
    except BaseException:
        if debug:
            print('EX: valid_post_date invalid published date ' +
                  str(published))
        return False

    days_diff = post_time_object - baseline_time
    post_days_since_epoch = days_diff.days

    if post_days_since_epoch > now_days_since_epoch:
        if debug:
            print("Inbox post has a published date in the future!")
        return False

    if now_days_since_epoch - post_days_since_epoch >= max_age_days:
        if debug:
            print("Inbox post is not recent enough")
        return False
    return True


def get_full_domain(domain: str, port: int) -> str:
    """Returns the full domain name, including port number
    """
    if not port:
        return domain
    if ':' in domain:
        return domain
    if port in (80, 443):
        return domain
    return domain + ':' + str(port)


def is_dormant(base_dir: str, nickname: str, domain: str, actor: str,
               dormant_months: int) -> bool:
    """Is the given followed actor dormant, from the standpoint
    of the given account
    """
    last_seen_filename = acct_dir(base_dir, nickname, domain) + \
        '/lastseen/' + actor.replace('/', '#') + '.txt'

    if not os.path.isfile(last_seen_filename):
        return False

    days_since_epoch_str = None
    try:
        with open(last_seen_filename, 'r') as last_seen_file:
            days_since_epoch_str = last_seen_file.read()
    except OSError:
        print('EX: failed to read last seen ' + last_seen_filename)
        return False

    if days_since_epoch_str:
        days_since_epoch = int(days_since_epoch_str)
        curr_time = datetime.datetime.utcnow()
        curr_days_since_epoch = \
            (curr_time - datetime.datetime(1970, 1, 1)).days
        time_diff_months = \
            int((curr_days_since_epoch - days_since_epoch) / 30)
        if time_diff_months >= dormant_months:
            return True
    return False


def is_editor(base_dir: str, nickname: str) -> bool:
    """Returns true if the given nickname is an editor
    """
    editors_file = base_dir + '/accounts/editors.txt'

    if not os.path.isfile(editors_file):
        admin_name = get_config_param(base_dir, 'admin')
        if admin_name:
            if admin_name == nickname:
                return True
        return False

    with open(editors_file, 'r') as editors:
        lines = editors.readlines()
        if len(lines) == 0:
            admin_name = get_config_param(base_dir, 'admin')
            if admin_name:
                if admin_name == nickname:
                    return True
        for editor in lines:
            editor = editor.strip('\n').strip('\r')
            if editor == nickname:
                return True
    return False


def is_artist(base_dir: str, nickname: str) -> bool:
    """Returns true if the given nickname is an artist
    """
    artists_file = base_dir + '/accounts/artists.txt'

    if not os.path.isfile(artists_file):
        admin_name = get_config_param(base_dir, 'admin')
        if admin_name:
            if admin_name == nickname:
                return True
        return False

    with open(artists_file, 'r') as artists:
        lines = artists.readlines()
        if len(lines) == 0:
            admin_name = get_config_param(base_dir, 'admin')
            if admin_name:
                if admin_name == nickname:
                    return True
        for artist in lines:
            artist = artist.strip('\n').strip('\r')
            if artist == nickname:
                return True
    return False


def get_video_extensions() -> []:
    """Returns a list of the possible video file extensions
    """
    return ('mp4', 'webm', 'ogv')


def get_audio_extensions() -> []:
    """Returns a list of the possible audio file extensions
    """
    return ('mp3', 'ogg', 'flac')


def get_image_extensions() -> []:
    """Returns a list of the possible image file extensions
    """
    return ('png', 'jpg', 'jpeg', 'gif', 'webp', 'avif', 'svg', 'ico')


def get_image_mime_type(image_filename: str) -> str:
    """Returns the mime type for the given image
    """
    extensions_to_mime = {
        'png': 'png',
        'jpg': 'jpeg',
        'gif': 'gif',
        'avif': 'avif',
        'svg': 'svg+xml',
        'webp': 'webp',
        'ico': 'x-icon'
    }
    for ext, mime_ext in extensions_to_mime.items():
        if image_filename.endswith('.' + ext):
            return 'image/' + mime_ext
    return 'image/png'


def get_image_extension_from_mime_type(content_type: str) -> str:
    """Returns the image extension from a mime type, such as image/jpeg
    """
    image_media = {
        'png': 'png',
        'jpeg': 'jpg',
        'gif': 'gif',
        'svg+xml': 'svg',
        'webp': 'webp',
        'avif': 'avif',
        'x-icon': 'ico'
    }
    for mime_ext, ext in image_media.items():
        if content_type.endswith(mime_ext):
            return ext
    return 'png'


def get_media_extensions() -> []:
    """Returns a list of the possible media file extensions
    """
    return get_image_extensions() + \
        get_video_extensions() + get_audio_extensions()


def get_image_formats() -> str:
    """Returns a string of permissable image formats
    used when selecting an image for a new post
    """
    image_ext = get_image_extensions()

    image_formats = ''
    for ext in image_ext:
        if image_formats:
            image_formats += ', '
        image_formats += '.' + ext
    return image_formats


def is_image_file(filename: str) -> bool:
    """Is the given filename an image?
    """
    for ext in get_image_extensions():
        if filename.endswith('.' + ext):
            return True
    return False


def get_media_formats() -> str:
    """Returns a string of permissable media formats
    used when selecting an attachment for a new post
    """
    media_ext = get_media_extensions()

    media_formats = ''
    for ext in media_ext:
        if media_formats:
            media_formats += ', '
        media_formats += '.' + ext
    return media_formats


def remove_html(content: str) -> str:
    """Removes html links from the given content.
    Used to ensure that profile descriptions don't contain dubious content
    """
    if '<' not in content:
        return content
    removing = False
    content = content.replace('<a href', ' <a href')
    content = content.replace('<q>', '"').replace('</q>', '"')
    content = content.replace('</p>', '\n\n').replace('<br>', '\n')
    result = ''
    for char in content:
        if char == '<':
            removing = True
        elif char == '>':
            removing = False
        elif not removing:
            result += char

    plain_text = result.replace('  ', ' ')

    # insert spaces after full stops
    str_len = len(plain_text)
    result = ''
    for i in range(str_len):
        result += plain_text[i]
        if plain_text[i] == '.' and i < str_len - 1:
            if plain_text[i + 1] >= 'A' and plain_text[i + 1] <= 'Z':
                result += ' '

    result = result.replace('  ', ' ').strip()
    return result


def first_paragraph_from_string(content: str) -> str:
    """Get the first paragraph from a blog post
    to be used as a summary in the newswire feed
    """
    if '<p>' not in content or '</p>' not in content:
        return remove_html(content)
    paragraph = content.split('<p>')[1]
    if '</p>' in paragraph:
        paragraph = paragraph.split('</p>')[0]
    return remove_html(paragraph)


def is_system_account(nickname: str) -> bool:
    """Returns true if the given nickname is a system account
    """
    if nickname in ('news', 'inbox'):
        return True
    return False


def _create_config(base_dir: str) -> None:
    """Creates a configuration file
    """
    config_filename = base_dir + '/config.json'
    if os.path.isfile(config_filename):
        return
    config_json = {
    }
    save_json(config_json, config_filename)


def set_config_param(base_dir: str, variable_name: str,
                     variable_value) -> None:
    """Sets a configuration value
    """
    _create_config(base_dir)
    config_filename = base_dir + '/config.json'
    config_json = {}
    if os.path.isfile(config_filename):
        config_json = load_json(config_filename)
    config_json[variable_name] = variable_value
    save_json(config_json, config_filename)


def get_config_param(base_dir: str, variable_name: str):
    """Gets a configuration value
    """
    _create_config(base_dir)
    config_filename = base_dir + '/config.json'
    config_json = load_json(config_filename)
    if config_json:
        if variable_name in config_json:
            return config_json[variable_name]
    return None


def is_suspended(base_dir: str, nickname: str) -> bool:
    """Returns true if the given nickname is suspended
    """
    admin_nickname = get_config_param(base_dir, 'admin')
    if not admin_nickname:
        return False
    if nickname == admin_nickname:
        return False

    suspended_filename = base_dir + '/accounts/suspended.txt'
    if os.path.isfile(suspended_filename):
        with open(suspended_filename, 'r') as susp_file:
            lines = susp_file.readlines()
        for suspended in lines:
            if suspended.strip('\n').strip('\r') == nickname:
                return True
    return False


def get_followers_list(base_dir: str,
                       nickname: str, domain: str,
                       follow_file='following.txt') -> []:
    """Returns a list of followers for the given account
    """
    filename = acct_dir(base_dir, nickname, domain) + '/' + follow_file

    if not os.path.isfile(filename):
        return []

    with open(filename, 'r') as foll_file:
        lines = foll_file.readlines()
        for i in range(len(lines)):
            lines[i] = lines[i].strip()
        return lines
    return []


def get_followers_of_person(base_dir: str,
                            nickname: str, domain: str,
                            follow_file='following.txt') -> []:
    """Returns a list containing the followers of the given person
    Used by the shared inbox to know who to send incoming mail to
    """
    followers = []
    domain = remove_domain_port(domain)
    handle = nickname + '@' + domain
    if not os.path.isdir(base_dir + '/accounts/' + handle):
        return followers
    for subdir, dirs, _ in os.walk(base_dir + '/accounts'):
        for account in dirs:
            filename = os.path.join(subdir, account) + '/' + follow_file
            if account == handle or \
               account.startswith('inbox@') or \
               account.startswith('news@'):
                continue
            if not os.path.isfile(filename):
                continue
            with open(filename, 'r') as followingfile:
                for following_handle in followingfile:
                    following_handle2 = following_handle.replace('\n', '')
                    following_handle2 = following_handle2.replace('\r', '')
                    if following_handle2 == handle:
                        if account not in followers:
                            followers.append(account)
                        break
        break
    return followers


def remove_id_ending(id_str: str) -> str:
    """Removes endings such as /activity and /undo
    """
    if id_str.endswith('/activity'):
        id_str = id_str[:-len('/activity')]
    elif id_str.endswith('/undo'):
        id_str = id_str[:-len('/undo')]
    elif id_str.endswith('/event'):
        id_str = id_str[:-len('/event')]
    elif id_str.endswith('/replies'):
        id_str = id_str[:-len('/replies')]
    if id_str.endswith('#Create'):
        id_str = id_str.split('#Create')[0]
    return id_str


def remove_hash_from_post_id(post_id: str) -> str:
    """Removes any has from a post id
    """
    if '#' not in post_id:
        return post_id
    return post_id.split('#')[0]


def get_protocol_prefixes() -> []:
    """Returns a list of valid prefixes
    """
    return ('https://', 'http://', 'ftp://',
            'dat://', 'i2p://', 'gnunet://',
            'hyper://', 'gemini://', 'gopher://')


def get_link_prefixes() -> []:
    """Returns a list of valid web link prefixes
    """
    return ('https://', 'http://', 'ftp://',
            'dat://', 'i2p://', 'gnunet://', 'payto://',
            'hyper://', 'gemini://', 'gopher://', 'briar:')


def remove_avatar_from_cache(base_dir: str, actor_str: str) -> None:
    """Removes any existing avatar entries from the cache
    This avoids duplicate entries with differing extensions
    """
    avatar_filename_extensions = get_image_extensions()
    for extension in avatar_filename_extensions:
        avatar_filename = \
            base_dir + '/cache/avatars/' + actor_str + '.' + extension
        if os.path.isfile(avatar_filename):
            try:
                os.remove(avatar_filename)
            except OSError:
                print('EX: remove_avatar_from_cache ' +
                      'unable to delete cached avatar ' +
                      str(avatar_filename))


def save_json(json_object: {}, filename: str) -> bool:
    """Saves json to a file
    """
    tries = 0
    while tries < 5:
        try:
            with open(filename, 'w+') as json_file:
                json_file.write(json.dumps(json_object))
                return True
        except OSError:
            print('EX: save_json ' + str(tries))
            time.sleep(1)
            tries += 1
    return False


def load_json(filename: str, delay_sec: int = 2, max_tries: int = 5) -> {}:
    """Makes a few attempts to load a json formatted file
    """
    json_object = None
    tries = 0
    while tries < max_tries:
        try:
            with open(filename, 'r') as json_file:
                data = json_file.read()
                json_object = json.loads(data)
                break
        except BaseException:
            print('EX: load_json exception ' + str(filename))
            if delay_sec > 0:
                time.sleep(delay_sec)
            tries += 1
    return json_object


def load_json_onionify(filename: str, domain: str, onion_domain: str,
                       delay_sec: int = 2) -> {}:
    """Makes a few attempts to load a json formatted file
    This also converts the domain name to the onion domain
    """
    json_object = None
    tries = 0
    while tries < 5:
        try:
            with open(filename, 'r') as json_file:
                data = json_file.read()
                if data:
                    data = data.replace(domain, onion_domain)
                    data = data.replace('https:', 'http:')
                    print('*****data: ' + data)
                json_object = json.loads(data)
                break
        except BaseException:
            print('EX: load_json_onionify exception ' + str(filename))
            if delay_sec > 0:
                time.sleep(delay_sec)
            tries += 1
    return json_object


def get_status_number(published_str: str = None) -> (str, str):
    """Returns the status number and published date
    """
    if not published_str:
        curr_time = datetime.datetime.utcnow()
    else:
        curr_time = \
            datetime.datetime.strptime(published_str, '%Y-%m-%dT%H:%M:%SZ')
    days_since_epoch = (curr_time - datetime.datetime(1970, 1, 1)).days
    # status is the number of seconds since epoch
    status_number = \
        str(((days_since_epoch * 24 * 60 * 60) +
             (curr_time.hour * 60 * 60) +
             (curr_time.minute * 60) +
             curr_time.second) * 1000 +
            int(curr_time.microsecond / 1000))
    # See https://github.com/tootsuite/mastodon/blob/
    # 995f8b389a66ab76ec92d9a240de376f1fc13a38/lib/mastodon/snowflake.rb
    # use the leftover microseconds as the sequence number
    sequence_id = curr_time.microsecond % 1000
    # shift by 16bits "sequence data"
    status_number = str((int(status_number) << 16) + sequence_id)
    published = curr_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    return status_number, published


def evil_incarnate() -> []:
    """Hardcoded blocked domains
    """
    return ('fedilist.com', 'gab.com', 'gabfed.com', 'spinster.xyz',
            'kiwifarms.cc', 'djitter.com')


def is_evil(domain: str) -> bool:
    """ https://www.youtube.com/watch?v=5qw1hcevmdU
    """
    if not isinstance(domain, str):
        print('WARN: Malformed domain ' + str(domain))
        return True
    # if a domain contains any of these strings then it is
    # declaring itself to be hostile
    evil_emporium = (
        'nazi', 'extremis', 'extreemis', 'gendercritic',
        'kiwifarm', 'illegal', 'raplst', 'rapist',
        'antivax', 'plandemic'
    )
    for hostile_str in evil_emporium:
        if hostile_str in domain:
            return True
    evil_domains = evil_incarnate()
    for concentrated_evil in evil_domains:
        if domain.endswith(concentrated_evil):
            return True
    return False


def contains_invalid_chars(json_str: str) -> bool:
    """Does the given json string contain invalid characters?
    """
    for is_invalid in INVALID_CHARACTERS:
        if is_invalid in json_str:
            return True
    return False


def remove_invalid_chars(text: str) -> str:
    """Removes any invalid characters from a string
    """
    for is_invalid in INVALID_CHARACTERS:
        if is_invalid not in text:
            continue
        text = text.replace(is_invalid, '')
    return text


def create_person_dir(nickname: str, domain: str, base_dir: str,
                      dir_name: str) -> str:
    """Create a directory for a person
    """
    handle = nickname + '@' + domain
    if not os.path.isdir(base_dir + '/accounts/' + handle):
        os.mkdir(base_dir + '/accounts/' + handle)
    box_dir = base_dir + '/accounts/' + handle + '/' + dir_name
    if not os.path.isdir(box_dir):
        os.mkdir(box_dir)
    return box_dir


def create_outbox_dir(nickname: str, domain: str, base_dir: str) -> str:
    """Create an outbox for a person
    """
    return create_person_dir(nickname, domain, base_dir, 'outbox')


def create_inbox_queue_dir(nickname: str, domain: str, base_dir: str) -> str:
    """Create an inbox queue and returns the feed filename and directory
    """
    return create_person_dir(nickname, domain, base_dir, 'queue')


def domain_permitted(domain: str, federation_list: []) -> bool:
    """Is the given domain permitted according to the federation list?
    """
    if len(federation_list) == 0:
        return True
    domain = remove_domain_port(domain)
    if domain in federation_list:
        return True
    return False


def url_permitted(url: str, federation_list: []):
    if is_evil(url):
        return False
    if not federation_list:
        return True
    for domain in federation_list:
        if domain in url:
            return True
    return False


def get_local_network_addresses() -> []:
    """Returns patterns for local network address detection
    """
    return ('localhost', '127.0.', '192.168', '10.0.')


def is_local_network_address(ip_address: str) -> bool:
    """Is the given ip address local?
    """
    local_ips = get_local_network_addresses()
    for ip_addr in local_ips:
        if ip_address.startswith(ip_addr):
            return True
    return False


def _is_dangerous_string(content: str, allow_local_network_access: bool,
                         separators: [], invalid_strings: []) -> bool:
    """Returns true if the given string is dangerous
    """
    for separator_style in separators:
        start_char = separator_style[0]
        end_char = separator_style[1]
        if start_char not in content:
            continue
        if end_char not in content:
            continue
        content_sections = content.split(start_char)
        invalid_partials = ()
        if not allow_local_network_access:
            invalid_partials = get_local_network_addresses()
        for markup in content_sections:
            if end_char not in markup:
                continue
            markup = markup.split(end_char)[0].strip()
            for partial_match in invalid_partials:
                if partial_match in markup:
                    return True
            if ' ' not in markup:
                for bad_str in invalid_strings:
                    if bad_str in markup:
                        return True
            else:
                for bad_str in invalid_strings:
                    if bad_str + ' ' in markup:
                        return True
    return False


def dangerous_markup(content: str, allow_local_network_access: bool) -> bool:
    """Returns true if the given content contains dangerous html markup
    """
    separators = [['<', '>'], ['&lt;', '&gt;']]
    invalid_strings = [
        'script', 'noscript', 'code', 'pre',
        'canvas', 'style', 'abbr',
        'frame', 'iframe', 'html', 'body',
        'hr', 'allow-popups', 'allow-scripts'
    ]
    return _is_dangerous_string(content, allow_local_network_access,
                                separators, invalid_strings)


def dangerous_svg(content: str, allow_local_network_access: bool) -> bool:
    """Returns true if the given svg file content contains dangerous scripts
    """
    separators = [['<', '>'], ['&lt;', '&gt;']]
    invalid_strings = [
        'script'
    ]
    return _is_dangerous_string(content, allow_local_network_access,
                                separators, invalid_strings)


def getDisplayName(base_dir: str, actor: str, person_cache: {}) -> str:
    """Returns the display name for the given actor
    """
    if '/statuses/' in actor:
        actor = actor.split('/statuses/')[0]
    if not person_cache.get(actor):
        return None
    nameFound = None
    if person_cache[actor].get('actor'):
        if person_cache[actor]['actor'].get('name'):
            nameFound = person_cache[actor]['actor']['name']
    else:
        # Try to obtain from the cached actors
        cachedActorFilename = \
            base_dir + '/cache/actors/' + (actor.replace('/', '#')) + '.json'
        if os.path.isfile(cachedActorFilename):
            actor_json = load_json(cachedActorFilename, 1)
            if actor_json:
                if actor_json.get('name'):
                    nameFound = actor_json['name']
    if nameFound:
        if dangerous_markup(nameFound, False):
            nameFound = "*ADVERSARY*"
    return nameFound


def _genderFromString(translate: {}, text: str) -> str:
    """Given some text, does it contain a gender description?
    """
    gender = None
    if not text:
        return None
    textOrig = text
    text = text.lower()
    if translate['He/Him'].lower() in text or \
       translate['boy'].lower() in text:
        gender = 'He/Him'
    elif (translate['She/Her'].lower() in text or
          translate['girl'].lower() in text):
        gender = 'She/Her'
    elif 'him' in text or 'male' in text:
        gender = 'He/Him'
    elif 'her' in text or 'she' in text or \
         'fem' in text or 'woman' in text:
        gender = 'She/Her'
    elif 'man' in text or 'He' in textOrig:
        gender = 'He/Him'
    return gender


def getGenderFromBio(base_dir: str, actor: str, person_cache: {},
                     translate: {}) -> str:
    """Tries to ascertain gender from bio description
    This is for use by text-to-speech for pitch setting
    """
    defaultGender = 'They/Them'
    if '/statuses/' in actor:
        actor = actor.split('/statuses/')[0]
    if not person_cache.get(actor):
        return defaultGender
    bioFound = None
    if translate:
        pronounStr = translate['pronoun'].lower()
    else:
        pronounStr = 'pronoun'
    actor_json = None
    if person_cache[actor].get('actor'):
        actor_json = person_cache[actor]['actor']
    else:
        # Try to obtain from the cached actors
        cachedActorFilename = \
            base_dir + '/cache/actors/' + (actor.replace('/', '#')) + '.json'
        if os.path.isfile(cachedActorFilename):
            actor_json = load_json(cachedActorFilename, 1)
    if not actor_json:
        return defaultGender
    # is gender defined as a profile tag?
    if actor_json.get('attachment'):
        tagsList = actor_json['attachment']
        if isinstance(tagsList, list):
            # look for a gender field name
            for tag in tagsList:
                if not isinstance(tag, dict):
                    continue
                if not tag.get('name') or not tag.get('value'):
                    continue
                if tag['name'].lower() == \
                   translate['gender'].lower():
                    bioFound = tag['value']
                    break
                elif tag['name'].lower().startswith(pronounStr):
                    bioFound = tag['value']
                    break
            # the field name could be anything,
            # just look at the value
            if not bioFound:
                for tag in tagsList:
                    if not isinstance(tag, dict):
                        continue
                    if not tag.get('name') or not tag.get('value'):
                        continue
                    gender = _genderFromString(translate, tag['value'])
                    if gender:
                        return gender
    # if not then use the bio
    if not bioFound and actor_json.get('summary'):
        bioFound = actor_json['summary']
    if not bioFound:
        return defaultGender
    gender = _genderFromString(translate, bioFound)
    if not gender:
        gender = defaultGender
    return gender


def getNicknameFromActor(actor: str) -> str:
    """Returns the nickname from an actor url
    """
    if actor.startswith('@'):
        actor = actor[1:]
    usersPaths = get_user_paths()
    for possiblePath in usersPaths:
        if possiblePath in actor:
            nickStr = actor.split(possiblePath)[1].replace('@', '')
            if '/' not in nickStr:
                return nickStr
            else:
                return nickStr.split('/')[0]
    if '/@' in actor:
        # https://domain/@nick
        nickStr = actor.split('/@')[1]
        if '/' in nickStr:
            nickStr = nickStr.split('/')[0]
        return nickStr
    elif '@' in actor:
        nickStr = actor.split('@')[0]
        return nickStr
    elif '://' in actor:
        domain = actor.split('://')[1]
        if '/' in domain:
            domain = domain.split('/')[0]
        if '://' + domain + '/' not in actor:
            return None
        nickStr = actor.split('://' + domain + '/')[1]
        if '/' in nickStr or '.' in nickStr:
            return None
        return nickStr
    return None


def get_user_paths() -> []:
    """Returns possible user paths
    e.g. /users/nickname, /channel/nickname
    """
    return ('/users/', '/profile/', '/accounts/', '/channel/', '/u/',
            '/c/', '/video-channels/')


def get_group_paths() -> []:
    """Returns possible group paths
    e.g. https://lemmy/c/groupname
    """
    return ['/c/', '/video-channels/']


def get_domain_from_actor(actor: str) -> (str, int):
    """Returns the domain name from an actor url
    """
    if actor.startswith('@'):
        actor = actor[1:]
    port = None
    prefixes = get_protocol_prefixes()
    usersPaths = get_user_paths()
    for possiblePath in usersPaths:
        if possiblePath in actor:
            domain = actor.split(possiblePath)[0]
            for prefix in prefixes:
                domain = domain.replace(prefix, '')
            break
    if '/@' in actor:
        domain = actor.split('/@')[0]
        for prefix in prefixes:
            domain = domain.replace(prefix, '')
    elif '@' in actor:
        domain = actor.split('@')[1].strip()
    else:
        domain = actor
        for prefix in prefixes:
            domain = domain.replace(prefix, '')
        if '/' in actor:
            domain = domain.split('/')[0]
    if ':' in domain:
        port = get_port_from_domain(domain)
        domain = remove_domain_port(domain)
    return domain, port


def _set_default_pet_name(base_dir: str, nickname: str, domain: str,
                          follow_nickname: str, follow_domain: str) -> None:
    """Sets a default petname
    This helps especially when using onion or i2p address
    """
    domain = remove_domain_port(domain)
    userPath = acct_dir(base_dir, nickname, domain)
    petnamesFilename = userPath + '/petnames.txt'

    petnameLookupEntry = follow_nickname + ' ' + \
        follow_nickname + '@' + follow_domain + '\n'
    if not os.path.isfile(petnamesFilename):
        # if there is no existing petnames lookup file
        with open(petnamesFilename, 'w+') as petnamesFile:
            petnamesFile.write(petnameLookupEntry)
        return

    with open(petnamesFilename, 'r') as petnamesFile:
        petnamesStr = petnamesFile.read()
        if petnamesStr:
            petnamesList = petnamesStr.split('\n')
            for pet in petnamesList:
                if pet.startswith(follow_nickname + ' '):
                    # petname already exists
                    return
    # petname doesn't already exist
    with open(petnamesFilename, 'a+') as petnames_file:
        petnames_file.write(petnameLookupEntry)


def follow_person(base_dir: str, nickname: str, domain: str,
                  follow_nickname: str, follow_domain: str,
                  federation_list: [], debug: bool,
                  group_account: bool,
                  follow_file: str = 'following.txt') -> bool:
    """Adds a person to the follow list
    """
    follow_domainStrLower = follow_domain.lower().replace('\n', '')
    if not domain_permitted(follow_domainStrLower,
                            federation_list):
        if debug:
            print('DEBUG: follow of domain ' +
                  follow_domain + ' not permitted')
        return False
    if debug:
        print('DEBUG: follow of domain ' + follow_domain)

    if ':' in domain:
        domainOnly = remove_domain_port(domain)
        handle = nickname + '@' + domainOnly
    else:
        handle = nickname + '@' + domain

    if not os.path.isdir(base_dir + '/accounts/' + handle):
        print('WARN: account for ' + handle + ' does not exist')
        return False

    if ':' in follow_domain:
        follow_domainOnly = remove_domain_port(follow_domain)
        handleToFollow = follow_nickname + '@' + follow_domainOnly
    else:
        handleToFollow = follow_nickname + '@' + follow_domain

    if group_account:
        handleToFollow = '!' + handleToFollow

    # was this person previously unfollowed?
    unfollowedFilename = base_dir + '/accounts/' + handle + '/unfollowed.txt'
    if os.path.isfile(unfollowedFilename):
        if handleToFollow in open(unfollowedFilename).read():
            # remove them from the unfollowed file
            newLines = ''
            with open(unfollowedFilename, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    if handleToFollow not in line:
                        newLines += line
            with open(unfollowedFilename, 'w+') as f:
                f.write(newLines)

    if not os.path.isdir(base_dir + '/accounts'):
        os.mkdir(base_dir + '/accounts')
    handleToFollow = follow_nickname + '@' + follow_domain
    if group_account:
        handleToFollow = '!' + handleToFollow
    filename = base_dir + '/accounts/' + handle + '/' + follow_file
    if os.path.isfile(filename):
        if handleToFollow in open(filename).read():
            if debug:
                print('DEBUG: follow already exists')
            return True
        # prepend to follow file
        try:
            with open(filename, 'r+') as foll_file:
                content = foll_file.read()
                if handleToFollow + '\n' not in content:
                    foll_file.seek(0, 0)
                    foll_file.write(handleToFollow + '\n' + content)
                    print('DEBUG: follow added')
        except OSError as ex:
            print('WARN: Failed to write entry to follow file ' +
                  filename + ' ' + str(ex))
    else:
        # first follow
        if debug:
            print('DEBUG: ' + handle +
                  ' creating new following file to follow ' + handleToFollow +
                  ', filename is ' + filename)
        with open(filename, 'w+') as fp:
            fp.write(handleToFollow + '\n')

    if follow_file.endswith('following.txt'):
        # Default to adding new follows to the calendar.
        # Possibly this could be made optional
        # if following a person add them to the list of
        # calendar follows
        print('DEBUG: adding ' +
              follow_nickname + '@' + follow_domain + ' to calendar of ' +
              nickname + '@' + domain)
        add_person_to_calendar(base_dir, nickname, domain,
                               follow_nickname, follow_domain)
        # add a default petname
        _set_default_pet_name(base_dir, nickname, domain,
                              follow_nickname, follow_domain)
    return True


def votesOnNewswireItem(status: []) -> int:
    """Returns the number of votes on a newswire item
    """
    totalVotes = 0
    for line in status:
        if 'vote:' in line:
            totalVotes += 1
    return totalVotes


def locateNewsVotes(base_dir: str, domain: str,
                    postUrl: str) -> str:
    """Returns the votes filename for a news post
    within the news user account
    """
    postUrl = \
        postUrl.strip().replace('\n', '').replace('\r', '')

    # if this post in the shared inbox?
    postUrl = remove_id_ending(postUrl.strip()).replace('/', '#')

    if postUrl.endswith('.json'):
        postUrl = postUrl + '.votes'
    else:
        postUrl = postUrl + '.json.votes'

    accountDir = base_dir + '/accounts/news@' + domain + '/'
    post_filename = accountDir + 'outbox/' + postUrl
    if os.path.isfile(post_filename):
        return post_filename

    return None


def locateNewsArrival(base_dir: str, domain: str,
                      postUrl: str) -> str:
    """Returns the arrival time for a news post
    within the news user account
    """
    postUrl = \
        postUrl.strip().replace('\n', '').replace('\r', '')

    # if this post in the shared inbox?
    postUrl = remove_id_ending(postUrl.strip()).replace('/', '#')

    if postUrl.endswith('.json'):
        postUrl = postUrl + '.arrived'
    else:
        postUrl = postUrl + '.json.arrived'

    accountDir = base_dir + '/accounts/news@' + domain + '/'
    post_filename = accountDir + 'outbox/' + postUrl
    if os.path.isfile(post_filename):
        with open(post_filename, 'r') as arrivalFile:
            arrival = arrivalFile.read()
            if arrival:
                arrivalDate = \
                    datetime.datetime.strptime(arrival,
                                               "%Y-%m-%dT%H:%M:%SZ")
                return arrivalDate

    return None


def clearFromPostCaches(base_dir: str, recent_posts_cache: {},
                        post_id: str) -> None:
    """Clears cached html for the given post, so that edits
    to news will appear
    """
    filename = '/postcache/' + post_id + '.html'
    for subdir, dirs, files in os.walk(base_dir + '/accounts'):
        for acct in dirs:
            if '@' not in acct:
                continue
            if acct.startswith('inbox@'):
                continue
            cacheDir = os.path.join(base_dir + '/accounts', acct)
            post_filename = cacheDir + filename
            if os.path.isfile(post_filename):
                try:
                    os.remove(post_filename)
                except OSError:
                    print('EX: clearFromPostCaches file not removed ' +
                          str(post_filename))
            # if the post is in the recent posts cache then remove it
            if recent_posts_cache.get('index'):
                if post_id in recent_posts_cache['index']:
                    recent_posts_cache['index'].remove(post_id)
            if recent_posts_cache.get('json'):
                if recent_posts_cache['json'].get(post_id):
                    del recent_posts_cache['json'][post_id]
            if recent_posts_cache.get('html'):
                if recent_posts_cache['html'].get(post_id):
                    del recent_posts_cache['html'][post_id]
        break


def locate_post(base_dir: str, nickname: str, domain: str,
                postUrl: str, replies: bool = False) -> str:
    """Returns the filename for the given status post url
    """
    if not replies:
        extension = 'json'
    else:
        extension = 'replies'

    # if this post in the shared inbox?
    postUrl = remove_id_ending(postUrl.strip()).replace('/', '#')

    # add the extension
    postUrl = postUrl + '.' + extension

    # search boxes
    boxes = ('inbox', 'outbox', 'tlblogs')
    accountDir = acct_dir(base_dir, nickname, domain) + '/'
    for boxName in boxes:
        post_filename = accountDir + boxName + '/' + postUrl
        if os.path.isfile(post_filename):
            return post_filename

    # check news posts
    accountDir = base_dir + '/accounts/news' + '@' + domain + '/'
    post_filename = accountDir + 'outbox/' + postUrl
    if os.path.isfile(post_filename):
        return post_filename

    # is it in the announce cache?
    post_filename = base_dir + '/cache/announce/' + nickname + '/' + postUrl
    if os.path.isfile(post_filename):
        return post_filename

    # print('WARN: unable to locate ' + nickname + ' ' + postUrl)
    return None


def _getPublishedDate(post_json_object: {}) -> str:
    """Returns the published date on the given post
    """
    published = None
    if post_json_object.get('published'):
        published = post_json_object['published']
    elif has_object_dict(post_json_object):
        if post_json_object['object'].get('published'):
            published = post_json_object['object']['published']
    if not published:
        return None
    if not isinstance(published, str):
        return None
    return published


def getReplyIntervalHours(base_dir: str, nickname: str, domain: str,
                          default_reply_interval_hrs: int) -> int:
    """Returns the reply interval for the given account.
    The reply interval is the number of hours after a post being made
    during which replies are allowed
    """
    replyIntervalFilename = \
        acct_dir(base_dir, nickname, domain) + '/.replyIntervalHours'
    if os.path.isfile(replyIntervalFilename):
        with open(replyIntervalFilename, 'r') as fp:
            hoursStr = fp.read()
            if hoursStr.isdigit():
                return int(hoursStr)
    return default_reply_interval_hrs


def setReplyIntervalHours(base_dir: str, nickname: str, domain: str,
                          replyIntervalHours: int) -> bool:
    """Sets the reply interval for the given account.
    The reply interval is the number of hours after a post being made
    during which replies are allowed
    """
    replyIntervalFilename = \
        acct_dir(base_dir, nickname, domain) + '/.replyIntervalHours'
    with open(replyIntervalFilename, 'w+') as fp:
        try:
            fp.write(str(replyIntervalHours))
            return True
        except BaseException:
            print('EX: setReplyIntervalHours unable to save reply interval ' +
                  str(replyIntervalFilename) + ' ' +
                  str(replyIntervalHours))
            pass
    return False


def canReplyTo(base_dir: str, nickname: str, domain: str,
               postUrl: str, replyIntervalHours: int,
               currDateStr: str = None,
               post_json_object: {} = None) -> bool:
    """Is replying to the given post permitted?
    This is a spam mitigation feature, so that spammers can't
    add a lot of replies to old post which you don't notice.
    """
    if '/statuses/' not in postUrl:
        return True
    if not post_json_object:
        post_filename = locate_post(base_dir, nickname, domain, postUrl)
        if not post_filename:
            return False
        post_json_object = load_json(post_filename)
    if not post_json_object:
        return False
    published = _getPublishedDate(post_json_object)
    if not published:
        return False
    try:
        pubDate = datetime.datetime.strptime(published, '%Y-%m-%dT%H:%M:%SZ')
    except BaseException:
        print('EX: canReplyTo unrecognized published date ' + str(published))
        return False
    if not currDateStr:
        currDate = datetime.datetime.utcnow()
    else:
        try:
            currDate = datetime.datetime.strptime(currDateStr,
                                                  '%Y-%m-%dT%H:%M:%SZ')
        except BaseException:
            print('EX: canReplyTo unrecognized current date ' +
                  str(currDateStr))
            return False
    hoursSincePublication = int((currDate - pubDate).total_seconds() / 3600)
    if hoursSincePublication < 0 or \
       hoursSincePublication >= replyIntervalHours:
        return False
    return True


def _removeAttachment(base_dir: str, http_prefix: str, domain: str,
                      postJson: {}):
    if not postJson.get('attachment'):
        return
    if not postJson['attachment'][0].get('url'):
        return
    attachmentUrl = postJson['attachment'][0]['url']
    if not attachmentUrl:
        return
    mediaFilename = base_dir + '/' + \
        attachmentUrl.replace(http_prefix + '://' + domain + '/', '')
    if os.path.isfile(mediaFilename):
        try:
            os.remove(mediaFilename)
        except OSError:
            print('EX: _removeAttachment unable to delete media file ' +
                  str(mediaFilename))
    etagFilename = mediaFilename + '.etag'
    if os.path.isfile(etagFilename):
        try:
            os.remove(etagFilename)
        except OSError:
            print('EX: _removeAttachment unable to delete etag file ' +
                  str(etagFilename))
    postJson['attachment'] = []


def removeModerationPostFromIndex(base_dir: str, postUrl: str,
                                  debug: bool) -> None:
    """Removes a url from the moderation index
    """
    moderation_index_file = base_dir + '/accounts/moderation.txt'
    if not os.path.isfile(moderation_index_file):
        return
    post_id = remove_id_ending(postUrl)
    if post_id in open(moderation_index_file).read():
        with open(moderation_index_file, 'r') as f:
            lines = f.readlines()
            with open(moderation_index_file, 'w+') as f:
                for line in lines:
                    if line.strip("\n").strip("\r") != post_id:
                        f.write(line)
                    else:
                        if debug:
                            print('DEBUG: removed ' + post_id +
                                  ' from moderation index')


def _is_reply_to_blog_post(base_dir: str, nickname: str, domain: str,
                           post_json_object: str):
    """Is the given post a reply to a blog post?
    """
    if not has_object_dict(post_json_object):
        return False
    if not post_json_object['object'].get('inReplyTo'):
        return False
    if not isinstance(post_json_object['object']['inReplyTo'], str):
        return False
    blogs_index_filename = \
        acct_dir(base_dir, nickname, domain) + '/tlblogs.index'
    if not os.path.isfile(blogs_index_filename):
        return False
    post_id = remove_id_ending(post_json_object['object']['inReplyTo'])
    post_id = post_id.replace('/', '#')
    if post_id in open(blogs_index_filename).read():
        return True
    return False


def _deletePostRemoveReplies(base_dir: str, nickname: str, domain: str,
                             http_prefix: str, post_filename: str,
                             recent_posts_cache: {}, debug: bool) -> None:
    """Removes replies when deleting a post
    """
    repliesFilename = post_filename.replace('.json', '.replies')
    if not os.path.isfile(repliesFilename):
        return
    if debug:
        print('DEBUG: removing replies to ' + post_filename)
    with open(repliesFilename, 'r') as f:
        for replyId in f:
            replyFile = locate_post(base_dir, nickname, domain, replyId)
            if not replyFile:
                continue
            if os.path.isfile(replyFile):
                deletePost(base_dir, http_prefix,
                           nickname, domain, replyFile, debug,
                           recent_posts_cache)
    # remove the replies file
    try:
        os.remove(repliesFilename)
    except OSError:
        print('EX: _deletePostRemoveReplies unable to delete replies file ' +
              str(repliesFilename))


def _isBookmarked(base_dir: str, nickname: str, domain: str,
                  post_filename: str) -> bool:
    """Returns True if the given post is bookmarked
    """
    bookmarksIndexFilename = \
        acct_dir(base_dir, nickname, domain) + '/bookmarks.index'
    if os.path.isfile(bookmarksIndexFilename):
        bookmarkIndex = post_filename.split('/')[-1] + '\n'
        if bookmarkIndex in open(bookmarksIndexFilename).read():
            return True
    return False


def remove_post_from_cache(post_json_object: {},
                           recent_posts_cache: {}) -> None:
    """ if the post exists in the recent posts cache then remove it
    """
    if not recent_posts_cache:
        return

    if not post_json_object.get('id'):
        return

    if not recent_posts_cache.get('index'):
        return

    post_id = post_json_object['id']
    if '#' in post_id:
        post_id = post_id.split('#', 1)[0]
    post_id = remove_id_ending(post_id).replace('/', '#')
    if post_id not in recent_posts_cache['index']:
        return

    if recent_posts_cache.get('index'):
        if post_id in recent_posts_cache['index']:
            recent_posts_cache['index'].remove(post_id)

    if recent_posts_cache.get('json'):
        if recent_posts_cache['json'].get(post_id):
            del recent_posts_cache['json'][post_id]

    if recent_posts_cache.get('html'):
        if recent_posts_cache['html'].get(post_id):
            del recent_posts_cache['html'][post_id]


def _deleteCachedHtml(base_dir: str, nickname: str, domain: str,
                      post_json_object: {}):
    """Removes cached html file for the given post
    """
    cached_post_filename = \
        get_cached_post_filename(base_dir, nickname, domain, post_json_object)
    if cached_post_filename:
        if os.path.isfile(cached_post_filename):
            try:
                os.remove(cached_post_filename)
            except OSError:
                print('EX: _deleteCachedHtml ' +
                      'unable to delete cached post file ' +
                      str(cached_post_filename))


def _deleteHashtagsOnPost(base_dir: str, post_json_object: {}) -> None:
    """Removes hashtags when a post is deleted
    """
    removeHashtagIndex = False
    if has_object_dict(post_json_object):
        if post_json_object['object'].get('content'):
            if '#' in post_json_object['object']['content']:
                removeHashtagIndex = True

    if not removeHashtagIndex:
        return

    if not post_json_object['object'].get('id') or \
       not post_json_object['object'].get('tag'):
        return

    # get the id of the post
    post_id = remove_id_ending(post_json_object['object']['id'])
    for tag in post_json_object['object']['tag']:
        if not tag.get('type'):
            continue
        if tag['type'] != 'Hashtag':
            continue
        if not tag.get('name'):
            continue
        # find the index file for this tag
        tagIndexFilename = base_dir + '/tags/' + tag['name'][1:] + '.txt'
        if not os.path.isfile(tagIndexFilename):
            continue
        # remove post_id from the tag index file
        lines = None
        with open(tagIndexFilename, 'r') as f:
            lines = f.readlines()
        if not lines:
            continue
        newlines = ''
        for fileLine in lines:
            if post_id in fileLine:
                # skip over the deleted post
                continue
            newlines += fileLine
        if not newlines.strip():
            # if there are no lines then remove the hashtag file
            try:
                os.remove(tagIndexFilename)
            except OSError:
                print('EX: _deleteHashtagsOnPost unable to delete tag index ' +
                      str(tagIndexFilename))
        else:
            # write the new hashtag index without the given post in it
            with open(tagIndexFilename, 'w+') as f:
                f.write(newlines)


def _deleteConversationPost(base_dir: str, nickname: str, domain: str,
                            post_json_object: {}) -> None:
    """Deletes a post from a conversation
    """
    if not has_object_dict(post_json_object):
        return False
    if not post_json_object['object'].get('conversation'):
        return False
    if not post_json_object['object'].get('id'):
        return False
    conversationDir = acct_dir(base_dir, nickname, domain) + '/conversation'
    conversationId = post_json_object['object']['conversation']
    conversationId = conversationId.replace('/', '#')
    post_id = post_json_object['object']['id']
    conversationFilename = conversationDir + '/' + conversationId
    if not os.path.isfile(conversationFilename):
        return False
    conversationStr = ''
    with open(conversationFilename, 'r') as fp:
        conversationStr = fp.read()
    if post_id + '\n' not in conversationStr:
        return False
    conversationStr = conversationStr.replace(post_id + '\n', '')
    if conversationStr:
        with open(conversationFilename, 'w+') as fp:
            fp.write(conversationStr)
    else:
        if os.path.isfile(conversationFilename + '.muted'):
            try:
                os.remove(conversationFilename + '.muted')
            except OSError:
                print('EX: _deleteConversationPost ' +
                      'unable to remove conversation ' +
                      str(conversationFilename) + '.muted')
        try:
            os.remove(conversationFilename)
        except OSError:
            print('EX: _deleteConversationPost ' +
                  'unable to remove conversation ' +
                  str(conversationFilename))


def deletePost(base_dir: str, http_prefix: str,
               nickname: str, domain: str, post_filename: str,
               debug: bool, recent_posts_cache: {}) -> None:
    """Recursively deletes a post and its replies and attachments
    """
    post_json_object = load_json(post_filename, 1)
    if not post_json_object:
        # remove any replies
        _deletePostRemoveReplies(base_dir, nickname, domain,
                                 http_prefix, post_filename,
                                 recent_posts_cache, debug)
        # finally, remove the post itself
        try:
            os.remove(post_filename)
        except OSError:
            if debug:
                print('EX: deletePost unable to delete post ' +
                      str(post_filename))
        return

    # don't allow deletion of bookmarked posts
    if _isBookmarked(base_dir, nickname, domain, post_filename):
        return

    # don't remove replies to blog posts
    if _is_reply_to_blog_post(base_dir, nickname, domain,
                              post_json_object):
        return

    # remove from recent posts cache in memory
    remove_post_from_cache(post_json_object, recent_posts_cache)

    # remove from conversation index
    _deleteConversationPost(base_dir, nickname, domain, post_json_object)

    # remove any attachment
    _removeAttachment(base_dir, http_prefix, domain, post_json_object)

    extensions = ('votes', 'arrived', 'muted', 'tts', 'reject')
    for ext in extensions:
        extFilename = post_filename + '.' + ext
        if os.path.isfile(extFilename):
            try:
                os.remove(extFilename)
            except OSError:
                print('EX: deletePost unable to remove ext ' +
                      str(extFilename))

    # remove cached html version of the post
    _deleteCachedHtml(base_dir, nickname, domain, post_json_object)

    has_object = False
    if post_json_object.get('object'):
        has_object = True

    # remove from moderation index file
    if has_object:
        if has_object_dict(post_json_object):
            if post_json_object['object'].get('moderationStatus'):
                if post_json_object.get('id'):
                    post_id = remove_id_ending(post_json_object['id'])
                    removeModerationPostFromIndex(base_dir, post_id, debug)

    # remove any hashtags index entries
    if has_object:
        _deleteHashtagsOnPost(base_dir, post_json_object)

    # remove any replies
    _deletePostRemoveReplies(base_dir, nickname, domain,
                             http_prefix, post_filename,
                             recent_posts_cache, debug)
    # finally, remove the post itself
    try:
        os.remove(post_filename)
    except OSError:
        if debug:
            print('EX: deletePost unable to delete post ' + str(post_filename))


def isValidLanguage(text: str) -> bool:
    """Returns true if the given text contains a valid
    natural language string
    """
    naturalLanguages = {
        "Latin": [65, 866],
        "Cyrillic": [1024, 1274],
        "Greek": [880, 1280],
        "isArmenian": [1328, 1424],
        "isHebrew": [1424, 1536],
        "Arabic": [1536, 1792],
        "Syriac": [1792, 1872],
        "Thaan": [1920, 1984],
        "Devanagari": [2304, 2432],
        "Bengali": [2432, 2560],
        "Gurmukhi": [2560, 2688],
        "Gujarati": [2688, 2816],
        "Oriya": [2816, 2944],
        "Tamil": [2944, 3072],
        "Telugu": [3072, 3200],
        "Kannada": [3200, 3328],
        "Malayalam": [3328, 3456],
        "Sinhala": [3456, 3584],
        "Thai": [3584, 3712],
        "Lao": [3712, 3840],
        "Tibetan": [3840, 4096],
        "Myanmar": [4096, 4256],
        "Georgian": [4256, 4352],
        "HangulJamo": [4352, 4608],
        "Cherokee": [5024, 5120],
        "UCAS": [5120, 5760],
        "Ogham": [5760, 5792],
        "Runic": [5792, 5888],
        "Khmer": [6016, 6144],
        "Mongolian": [6144, 6320]
    }
    for langName, langRange in naturalLanguages.items():
        okLang = True
        for ch in text:
            if ch.isdigit():
                continue
            if ord(ch) not in range(langRange[0], langRange[1]):
                okLang = False
                break
        if okLang:
            return True
    return False


def _getReservedWords() -> str:
    return ('inbox', 'dm', 'outbox', 'following',
            'public', 'followers', 'category',
            'channel', 'calendar', 'video-channels',
            'tlreplies', 'tlmedia', 'tlblogs',
            'tlblogs', 'tlfeatures',
            'moderation', 'moderationaction',
            'activity', 'undo', 'pinned',
            'actor', 'Actor',
            'reply', 'replies', 'question', 'like',
            'likes', 'users', 'statuses', 'tags',
            'accounts', 'headers',
            'channels', 'profile', 'u', 'c',
            'updates', 'repeat', 'announce',
            'shares', 'fonts', 'icons', 'avatars',
            'welcome', 'helpimages',
            'bookmark', 'bookmarks', 'tlbookmarks',
            'ignores', 'linksmobile', 'newswiremobile',
            'minimal', 'search', 'eventdelete',
            'searchemoji', 'catalog', 'conversationId',
            'mention', 'http', 'https',
            'ontologies', 'data')


def getNicknameValidationPattern() -> str:
    """Returns a html text input validation pattern for nickname
    """
    reservedNames = _getReservedWords()
    pattern = ''
    for word in reservedNames:
        if pattern:
            pattern += '(?!.*\\b' + word + '\\b)'
        else:
            pattern = '^(?!.*\\b' + word + '\\b)'
    return pattern + '.*${1,30}'


def _isReservedName(nickname: str) -> bool:
    """Is the given nickname reserved for some special function?
    """
    reservedNames = _getReservedWords()
    if nickname in reservedNames:
        return True
    return False


def validNickname(domain: str, nickname: str) -> bool:
    """Is the given nickname valid?
    """
    if len(nickname) == 0:
        return False
    if len(nickname) > 30:
        return False
    if not isValidLanguage(nickname):
        return False
    forbiddenChars = ('.', ' ', '/', '?', ':', ';', '@', '#', '!')
    for c in forbiddenChars:
        if c in nickname:
            return False
    # this should only apply for the shared inbox
    if nickname == domain:
        return False
    if _isReservedName(nickname):
        return False
    return True


def noOfAccounts(base_dir: str) -> bool:
    """Returns the number of accounts on the system
    """
    accountCtr = 0
    for subdir, dirs, files in os.walk(base_dir + '/accounts'):
        for account in dirs:
            if is_account_dir(account):
                accountCtr += 1
        break
    return accountCtr


def noOfActiveAccountsMonthly(base_dir: str, months: int) -> bool:
    """Returns the number of accounts on the system this month
    """
    accountCtr = 0
    curr_time = int(time.time())
    monthSeconds = int(60*60*24*30*months)
    for subdir, dirs, files in os.walk(base_dir + '/accounts'):
        for account in dirs:
            if not is_account_dir(account):
                continue
            lastUsedFilename = \
                base_dir + '/accounts/' + account + '/.lastUsed'
            if not os.path.isfile(lastUsedFilename):
                continue
            with open(lastUsedFilename, 'r') as lastUsedFile:
                lastUsed = lastUsedFile.read()
                if lastUsed.isdigit():
                    timeDiff = (curr_time - int(lastUsed))
                    if timeDiff < monthSeconds:
                        accountCtr += 1
        break
    return accountCtr


def isPublicPostFromUrl(base_dir: str, nickname: str, domain: str,
                        postUrl: str) -> bool:
    """Returns whether the given url is a public post
    """
    post_filename = locate_post(base_dir, nickname, domain, postUrl)
    if not post_filename:
        return False
    post_json_object = load_json(post_filename, 1)
    if not post_json_object:
        return False
    return isPublicPost(post_json_object)


def isPublicPost(post_json_object: {}) -> bool:
    """Returns true if the given post is public
    """
    if not post_json_object.get('type'):
        return False
    if post_json_object['type'] != 'Create':
        return False
    if not has_object_dict(post_json_object):
        return False
    if not post_json_object['object'].get('to'):
        return False
    for recipient in post_json_object['object']['to']:
        if recipient.endswith('#Public'):
            return True
    return False


def copytree(src: str, dst: str, symlinks: str = False, ignore: bool = None):
    """Copy a directory
    """
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)


def get_cached_post_directory(base_dir: str,
                              nickname: str, domain: str) -> str:
    """Returns the directory where the html post cache exists
    """
    html_post_cache_dir = acct_dir(base_dir, nickname, domain) + '/postcache'
    return html_post_cache_dir


def get_cached_post_filename(base_dir: str, nickname: str, domain: str,
                             post_json_object: {}) -> str:
    """Returns the html cache filename for the given post
    """
    cachedPostDir = get_cached_post_directory(base_dir, nickname, domain)
    if not os.path.isdir(cachedPostDir):
        # print('ERROR: invalid html cache directory ' + cachedPostDir)
        return None
    if '@' not in cachedPostDir:
        # print('ERROR: invalid html cache directory ' + cachedPostDir)
        return None
    cachedPostId = remove_id_ending(post_json_object['id'])
    cached_post_filename = cachedPostDir + '/' + cachedPostId.replace('/', '#')
    return cached_post_filename + '.html'


def updateRecentPostsCache(recent_posts_cache: {}, max_recent_posts: int,
                           post_json_object: {}, htmlStr: str) -> None:
    """Store recent posts in memory so that they can be quickly recalled
    """
    if not post_json_object.get('id'):
        return
    post_id = post_json_object['id']
    if '#' in post_id:
        post_id = post_id.split('#', 1)[0]
    post_id = remove_id_ending(post_id).replace('/', '#')
    if recent_posts_cache.get('index'):
        if post_id in recent_posts_cache['index']:
            return
        recent_posts_cache['index'].append(post_id)
        post_json_object['muted'] = False
        recent_posts_cache['json'][post_id] = json.dumps(post_json_object)
        recent_posts_cache['html'][post_id] = htmlStr

        while len(recent_posts_cache['html'].items()) > max_recent_posts:
            post_id = recent_posts_cache['index'][0]
            recent_posts_cache['index'].pop(0)
            if recent_posts_cache['json'].get(post_id):
                del recent_posts_cache['json'][post_id]
            if recent_posts_cache['html'].get(post_id):
                del recent_posts_cache['html'][post_id]
    else:
        recent_posts_cache['index'] = [post_id]
        recent_posts_cache['json'] = {}
        recent_posts_cache['html'] = {}
        recent_posts_cache['json'][post_id] = json.dumps(post_json_object)
        recent_posts_cache['html'][post_id] = htmlStr


def fileLastModified(filename: str) -> str:
    """Returns the date when a file was last modified
    """
    t = os.path.getmtime(filename)
    modifiedTime = datetime.datetime.fromtimestamp(t)
    return modifiedTime.strftime("%Y-%m-%dT%H:%M:%SZ")


def getCSS(base_dir: str, cssFilename: str, cssCache: {}) -> str:
    """Retrieves the css for a given file, or from a cache
    """
    # does the css file exist?
    if not os.path.isfile(cssFilename):
        return None

    lastModified = fileLastModified(cssFilename)

    # has this already been loaded into the cache?
    if cssCache.get(cssFilename):
        if cssCache[cssFilename][0] == lastModified:
            # file hasn't changed, so return the version in the cache
            return cssCache[cssFilename][1]

    with open(cssFilename, 'r') as fpCSS:
        css = fpCSS.read()
        if cssCache.get(cssFilename):
            # alter the cache contents
            cssCache[cssFilename][0] = lastModified
            cssCache[cssFilename][1] = css
        else:
            # add entry to the cache
            cssCache[cssFilename] = [lastModified, css]
        return css

    return None


def isBlogPost(post_json_object: {}) -> bool:
    """Is the given post a blog post?
    """
    if post_json_object['type'] != 'Create':
        return False
    if not has_object_dict(post_json_object):
        return False
    if not has_object_stringType(post_json_object, False):
        return False
    if not post_json_object['object'].get('content'):
        return False
    if post_json_object['object']['type'] != 'Article':
        return False
    return True


def isNewsPost(post_json_object: {}) -> bool:
    """Is the given post a blog post?
    """
    return post_json_object.get('news')


def _searchVirtualBoxPosts(base_dir: str, nickname: str, domain: str,
                           searchStr: str, maxResults: int,
                           boxName: str) -> []:
    """Searches through a virtual box, which is typically an index on the inbox
    """
    indexFilename = \
        acct_dir(base_dir, nickname, domain) + '/' + boxName + '.index'
    if boxName == 'bookmarks':
        boxName = 'inbox'
    path = acct_dir(base_dir, nickname, domain) + '/' + boxName
    if not os.path.isdir(path):
        return []

    searchStr = searchStr.lower().strip()

    if '+' in searchStr:
        searchWords = searchStr.split('+')
        for index in range(len(searchWords)):
            searchWords[index] = searchWords[index].strip()
        print('SEARCH: ' + str(searchWords))
    else:
        searchWords = [searchStr]

    res = []
    with open(indexFilename, 'r') as indexFile:
        post_filename = 'start'
        while post_filename:
            post_filename = indexFile.readline()
            if not post_filename:
                break
            if '.json' not in post_filename:
                break
            post_filename = path + '/' + post_filename.strip()
            if not os.path.isfile(post_filename):
                continue
            with open(post_filename, 'r') as postFile:
                data = postFile.read().lower()

                notFound = False
                for keyword in searchWords:
                    if keyword not in data:
                        notFound = True
                        break
                if notFound:
                    continue

                res.append(post_filename)
                if len(res) >= maxResults:
                    return res
    return res


def searchBoxPosts(base_dir: str, nickname: str, domain: str,
                   searchStr: str, maxResults: int,
                   boxName='outbox') -> []:
    """Search your posts and return a list of the filenames
    containing matching strings
    """
    path = acct_dir(base_dir, nickname, domain) + '/' + boxName
    # is this a virtual box, such as direct messages?
    if not os.path.isdir(path):
        if os.path.isfile(path + '.index'):
            return _searchVirtualBoxPosts(base_dir, nickname, domain,
                                          searchStr, maxResults, boxName)
        return []
    searchStr = searchStr.lower().strip()

    if '+' in searchStr:
        searchWords = searchStr.split('+')
        for index in range(len(searchWords)):
            searchWords[index] = searchWords[index].strip()
        print('SEARCH: ' + str(searchWords))
    else:
        searchWords = [searchStr]

    res = []
    for root, dirs, fnames in os.walk(path):
        for fname in fnames:
            filePath = os.path.join(root, fname)
            with open(filePath, 'r') as postFile:
                data = postFile.read().lower()

                notFound = False
                for keyword in searchWords:
                    if keyword not in data:
                        notFound = True
                        break
                if notFound:
                    continue

                res.append(filePath)
                if len(res) >= maxResults:
                    return res
        break
    return res


def getFileCaseInsensitive(path: str) -> str:
    """Returns a case specific filename given a case insensitive version of it
    """
    if os.path.isfile(path):
        return path
    if path != path.lower():
        if os.path.isfile(path.lower()):
            return path.lower()
    return None


def undoLikesCollectionEntry(recent_posts_cache: {},
                             base_dir: str, post_filename: str, objectUrl: str,
                             actor: str, domain: str, debug: bool,
                             post_json_object: {}) -> None:
    """Undoes a like for a particular actor
    """
    if not post_json_object:
        post_json_object = load_json(post_filename)
    if not post_json_object:
        return
    # remove any cached version of this post so that the
    # like icon is changed
    nickname = getNicknameFromActor(actor)
    cached_post_filename = \
        get_cached_post_filename(base_dir, nickname,
                                 domain, post_json_object)
    if cached_post_filename:
        if os.path.isfile(cached_post_filename):
            try:
                os.remove(cached_post_filename)
            except OSError:
                print('EX: undoLikesCollectionEntry ' +
                      'unable to delete cached post ' +
                      str(cached_post_filename))
    remove_post_from_cache(post_json_object, recent_posts_cache)

    if not post_json_object.get('type'):
        return
    if post_json_object['type'] != 'Create':
        return
    obj = post_json_object
    if has_object_dict(post_json_object):
        obj = post_json_object['object']
    if not obj.get('likes'):
        return
    if not isinstance(obj['likes'], dict):
        return
    if not obj['likes'].get('items'):
        return
    totalItems = 0
    if obj['likes'].get('totalItems'):
        totalItems = obj['likes']['totalItems']
    itemFound = False
    for likeItem in obj['likes']['items']:
        if likeItem.get('actor'):
            if likeItem['actor'] == actor:
                if debug:
                    print('DEBUG: like was removed for ' + actor)
                obj['likes']['items'].remove(likeItem)
                itemFound = True
                break
    if not itemFound:
        return
    if totalItems == 1:
        if debug:
            print('DEBUG: likes was removed from post')
        del obj['likes']
    else:
        itlen = len(obj['likes']['items'])
        obj['likes']['totalItems'] = itlen

    save_json(post_json_object, post_filename)


def undoReactionCollectionEntry(recent_posts_cache: {},
                                base_dir: str, post_filename: str,
                                objectUrl: str,
                                actor: str, domain: str, debug: bool,
                                post_json_object: {},
                                emojiContent: str) -> None:
    """Undoes an emoji reaction for a particular actor
    """
    if not post_json_object:
        post_json_object = load_json(post_filename)
    if not post_json_object:
        return
    # remove any cached version of this post so that the
    # like icon is changed
    nickname = getNicknameFromActor(actor)
    cached_post_filename = \
        get_cached_post_filename(base_dir, nickname,
                                 domain, post_json_object)
    if cached_post_filename:
        if os.path.isfile(cached_post_filename):
            try:
                os.remove(cached_post_filename)
            except OSError:
                print('EX: undoReactionCollectionEntry ' +
                      'unable to delete cached post ' +
                      str(cached_post_filename))
    remove_post_from_cache(post_json_object, recent_posts_cache)

    if not post_json_object.get('type'):
        return
    if post_json_object['type'] != 'Create':
        return
    obj = post_json_object
    if has_object_dict(post_json_object):
        obj = post_json_object['object']
    if not obj.get('reactions'):
        return
    if not isinstance(obj['reactions'], dict):
        return
    if not obj['reactions'].get('items'):
        return
    totalItems = 0
    if obj['reactions'].get('totalItems'):
        totalItems = obj['reactions']['totalItems']
    itemFound = False
    for likeItem in obj['reactions']['items']:
        if likeItem.get('actor'):
            if likeItem['actor'] == actor and \
               likeItem['content'] == emojiContent:
                if debug:
                    print('DEBUG: emoji reaction was removed for ' + actor)
                obj['reactions']['items'].remove(likeItem)
                itemFound = True
                break
    if not itemFound:
        return
    if totalItems == 1:
        if debug:
            print('DEBUG: emoji reaction was removed from post')
        del obj['reactions']
    else:
        itlen = len(obj['reactions']['items'])
        obj['reactions']['totalItems'] = itlen

    save_json(post_json_object, post_filename)


def undo_announce_collection_entry(recent_posts_cache: {},
                                   base_dir: str, post_filename: str,
                                   actor: str, domain: str,
                                   debug: bool) -> None:
    """Undoes an announce for a particular actor by removing it from
    the "shares" collection within a post. Note that the "shares"
    collection has no relation to shared items in shares.py. It's
    shares of posts, not shares of physical objects.
    """
    post_json_object = load_json(post_filename)
    if not post_json_object:
        return
    # remove any cached version of this announce so that the announce
    # icon is changed
    nickname = getNicknameFromActor(actor)
    cached_post_filename = \
        get_cached_post_filename(base_dir, nickname, domain,
                                 post_json_object)
    if cached_post_filename:
        if os.path.isfile(cached_post_filename):
            try:
                os.remove(cached_post_filename)
            except OSError:
                if debug:
                    print('EX: undo_announce_collection_entry ' +
                          'unable to delete cached post ' +
                          str(cached_post_filename))
    remove_post_from_cache(post_json_object, recent_posts_cache)

    if not post_json_object.get('type'):
        return
    if post_json_object['type'] != 'Create':
        return
    if not has_object_dict(post_json_object):
        if debug:
            pprint(post_json_object)
            print('DEBUG: post has no object')
        return
    if not post_json_object['object'].get('shares'):
        return
    if not post_json_object['object']['shares'].get('items'):
        return
    totalItems = 0
    if post_json_object['object']['shares'].get('totalItems'):
        totalItems = post_json_object['object']['shares']['totalItems']
    itemFound = False
    for announceItem in post_json_object['object']['shares']['items']:
        if announceItem.get('actor'):
            if announceItem['actor'] == actor:
                if debug:
                    print('DEBUG: Announce was removed for ' + actor)
                anIt = announceItem
                post_json_object['object']['shares']['items'].remove(anIt)
                itemFound = True
                break
    if not itemFound:
        return
    if totalItems == 1:
        if debug:
            print('DEBUG: shares (announcements) ' +
                  'was removed from post')
        del post_json_object['object']['shares']
    else:
        itlen = len(post_json_object['object']['shares']['items'])
        post_json_object['object']['shares']['totalItems'] = itlen

    save_json(post_json_object, post_filename)


def update_announce_collection(recent_posts_cache: {},
                               base_dir: str, post_filename: str,
                               actor: str, nickname: str, domain: str,
                               debug: bool) -> None:
    """Updates the announcements collection within a post
    Confusingly this is known as "shares", but isn't the
    same as shared items within shares.py
    It's shares of posts, not shares of physical objects.
    """
    post_json_object = load_json(post_filename)
    if not post_json_object:
        return
    # remove any cached version of this announce so that the announce
    # icon is changed
    cached_post_filename = \
        get_cached_post_filename(base_dir, nickname, domain,
                                 post_json_object)
    if cached_post_filename:
        if os.path.isfile(cached_post_filename):
            try:
                os.remove(cached_post_filename)
            except OSError:
                if debug:
                    print('EX: update_announce_collection ' +
                          'unable to delete cached post ' +
                          str(cached_post_filename))
    remove_post_from_cache(post_json_object, recent_posts_cache)

    if not has_object_dict(post_json_object):
        if debug:
            pprint(post_json_object)
            print('DEBUG: post ' + post_filename + ' has no object')
        return
    postUrl = remove_id_ending(post_json_object['id']) + '/shares'
    if not post_json_object['object'].get('shares'):
        if debug:
            print('DEBUG: Adding initial shares (announcements) to ' +
                  postUrl)
        announcementsJson = {
            "@context": "https://www.w3.org/ns/activitystreams",
            'id': postUrl,
            'type': 'Collection',
            "totalItems": 1,
            'items': [{
                'type': 'Announce',
                'actor': actor
            }]
        }
        post_json_object['object']['shares'] = announcementsJson
    else:
        if post_json_object['object']['shares'].get('items'):
            sharesItems = post_json_object['object']['shares']['items']
            for announceItem in sharesItems:
                if announceItem.get('actor'):
                    if announceItem['actor'] == actor:
                        return
            newAnnounce = {
                'type': 'Announce',
                'actor': actor
            }
            post_json_object['object']['shares']['items'].append(newAnnounce)
            itlen = len(post_json_object['object']['shares']['items'])
            post_json_object['object']['shares']['totalItems'] = itlen
        else:
            if debug:
                print('DEBUG: shares (announcements) section of post ' +
                      'has no items list')

    if debug:
        print('DEBUG: saving post with shares (announcements) added')
        pprint(post_json_object)
    save_json(post_json_object, post_filename)


def week_day_of_month_start(month_number: int, year: int) -> int:
    """Gets the day number of the first day of the month
    1=sun, 7=sat
    """
    first_day_of_month = datetime.datetime(year, month_number, 1, 0, 0)
    return int(first_day_of_month.strftime("%w")) + 1


def media_file_mime_type(filename: str) -> str:
    """Given a media filename return its mime type
    """
    if '.' not in filename:
        return 'image/png'
    extensions = {
        'json': 'application/json',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'svg': 'image/svg+xml',
        'webp': 'image/webp',
        'avif': 'image/avif',
        'ico': 'image/x-icon',
        'mp3': 'audio/mpeg',
        'ogg': 'audio/ogg',
        'flac': 'audio/flac',
        'mp4': 'video/mp4',
        'ogv': 'video/ogv'
    }
    file_ext = filename.split('.')[-1]
    if not extensions.get(file_ext):
        return 'image/png'
    return extensions[file_ext]


def is_recent_post(post_json_object: {}, max_days: int) -> bool:
    """ Is the given post recent?
    """
    if not has_object_dict(post_json_object):
        return False
    if not post_json_object['object'].get('published'):
        return False
    if not isinstance(post_json_object['object']['published'], str):
        return False
    curr_time = datetime.datetime.utcnow()
    days_since_epoch = (curr_time - datetime.datetime(1970, 1, 1)).days
    recently = days_since_epoch - max_days

    published_date_str = post_json_object['object']['published']
    try:
        published_date = \
            datetime.datetime.strptime(published_date_str,
                                       "%Y-%m-%dT%H:%M:%SZ")
    except BaseException:
        print('EX: is_recent_post unrecognized published date ' +
              str(published_date_str))
        return False

    published_days_since_epoch = \
        (published_date - datetime.datetime(1970, 1, 1)).days
    if published_days_since_epoch < recently:
        return False
    return True


def camel_case_split(text: str) -> str:
    """ Splits CamelCase into "Camel Case"
    """
    matches = re.finditer('.+?(?:(?<=[a-z])(?=[A-Z])|' +
                          '(?<=[A-Z])(?=[A-Z][a-z])|$)', text)
    if not matches:
        return text
    resultStr = ''
    for word in matches:
        resultStr += word.group(0) + ' '
    return resultStr.strip()


def reject_post_id(base_dir: str, nickname: str, domain: str,
                   post_id: str, recent_posts_cache: {}) -> None:
    """ Marks the given post as rejected,
    for example an announce which is too old
    """
    post_filename = locate_post(base_dir, nickname, domain, post_id)
    if not post_filename:
        return

    if recent_posts_cache.get('index'):
        # if this is a full path then remove the directories
        index_filename = post_filename
        if '/' in post_filename:
            index_filename = post_filename.split('/')[-1]

        # filename of the post without any extension or path
        # This should also correspond to any index entry in
        # the posts cache
        postUrl = \
            index_filename.replace('\n', '').replace('\r', '')
        postUrl = postUrl.replace('.json', '').strip()

        if postUrl in recent_posts_cache['index']:
            if recent_posts_cache['json'].get(postUrl):
                del recent_posts_cache['json'][postUrl]
            if recent_posts_cache['html'].get(postUrl):
                del recent_posts_cache['html'][postUrl]

    with open(post_filename + '.reject', 'w+') as rejectFile:
        rejectFile.write('\n')


def is_dm(post_json_object: {}) -> bool:
    """Returns true if the given post is a DM
    """
    if post_json_object['type'] != 'Create':
        return False
    if not has_object_dict(post_json_object):
        return False
    if post_json_object['object']['type'] != 'Note' and \
       post_json_object['object']['type'] != 'Page' and \
       post_json_object['object']['type'] != 'Patch' and \
       post_json_object['object']['type'] != 'EncryptedMessage' and \
       post_json_object['object']['type'] != 'Article':
        return False
    if post_json_object['object'].get('moderationStatus'):
        return False
    fields = ('to', 'cc')
    for f in fields:
        if not post_json_object['object'].get(f):
            continue
        for to_address in post_json_object['object'][f]:
            if to_address.endswith('#Public'):
                return False
            if to_address.endswith('followers'):
                return False
    return True


def is_reply(post_json_object: {}, actor: str) -> bool:
    """Returns true if the given post is a reply to the given actor
    """
    if post_json_object['type'] != 'Create':
        return False
    if not has_object_dict(post_json_object):
        return False
    if post_json_object['object'].get('moderationStatus'):
        return False
    if post_json_object['object']['type'] != 'Note' and \
       post_json_object['object']['type'] != 'Page' and \
       post_json_object['object']['type'] != 'EncryptedMessage' and \
       post_json_object['object']['type'] != 'Article':
        return False
    if post_json_object['object'].get('inReplyTo'):
        if isinstance(post_json_object['object']['inReplyTo'], str):
            if post_json_object['object']['inReplyTo'].startswith(actor):
                return True
    if not post_json_object['object'].get('tag'):
        return False
    if not isinstance(post_json_object['object']['tag'], list):
        return False
    for tag in post_json_object['object']['tag']:
        if not tag.get('type'):
            continue
        if tag['type'] == 'Mention':
            if not tag.get('href'):
                continue
            if actor in tag['href']:
                return True
    return False


def contains_pgp_public_key(content: str) -> bool:
    """Returns true if the given content contains a PGP public key
    """
    if '--BEGIN PGP PUBLIC KEY BLOCK--' in content:
        if '--END PGP PUBLIC KEY BLOCK--' in content:
            return True
    return False


def is_pgp_encrypted(content: str) -> bool:
    """Returns true if the given content is PGP encrypted
    """
    if '--BEGIN PGP MESSAGE--' in content:
        if '--END PGP MESSAGE--' in content:
            return True
    return False


def invalid_ciphertext(content: str) -> bool:
    """Returns true if the given content contains an invalid key
    """
    if '----BEGIN ' in content or '----END ' in content:
        if not contains_pgp_public_key(content) and \
           not is_pgp_encrypted(content):
            return True
    return False


def load_translations_from_file(base_dir: str, language: str) -> ({}, str):
    """Returns the translations dictionary
    """
    if not os.path.isdir(base_dir + '/translations'):
        print('ERROR: translations directory not found')
        return None, None
    if not language:
        system_language = locale.getdefaultlocale()[0]
    else:
        system_language = language
    if not system_language:
        system_language = 'en'
    if '_' in system_language:
        system_language = system_language.split('_')[0]
    while '/' in system_language:
        system_language = system_language.split('/')[1]
    if '.' in system_language:
        system_language = system_language.split('.')[0]
    translations_file = base_dir + '/translations/' + \
        system_language + '.json'
    if not os.path.isfile(translations_file):
        system_language = 'en'
        translations_file = base_dir + '/translations/' + \
            system_language + '.json'
    return load_json(translations_file), system_language


def dm_allowed_from_domain(base_dir: str,
                           nickname: str, domain: str,
                           sending_actor_domain: str) -> bool:
    """When a DM is received and the .followDMs flag file exists
    Then optionally some domains can be specified as allowed,
    regardless of individual follows.
    i.e. Mostly you only want DMs from followers, but there are
    a few particular instances that you trust
    """
    dm_allowed_instances_file = \
        acct_dir(base_dir, nickname, domain) + '/dmAllowedInstances.txt'
    if not os.path.isfile(dm_allowed_instances_file):
        return False
    if sending_actor_domain + '\n' in open(dm_allowed_instances_file).read():
        return True
    return False


def get_occupation_skills(actor_json: {}) -> []:
    """Returns the list of skills for an actor
    """
    if 'hasOccupation' not in actor_json:
        return []
    if not isinstance(actor_json['hasOccupation'], list):
        return []
    for occupation_item in actor_json['hasOccupation']:
        if not isinstance(occupation_item, dict):
            continue
        if not occupation_item.get('@type'):
            continue
        if not occupation_item['@type'] == 'Occupation':
            continue
        if not occupation_item.get('skills'):
            continue
        if isinstance(occupation_item['skills'], list):
            return occupation_item['skills']
        elif isinstance(occupation_item['skills'], str):
            return [occupation_item['skills']]
        break
    return []


def get_occupation_name(actor_json: {}) -> str:
    """Returns the occupation name an actor
    """
    if not actor_json.get('hasOccupation'):
        return ""
    if not isinstance(actor_json['hasOccupation'], list):
        return ""
    for occupation_item in actor_json['hasOccupation']:
        if not isinstance(occupation_item, dict):
            continue
        if not occupation_item.get('@type'):
            continue
        if occupation_item['@type'] != 'Occupation':
            continue
        if not occupation_item.get('name'):
            continue
        if isinstance(occupation_item['name'], str):
            return occupation_item['name']
        break
    return ""


def set_occupation_name(actor_json: {}, name: str) -> bool:
    """Sets the occupation name of an actor
    """
    if not actor_json.get('hasOccupation'):
        return False
    if not isinstance(actor_json['hasOccupation'], list):
        return False
    for index in range(len(actor_json['hasOccupation'])):
        occupation_item = actor_json['hasOccupation'][index]
        if not isinstance(occupation_item, dict):
            continue
        if not occupation_item.get('@type'):
            continue
        if occupation_item['@type'] != 'Occupation':
            continue
        occupation_item['name'] = name
        return True
    return False


def set_occupation_skills_list(actor_json: {}, skills_list: []) -> bool:
    """Sets the occupation skills for an actor
    """
    if 'hasOccupation' not in actor_json:
        return False
    if not isinstance(actor_json['hasOccupation'], list):
        return False
    for index in range(len(actor_json['hasOccupation'])):
        occupation_item = actor_json['hasOccupation'][index]
        if not isinstance(occupation_item, dict):
            continue
        if not occupation_item.get('@type'):
            continue
        if occupation_item['@type'] != 'Occupation':
            continue
        occupation_item['skills'] = skills_list
        return True
    return False


def is_account_dir(dir_name: str) -> bool:
    """Is the given directory an account within /accounts ?
    """
    if '@' not in dir_name:
        return False
    if 'inbox@' in dir_name or 'news@' in dir_name:
        return False
    return True


def permitted_dir(path: str) -> bool:
    """These are special paths which should not be accessible
       directly via GET or POST
    """
    if path.startswith('/wfendpoints') or \
       path.startswith('/keys') or \
       path.startswith('/accounts'):
        return False
    return True


def user_agent_domain(user_agent: str, debug: bool) -> str:
    """If the User-Agent string contains a domain
    then return it
    """
    if '+http' not in user_agent:
        return None
    agent_domain = user_agent.split('+http')[1].strip()
    if '://' in agent_domain:
        agent_domain = agent_domain.split('://')[1]
    if '/' in agent_domain:
        agent_domain = agent_domain.split('/')[0]
    if ')' in agent_domain:
        agent_domain = agent_domain.split(')')[0].strip()
    if ' ' in agent_domain:
        agent_domain = agent_domain.replace(' ', '')
    if ';' in agent_domain:
        agent_domain = agent_domain.replace(';', '')
    if '.' not in agent_domain:
        return None
    if debug:
        print('User-Agent Domain: ' + agent_domain)
    return agent_domain


def has_object_dict(post_json_object: {}) -> bool:
    """Returns true if the given post has an object dict
    """
    if post_json_object.get('object'):
        if isinstance(post_json_object['object'], dict):
            return True
    return False


def get_alt_path(actor: str, domain_full: str, calling_domain: str) -> str:
    """Returns alternate path from the actor
    eg. https://clearnetdomain/path becomes http://oniondomain/path
    """
    post_actor = actor
    if calling_domain not in actor and domain_full in actor:
        if calling_domain.endswith('.onion') or \
           calling_domain.endswith('.i2p'):
            post_actor = \
                'http://' + calling_domain + actor.split(domain_full)[1]
            print('Changed POST domain from ' + actor + ' to ' + post_actor)
    return post_actor


def get_actor_property_url(actor_json: {}, property_name: str) -> str:
    """Returns a url property from an actor
    """
    if not actor_json.get('attachment'):
        return ''
    property_name = property_name.lower()
    for property_value in actor_json['attachment']:
        if not property_value.get('name'):
            continue
        if not property_value['name'].lower().startswith(property_name):
            continue
        if not property_value.get('type'):
            continue
        if not property_value.get('value'):
            continue
        if property_value['type'] != 'PropertyValue':
            continue
        property_value['value'] = property_value['value'].strip()
        prefixes = get_protocol_prefixes()
        prefixFound = False
        for prefix in prefixes:
            if property_value['value'].startswith(prefix):
                prefixFound = True
                break
        if not prefixFound:
            continue
        if '.' not in property_value['value']:
            continue
        if ' ' in property_value['value']:
            continue
        if ',' in property_value['value']:
            continue
        return property_value['value']
    return ''


def remove_domain_port(domain: str) -> str:
    """If the domain has a port appended then remove it
    eg. mydomain.com:80 becomes mydomain.com
    """
    if ':' in domain:
        if domain.startswith('did:'):
            return domain
        domain = domain.split(':')[0]
    return domain


def get_port_from_domain(domain: str) -> int:
    """If the domain has a port number appended then return it
    eg. mydomain.com:80 returns 80
    """
    if ':' in domain:
        if domain.startswith('did:'):
            return None
        portStr = domain.split(':')[1]
        if portStr.isdigit():
            return int(portStr)
    return None


def valid_url_prefix(url: str) -> bool:
    """Does the given url have a valid prefix?
    """
    if '/' not in url:
        return False
    prefixes = ('https:', 'http:', 'hyper:', 'i2p:', 'gnunet:')
    for pre in prefixes:
        if url.startswith(pre):
            return True
    return False


def remove_line_endings(text: str) -> str:
    """Removes any newline from the end of a string
    """
    text = text.replace('\n', '')
    text = text.replace('\r', '')
    return text.strip()


def valid_password(password: str) -> bool:
    """Returns true if the given password is valid
    """
    if len(password) < 8:
        return False
    return True


def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


def date_string_to_seconds(date_str: str) -> int:
    """Converts a date string (eg "published") into seconds since epoch
    """
    try:
        expiry_time = \
            datetime.datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
    except BaseException:
        print('EX: date_string_to_seconds unable to parse date ' +
              str(date_str))
        return None
    return int(datetime.datetime.timestamp(expiry_time))


def date_seconds_to_string(date_sec: int) -> str:
    """Converts a date in seconds since epoch to a string
    """
    this_date = datetime.datetime.fromtimestamp(date_sec)
    return this_date.strftime("%Y-%m-%dT%H:%M:%SZ")


def has_group_type(base_dir: str, actor: str, person_cache: {},
                   debug: bool = False) -> bool:
    """Does the given actor url have a group type?
    """
    # does the actor path clearly indicate that this is a group?
    # eg. https://lemmy/c/groupname
    group_paths = get_group_paths()
    for grp_path in group_paths:
        if grp_path in actor:
            if debug:
                print('grpPath ' + grp_path + ' in ' + actor)
            return True
    # is there a cached actor which can be examined for Group type?
    return is_group_actor(base_dir, actor, person_cache, debug)


def is_group_actor(base_dir: str, actor: str, person_cache: {},
                   debug: bool = False) -> bool:
    """Is the given actor a group?
    """
    if person_cache:
        if person_cache.get(actor):
            if person_cache[actor].get('actor'):
                if person_cache[actor]['actor'].get('type'):
                    if person_cache[actor]['actor']['type'] == 'Group':
                        if debug:
                            print('Cached actor ' + actor + ' has Group type')
                        return True
                return False
    if debug:
        print('Actor ' + actor + ' not in cache')
    cached_actor_filename = \
        base_dir + '/cache/actors/' + (actor.replace('/', '#')) + '.json'
    if not os.path.isfile(cached_actor_filename):
        if debug:
            print('Cached actor file not found ' + cached_actor_filename)
        return False
    if '"type": "Group"' in open(cached_actor_filename).read():
        if debug:
            print('Group type found in ' + cached_actor_filename)
        return True
    return False


def is_group_account(base_dir: str, nickname: str, domain: str) -> bool:
    """Returns true if the given account is a group
    """
    account_filename = acct_dir(base_dir, nickname, domain) + '.json'
    if not os.path.isfile(account_filename):
        return False
    if '"type": "Group"' in open(account_filename).read():
        return True
    return False


def get_currencies() -> {}:
    """Returns a dictionary of currencies
    """
    return {
        "CA$": "CAD",
        "J$": "JMD",
        "£": "GBP",
        "€": "EUR",
        "؋": "AFN",
        "ƒ": "AWG",
        "₼": "AZN",
        "Br": "BYN",
        "BZ$": "BZD",
        "$b": "BOB",
        "KM": "BAM",
        "P": "BWP",
        "лв": "BGN",
        "R$": "BRL",
        "៛": "KHR",
        "$U": "UYU",
        "RD$": "DOP",
        "$": "USD",
        "₡": "CRC",
        "kn": "HRK",
        "₱": "CUP",
        "Kč": "CZK",
        "kr": "NOK",
        "¢": "GHS",
        "Q": "GTQ",
        "L": "HNL",
        "Ft": "HUF",
        "Rp": "IDR",
        "₹": "INR",
        "﷼": "IRR",
        "₪": "ILS",
        "¥": "JPY",
        "₩": "KRW",
        "₭": "LAK",
        "ден": "MKD",
        "RM": "MYR",
        "₨": "MUR",
        "₮": "MNT",
        "MT": "MZN",
        "C$": "NIO",
        "₦": "NGN",
        "Gs": "PYG",
        "zł": "PLN",
        "lei": "RON",
        "₽": "RUB",
        "Дин": "RSD",
        "S": "SOS",
        "R": "ZAR",
        "CHF": "CHF",
        "NT$": "TWD",
        "฿": "THB",
        "TT$": "TTD",
        "₴": "UAH",
        "Bs": "VEF",
        "₫": "VND",
        "Z$": "ZQD"
    }


def get_supported_languages(base_dir: str) -> []:
    """Returns a list of supported languages
    """
    translations_dir = base_dir + '/translations'
    languages_str = []
    for _, _, files in os.walk(translations_dir):
        for f in files:
            if not f.endswith('.json'):
                continue
            lang = f.split('.')[0]
            if len(lang) == 2:
                languages_str.append(lang)
        break
    return languages_str


def get_category_types(base_dir: str) -> []:
    """Returns the list of ontologies
    """
    ontology_dir = base_dir + '/ontology'
    categories = []
    for _, _, files in os.walk(ontology_dir):
        for f in files:
            if not f.endswith('.json'):
                continue
            if '#' in f or '~' in f:
                continue
            if f.startswith('custom'):
                continue
            ontology_filename = f.split('.')[0]
            if 'Types' in ontology_filename:
                categories.append(ontology_filename.replace('Types', ''))
        break
    return categories


def get_shares_files_list() -> []:
    """Returns the possible shares files
    """
    return ('shares', 'wanted')


def replace_users_with_at(actor: str) -> str:
    """ https://domain/users/nick becomes https://domain/@nick
    """
    u_paths = get_user_paths()
    for path in u_paths:
        if path in actor:
            actor = actor.replace(path, '/@')
            break
    return actor


def has_actor(post_json_object: {}, debug: bool) -> bool:
    """Does the given post have an actor?
    """
    if post_json_object.get('actor'):
        if '#' in post_json_object['actor']:
            return False
        return True
    if debug:
        if post_json_object.get('type'):
            msg = post_json_object['type'] + ' has missing actor'
            if post_json_object.get('id'):
                msg += ' ' + post_json_object['id']
            print(msg)
    return False


def has_object_stringType(post_json_object: {}, debug: bool) -> bool:
    """Does the given post have a type field within an object dict?
    """
    if not has_object_dict(post_json_object):
        if debug:
            print('has_object_stringType no object found')
        return False
    if post_json_object['object'].get('type'):
        if isinstance(post_json_object['object']['type'], str):
            return True
        elif debug:
            if post_json_object.get('type'):
                print('DEBUG: ' + post_json_object['type'] +
                      ' type within object is not a string')
    if debug:
        print('No type field within object ' + post_json_object['id'])
    return False


def has_object_string_object(post_json_object: {}, debug: bool) -> bool:
    """Does the given post have an object string field within an object dict?
    """
    if not has_object_dict(post_json_object):
        if debug:
            print('has_object_stringType no object found')
        return False
    if post_json_object['object'].get('object'):
        if isinstance(post_json_object['object']['object'], str):
            return True
        elif debug:
            if post_json_object.get('type'):
                print('DEBUG: ' + post_json_object['type'] +
                      ' object within dict is not a string')
    if debug:
        print('No object field within dict ' + post_json_object['id'])
    return False


def has_object_string(post_json_object: {}, debug: bool) -> bool:
    """Does the given post have an object string field?
    """
    if post_json_object.get('object'):
        if isinstance(post_json_object['object'], str):
            return True
        elif debug:
            if post_json_object.get('type'):
                print('DEBUG: ' + post_json_object['type'] +
                      ' object is not a string')
    if debug:
        print('No object field within post ' + post_json_object['id'])
    return False


def get_new_post_endpoints() -> []:
    """Returns a list of endpoints for new posts
    """
    return (
        'newpost', 'newblog', 'newunlisted', 'newfollowers', 'newdm',
        'newreminder', 'newreport', 'newquestion', 'newshare', 'newwanted',
        'editblogpost'
    )


def get_fav_filename_from_url(base_dir: str, favicon_url: str) -> str:
    """Returns the cached filename for a favicon based upon its url
    """
    if '://' in favicon_url:
        favicon_url = favicon_url.split('://')[1]
    if '/favicon.' in favicon_url:
        favicon_url = favicon_url.replace('/favicon.', '.')
    return base_dir + '/favicons/' + favicon_url.replace('/', '-')
