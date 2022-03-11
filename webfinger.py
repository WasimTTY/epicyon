__filename__ = "webfinger.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.3.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "ActivityPub"

import os
import urllib.parse
from session import get_json
from cache import store_webfinger_in_cache
from cache import get_webfinger_from_cache
from utils import get_full_domain
from utils import load_json
from utils import load_json_onionify
from utils import save_json
from utils import get_protocol_prefixes
from utils import remove_domain_port
from utils import get_user_paths
from utils import get_group_paths
from utils import local_actor_url


def _parse_handle(handle: str) -> (str, str, bool):
    """Parses a handle and returns nickname and domain
    """
    group_account = False
    if '.' not in handle:
        return None, None, False
    prefixes = get_protocol_prefixes()
    handle_str = handle
    for prefix in prefixes:
        handle_str = handle_str.replace(prefix, '')

    # try domain/@nick
    if '/@' in handle:
        domain, nickname = handle_str.split('/@')
        return nickname, domain, False

    # try nick@domain
    if '@' in handle:
        if handle.startswith('!'):
            handle = handle[1:]
            group_account = True
        nickname, domain = handle.split('@')
        return nickname, domain, group_account

    # try for different /users/ paths
    users_paths = get_user_paths()
    group_paths = get_group_paths()
    for possible_users_path in users_paths:
        if possible_users_path in handle:
            if possible_users_path in group_paths:
                group_account = True
            domain, nickname = handle_str.split(possible_users_path)
            return nickname, domain, group_account

    return None, None, False


def webfinger_handle(session, handle: str, http_prefix: str,
                     cached_webfingers: {},
                     from_domain: str, project_version: str,
                     debug: bool, group_account: bool,
                     signing_priv_key_pem: str) -> {}:
    """Gets webfinger result for the given ActivityPub handle
    """
    if not session:
        print('WARN: No session specified for webfinger_handle')
        return None

    nickname, domain, _ = _parse_handle(handle)
    if not nickname:
        print('WARN: No nickname found in handle ' + handle)
        return None
    wf_domain = remove_domain_port(domain)

    wf_handle = nickname + '@' + wf_domain
    if debug:
        print('Parsed webfinger handle: ' + handle + ' -> ' + wf_handle)
    wfg = get_webfinger_from_cache(wf_handle, cached_webfingers)
    if wfg:
        if debug:
            print('Webfinger from cache: ' + str(wfg))
        return wfg
    url = '{}://{}/.well-known/webfinger'.format(http_prefix, domain)
    hdr = {
        'Accept': 'application/jrd+json'
    }
    par = {
        'resource': 'acct:{}'.format(wf_handle)
    }
    try:
        result = \
            get_json(signing_priv_key_pem, session, url, hdr, par,
                     debug, project_version, http_prefix, from_domain)
    except Exception as ex:
        print('ERROR: webfinger_handle ' + wf_handle + ' ' + str(ex))
        return None

    # if the first attempt fails then try specifying the webfinger
    # resource in a different way
    if not result:
        resource = handle
        if handle == wf_handle:
            # reconstruct the actor
            resource = http_prefix + '://' + wf_domain + '/users/' + nickname
        # try again using the actor as the resource
        # See https://datatracker.ietf.org/doc/html/rfc7033 section 4.5
        par = {
            'resource': '{}'.format(resource)
        }
        try:
            result = \
                get_json(signing_priv_key_pem, session, url, hdr, par,
                         debug, project_version, http_prefix, from_domain)
        except Exception as ex:
            print('ERROR: webfinger_handle ' + wf_handle + ' ' + str(ex))
            return None

    if result:
        store_webfinger_in_cache(wf_handle, result, cached_webfingers)
    else:
        print("WARN: Unable to webfinger " + url + ' ' +
              'nickname: ' + str(nickname) + ' ' +
              'handle: ' + str(handle) + ' ' +
              'wf_handle: ' + str(wf_handle) + ' ' +
              'domain: ' + str(wf_domain) + ' ' +
              'headers: ' + str(hdr) + ' ' +
              'params: ' + str(par))

    return result


