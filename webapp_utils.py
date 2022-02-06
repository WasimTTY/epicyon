__filename__ = "webapp_utils.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.3.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Web Interface"

import os
from shutil import copyfile
from collections import OrderedDict
from session import get_json
from utils import is_account_dir
from utils import remove_html
from utils import get_protocol_prefixes
from utils import load_json
from utils import get_cached_post_filename
from utils import get_config_param
from utils import acct_dir
from utils import get_nickname_from_actor
from utils import is_float
from utils import get_audio_extensions
from utils import get_video_extensions
from utils import get_image_extensions
from utils import local_actor_url
from cache import store_person_in_cache
from content import add_html_tags
from content import replace_emoji_from_tags
from person import get_person_avatar_url
from posts import is_moderator
from blocking import is_blocked


def get_broken_link_substitute() -> str:
    """Returns html used to show a default image if the link to
    an image is broken
    """
    return " onerror=\"this.onerror=null; this.src='" + \
        "/icons/avatar_default.png'\""


def html_following_list(css_cache: {}, base_dir: str,
                        following_filename: str) -> str:
    """Returns a list of handles being followed
    """
    with open(following_filename, 'r') as following_file:
        msg = following_file.read()
        following_list = msg.split('\n')
        following_list.sort()
        if following_list:
            css_filename = base_dir + '/epicyon-profile.css'
            if os.path.isfile(base_dir + '/epicyon.css'):
                css_filename = base_dir + '/epicyon.css'

            instance_title = \
                get_config_param(base_dir, 'instanceTitle')
            following_list_html = \
                html_header_with_external_style(css_filename,
                                                instance_title, None)
            for following_address in following_list:
                if following_address:
                    following_list_html += \
                        '<h3>@' + following_address + '</h3>'
            following_list_html += html_footer()
            msg = following_list_html
        return msg
    return ''


def html_hashtag_blocked(css_cache: {}, base_dir: str, translate: {}) -> str:
    """Show the screen for a blocked hashtag
    """
    blocked_hashtag_form = ''
    css_filename = base_dir + '/epicyon-suspended.css'
    if os.path.isfile(base_dir + '/suspended.css'):
        css_filename = base_dir + '/suspended.css'

    instance_title = \
        get_config_param(base_dir, 'instanceTitle')
    blocked_hashtag_form = \
        html_header_with_external_style(css_filename, instance_title, None)
    blocked_hashtag_form += '<div><center>\n'
    blocked_hashtag_form += \
        '  <p class="screentitle">' + \
        translate['Hashtag Blocked'] + '</p>\n'
    blocked_hashtag_form += \
        '  <p>See <a href="/terms">' + \
        translate['Terms of Service'] + '</a></p>\n'
    blocked_hashtag_form += '</center></div>\n'
    blocked_hashtag_form += html_footer()
    return blocked_hashtag_form


def header_buttons_front_screen(translate: {},
                                nickname: str, box_name: str,
                                authorized: bool,
                                icons_as_buttons: bool) -> str:
    """Returns the header buttons for the front page of a news instance
    """
    header_str = ''
    if nickname == 'news':
        button_features = 'buttonMobile'
        button_newswire = 'buttonMobile'
        button_links = 'buttonMobile'
        if box_name == 'features':
            button_features = 'buttonselected'
        elif box_name == 'newswire':
            button_newswire = 'buttonselected'
        elif box_name == 'links':
            button_links = 'buttonselected'

        header_str += \
            '        <a href="/">' + \
            '<button class="' + button_features + '">' + \
            '<span>' + translate['Features'] + \
            '</span></button></a>'
        if not authorized:
            header_str += \
                '        <a href="/login">' + \
                '<button class="buttonMobile">' + \
                '<span>' + translate['Login'] + \
                '</span></button></a>'
        if icons_as_buttons:
            header_str += \
                '        <a href="/users/news/newswiremobile">' + \
                '<button class="' + button_newswire + '">' + \
                '<span>' + translate['Newswire'] + \
                '</span></button></a>'
            header_str += \
                '        <a href="/users/news/linksmobile">' + \
                '<button class="' + button_links + '">' + \
                '<span>' + translate['Links'] + \
                '</span></button></a>'
        else:
            header_str += \
                '        <a href="' + \
                '/users/news/newswiremobile">' + \
                '<img loading="lazy" src="/icons' + \
                '/newswire.png" title="' + translate['Newswire'] + \
                '" alt="| ' + translate['Newswire'] + '"/></a>\n'
            header_str += \
                '        <a href="' + \
                '/users/news/linksmobile">' + \
                '<img loading="lazy" src="/icons' + \
                '/links.png" title="' + translate['Links'] + \
                '" alt="| ' + translate['Links'] + '"/></a>\n'
    else:
        if not authorized:
            header_str += \
                '        <a href="/login">' + \
                '<button class="buttonMobile">' + \
                '<span>' + translate['Login'] + \
                '</span></button></a>'

    if header_str:
        header_str = \
            '\n      <div class="frontPageMobileButtons">\n' + \
            header_str + \
            '      </div>\n'
    return header_str


def get_content_warning_button(post_id: str, translate: {},
                               content: str) -> str:
    """Returns the markup for a content warning button
    """
    return '       <details><summary class="cw">' + \
        translate['SHOW MORE'] + '</summary>' + \
        '<div id="' + post_id + '">' + content + \
        '</div></details>\n'


def _set_actor_property_url(actor_json: {},
                            property_name: str, url: str) -> None:
    """Sets a url for the given actor property
    """
    if not actor_json.get('attachment'):
        actor_json['attachment'] = []

    property_name_lower = property_name.lower()

    # remove any existing value
    property_found = None
    for property_value in actor_json['attachment']:
        if not property_value.get('name'):
            continue
        if not property_value.get('type'):
            continue
        if not property_value['name'].lower().startswith(property_name_lower):
            continue
        property_found = property_value
        break
    if property_found:
        actor_json['attachment'].remove(property_found)

    prefixes = get_protocol_prefixes()
    prefix_found = False
    for prefix in prefixes:
        if url.startswith(prefix):
            prefix_found = True
            break
    if not prefix_found:
        return
    if '.' not in url:
        return
    if ' ' in url:
        return
    if ',' in url:
        return

    for property_value in actor_json['attachment']:
        if not property_value.get('name'):
            continue
        if not property_value.get('type'):
            continue
        if not property_value['name'].lower().startswith(property_name_lower):
            continue
        if property_value['type'] != 'PropertyValue':
            continue
        property_value['value'] = url
        return

    new_address = {
        "name": property_name,
        "type": "PropertyValue",
        "value": url
    }
    actor_json['attachment'].append(new_address)


def set_blog_address(actor_json: {}, blog_address: str) -> None:
    """Sets an blog address for the given actor
    """
    _set_actor_property_url(actor_json, 'Blog', remove_html(blog_address))


