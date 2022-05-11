__filename__ = "languages.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.3.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Core"

import json
from urllib import request, parse
from utils import get_actor_languages_list
from utils import remove_html
from utils import has_object_dict
from utils import get_config_param
from utils import local_actor_url
from cache import get_person_from_cache


def get_actor_languages(actor_json: {}) -> str:
    """Returns a string containing languages used by the given actor
    """
    lang_list = get_actor_languages_list(actor_json)
    if not lang_list:
        return ''
    languages_str = ''
    for lang in lang_list:
        if languages_str:
            languages_str += ' / ' + lang
        else:
            languages_str = lang
    return languages_str


def get_understood_languages(base_dir: str, http_prefix: str,
                             nickname: str, domain_full: str,
                             person_cache: {}) -> []:
    """Returns a list of understood languages for the given account
    """
    person_url = local_actor_url(http_prefix, nickname, domain_full)
    actor_json = \
        get_person_from_cache(base_dir, person_url, person_cache, False)
    if not actor_json:
        print('WARN: unable to load actor to obtain languages ' + person_url)
        return []
    return get_actor_languages_list(actor_json)


def set_actor_languages(base_dir: str, actor_json: {},
                        languages_str: str) -> None:
    """Sets the languages understood by the given actor
    """
    languages_str = languages_str.strip()
    separator = None
    possible_separators = (',', '/', ';', '+', ' ')
    for poss in possible_separators:
        if poss in languages_str:
            separator = poss
            break
    if separator:
        lang_list = languages_str.lower().split(separator)
    else:
        lang_list = [languages_str.lower()]
    lang_list2 = ''
    for lang in lang_list:
        lang = lang.strip()
        if lang_list2:
            if ' ' + lang not in lang_list2:
                lang_list2 += ', ' + lang
        else:
            lang_list2 += lang

    # remove any existing value
    property_found = None
    for property_value in actor_json['attachment']:
        name_value = None
        if property_value.get('name'):
            name_value = property_value['name']
        elif property_value.get('schema:name'):
            name_value = property_value['schema:name']
        if not name_value:
            continue
        if not property_value.get('type'):
            continue
        if not name_value.lower().startswith('languages'):
            continue
        property_found = property_value
        break
    if property_found:
        actor_json['attachment'].remove(property_found)

    if not lang_list2:
        return

    new_languages = {
        "name": "Languages",
        "type": "PropertyValue",
        "value": lang_list2
    }
    actor_json['attachment'].append(new_languages)


def understood_post_language(base_dir: str, nickname: str, domain: str,
                             message_json: {}, system_language: str,
                             http_prefix: str, domain_full: str,
                             person_cache: {}) -> bool:
    """Returns true if the post is written in a language
    understood by this account
    """
    msg_object = message_json
    if has_object_dict(message_json):
        msg_object = message_json['object']
    if not msg_object.get('contentMap'):
        return True
    if not isinstance(msg_object['contentMap'], dict):
        return True
    if msg_object['contentMap'].get(system_language):
        return True
    person_url = local_actor_url(http_prefix, nickname, domain_full)
    actor_json = \
        get_person_from_cache(base_dir, person_url, person_cache, False)
    if not actor_json:
        print('WARN: unable to load actor to check languages ' + person_url)
        return False
    languages_understood = get_actor_languages_list(actor_json)
    if not languages_understood:
        return True
    for lang in languages_understood:
        if msg_object['contentMap'].get(lang):
            return True
    # is the language for this post supported by libretranslate?
    libretranslate_url = get_config_param(base_dir, "libretranslateUrl")
    if libretranslate_url:
        libretranslate_api_key = \
            get_config_param(base_dir, "libretranslateApiKey")
        lang_list = \
            libretranslate_languages(libretranslate_url,
                                     libretranslate_api_key)
        for lang in lang_list:
            if msg_object['contentMap'].get(lang):
                return True
    return False