def store_webfinger_endpoint(nickname: str, domain: str, port: int,
                             base_dir: str, wf_json: {}) -> bool:
    """Stores webfinger endpoint for a user to a file
    """
    original_domain = domain
    domain = get_full_domain(domain, port)
    handle = nickname + '@' + domain
    wf_subdir = '/wfendpoints'
    if not os.path.isdir(base_dir + wf_subdir):
        os.mkdir(base_dir + wf_subdir)
    filename = base_dir + wf_subdir + '/' + handle + '.json'
    save_json(wf_json, filename)
    if nickname == 'inbox':
        handle = original_domain + '@' + domain
        filename = base_dir + wf_subdir + '/' + handle + '.json'
        save_json(wf_json, filename)
    return True


def create_webfinger_endpoint(nickname: str, domain: str, port: int,
                              http_prefix: str, public_key_pem: str,
                              group_account: bool) -> {}:
    """Creates a webfinger endpoint for a user
    """
    original_domain = domain
    domain = get_full_domain(domain, port)

    person_name = nickname
    person_id = local_actor_url(http_prefix, person_name, domain)
    subject_str = "acct:" + person_name + "@" + original_domain
    profile_page_href = http_prefix + "://" + domain + "/@" + nickname
    if nickname in ('inbox', original_domain):
        person_name = 'actor'
        person_id = http_prefix + "://" + domain + "/" + person_name
        subject_str = "acct:" + original_domain + "@" + original_domain
        profile_page_href = http_prefix + '://' + domain + \
            '/about/more?instance_actor=true'

    person_link = http_prefix + "://" + domain + "/@" + person_name
    blog_url = http_prefix + "://" + domain + "/blog/" + person_name
    account = {
        "aliases": [
            person_link,
            person_id
        ],
        "links": [
            {
                "href": person_link + "/avatar.png",
                "rel": "http://webfinger.net/rel/avatar",
                "type": "image/png"
            },
            {
                "href": blog_url,
                "rel": "http://webfinger.net/rel/blog"
            },
            {
                "href": profile_page_href,
                "rel": "http://webfinger.net/rel/profile-page",
                "type": "text/html"
            },
            {
                "href": profile_page_href,
                "rel": "http://webfinger.net/rel/profile-page",
                "type": "text/vcard"
            },
            {
                "href": person_id,
                "rel": "self",
                "type": "application/activity+json"
            }
        ],
        "subject": subject_str
    }
    return account


def webfinger_node_info(http_prefix: str, domain_full: str) -> {}:
    """ /.well-known/nodeinfo endpoint
    """
    nodeinfo = {
        'links': [
            {
                'href': http_prefix + '://' + domain_full + '/nodeinfo/2.0',
                'rel': 'http://nodeinfo.diaspora.software/ns/schema/2.0'
            }
        ]
    }
    return nodeinfo


def webfinger_meta(http_prefix: str, domain_full: str) -> str:
    """Return /.well-known/host-meta
    """
    meta_str = \
        "<?xml version=’1.0' encoding=’UTF-8'?>" + \
        "<XRD xmlns=’http://docs.oasis-open.org/ns/xri/xrd-1.0'" + \
        " xmlns:hm=’http://host-meta.net/xrd/1.0'>" + \
        "" + \
        "<hm:Host>" + domain_full + "</hm:Host>" + \
        "" + \
        "<Link rel=’lrdd’" + \
        " template=’" + http_prefix + "://" + domain_full + \
        "/describe?uri={uri}'>" + \
        " <Title>Resource Descriptor</Title>" + \
        " </Link>" + \
        "</XRD>"
    return meta_str


