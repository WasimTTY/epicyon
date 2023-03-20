__filename__ = "cwlists.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.4.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Core"

import os
from utils import load_json
from utils import get_content_from_post


def load_cw_lists(base_dir: str, verbose: bool) -> {}:
    """Load lists used for content warnings
    """
    if not os.path.isdir(base_dir + '/cwlists'):
        return {}
    result = {}
    # NOTE: here we do want to allow recursive walk through
    # possible subdirectories
    for _, _, files in os.walk(base_dir + '/cwlists'):
        for fname in files:
            if not fname.endswith('.json'):
                continue
            list_filename = os.path.join(base_dir + '/cwlists', fname)
            print('list_filename: ' + list_filename)
            list_json = load_json(list_filename, 0, 1)
            if not list_json:
                continue
            if not list_json.get('name'):
                continue
            if not list_json.get('words') and not list_json.get('domains'):
                continue
            name = list_json['name']
            if verbose:
                print('List: ' + name)
            result[name] = list_json
    return result


def add_cw_from_lists(post_json_object: {}, cw_lists: {}, translate: {},
                      lists_enabled: str, system_language: str,
                      languages_understood: []) -> None:
    """Adds content warnings by matching the post content
    against domains or keywords
    """
    if not lists_enabled:
        return
    if 'content' not in post_json_object['object']:
        if 'contentMap' not in post_json_object['object']:
            return
    cw_text = ''
    if post_json_object['object'].get('summary'):
        cw_text = post_json_object['object']['summary']

    content = get_content_from_post(post_json_object, system_language,
                                    languages_understood, "content")
    if not content:
        return
    for name, item in cw_lists.items():
        if name not in lists_enabled:
            continue
        if not item.get('warning'):
            continue
        warning = item['warning']

        # is there a translated version of the warning?
        if translate.get(warning):
            warning = translate[warning]

        # is the warning already in the CW?
        if warning in cw_text:
            continue

        matched = False

        # match domains within the content
        if item.get('domains'):
            for domain in item['domains']:
                if domain in content:
                    if cw_text:
                        cw_text = warning + ' / ' + cw_text
                    else:
                        cw_text = warning
                    matched = True
                    break

        if matched:
            continue

        # match words within the content
        if item.get('words'):
            for word_str in item['words']:
                if word_str in content or word_str.title() in content:
                    if cw_text:
                        cw_text = warning + ' / ' + cw_text
                    else:
                        cw_text = warning
                    break
    if cw_text:
        post_json_object['object']['summary'] = cw_text
        post_json_object['object']['sensitive'] = True


def get_cw_list_variable(list_name: str) -> str:
    """Returns the variable associated with a CW list
    """
    return 'list' + list_name.replace(' ', '').replace("'", '')
