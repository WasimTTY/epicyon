__filename__ = "conversation.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.5.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Timeline"

import os
from utils import has_object_dict
from utils import acct_dir
from utils import remove_id_ending
from utils import text_in_file
from utils import locate_post
from utils import load_json
from utils import harmless_markup
from utils import get_attributed_to
from utils import get_reply_to
from utils import resembles_url
from keys import get_instance_actor_key
from session import get_json
from session import get_json_valid


def _get_conversation_filename(base_dir: str, nickname: str, domain: str,
                               post_json_object: {}) -> str:
    """Returns the conversation filename
    """
    if not has_object_dict(post_json_object):
        return None
    if not post_json_object['object'].get('conversation') and \
       not post_json_object['object'].get('context'):
        return None
    if not post_json_object['object'].get('id'):
        return None
    conversation_dir = acct_dir(base_dir, nickname, domain) + '/conversation'
    if not os.path.isdir(conversation_dir):
        os.mkdir(conversation_dir)
    if post_json_object['object'].get('conversation'):
        conversation_id = post_json_object['object']['conversation']
    else:
        conversation_id = post_json_object['object']['context']
    conversation_id = conversation_id.replace('/', '#')
    return conversation_dir + '/' + conversation_id


def update_conversation(base_dir: str, nickname: str, domain: str,
                        post_json_object: {}) -> bool:
    """Adds a post to a conversation index in the /conversation subdirectory
    """
    conversation_filename = \
        _get_conversation_filename(base_dir, nickname, domain,
                                   post_json_object)
    if not conversation_filename:
        return False
    post_id = remove_id_ending(post_json_object['object']['id'])
    if not os.path.isfile(conversation_filename):
        try:
            with open(conversation_filename, 'w+',
                      encoding='utf-8') as conv_file:
                conv_file.write(post_id + '\n')
                return True
        except OSError:
            print('EX: update_conversation ' +
                  'unable to write to ' + conversation_filename)
    elif not text_in_file(post_id + '\n', conversation_filename):
        try:
            with open(conversation_filename, 'a+',
                      encoding='utf-8') as conv_file:
                conv_file.write(post_id + '\n')
                return True
        except OSError:
            print('EX: update_conversation 2 ' +
                  'unable to write to ' + conversation_filename)
    return False


def mute_conversation(base_dir: str, nickname: str, domain: str,
                      conversation_id: str) -> None:
    """Mutes the given conversation
    """
    conversation_dir = acct_dir(base_dir, nickname, domain) + '/conversation'
    conversation_filename = \
        conversation_dir + '/' + conversation_id.replace('/', '#')
    if not os.path.isfile(conversation_filename):
        return
    if os.path.isfile(conversation_filename + '.muted'):
        return
    try:
        with open(conversation_filename + '.muted', 'w+',
                  encoding='utf-8') as conv_file:
            conv_file.write('\n')
    except OSError:
        print('EX: unable to write mute ' + conversation_filename)


def unmute_conversation(base_dir: str, nickname: str, domain: str,
                        conversation_id: str) -> None:
    """Unmutes the given conversation
    """
    conversation_dir = acct_dir(base_dir, nickname, domain) + '/conversation'
    conversation_filename = \
        conversation_dir + '/' + conversation_id.replace('/', '#')
    if not os.path.isfile(conversation_filename):
        return
    if not os.path.isfile(conversation_filename + '.muted'):
        return
    try:
        os.remove(conversation_filename + '.muted')
    except OSError:
        print('EX: unmute_conversation unable to delete ' +
              conversation_filename + '.muted')


def _get_replies_to_post(post_json_object: {},
                         signing_priv_key_pem: str,
                         session, as_header, debug: bool,
                         http_prefix: str, domain: str,
                         depth: int) -> []:
    """Returns a list of reply posts to the given post as json
    """
    result = []
    post_obj = post_json_object
    if has_object_dict(post_json_object):
        post_obj = post_json_object['object']
    if not post_obj.get('replies'):
        return result

    # get the replies collection url
    replies_collection_id = None
    if isinstance(post_obj['replies'], dict):
        if post_obj['replies'].get('id'):
            replies_collection_id = post_obj['replies']['id']
    elif isinstance(post_obj['replies'], str):
        replies_collection_id = post_obj['replies']

    if replies_collection_id:
        print('DEBUG: get_replies_to_post replies_collection_id ' +
              str(replies_collection_id))

        replies_collection = \
            get_json(signing_priv_key_pem, session, replies_collection_id,
                     as_header, None, debug, __version__,
                     http_prefix, domain)
        if not get_json_valid(replies_collection):
            return result

        print('DEBUG: get_replies_to_post replies_collection ' +
              str(replies_collection))
        # get the list of replies
        if not replies_collection.get('first'):
            return result
        if not isinstance(replies_collection['first'], dict):
            return result
        if not replies_collection['first'].get('items'):
            if not replies_collection['first'].get('next'):
                return result

        items_list = []
        if replies_collection['first'].get('items'):
            items_list = replies_collection['first']['items']
        if not items_list:
            # if there are no items try the next one
            next_page_id = replies_collection['first']['next']
            if not isinstance(next_page_id, str):
                return result
            replies_collection = \
                get_json(signing_priv_key_pem, session, next_page_id,
                         as_header, None, debug, __version__,
                         http_prefix, domain)
            print('DEBUG: get_replies_to_post next replies_collection ' +
                  str(replies_collection))
            if not get_json_valid(replies_collection):
                return result
            if not replies_collection.get('items'):
                return result
            if not isinstance(replies_collection['items'], list):
                return result
            items_list = replies_collection['items']

        print('DEBUG: get_replies_to_post items_list ' +
              str(items_list))

        if not isinstance(items_list, list):
            return result

        # check each item in the list
        for item in items_list:
            # download the item if needed
            if isinstance(item, str):
                if resembles_url(item):
                    if debug:
                        print('Downloading conversation item ' + item)
                    item_dict = \
                        get_json(signing_priv_key_pem, session, item,
                                 as_header, None, debug, __version__,
                                 http_prefix, domain)
                    if not get_json_valid(item_dict):
                        continue
                    item = item_dict

            if not isinstance(item, dict):
                continue
            if not has_object_dict(item):
                if not item.get('attributedTo'):
                    continue
                attrib_str = get_attributed_to(item['attributedTo'])
                if not attrib_str:
                    continue
                if not item.get('published'):
                    continue
                if not item.get('id'):
                    continue
                if not isinstance(item['id'], str):
                    continue
                if not item.get('to'):
                    continue
                if not isinstance(item['to'], list):
                    continue
                if 'cc' not in item:
                    continue
                if not isinstance(item['cc'], list):
                    continue
                wrapped_post = {
                    "@context": "https://www.w3.org/ns/activitystreams",
                    'id': item['id'] + '/activity',
                    'type': 'Create',
                    'actor': attrib_str,
                    'published': item['published'],
                    'to': item['to'],
                    'cc': item['cc'],
                    'object': item
                }
                item = wrapped_post
            if not item['object'].get('published'):
                continue

            # render harmless any dangerous markup
            harmless_markup(item)

            # add it to the list
            result.append(item)

            if depth < 10 and item.get('id'):
                if isinstance(item['id'], str):
                    result += \
                        _get_replies_to_post(post_json_object,
                                             signing_priv_key_pem,
                                             session, as_header,
                                             debug,
                                             http_prefix, domain,
                                             depth + 1)
    return result