def update_avatar_image_cache(signing_priv_key_pem: str,
                              session, base_dir: str, http_prefix: str,
                              actor: str, avatar_url: str,
                              person_cache: {}, allow_downloads: bool,
                              force: bool = False, debug: bool = False) -> str:
    """Updates the cached avatar for the given actor
    """
    if not avatar_url:
        return None
    actor_str = actor.replace('/', '-')
    avatar_image_path = base_dir + '/cache/avatars/' + actor_str

    # try different image types
    image_formats = {
        'png': 'png',
        'jpg': 'jpeg',
        'jxl': 'jxl',
        'jpeg': 'jpeg',
        'gif': 'gif',
        'svg': 'svg+xml',
        'webp': 'webp',
        'avif': 'avif'
    }
    avatar_image_filename = None
    for im_format, mime_type in image_formats.items():
        if avatar_url.endswith('.' + im_format) or \
           '.' + im_format + '?' in avatar_url:
            session_headers = {
                'Accept': 'image/' + mime_type
            }
            avatar_image_filename = avatar_image_path + '.' + im_format

    if not avatar_image_filename:
        return None

    if (not os.path.isfile(avatar_image_filename) or force) and \
       allow_downloads:
        try:
            if debug:
                print('avatar image url: ' + avatar_url)
            result = session.get(avatar_url,
                                 headers=session_headers,
                                 params=None)
            if result.status_code < 200 or \
               result.status_code > 202:
                if debug:
                    print('Avatar image download failed with status ' +
                          str(result.status_code))
                # remove partial download
                if os.path.isfile(avatar_image_filename):
                    try:
                        os.remove(avatar_image_filename)
                    except OSError:
                        print('EX: ' +
                              'update_avatar_image_cache unable to delete ' +
                              avatar_image_filename)
            else:
                with open(avatar_image_filename, 'wb') as fp_av:
                    fp_av.write(result.content)
                    if debug:
                        print('avatar image downloaded for ' + actor)
                    return avatar_image_filename.replace(base_dir + '/cache',
                                                         '')
        except Exception as ex:
            print('EX: Failed to download avatar image: ' +
                  str(avatar_url) + ' ' + str(ex))
        prof = 'https://www.w3.org/ns/activitystreams'
        if '/channel/' not in actor or '/accounts/' not in actor:
            session_headers = {
                'Accept': 'application/activity+json; profile="' + prof + '"'
            }
        else:
            session_headers = {
                'Accept': 'application/ld+json; profile="' + prof + '"'
            }
        person_json = \
            get_json(signing_priv_key_pem, session, actor,
                     session_headers, None,
                     debug, __version__, http_prefix, None)
        if person_json:
            if not person_json.get('id'):
                return None
            if not person_json.get('publicKey'):
                return None
            if not person_json['publicKey'].get('publicKeyPem'):
                return None
            if person_json['id'] != actor:
                return None
            if not person_cache.get(actor):
                return None
            if person_cache[actor]['actor']['publicKey']['publicKeyPem'] != \
               person_json['publicKey']['publicKeyPem']:
                print("ERROR: " +
                      "public keys don't match when downloading actor for " +
                      actor)
                return None
            store_person_in_cache(base_dir, actor, person_json, person_cache,
                                  allow_downloads)
            return get_person_avatar_url(base_dir, actor, person_cache,
                                         allow_downloads)
        return None
    return avatar_image_filename.replace(base_dir + '/cache', '')


def scheduled_posts_exist(base_dir: str, nickname: str, domain: str) -> bool:
    """Returns true if there are posts scheduled to be delivered
    """
    schedule_index_filename = \
        acct_dir(base_dir, nickname, domain) + '/schedule.index'
    if not os.path.isfile(schedule_index_filename):
        return False
    if '#users#' in open(schedule_index_filename).read():
        return True
    return False


def shares_timeline_json(actor: str, pageNumber: int, items_per_page: int,
                         base_dir: str, domain: str, nickname: str,
                         max_shares_per_account: int,
                         shared_items_federated_domains: [],
                         shares_file_type: str) -> ({}, bool):
    """Get a page on the shared items timeline as json
    max_shares_per_account helps to avoid one person dominating the timeline
    by sharing a large number of things
    """
    all_shares_json = {}
    for _, dirs, files in os.walk(base_dir + '/accounts'):
        for handle in dirs:
            if not is_account_dir(handle):
                continue
            account_dir = base_dir + '/accounts/' + handle
            shares_filename = account_dir + '/' + shares_file_type + '.json'
            if not os.path.isfile(shares_filename):
                continue
            shares_json = load_json(shares_filename)
            if not shares_json:
                continue
            account_nickname = handle.split('@')[0]
            # Don't include shared items from blocked accounts
            if account_nickname != nickname:
                if is_blocked(base_dir, nickname, domain,
                              account_nickname, domain, None):
                    continue
            # actor who owns this share
            owner = actor.split('/users/')[0] + '/users/' + account_nickname
            ctr = 0
            for item_id, item in shares_json.items():
                # assign owner to the item
                item['actor'] = owner
                item['shareId'] = item_id
                all_shares_json[str(item['published'])] = item
                ctr += 1
                if ctr >= max_shares_per_account:
                    break
        break
    if shared_items_federated_domains:
        if shares_file_type == 'shares':
            catalogs_dir = base_dir + '/cache/catalogs'
        else:
            catalogs_dir = base_dir + '/cache/wantedItems'
        if os.path.isdir(catalogs_dir):
            for _, dirs, files in os.walk(catalogs_dir):
                for fname in files:
                    if '#' in fname:
                        continue
                    if not fname.endswith('.' + shares_file_type + '.json'):
                        continue
                    federated_domain = fname.split('.')[0]
                    if federated_domain not in shared_items_federated_domains:
                        continue
                    shares_filename = catalogs_dir + '/' + fname
                    shares_json = load_json(shares_filename)
                    if not shares_json:
                        continue
                    ctr = 0
                    for item_id, item in shares_json.items():
                        # assign owner to the item
                        if '--shareditems--' not in item_id:
                            continue
                        share_actor = item_id.split('--shareditems--')[0]
                        share_actor = share_actor.replace('___', '://')
                        share_actor = share_actor.replace('--', '/')
                        share_nickname = get_nickname_from_actor(share_actor)
                        if is_blocked(base_dir, nickname, domain,
                                      share_nickname, federated_domain, None):
                            continue
                        item['actor'] = share_actor
                        item['shareId'] = item_id
                        all_shares_json[str(item['published'])] = item
                        ctr += 1
                        if ctr >= max_shares_per_account:
                            break
                break
    # sort the shared items in descending order of publication date
    shares_json = OrderedDict(sorted(all_shares_json.items(), reverse=True))
    last_page = False
    start_index = items_per_page * pageNumber
    max_index = len(shares_json.items())
    if max_index < items_per_page:
        last_page = True
    if start_index >= max_index - items_per_page:
        last_page = True
        start_index = max_index - items_per_page
        if start_index < 0:
            start_index = 0
    ctr = 0
    result_json = {}
    for published, item in shares_json.items():
        if ctr >= start_index + items_per_page:
            break
        if ctr < start_index:
            ctr += 1
            continue
        result_json[published] = item
        ctr += 1
    return result_json, last_page