def webfinger_lookup(path: str, base_dir: str,
                     domain: str, onion_domain: str,
                     port: int, debug: bool) -> {}:
    """Lookup the webfinger endpoint for an account
    """
    if not path.startswith('/.well-known/webfinger?'):
        return None
    handle = None
    res_type = 'acct'
    if 'resource=' + res_type + ':' in path:
        handle = path.split('resource=' + res_type + ':')[1].strip()
        handle = urllib.parse.unquote(handle)
        if debug:
            print('DEBUG: WEBFINGER handle ' + handle)
    elif 'resource=' + res_type + '%3A' in path:
        handle = path.split('resource=' + res_type + '%3A')[1]
        handle = urllib.parse.unquote(handle.strip())
        if debug:
            print('DEBUG: WEBFINGER handle ' + handle)
    if not handle:
        if debug:
            print('DEBUG: WEBFINGER handle missing')
        return None
    if '&' in handle:
        handle = handle.split('&')[0].strip()
        print('DEBUG: WEBFINGER handle with & removed ' + handle)
    if '@' not in handle:
        if debug:
            print('DEBUG: WEBFINGER no @ in handle ' + handle)
        return None
    handle = get_full_domain(handle, port)
    # convert @domain@domain to inbox@domain
    if '@' in handle:
        handle_domain = handle.split('@')[1]
        if handle.startswith(handle_domain + '@'):
            handle = 'inbox@' + handle_domain
    # if this is a lookup for a handle using its onion domain
    # then swap the onion domain for the clearnet version
    onionify = False
    if onion_domain:
        if onion_domain in handle:
            handle = handle.replace(onion_domain, domain)
            onionify = True
    # instance actor
    if handle.startswith('actor@'):
        handle = handle.replace('actor@', 'inbox@', 1)
    elif handle.startswith('Actor@'):
        handle = handle.replace('Actor@', 'inbox@', 1)
    filename = base_dir + '/wfendpoints/' + handle + '.json'
    if debug:
        print('DEBUG: WEBFINGER filename ' + filename)
    if not os.path.isfile(filename):
        if debug:
            print('DEBUG: WEBFINGER filename not found ' + filename)
        return None
    if not onionify:
        wf_json = load_json(filename)
    else:
        print('Webfinger request for onionified ' + handle)
        wf_json = load_json_onionify(filename, domain, onion_domain)
    if not wf_json:
        wf_json = {"nickname": "unknown"}
    return wf_json


def _webfinger_update_avatar(wf_json: {}, actor_json: {}) -> bool:
    """Updates the avatar image link
    """
    found = False
    avatar_url = actor_json['icon']['url']
    media_type = actor_json['icon']['mediaType']
    for link in wf_json['links']:
        if not link.get('rel'):
            continue
        if not link['rel'].endswith('://webfinger.net/rel/avatar'):
            continue
        found = True
        if link['href'] != avatar_url or link['type'] != media_type:
            link['href'] = avatar_url
            link['type'] = media_type
            return True
        break
    if found:
        return False
    wf_json['links'].append({
        "href": avatar_url,
        "rel": "http://webfinger.net/rel/avatar",
        "type": media_type
    })
    return True


def _webfinger_update_vcard(wf_json: {}, actor_json: {}) -> bool:
    """Updates the vcard link
    """
    for link in wf_json['links']:
        if link.get('type'):
            if link['type'] == 'text/vcard':
                return False
    wf_json['links'].append({
        "href": actor_json['url'],
        "rel": "http://webfinger.net/rel/profile-page",
        "type": "text/vcard"
    })
    return True