def download_conversation_posts(authorized: bool, session,
                                http_prefix: str, base_dir: str,
                                nickname: str, domain: str,
                                post_id: str, debug: bool) -> []:
    """Downloads all posts for a conversation and returns a list of the
    json objects
    """
    if '://' not in post_id:
        return []
    profile_str = 'https://www.w3.org/ns/activitystreams'
    as_header = {
        'Accept': 'application/ld+json; profile="' + profile_str + '"'
    }
    conversation_view = []
    signing_priv_key_pem = get_instance_actor_key(base_dir, domain)
    post_id = remove_id_ending(post_id)
    post_filename = \
        locate_post(base_dir, nickname, domain, post_id)
    post_json_object = None
    if post_filename:
        post_json_object = load_json(post_filename)
    else:
        if authorized:
            post_json_object = \
                get_json(signing_priv_key_pem, session, post_id,
                         as_header, None, debug, __version__,
                         http_prefix, domain)
    if debug:
        if not get_json_valid(post_json_object):
            print(post_id + ' returned no json')

    # get any replies
    replies_to_post = []
    if get_json_valid(post_json_object):
        replies_to_post = \
            _get_replies_to_post(post_json_object,
                                 signing_priv_key_pem,
                                 session, as_header, debug,
                                 http_prefix, domain, 0)

    while get_json_valid(post_json_object):
        if not isinstance(post_json_object, dict):
            break
        if not has_object_dict(post_json_object):
            if not post_json_object.get('id'):
                break
            if not isinstance(post_json_object['id'], str):
                break
            if not post_json_object.get('attributedTo'):
                if debug:
                    print(str(post_json_object))
                    print(post_json_object['id'] + ' has no attributedTo')
                break
            attrib_str = get_attributed_to(post_json_object['attributedTo'])
            if not attrib_str:
                break
            if not post_json_object.get('published'):
                if debug:
                    print(str(post_json_object))
                    print(post_json_object['id'] + ' has no published date')
                break
            if not post_json_object.get('to'):
                if debug:
                    print(str(post_json_object))
                    print(post_json_object['id'] + ' has no "to" list')
                break
            if not isinstance(post_json_object['to'], list):
                break
            if 'cc' not in post_json_object:
                if debug:
                    print(str(post_json_object))
                    print(post_json_object['id'] + ' has no "cc" list')
                break
            if not isinstance(post_json_object['cc'], list):
                break
            wrapped_post = {
                "@context": "https://www.w3.org/ns/activitystreams",
                'id': post_json_object['id'] + '/activity',
                'type': 'Create',
                'actor': attrib_str,
                'published': post_json_object['published'],
                'to': post_json_object['to'],
                'cc': post_json_object['cc'],
                'object': post_json_object
            }
            post_json_object = wrapped_post
        if not post_json_object['object'].get('published'):
            break

        # render harmless any dangerous markup
        harmless_markup(post_json_object)

        conversation_view = [post_json_object] + conversation_view
        if not authorized:
            # only show a single post to non-authorized viewers
            break
        post_id = get_reply_to(post_json_object['object'])
        if not post_id:
            if debug:
                print(post_id + ' is not a reply')
            break
        post_id = remove_id_ending(post_id)
        post_filename = \
            locate_post(base_dir, nickname, domain, post_id)
        post_json_object = None
        if post_filename:
            post_json_object = load_json(post_filename)
        else:
            if authorized:
                post_json_object = \
                    get_json(signing_priv_key_pem, session, post_id,
                             as_header, None, debug, __version__,
                             http_prefix, domain)
        if debug:
            if not get_json_valid(post_json_object):
                print(post_id + ' returned no json')

    return conversation_view + replies_to_post