def post_contains_public(post_json_object: {}) -> bool:
    """Does the given post contain #Public
    """
    contains_public = False
    if not post_json_object['object'].get('to'):
        return contains_public

    for to_address in post_json_object['object']['to']:
        if to_address.endswith('#Public'):
            contains_public = True
            break
        if not contains_public:
            if post_json_object['object'].get('cc'):
                for to_address2 in post_json_object['object']['cc']:
                    if to_address2.endswith('#Public'):
                        contains_public = True
                        break
    return contains_public


def _get_image_file(base_dir: str, name: str, directory: str,
                    nickname: str, domain: str, theme: str) -> (str, str):
    """
    returns the filenames for an image with the given name
    """
    banner_extensions = get_image_extensions()
    banner_file = ''
    banner_filename = ''
    for ext in banner_extensions:
        banner_file_test = name + '.' + ext
        banner_filename_test = directory + '/' + banner_file_test
        if os.path.isfile(banner_filename_test):
            banner_file = name + '_' + theme + '.' + ext
            banner_filename = banner_filename_test
            return banner_file, banner_filename
    # if not found then use the default image
    theme = 'default'
    directory = base_dir + '/theme/' + theme
    for ext in banner_extensions:
        banner_file_test = name + '.' + ext
        banner_filename_test = directory + '/' + banner_file_test
        if os.path.isfile(banner_filename_test):
            banner_file = name + '_' + theme + '.' + ext
            banner_filename = banner_filename_test
            break
    return banner_file, banner_filename


def get_banner_file(base_dir: str,
                    nickname: str, domain: str, theme: str) -> (str, str):
    """Gets the image for the timeline banner
    """
    account_dir = acct_dir(base_dir, nickname, domain)
    return _get_image_file(base_dir, 'banner', account_dir,
                           nickname, domain, theme)


def get_search_banner_file(base_dir: str,
                           nickname: str, domain: str,
                           theme: str) -> (str, str):
    """Gets the image for the search banner
    """
    account_dir = acct_dir(base_dir, nickname, domain)
    return _get_image_file(base_dir, 'search_banner', account_dir,
                           nickname, domain, theme)


def get_left_image_file(base_dir: str,
                        nickname: str, domain: str, theme: str) -> (str, str):
    """Gets the image for the left column
    """
    account_dir = acct_dir(base_dir, nickname, domain)
    return _get_image_file(base_dir, 'left_col_image', account_dir,
                           nickname, domain, theme)


def get_right_image_file(base_dir: str,
                         nickname: str, domain: str, theme: str) -> (str, str):
    """Gets the image for the right column
    """
    account_dir = acct_dir(base_dir, nickname, domain)
    return _get_image_file(base_dir, 'right_col_image',
                           account_dir, nickname, domain, theme)


def html_header_with_external_style(css_filename: str, instance_title: str,
                                    metadata: str, lang='en') -> str:
    if metadata is None:
        metadata = ''
    css_file = '/' + css_filename.split('/')[-1]
    html_str = \
        '<!DOCTYPE html>\n' + \
        '<html lang="' + lang + '">\n' + \
        '  <head>\n' + \
        '    <meta charset="utf-8">\n' + \
        '    <link rel="stylesheet" media="all" ' + \
        'href="' + css_file + '">\n' + \
        '    <link rel="manifest" href="/manifest.json">\n' + \
        '    <link href="/favicon.ico" rel="icon" type="image/x-icon">\n' + \
        '    <meta content="/browserconfig.xml" ' + \
        'name="msapplication-config">\n' + \
        '    <meta content="yes" name="apple-mobile-web-app-capable">\n' + \
        '    <link href="/apple-touch-icon.png" rel="apple-touch-icon" ' + \
        'sizes="180x180">\n' + \
        '    <meta name="theme-color" content="grey">\n' + \
        metadata + \
        '    <title>' + instance_title + '</title>\n' + \
        '  </head>\n' + \
        '  <body>\n'
    return html_str