def libretranslate_languages(url: str, api_key: str = None) -> []:
    """Returns a list of supported languages
    """
    if not url:
        return []
    if not url.endswith('/languages'):
        if not url.endswith('/'):
            url += "/languages"
        else:
            url += "languages"

    params = dict()

    if api_key:
        params["api_key"] = api_key

    url_params = parse.urlencode(params)

    req = request.Request(url, data=url_params.encode())

    response = request.urlopen(req)

    response_str = response.read().decode()

    result = json.loads(response_str)
    if not result:
        return []
    if not isinstance(result, list):
        return []

    lang_list = []
    for lang in result:
        if not isinstance(lang, dict):
            continue
        if not lang.get('code'):
            continue
        lang_code = lang['code']
        if len(lang_code) != 2:
            continue
        lang_list.append(lang_code)
    lang_list.sort()
    return lang_list


def get_links_from_content(content: str) -> {}:
    """Returns a list of links within the given content
    """
    if '<a href' not in content:
        return {}
    sections = content.split('<a href')
    first = True
    links = {}
    for subsection in sections:
        if first:
            first = False
            continue
        if '"' not in subsection:
            continue
        url = subsection.split('"')[1].strip()
        if '://' in url and '.' in url and \
           '>' in subsection:
            if url not in links:
                link_text = subsection.split('>')[1]
                if '<' in link_text:
                    link_text = link_text.split('<')[0]
                    links[link_text] = url
    return links


def add_links_to_content(content: str, links: {}) -> str:
    """Adds links back into plain text
    """
    for link_text, url in links.items():
        url_desc = url
        if link_text.startswith('@') and link_text in content:
            content = \
                content.replace(link_text,
                                '<a href="' + url +
                                '" rel="nofollow noopener ' +
                                'noreferrer" target="_blank">' +
                                link_text + '</a>')
        else:
            if len(url_desc) > 40:
                url_desc = url_desc[:40]
            content += \
                '<p><a href="' + url + \
                '" rel="nofollow noopener noreferrer" target="_blank">' + \
                url_desc + '</a></p>'
    return content


def libretranslate(url: str, text: str,
                   source: str, target: str, api_key: str = None) -> str:
    """Translate string using libretranslate
    """
    if not url:
        return None

    if not url.endswith('/translate'):
        if not url.endswith('/'):
            url += "/translate"
        else:
            url += "translate"

    original_text = text

    # get any links from the text
    links = get_links_from_content(text)

    # LibreTranslate doesn't like markup
    text = remove_html(text)

    # remove any links from plain text version of the content
    for _, url2 in links.items():
        text = text.replace(url2, '')

    lt_params = {
        "q": text,
        "source": source,
        "target": target
    }

    if api_key:
        lt_params["api_key"] = api_key

    url_params = parse.urlencode(lt_params)

    req = request.Request(url, data=url_params.encode())
    try:
        response = request.urlopen(req)
    except BaseException:
        print('EX: Unable to translate: ' + text)
        return original_text

    response_str = response.read().decode()

    translated_text = \
        '<p>' + json.loads(response_str)['translatedText'] + '</p>'

    # append links form the original text
    if links:
        translated_text = add_links_to_content(translated_text, links)
    return translated_text


def auto_translate_post(base_dir: str, post_json_object: {},
                        system_language: str, translate: {}) -> str:
    """Tries to automatically translate the given post
    """
    if not has_object_dict(post_json_object):
        return ''
    msg_object = post_json_object['object']
    if not msg_object.get('contentMap'):
        return ''
    if not isinstance(msg_object['contentMap'], dict):
        return ''

    # is the language for this post supported by libretranslate?
    libretranslate_url = get_config_param(base_dir, "libretranslateUrl")
    if not libretranslate_url:
        return ''
    libretranslate_api_key = get_config_param(base_dir, "libretranslateApiKey")
    lang_list = \
        libretranslate_languages(libretranslate_url, libretranslate_api_key)
    for lang in lang_list:
        content = None
        if msg_object['contentMap'].get(lang):
            content = msg_object['contentMap'][lang]
        if not content:
            continue
        translated_text = \
            libretranslate(libretranslate_url, content,
                           lang, system_language,
                           libretranslate_api_key)
        if translated_text:
            if remove_html(translated_text) == remove_html(content):
                return content
            translated_text = \
                '<p>' + translate['Translated'].upper() + '</p>' + \
                translated_text
        return translated_text
    return ''