def _webfinger_add_blog_link(wf_json: {}, actor_json: {}) -> bool:
    """Adds a blog link to webfinger if needed
    """
    found = False
    if '/users/' in actor_json['id']:
        blog_url = \
            actor_json['id'].split('/users/')[0] + '/blog/' + \
            actor_json['id'].split('/users/')[1]
    else:
        blog_url = \
            actor_json['id'].split('/@')[0] + '/blog/' + \
            actor_json['id'].split('/@')[1]
    for link in wf_json['links']:
        if not link.get('rel'):
            continue
        if not link['rel'].endswith('://webfinger.net/rel/blog'):
            continue
        found = True
        if link['href'] != blog_url:
            link['href'] = blog_url
            return True
        break
    if found:
        return False
    wf_json['links'].append({
        "href": blog_url,
        "rel": "http://webfinger.net/rel/blog"
    })
    return True


def _webfinger_updateFromProfile(wf_json: {}, actor_json: {}) -> bool:
    """Updates webfinger Email/blog/xmpp links from profile
    Returns true if one or more tags has been changed
    """
    if not actor_json.get('attachment'):
        return False

    changed = False

    webfinger_property_name = {
        "xmpp": "xmpp",
        "matrix": "matrix",
        "email": "mailto",
        "ssb": "ssb",
        "briar": "briar",
        "cwtch": "cwtch",
        "jami": "jami",
        "tox": "toxId"
    }

    aliases_not_found = []
    for name, alias in webfinger_property_name.items():
        aliases_not_found.append(alias)

    for property_value in actor_json['attachment']:
        if not property_value.get('name'):
            continue
        property_name = property_value['name'].lower()
        found = False
        for name, alias in webfinger_property_name.items():
            if name == property_name:
                if alias in aliases_not_found:
                    aliases_not_found.remove(alias)
                found = True
                break
        if not found:
            continue
        if not property_value.get('type'):
            continue
        if not property_value.get('value'):
            continue
        if property_value['type'] != 'PropertyValue':
            continue

        new_value = property_value['value'].strip()
        if '://' in new_value:
            new_value = new_value.split('://')[1]

        alias_index = 0
        found = False
        for alias in wf_json['aliases']:
            if alias.startswith(webfinger_property_name[property_name] + ':'):
                found = True
                break
            alias_index += 1
        new_alias = webfinger_property_name[property_name] + ':' + new_value
        if found:
            if wf_json['aliases'][alias_index] != new_alias:
                changed = True
                wf_json['aliases'][alias_index] = new_alias
        else:
            wf_json['aliases'].append(new_alias)
            changed = True

    # remove any aliases which are no longer in the actor profile
    remove_alias = []
    for alias in aliases_not_found:
        for full_alias in wf_json['aliases']:
            if full_alias.startswith(alias + ':'):
                remove_alias.append(full_alias)
    for full_alias in remove_alias:
        wf_json['aliases'].remove(full_alias)
        changed = True

    if _webfinger_update_avatar(wf_json, actor_json):
        changed = True

    if _webfinger_update_vcard(wf_json, actor_json):
        changed = True

    if _webfinger_add_blog_link(wf_json, actor_json):
        changed = True

    return changed


def webfinger_update(base_dir: str, nickname: str, domain: str,
                     onion_domain: str,
                     cached_webfingers: {}) -> None:
    """Regenerates stored webfinger
    """
    handle = nickname + '@' + domain
    wf_subdir = '/wfendpoints'
    if not os.path.isdir(base_dir + wf_subdir):
        return

    filename = base_dir + wf_subdir + '/' + handle + '.json'
    onionify = False
    if onion_domain:
        if onion_domain in handle:
            handle = handle.replace(onion_domain, domain)
            onionify = True
    if not onionify:
        wf_json = load_json(filename)
    else:
        wf_json = load_json_onionify(filename, domain, onion_domain)
    if not wf_json:
        return

    actor_filename = base_dir + '/accounts/' + handle + '.json'
    actor_json = load_json(actor_filename)
    if not actor_json:
        return

    if _webfinger_updateFromProfile(wf_json, actor_json):
        if save_json(wf_json, filename):
            store_webfinger_in_cache(handle, wf_json, cached_webfingers)