def html_header_with_person_markup(css_filename: str, instance_title: str,
                                   actor_json: {}, city: str,
                                   content_license_url: str,
                                   lang='en') -> str:
    """html header which includes person markup
    https://schema.org/Person
    """
    if not actor_json:
        html_str = \
            html_header_with_external_style(css_filename,
                                            instance_title, None, lang)
        return html_str

    city_markup = ''
    if city:
        city = city.lower().title()
        add_comma = ''
        country_markup = ''
        if ',' in city:
            country = city.split(',', 1)[1].strip().title()
            city = city.split(',', 1)[0]
            country_markup = \
                '          "addressCountry": "' + country + '"\n'
            add_comma = ','
        city_markup = \
            '        "address": {\n' + \
            '          "@type": "PostalAddress",\n' + \
            '          "addressLocality": "' + city + '"' + \
            add_comma + '\n' + country_markup + '        },\n'

    skills_markup = ''
    if actor_json.get('hasOccupation'):
        if isinstance(actor_json['hasOccupation'], list):
            skills_markup = '        "hasOccupation": [\n'
            first_entry = True
            for skill_dict in actor_json['hasOccupation']:
                if skill_dict['@type'] == 'Role':
                    if not first_entry:
                        skills_markup += ',\n'
                    skl = skill_dict['hasOccupation']
                    role_name = skl['name']
                    if not role_name:
                        role_name = 'member'
                    category = \
                        skl['occupationalCategory']['codeValue']
                    category_url = \
                        'https://www.onetonline.org/link/summary/' + category
                    skills_markup += \
                        '        {\n' + \
                        '          "@type": "Role",\n' + \
                        '          "hasOccupation": {\n' + \
                        '            "@type": "Occupation",\n' + \
                        '            "name": "' + role_name + '",\n' + \
                        '            "description": ' + \
                        '"Fediverse instance role",\n' + \
                        '            "occupationLocation": {\n' + \
                        '              "@type": "City",\n' + \
                        '              "name": "' + city + '"\n' + \
                        '            },\n' + \
                        '            "occupationalCategory": {\n' + \
                        '              "@type": "CategoryCode",\n' + \
                        '              "inCodeSet": {\n' + \
                        '                "@type": "CategoryCodeSet",\n' + \
                        '                "name": "O*Net-SOC",\n' + \
                        '                "dateModified": "2019",\n' + \
                        '                ' + \
                        '"url": "https://www.onetonline.org/"\n' + \
                        '              },\n' + \
                        '              "codeValue": "' + category + '",\n' + \
                        '              "url": "' + category_url + '"\n' + \
                        '            }\n' + \
                        '          }\n' + \
                        '        }'
                elif skill_dict['@type'] == 'Occupation':
                    if not first_entry:
                        skills_markup += ',\n'
                    oc_name = skill_dict['name']
                    if not oc_name:
                        oc_name = 'member'
                    skills_list = skill_dict['skills']
                    skills_list_str = '['
                    for skill_str in skills_list:
                        if skills_list_str != '[':
                            skills_list_str += ', '
                        skills_list_str += '"' + skill_str + '"'
                    skills_list_str += ']'
                    skills_markup += \
                        '        {\n' + \
                        '          "@type": "Occupation",\n' + \
                        '          "name": "' + oc_name + '",\n' + \
                        '          "description": ' + \
                        '"Fediverse instance occupation",\n' + \
                        '          "occupationLocation": {\n' + \
                        '            "@type": "City",\n' + \
                        '            "name": "' + city + '"\n' + \
                        '          },\n' + \
                        '          "skills": ' + skills_list_str + '\n' + \
                        '        }'
                first_entry = False
            skills_markup += '\n        ],\n'

    description = remove_html(actor_json['summary'])
    name_str = remove_html(actor_json['name'])
    domain_full = actor_json['id'].split('://')[1].split('/')[0]
    handle = actor_json['preferredUsername'] + '@' + domain_full

    person_markup = \
        '      "about": {\n' + \
        '        "@type" : "Person",\n' + \
        '        "name": "' + name_str + '",\n' + \
        '        "image": "' + actor_json['icon']['url'] + '",\n' + \
        '        "description": "' + description + '",\n' + \
        city_markup + skills_markup + \
        '        "url": "' + actor_json['id'] + '"\n' + \
        '      },\n'

    profile_markup = \
        '    <script id="initial-state" type="application/ld+json">\n' + \
        '    {\n' + \
        '      "@context":"https://schema.org",\n' + \
        '      "@type": "ProfilePage",\n' + \
        '      "mainEntityOfPage": {\n' + \
        '        "@type": "WebPage",\n' + \
        "        \"@id\": \"" + actor_json['id'] + "\"\n" + \
        '      },\n' + person_markup + \
        '      "accountablePerson": {\n' + \
        '        "@type": "Person",\n' + \
        '        "name": "' + name_str + '"\n' + \
        '      },\n' + \
        '      "copyrightHolder": {\n' + \
        '        "@type": "Person",\n' + \
        '        "name": "' + name_str + '"\n' + \
        '      },\n' + \
        '      "name": "' + name_str + '",\n' + \
        '      "image": "' + actor_json['icon']['url'] + '",\n' + \
        '      "description": "' + description + '",\n' + \
        '      "license": "' + content_license_url + '"\n' + \
        '    }\n' + \
        '    </script>\n'

    description = remove_html(description)
    og_metadata = \
        "    <meta content=\"profile\" property=\"og:type\" />\n" + \
        "    <meta content=\"" + description + \
        "\" name='description'>\n" + \
        "    <meta content=\"" + actor_json['url'] + \
        "\" property=\"og:url\" />\n" + \
        "    <meta content=\"" + domain_full + \
        "\" property=\"og:site_name\" />\n" + \
        "    <meta content=\"" + name_str + " (@" + handle + \
        ")\" property=\"og:title\" />\n" + \
        "    <meta content=\"" + description + \
        "\" property=\"og:description\" />\n" + \
        "    <meta content=\"" + actor_json['icon']['url'] + \
        "\" property=\"og:image\" />\n" + \
        "    <meta content=\"400\" property=\"og:image:width\" />\n" + \
        "    <meta content=\"400\" property=\"og:image:height\" />\n" + \
        "    <meta content=\"summary\" property=\"twitter:card\" />\n" + \
        "    <meta content=\"" + handle + \
        "\" property=\"profile:username\" />\n"
    if actor_json.get('attachment'):
        og_tags = (
            'email', 'openpgp', 'blog', 'xmpp', 'matrix', 'briar',
            'jami', 'cwtch', 'languages'
        )
        for attach_json in actor_json['attachment']:
            if not attach_json.get('name'):
                continue
            if not attach_json.get('value'):
                continue
            name = attach_json['name'].lower()
            value = attach_json['value']
            for og_tag in og_tags:
                if name != og_tag:
                    continue
                og_metadata += \
                    "    <meta content=\"" + value + \
                    "\" property=\"og:" + og_tag + "\" />\n"

    html_str = \
        html_header_with_external_style(css_filename, instance_title,
                                        og_metadata + profile_markup, lang)
    return html_str


def html_header_with_website_markup(css_filename: str, instance_title: str,
                                    http_prefix: str, domain: str,
                                    system_language: str) -> str:
    """html header which includes website markup
    https://schema.org/WebSite
    """
    license_url = 'https://www.gnu.org/licenses/agpl-3.0.rdf'

    # social networking category
    genre_url = 'http://vocab.getty.edu/aat/300312270'

    website_markup = \
        '    <script id="initial-state" type="application/ld+json">\n' + \
        '    {\n' + \
        '      "@context" : "http://schema.org",\n' + \
        '      "@type" : "WebSite",\n' + \
        '      "name": "' + instance_title + '",\n' + \
        '      "url": "' + http_prefix + '://' + domain + '",\n' + \
        '      "license": "' + license_url + '",\n' + \
        '      "inLanguage": "' + system_language + '",\n' + \
        '      "isAccessibleForFree": true,\n' + \
        '      "genre": "' + genre_url + '",\n' + \
        '      "accessMode": ["textual", "visual"],\n' + \
        '      "accessModeSufficient": ["textual"],\n' + \
        '      "accessibilityAPI" : ["ARIA"],\n' + \
        '      "accessibilityControl" : [\n' + \
        '        "fullKeyboardControl",\n' + \
        '        "fullTouchControl",\n' + \
        '        "fullMouseControl"\n' + \
        '      ],\n' + \
        '      "encodingFormat" : [\n' + \
        '        "text/html", "image/png", "image/webp",\n' + \
        '        "image/jpeg", "image/gif", "text/css"\n' + \
        '      ]\n' + \
        '    }\n' + \
        '    </script>\n'

    og_metadata = \
        '    <meta content="Epicyon hosted on ' + domain + \
        '" property="og:site_name" />\n' + \
        '    <meta content="' + http_prefix + '://' + domain + \
        '/about" property="og:url" />\n' + \
        '    <meta content="website" property="og:type" />\n' + \
        '    <meta content="' + instance_title + \
        '" property="og:title" />\n' + \
        '    <meta content="' + http_prefix + '://' + domain + \
        '/logo.png" property="og:image" />\n' + \
        '    <meta content="' + system_language + \
        '" property="og:locale" />\n' + \
        '    <meta content="summary_large_image" property="twitter:card" />\n'

    html_str = \
        html_header_with_external_style(css_filename, instance_title,
                                        og_metadata + website_markup,
                                        system_language)
    return html_str


def html_header_with_blog_markup(css_filename: str, instance_title: str,
                                 http_prefix: str, domain: str, nickname: str,
                                 system_language: str,
                                 published: str, modified: str,
                                 title: str, snippet: str,
                                 translate: {}, url: str,
                                 content_license_url: str) -> str:
    """html header which includes blog post markup
    https://schema.org/BlogPosting
    """
    author_url = local_actor_url(http_prefix, nickname, domain)
    about_url = http_prefix + '://' + domain + '/about.html'

    # license for content on the site may be different from
    # the software license

    blog_markup = \
        '    <script id="initial-state" type="application/ld+json">\n' + \
        '    {\n' + \
        '      "@context" : "http://schema.org",\n' + \
        '      "@type" : "BlogPosting",\n' + \
        '      "headline": "' + title + '",\n' + \
        '      "datePublished": "' + published + '",\n' + \
        '      "dateModified": "' + modified + '",\n' + \
        '      "author": {\n' + \
        '        "@type": "Person",\n' + \
        '        "name": "' + nickname + '",\n' + \
        '        "sameAs": "' + author_url + '"\n' + \
        '      },\n' + \
        '      "publisher": {\n' + \
        '        "@type": "WebSite",\n' + \
        '        "name": "' + instance_title + '",\n' + \
        '        "sameAs": "' + about_url + '"\n' + \
        '      },\n' + \
        '      "license": "' + content_license_url + '",\n' + \
        '      "description": "' + snippet + '"\n' + \
        '    }\n' + \
        '    </script>\n'

    og_metadata = \
        '    <meta property="og:locale" content="' + \
        system_language + '" />\n' + \
        '    <meta property="og:type" content="article" />\n' + \
        '    <meta property="og:title" content="' + title + '" />\n' + \
        '    <meta property="og:url" content="' + url + '" />\n' + \
        '    <meta content="Epicyon hosted on ' + domain + \
        '" property="og:site_name" />\n' + \
        '    <meta property="article:published_time" content="' + \
        published + '" />\n' + \
        '    <meta property="article:modified_time" content="' + \
        modified + '" />\n'

    html_str = \
        html_header_with_external_style(css_filename, instance_title,
                                        og_metadata + blog_markup,
                                        system_language)
    return html_str


def html_footer() -> str:
    html_str = '  </body>\n'
    html_str += '</html>\n'
    return html_str


def load_individual_post_as_html_from_cache(base_dir: str,
                                            nickname: str, domain: str,
                                            post_json_object: {}) -> str:
    """If a cached html version of the given post exists then load it and
    return the html text
    This is much quicker than generating the html from the json object
    """
    cached_post_filename = \
        get_cached_post_filename(base_dir, nickname, domain, post_json_object)

    post_html = ''
    if not cached_post_filename:
        return post_html

    if not os.path.isfile(cached_post_filename):
        return post_html

    tries = 0
    while tries < 3:
        try:
            with open(cached_post_filename, 'r') as file:
                post_html = file.read()
                break
        except Exception as ex:
            print('ERROR: load_individual_post_as_html_from_cache ' +
                  str(tries) + ' ' + str(ex))
            # no sleep
            tries += 1
    if post_html:
        return post_html


def add_emoji_to_display_name(session, base_dir: str, http_prefix: str,
                              nickname: str, domain: str,
                              display_name: str, in_profile_name: bool) -> str:
    """Adds emoji icons to display names or CW on individual posts
    """
    if ':' not in display_name:
        return display_name

    display_name = display_name.replace('<p>', '').replace('</p>', '')
    emoji_tags = {}
#    print('TAG: display_name before tags: ' + display_name)
    display_name = \
        add_html_tags(base_dir, http_prefix,
                      nickname, domain, display_name, [], emoji_tags)
    display_name = display_name.replace('<p>', '').replace('</p>', '')
#    print('TAG: display_name after tags: ' + display_name)
    # convert the emoji dictionary to a list
    emoji_tags_list = []
    for _, tag in emoji_tags.items():
        emoji_tags_list.append(tag)
#    print('TAG: emoji tags list: ' + str(emoji_tags_list))
    if not in_profile_name:
        display_name = \
            replace_emoji_from_tags(session, base_dir,
                                    display_name, emoji_tags_list,
                                    'post header', False)
    else:
        display_name = \
            replace_emoji_from_tags(session, base_dir,
                                    display_name, emoji_tags_list, 'profile',
                                    False)
#    print('TAG: display_name after tags 2: ' + display_name)

    # remove any stray emoji
    while ':' in display_name:
        if '://' in display_name:
            break
        emoji_str = display_name.split(':')[1]
        prev_display_name = display_name
        display_name = display_name.replace(':' + emoji_str + ':', '').strip()
        if prev_display_name == display_name:
            break
#        print('TAG: display_name after tags 3: ' + display_name)
#    print('TAG: display_name after tag replacements: ' + display_name)

    return display_name


def _is_image_mime_type(mime_type: str) -> bool:
    """Is the given mime type an image?
    """
    if mime_type == 'image/svg+xml':
        return True
    if not mime_type.startswith('image/'):
        return False
    extensions = get_image_extensions()
    ext = mime_type.split('/')[1]
    if ext in extensions:
        return True
    return False


def _is_video_mime_type(mime_type: str) -> bool:
    """Is the given mime type a video?
    """
    if not mime_type.startswith('video/'):
        return False
    extensions = get_video_extensions()
    ext = mime_type.split('/')[1]
    if ext in extensions:
        return True
    return False


def _is_audio_mime_type(mime_type: str) -> bool:
    """Is the given mime type an audio file?
    """
    if mime_type == 'audio/mpeg':
        return True
    if not mime_type.startswith('audio/'):
        return False
    extensions = get_audio_extensions()
    ext = mime_type.split('/')[1]
    if ext in extensions:
        return True
    return False


def _is_attached_image(attachment_filename: str) -> bool:
    """Is the given attachment filename an image?
    """
    if '.' not in attachment_filename:
        return False
    image_ext = (
        'png', 'jpg', 'jpeg', 'webp', 'avif', 'svg', 'gif', 'jxl'
    )
    ext = attachment_filename.split('.')[-1]
    if ext in image_ext:
        return True
    return False


def _is_attached_video(attachment_filename: str) -> bool:
    """Is the given attachment filename a video?
    """
    if '.' not in attachment_filename:
        return False
    video_ext = (
        'mp4', 'webm', 'ogv'
    )
    ext = attachment_filename.split('.')[-1]
    if ext in video_ext:
        return True
    return False


def get_post_attachments_as_html(post_json_object: {}, box_name: str,
                                 translate: {},
                                 is_muted: bool, avatar_link: str,
                                 reply_str: str, announce_str: str,
                                 like_str: str,
                                 bookmark_str: str, delete_str: str,
                                 mute_str: str) -> (str, str):
    """Returns a string representing any attachments
    """
    attachment_str = ''
    gallery_str = ''
    if not post_json_object['object'].get('attachment'):
        return attachment_str, gallery_str

    if not isinstance(post_json_object['object']['attachment'], list):
        return attachment_str, gallery_str

    attachment_ctr = 0
    attachment_str = ''
    media_style_added = False
    for attach in post_json_object['object']['attachment']:
        if not (attach.get('mediaType') and attach.get('url')):
            continue

        media_type = attach['mediaType']
        image_description = ''
        if attach.get('name'):
            image_description = attach['name'].replace('"', "'")
        if _is_image_mime_type(media_type):
            image_url = attach['url']
            if _is_attached_image(attach['url']) and 'svg' not in media_type:
                if not attachment_str:
                    attachment_str += '<div class="media">\n'
                    media_style_added = True

                if attachment_ctr > 0:
                    attachment_str += '<br>'
                if box_name == 'tlmedia':
                    gallery_str += '<div class="gallery">\n'
                    if not is_muted:
                        gallery_str += '  <a href="' + image_url + '">\n'
                        gallery_str += \
                            '    <img loading="lazy" src="' + \
                            image_url + '" alt="" title="">\n'
                        gallery_str += '  </a>\n'
                    if post_json_object['object'].get('url'):
                        image_post_url = post_json_object['object']['url']
                    else:
                        image_post_url = post_json_object['object']['id']
                    if image_description and not is_muted:
                        gallery_str += \
                            '  <a href="' + image_post_url + \
                            '" class="gallerytext"><div ' + \
                            'class="gallerytext">' + \
                            image_description + '</div></a>\n'
                    else:
                        gallery_str += \
                            '<label class="transparent">---</label><br>'
                    gallery_str += '  <div class="mediaicons">\n'
                    gallery_str += \
                        '    ' + reply_str + announce_str + like_str + \
                        bookmark_str + delete_str + mute_str + '\n'
                    gallery_str += '  </div>\n'
                    gallery_str += '  <div class="mediaavatar">\n'
                    gallery_str += '    ' + avatar_link + '\n'
                    gallery_str += '  </div>\n'
                    gallery_str += '</div>\n'

                attachment_str += '<a href="' + image_url + '">'
                attachment_str += \
                    '<img loading="lazy" src="' + image_url + \
                    '" alt="' + image_description + '" title="' + \
                    image_description + '" class="attachment"></a>\n'
                attachment_ctr += 1
        elif _is_video_mime_type(media_type):
            if _is_attached_video(attach['url']):
                extension = attach['url'].split('.')[-1]
                if attachment_ctr > 0:
                    attachment_str += '<br>'
                if box_name == 'tlmedia':
                    gallery_str += '<div class="gallery">\n'
                    if not is_muted:
                        gallery_str += '  <a href="' + attach['url'] + '">\n'
                        gallery_str += \
                            '    <figure id="videoContainer" ' + \
                            'data-fullscreen="false">\n' + \
                            '    <video id="video" controls ' + \
                            'preload="metadata">\n'
                        gallery_str += \
                            '      <source src="' + attach['url'] + \
                            '" alt="' + image_description + \
                            '" title="' + image_description + \
                            '" class="attachment" type="video/' + \
                            extension + '">'
                        idx = 'Your browser does not support the video tag.'
                        gallery_str += translate[idx]
                        gallery_str += '    </video>\n'
                        gallery_str += '    </figure>\n'
                        gallery_str += '  </a>\n'
                    if post_json_object['object'].get('url'):
                        video_post_url = post_json_object['object']['url']
                    else:
                        video_post_url = post_json_object['object']['id']
                    if image_description and not is_muted:
                        gallery_str += \
                            '  <a href="' + video_post_url + \
                            '" class="gallerytext"><div ' + \
                            'class="gallerytext">' + \
                            image_description + '</div></a>\n'
                    else:
                        gallery_str += \
                            '<label class="transparent">---</label><br>'
                    gallery_str += '  <div class="mediaicons">\n'
                    gallery_str += \
                        '    ' + reply_str + announce_str + like_str + \
                        bookmark_str + delete_str + mute_str + '\n'
                    gallery_str += '  </div>\n'
                    gallery_str += '  <div class="mediaavatar">\n'
                    gallery_str += '    ' + avatar_link + '\n'
                    gallery_str += '  </div>\n'
                    gallery_str += '</div>\n'

                attachment_str += \
                    '<center><figure id="videoContainer" ' + \
                    'data-fullscreen="false">\n' + \
                    '    <video id="video" controls ' + \
                    'preload="metadata">\n'
                attachment_str += \
                    '<source src="' + attach['url'] + '" alt="' + \
                    image_description + '" title="' + image_description + \
                    '" class="attachment" type="video/' + \
                    extension + '">'
                attachment_str += \
                    translate['Your browser does not support the video tag.']
                attachment_str += '</video></figure></center>'
                attachment_ctr += 1
        elif _is_audio_mime_type(media_type):
            extension = '.mp3'
            if attach['url'].endswith('.ogg'):
                extension = '.ogg'
            if attach['url'].endswith(extension):
                if attachment_ctr > 0:
                    attachment_str += '<br>'
                if box_name == 'tlmedia':
                    gallery_str += '<div class="gallery">\n'
                    if not is_muted:
                        gallery_str += '  <a href="' + attach['url'] + '">\n'
                        gallery_str += '    <audio controls>\n'
                        gallery_str += \
                            '      <source src="' + attach['url'] + \
                            '" alt="' + image_description + \
                            '" title="' + image_description + \
                            '" class="attachment" type="audio/' + \
                            extension.replace('.', '') + '">'
                        idx = 'Your browser does not support the audio tag.'
                        gallery_str += translate[idx]
                        gallery_str += '    </audio>\n'
                        gallery_str += '  </a>\n'
                    if post_json_object['object'].get('url'):
                        audio_post_url = post_json_object['object']['url']
                    else:
                        audio_post_url = post_json_object['object']['id']
                    if image_description and not is_muted:
                        gallery_str += \
                            '  <a href="' + audio_post_url + \
                            '" class="gallerytext"><div ' + \
                            'class="gallerytext">' + \
                            image_description + '</div></a>\n'
                    else:
                        gallery_str += \
                            '<label class="transparent">---</label><br>'
                    gallery_str += '  <div class="mediaicons">\n'
                    gallery_str += \
                        '    ' + reply_str + announce_str + \
                        like_str + bookmark_str + \
                        delete_str + mute_str + '\n'
                    gallery_str += '  </div>\n'
                    gallery_str += '  <div class="mediaavatar">\n'
                    gallery_str += '    ' + avatar_link + '\n'
                    gallery_str += '  </div>\n'
                    gallery_str += '</div>\n'

                attachment_str += '<center>\n<audio controls>\n'
                attachment_str += \
                    '<source src="' + attach['url'] + '" alt="' + \
                    image_description + '" title="' + image_description + \
                    '" class="attachment" type="audio/' + \
                    extension.replace('.', '') + '">'
                attachment_str += \
                    translate['Your browser does not support the audio tag.']
                attachment_str += '</audio>\n</center>\n'
                attachment_ctr += 1
    if media_style_added:
        attachment_str += '</div>'
    return attachment_str, gallery_str


def html_post_separator(base_dir: str, column: str) -> str:
    """Returns the html for a timeline post separator image
    """
    theme = get_config_param(base_dir, 'theme')
    filename = 'separator.png'
    separator_class = "postSeparatorImage"
    if column:
        separator_class = "postSeparatorImage" + column.title()
        filename = 'separator_' + column + '.png'
    separator_image_filename = \
        base_dir + '/theme/' + theme + '/icons/' + filename
    separator_str = ''
    if os.path.isfile(separator_image_filename):
        separator_str = \
            '<div class="' + separator_class + '"><center>' + \
            '<img src="/icons/' + filename + '" ' + \
            'alt="" /></center></div>\n'
    return separator_str


def html_highlight_label(label: str, highlight: bool) -> str:
    """If the given text should be highlighted then return
    the appropriate markup.
    This is so that in shell browsers, like lynx, it's possible
    to see if the replies or DM button are highlighted.
    """
    if not highlight:
        return label
    return '*' + str(label) + '*'


def get_avatar_image_url(session,
                         base_dir: str, http_prefix: str,
                         post_actor: str, person_cache: {},
                         avatar_url: str, allow_downloads: bool,
                         signing_priv_key_pem: str) -> str:
    """Returns the avatar image url
    """
    # get the avatar image url for the post actor
    if not avatar_url:
        avatar_url = \
            get_person_avatar_url(base_dir, post_actor, person_cache,
                                  allow_downloads)
        avatar_url = \
            update_avatar_image_cache(signing_priv_key_pem,
                                      session, base_dir, http_prefix,
                                      post_actor, avatar_url, person_cache,
                                      allow_downloads)
    else:
        update_avatar_image_cache(signing_priv_key_pem,
                                  session, base_dir, http_prefix,
                                  post_actor, avatar_url, person_cache,
                                  allow_downloads)

    if not avatar_url:
        avatar_url = post_actor + '/avatar.png'

    return avatar_url


def html_hide_from_screen_reader(html_str: str) -> str:
    """Returns html which is hidden from screen readers
    """
    return '<span aria-hidden="true">' + html_str + '</span>'


def html_keyboard_navigation(banner: str, links: {}, access_keys: {},
                             sub_heading: str = None,
                             users_path: str = None, translate: {} = None,
                             follow_approvals: bool = False) -> str:
    """Given a set of links return the html for keyboard navigation
    """
    html_str = '<div class="transparent"><ul>\n'

    if banner:
        html_str += '<pre aria-label="">\n' + banner + '\n<br><br></pre>\n'

    if sub_heading:
        html_str += '<strong><label class="transparent">' + \
            sub_heading + '</label></strong><br>\n'

    # show new follower approvals
    if users_path and translate and follow_approvals:
        html_str += '<strong><label class="transparent">' + \
            '<a href="' + users_path + '/followers#timeline">' + \
            translate['Approve follow requests'] + '</a>' + \
            '</label></strong><br><br>\n'

    # show the list of links
    for title, url in links.items():
        access_key_str = ''
        if access_keys.get(title):
            access_key_str = 'accesskey="' + access_keys[title] + '"'

        html_str += '<li><label class="transparent">' + \
            '<a href="' + str(url) + '" ' + access_key_str + '>' + \
            str(title) + '</a></label></li>\n'
    html_str += '</ul></div>\n'
    return html_str


def begin_edit_section(label: str) -> str:
    """returns the html for begining a dropdown section on edit profile screen
    """
    return \
        '    <details><summary class="cw">' + label + '</summary>\n' + \
        '<div class="container">'


def end_edit_section() -> str:
    """returns the html for ending a dropdown section on edit profile screen
    """
    return '    </div></details>\n'


def edit_text_field(label: str, name: str, value: str = "",
                    placeholder: str = "", required: bool = False) -> str:
    """Returns html for editing a text field
    """
    if value is None:
        value = ''
    placeholder_str = ''
    if placeholder:
        placeholder_str = ' placeholder="' + placeholder + '"'
    required_str = ''
    if required:
        required_str = ' required'
    text_field_str = ''
    if label:
        text_field_str = \
            '<label class="labels">' + label + '</label><br>\n'
    text_field_str += \
        '      <input type="text" name="' + name + '" value="' + \
        value + '"' + placeholder_str + required_str + '>\n'
    return text_field_str


def edit_number_field(label: str, name: str, value: int,
                      min_value: int, max_value: int,
                      placeholder: int) -> str:
    """Returns html for editing an integer number field
    """
    if value is None:
        value = ''
    placeholder_str = ''
    if placeholder:
        placeholder_str = ' placeholder="' + str(placeholder) + '"'
    return \
        '<label class="labels">' + label + '</label><br>\n' + \
        '      <input type="number" name="' + name + '" value="' + \
        str(value) + '"' + placeholder_str + ' ' + \
        'min="' + str(min_value) + '" max="' + str(max_value) + '" step="1">\n'


def edit_currency_field(label: str, name: str, value: str,
                        placeholder: str, required: bool) -> str:
    """Returns html for editing a currency field
    """
    if value is None:
        value = '0.00'
    placeholder_str = ''
    if placeholder:
        if placeholder.isdigit():
            placeholder_str = ' placeholder="' + str(placeholder) + '"'
    required_str = ''
    if required:
        required_str = ' required'
    return \
        '<label class="labels">' + label + '</label><br>\n' + \
        '      <input type="text" name="' + name + '" value="' + \
        str(value) + '"' + placeholder_str + ' ' + \
        ' pattern="^\\d{1,3}(,\\d{3})*(\\.\\d+)?" data-type="currency"' + \
        required_str + '>\n'


def edit_check_box(label: str, name: str, checked: bool) -> str:
    """Returns html for editing a checkbox field
    """
    checked_str = ''
    if checked:
        checked_str = ' checked'

    return \
        '      <input type="checkbox" class="profilecheckbox" ' + \
        'name="' + name + '"' + checked_str + '> ' + label + '<br>\n'


def edit_text_area(label: str, name: str, value: str,
                   height: int, placeholder: str, spellcheck: bool) -> str:
    """Returns html for editing a textarea field
    """
    if value is None:
        value = ''
    text = ''
    if label:
        text = '<label class="labels">' + label + '</label><br>\n'
    text += \
        '      <textarea id="message" placeholder=' + \
        '"' + placeholder + '" '
    text += 'name="' + name + '" '
    text += 'style="height:' + str(height) + 'px" '
    text += 'spellcheck="' + str(spellcheck).lower() + '">'
    text += value + '</textarea>\n'
    return text


def html_search_result_share(base_dir: str, shared_item: {}, translate: {},
                             http_prefix: str, domain_full: str,
                             contact_nickname: str, item_id: str,
                             actor: str, shares_file_type: str,
                             category: str) -> str:
    """Returns the html for an individual shared item
    """
    shared_items_form = '<div class="container">\n'
    shared_items_form += \
        '<p class="share-title">' + shared_item['displayName'] + '</p>\n'
    if shared_item.get('imageUrl'):
        shared_items_form += \
            '<a href="' + shared_item['imageUrl'] + '">\n'
        shared_items_form += \
            '<img loading="lazy" src="' + shared_item['imageUrl'] + \
            '" alt="Item image"></a>\n'
    shared_items_form += '<p>' + shared_item['summary'] + '</p>\n<p>'
    if shared_item.get('itemQty'):
        if shared_item['itemQty'] > 1:
            shared_items_form += \
                '<b>' + translate['Quantity'] + \
                ':</b> ' + str(shared_item['itemQty']) + '<br>'
    shared_items_form += \
        '<b>' + translate['Type'] + ':</b> ' + shared_item['itemType'] + '<br>'
    shared_items_form += \
        '<b>' + translate['Category'] + ':</b> ' + \
        shared_item['category'] + '<br>'
    if shared_item.get('location'):
        shared_items_form += \
            '<b>' + translate['Location'] + ':</b> ' + \
            shared_item['location'] + '<br>'
    contact_title_str = translate['Contact']
    if shared_item.get('itemPrice') and \
       shared_item.get('itemCurrency'):
        if is_float(shared_item['itemPrice']):
            if float(shared_item['itemPrice']) > 0:
                shared_items_form += \
                    ' <b>' + translate['Price'] + \
                    ':</b> ' + shared_item['itemPrice'] + \
                    ' ' + shared_item['itemCurrency']
                contact_title_str = translate['Buy']
    shared_items_form += '</p>\n'
    contact_actor = \
        local_actor_url(http_prefix, contact_nickname, domain_full)
    button_style_str = 'button'
    if category == 'accommodation':
        contact_title_str = translate['Request to stay']
        button_style_str = 'contactbutton'

    shared_items_form += \
        '<p>' + \
        '<a href="' + actor + '?replydm=sharedesc:' + \
        shared_item['displayName'] + '?mention=' + contact_actor + \
        '?category=' + category + \
        '"><button class="' + button_style_str + '">' + contact_title_str + \
        '</button></a>\n' + \
        '<a href="' + contact_actor + '"><button class="button">' + \
        translate['Profile'] + '</button></a>\n'

    # should the remove button be shown?
    show_remove_button = False
    nickname = get_nickname_from_actor(actor)
    if actor.endswith('/users/' + contact_nickname):
        show_remove_button = True
    elif is_moderator(base_dir, nickname):
        show_remove_button = True
    else:
        admin_nickname = get_config_param(base_dir, 'admin')
        if admin_nickname:
            if actor.endswith('/users/' + admin_nickname):
                show_remove_button = True

    if show_remove_button:
        if shares_file_type == 'shares':
            shared_items_form += \
                ' <a href="' + actor + '?rmshare=' + \
                item_id + '"><button class="button">' + \
                translate['Remove'] + '</button></a>\n'
        else:
            shared_items_form += \
                ' <a href="' + actor + '?rmwanted=' + \
                item_id + '"><button class="button">' + \
                translate['Remove'] + '</button></a>\n'
    shared_items_form += '</p></div>\n'
    return shared_items_form


def html_show_share(base_dir: str, domain: str, nickname: str,
                    http_prefix: str, domain_full: str,
                    item_id: str, translate: {},
                    shared_items_federated_domains: [],
                    default_timeline: str, theme: str,
                    shares_file_type: str, category: str) -> str:
    """Shows an individual shared item after selecting it from the left column
    """
    shares_json = None

    share_url = item_id.replace('___', '://').replace('--', '/')
    contact_nickname = get_nickname_from_actor(share_url)
    if not contact_nickname:
        return None

    if '://' + domain_full + '/' in share_url:
        # shared item on this instance
        shares_filename = \
            acct_dir(base_dir, contact_nickname, domain) + '/' + \
            shares_file_type + '.json'
        if not os.path.isfile(shares_filename):
            return None
        shares_json = load_json(shares_filename)
    else:
        # federated shared item
        if shares_file_type == 'shares':
            catalogs_dir = base_dir + '/cache/catalogs'
        else:
            catalogs_dir = base_dir + '/cache/wantedItems'
        if not os.path.isdir(catalogs_dir):
            return None
        for _, _, files in os.walk(catalogs_dir):
            for fname in files:
                if '#' in fname:
                    continue
                if not fname.endswith('.' + shares_file_type + '.json'):
                    continue
                federated_domain = fname.split('.')[0]
                if federated_domain not in shared_items_federated_domains:
                    continue
                shares_filename = catalogs_dir + '/' + fname
                shares_json = load_json(shares_filename)
                if not shares_json:
                    continue
                if shares_json.get(item_id):
                    break
            break

    if not shares_json:
        return None
    if not shares_json.get(item_id):
        return None
    shared_item = shares_json[item_id]
    actor = local_actor_url(http_prefix, nickname, domain_full)

    # filename of the banner shown at the top
    banner_file, _ = \
        get_banner_file(base_dir, nickname, domain, theme)

    share_str = \
        '<header>\n' + \
        '<a href="/users/' + nickname + '/' + \
        default_timeline + '" title="" alt="">\n'
    share_str += '<img loading="lazy" class="timeline-banner" ' + \
        'alt="" ' + \
        'src="/users/' + nickname + '/' + banner_file + '" /></a>\n' + \
        '</header><br>\n'
    share_str += \
        html_search_result_share(base_dir, shared_item, translate, http_prefix,
                                 domain_full, contact_nickname, item_id,
                                 actor, shares_file_type, category)

    css_filename = base_dir + '/epicyon-profile.css'
    if os.path.isfile(base_dir + '/epicyon.css'):
        css_filename = base_dir + '/epicyon.css'
    instance_title = \
        get_config_param(base_dir, 'instanceTitle')

    return html_header_with_external_style(css_filename,
                                           instance_title, None) + \
        share_str + html_footer()


def set_custom_background(base_dir: str, background: str,
                          new_background: str) -> str:
    """Sets a custom background
    Returns the extension, if found
    """
    ext = 'jpg'
    if os.path.isfile(base_dir + '/img/' + background + '.' + ext):
        if not new_background:
            new_background = background
        if not os.path.isfile(base_dir + '/accounts/' +
                              new_background + '.' + ext):
            copyfile(base_dir + '/img/' + background + '.' + ext,
                     base_dir + '/accounts/' + new_background + '.' + ext)
        return ext
    return None
