__filename__ = "content.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Core"

import os
import email.parser
import urllib.parse
from shutil import copyfile
from utils import dangerous_svg
from utils import remove_domain_port
from utils import is_valid_language
from utils import get_image_extensions
from utils import load_json
from utils import save_json
from utils import file_last_modified
from utils import get_link_prefixes
from utils import dangerous_markup
from utils import is_pgp_encrypted
from utils import contains_pgp_public_key
from utils import acct_dir
from utils import is_float
from utils import get_currencies
from utils import remove_html
from petnames import get_pet_name
from session import download_image


def remove_htmlTag(htmlStr: str, tag: str) -> str:
    """Removes a given tag from a html string
    """
    tagFound = True
    while tagFound:
        matchStr = ' ' + tag + '="'
        if matchStr not in htmlStr:
            tagFound = False
            break
        sections = htmlStr.split(matchStr, 1)
        if '"' not in sections[1]:
            tagFound = False
            break
        htmlStr = sections[0] + sections[1].split('"', 1)[1]
    return htmlStr


def _remove_quotes_within_quotes(content: str) -> str:
    """Removes any blockquote inside blockquote
    """
    if '<blockquote>' not in content:
        return content
    if '</blockquote>' not in content:
        return content
    ctr = 1
    found = True
    while found:
        prefix = content.split('<blockquote>', ctr)[0] + '<blockquote>'
        quotedStr = content.split('<blockquote>', ctr)[1]
        if '</blockquote>' not in quotedStr:
            found = False
        else:
            endStr = quotedStr.split('</blockquote>')[1]
            quotedStr = quotedStr.split('</blockquote>')[0]
            if '<blockquote>' not in endStr:
                found = False
            if '<blockquote>' in quotedStr:
                quotedStr = quotedStr.replace('<blockquote>', '')
                content = prefix + quotedStr + '</blockquote>' + endStr
        ctr += 1
    return content


def html_replace_email_quote(content: str) -> str:
    """Replaces an email style quote "> Some quote" with html blockquote
    """
    if is_pgp_encrypted(content) or contains_pgp_public_key(content):
        return content
    # replace quote paragraph
    if '<p>&quot;' in content:
        if '&quot;</p>' in content:
            if content.count('<p>&quot;') == content.count('&quot;</p>'):
                content = content.replace('<p>&quot;', '<p><blockquote>')
                content = content.replace('&quot;</p>', '</blockquote></p>')
    if '>\u201c' in content:
        if '\u201d<' in content:
            if content.count('>\u201c') == content.count('\u201d<'):
                content = content.replace('>\u201c', '><blockquote>')
                content = content.replace('\u201d<', '</blockquote><')
    # replace email style quote
    if '>&gt; ' not in content:
        return content
    contentStr = content.replace('<p>', '')
    contentLines = contentStr.split('</p>')
    newContent = ''
    for lineStr in contentLines:
        if not lineStr:
            continue
        if '>&gt; ' not in lineStr:
            if lineStr.startswith('&gt; '):
                lineStr = lineStr.replace('&gt; ', '<blockquote>')
                lineStr = lineStr.replace('&gt;', '<br>')
                newContent += '<p>' + lineStr + '</blockquote></p>'
            else:
                newContent += '<p>' + lineStr + '</p>'
        else:
            lineStr = lineStr.replace('>&gt; ', '><blockquote>')
            if lineStr.startswith('&gt;'):
                lineStr = lineStr.replace('&gt;', '<blockquote>', 1)
            else:
                lineStr = lineStr.replace('&gt;', '<br>')
            newContent += '<p>' + lineStr + '</blockquote></p>'
    return _remove_quotes_within_quotes(newContent)


def html_replace_quote_marks(content: str) -> str:
    """Replaces quotes with html formatting
    "hello" becomes <q>hello</q>
    """
    if is_pgp_encrypted(content) or contains_pgp_public_key(content):
        return content
    if '"' not in content:
        if '&quot;' not in content:
            return content

    # only if there are a few quote marks
    if content.count('"') > 4:
        return content
    if content.count('&quot;') > 4:
        return content

    newContent = content
    if '"' in content:
        sections = content.split('"')
        if len(sections) > 1:
            newContent = ''
            openQuote = True
            markup = False
            for ch in content:
                currChar = ch
                if ch == '<':
                    markup = True
                elif ch == '>':
                    markup = False
                elif ch == '"' and not markup:
                    if openQuote:
                        currChar = '“'
                    else:
                        currChar = '”'
                    openQuote = not openQuote
                newContent += currChar

    if '&quot;' in newContent:
        openQuote = True
        content = newContent
        newContent = ''
        ctr = 0
        sections = content.split('&quot;')
        noOfSections = len(sections)
        for s in sections:
            newContent += s
            if ctr < noOfSections - 1:
                if openQuote:
                    newContent += '“'
                else:
                    newContent += '”'
                openQuote = not openQuote
            ctr += 1
    return newContent


def dangerous_css(filename: str, allow_local_network_access: bool) -> bool:
    """Returns true is the css file contains code which
    can create security problems
    """
    if not os.path.isfile(filename):
        return False

    content = None
    try:
        with open(filename, 'r') as fp:
            content = fp.read().lower()
    except OSError:
        print('EX: unable to read css file ' + filename)

    if content:
        cssMatches = ('behavior:', ':expression', '?php', '.php',
                      'google', 'regexp', 'localhost',
                      '127.0.', '192.168', '10.0.', '@import')
        for cssmatch in cssMatches:
            if cssmatch in content:
                return True

        # search for non-local web links
        if 'url(' in content:
            urlList = content.split('url(')
            ctr = 0
            for urlStr in urlList:
                if ctr > 0:
                    if ')' in urlStr:
                        urlStr = urlStr.split(')')[0]
                        if 'http' in urlStr:
                            print('ERROR: non-local web link in CSS ' +
                                  filename)
                            return True
                ctr += 1

        # an attacker can include html inside of the css
        # file as a comment and this may then be run from the html
        if dangerous_markup(content, allow_local_network_access):
            return True
    return False


def switch_words(base_dir: str, nickname: str, domain: str, content: str,
                 rules: [] = []) -> str:
    """Performs word replacements. eg. Trump -> The Orange Menace
    """
    if is_pgp_encrypted(content) or contains_pgp_public_key(content):
        return content

    if not rules:
        switch_words_filename = \
            acct_dir(base_dir, nickname, domain) + '/replacewords.txt'
        if not os.path.isfile(switch_words_filename):
            return content
        try:
            with open(switch_words_filename, 'r') as fp:
                rules = fp.readlines()
        except OSError:
            print('EX: unable to read switches ' + switch_words_filename)

    for line in rules:
        replaceStr = line.replace('\n', '').replace('\r', '')
        splitters = ('->', ':', ',', ';', '-')
        wordTransform = None
        for splitStr in splitters:
            if splitStr in replaceStr:
                wordTransform = replaceStr.split(splitStr)
                break
        if not wordTransform:
            continue
        if len(wordTransform) == 2:
            replaceStr1 = wordTransform[0].strip().replace('"', '')
            replaceStr2 = wordTransform[1].strip().replace('"', '')
            content = content.replace(replaceStr1, replaceStr2)
    return content


def _save_custom_emoji(session, base_dir: str, emojiName: str, url: str,
                       debug: bool) -> None:
    """Saves custom emoji to file
    """
    if not session:
        if debug:
            print('EX: _save_custom_emoji no session')
        return
    if '.' not in url:
        return
    ext = url.split('.')[-1]
    if ext != 'png':
        if debug:
            print('EX: Custom emoji is wrong format ' + url)
        return
    emojiName = emojiName.replace(':', '').strip().lower()
    customEmojiDir = base_dir + '/emojicustom'
    if not os.path.isdir(customEmojiDir):
        os.mkdir(customEmojiDir)
    emojiImageFilename = customEmojiDir + '/' + emojiName + '.' + ext
    if not download_image(session, base_dir, url,
                          emojiImageFilename, debug, False):
        if debug:
            print('EX: custom emoji not downloaded ' + url)
        return
    emojiJsonFilename = customEmojiDir + '/emoji.json'
    emojiJson = {}
    if os.path.isfile(emojiJsonFilename):
        emojiJson = load_json(emojiJsonFilename, 0, 1)
        if not emojiJson:
            emojiJson = {}
    if not emojiJson.get(emojiName):
        emojiJson[emojiName] = emojiName
        save_json(emojiJson, emojiJsonFilename)
        if debug:
            print('EX: Saved custom emoji ' + emojiJsonFilename)
    elif debug:
        print('EX: cusom emoji already saved')


def replace_emoji_from_tags(session, base_dir: str,
                            content: str, tag: [], messageType: str,
                            debug: bool) -> str:
    """Uses the tags to replace :emoji: with html image markup
    """
    for tagItem in tag:
        if not tagItem.get('type'):
            continue
        if tagItem['type'] != 'Emoji':
            continue
        if not tagItem.get('name'):
            continue
        if not tagItem.get('icon'):
            continue
        if not tagItem['icon'].get('url'):
            continue
        if '/' not in tagItem['icon']['url']:
            continue
        if tagItem['name'] not in content:
            continue
        iconName = tagItem['icon']['url'].split('/')[-1]
        if iconName:
            if len(iconName) > 1:
                if iconName[0].isdigit():
                    if '.' in iconName:
                        iconName = iconName.split('.')[0]
                        # see https://unicode.org/
                        # emoji/charts/full-emoji-list.html
                        if '-' not in iconName:
                            # a single code
                            replaced = False
                            try:
                                replaceChar = chr(int("0x" + iconName, 16))
                                content = content.replace(tagItem['name'],
                                                          replaceChar)
                                replaced = True
                            except BaseException:
                                print('EX: replace_emoji_from_tags 1 ' +
                                      'no conversion of ' +
                                      str(iconName) + ' to chr ' +
                                      tagItem['name'] + ' ' +
                                      tagItem['icon']['url'])
                            if not replaced:
                                _save_custom_emoji(session, base_dir,
                                                   tagItem['name'],
                                                   tagItem['icon']['url'],
                                                   debug)
                        else:
                            # sequence of codes
                            iconCodes = iconName.split('-')
                            iconCodeSequence = ''
                            for icode in iconCodes:
                                replaced = False
                                try:
                                    iconCodeSequence += chr(int("0x" +
                                                                icode, 16))
                                    replaced = True
                                except BaseException:
                                    iconCodeSequence = ''
                                    print('EX: replace_emoji_from_tags 2 ' +
                                          'no conversion of ' +
                                          str(icode) + ' to chr ' +
                                          tagItem['name'] + ' ' +
                                          tagItem['icon']['url'])
                                if not replaced:
                                    _save_custom_emoji(session, base_dir,
                                                       tagItem['name'],
                                                       tagItem['icon']['url'],
                                                       debug)
                            if iconCodeSequence:
                                content = content.replace(tagItem['name'],
                                                          iconCodeSequence)

        htmlClass = 'emoji'
        if messageType == 'post header':
            htmlClass = 'emojiheader'
        if messageType == 'profile':
            htmlClass = 'emojiprofile'
        emojiHtml = "<img src=\"" + tagItem['icon']['url'] + "\" alt=\"" + \
            tagItem['name'].replace(':', '') + \
            "\" align=\"middle\" class=\"" + htmlClass + "\"/>"
        content = content.replace(tagItem['name'], emojiHtml)
    return content


def _add_music_tag(content: str, tag: str) -> str:
    """If a music link is found then ensure that the post is
    tagged appropriately
    """
    if '#podcast' in content or '#documentary' in content:
        return content
    if '#' not in tag:
        tag = '#' + tag
    if tag in content:
        return content
    musicSites = ('soundcloud.com', 'bandcamp.com')
    musicSiteFound = False
    for site in musicSites:
        if site + '/' in content:
            musicSiteFound = True
            break
    if not musicSiteFound:
        return content
    return ':music: ' + content + ' ' + tag + ' '


def add_web_links(content: str) -> str:
    """Adds markup for web links
    """
    if ':' not in content:
        return content

    prefixes = get_link_prefixes()

    # do any of these prefixes exist within the content?
    prefixFound = False
    for prefix in prefixes:
        if prefix in content:
            prefixFound = True
            break

    # if there are no prefixes then just keep the content we have
    if not prefixFound:
        return content

    maxLinkLength = 40
    content = content.replace('\r', '')
    words = content.replace('\n', ' --linebreak-- ').split(' ')
    replaceDict = {}
    for w in words:
        if ':' not in w:
            continue
        # does the word begin with a prefix?
        prefixFound = False
        for prefix in prefixes:
            if w.startswith(prefix):
                prefixFound = True
                break
        if not prefixFound:
            continue
        # the word contains a prefix
        if w.endswith('.') or w.endswith(';'):
            w = w[:-1]
        markup = '<a href="' + w + \
            '" rel="nofollow noopener noreferrer" target="_blank">'
        for prefix in prefixes:
            if w.startswith(prefix):
                markup += '<span class="invisible">' + prefix + '</span>'
                break
        linkText = w
        for prefix in prefixes:
            linkText = linkText.replace(prefix, '')
        # prevent links from becoming too long
        if len(linkText) > maxLinkLength:
            markup += '<span class="ellipsis">' + \
                linkText[:maxLinkLength] + '</span>'
            markup += '<span class="invisible">' + \
                linkText[maxLinkLength:] + '</span></a>'
        else:
            markup += '<span class="ellipsis">' + linkText + '</span></a>'
        replaceDict[w] = markup

    # do the replacements
    for url, markup in replaceDict.items():
        content = content.replace(url, markup)

    # replace any line breaks
    content = content.replace(' --linebreak-- ', '<br>')

    return content


def valid_hash_tag(hashtag: str) -> bool:
    """Returns true if the give hashtag contains valid characters
    """
    # long hashtags are not valid
    if len(hashtag) >= 32:
        return False
    validChars = set('0123456789' +
                     'abcdefghijklmnopqrstuvwxyz' +
                     'ABCDEFGHIJKLMNOPQRSTUVWXYZ' +
                     '¡¿ÄäÀàÁáÂâÃãÅåǍǎĄąĂăÆæĀā' +
                     'ÇçĆćĈĉČčĎđĐďðÈèÉéÊêËëĚěĘęĖėĒē' +
                     'ĜĝĢģĞğĤĥÌìÍíÎîÏïıĪīĮįĴĵĶķ' +
                     'ĹĺĻļŁłĽľĿŀÑñŃńŇňŅņÖöÒòÓóÔôÕõŐőØøŒœ' +
                     'ŔŕŘřẞßŚśŜŝŞşŠšȘșŤťŢţÞþȚțÜüÙùÚúÛûŰűŨũŲųŮůŪū' +
                     'ŴŵÝýŸÿŶŷŹźŽžŻż')
    if set(hashtag).issubset(validChars):
        return True
    if is_valid_language(hashtag):
        return True
    return False


def _add_hash_tags(wordStr: str, http_prefix: str, domain: str,
                   replaceHashTags: {}, postHashtags: {}) -> bool:
    """Detects hashtags and adds them to the replacements dict
    Also updates the hashtags list to be added to the post
    """
    if replaceHashTags.get(wordStr):
        return True
    hashtag = wordStr[1:]
    if not valid_hash_tag(hashtag):
        return False
    hashtagUrl = http_prefix + "://" + domain + "/tags/" + hashtag
    postHashtags[hashtag] = {
        'href': hashtagUrl,
        'name': '#' + hashtag,
        'type': 'Hashtag'
    }
    replaceHashTags[wordStr] = "<a href=\"" + hashtagUrl + \
        "\" class=\"mention hashtag\" rel=\"tag\">#<span>" + \
        hashtag + "</span></a>"
    return True


def _add_emoji(base_dir: str, wordStr: str,
               http_prefix: str, domain: str,
               replaceEmoji: {}, postTags: {},
               emojiDict: {}) -> bool:
    """Detects Emoji and adds them to the replacements dict
    Also updates the tags list to be added to the post
    """
    if not wordStr.startswith(':'):
        return False
    if not wordStr.endswith(':'):
        return False
    if len(wordStr) < 3:
        return False
    if replaceEmoji.get(wordStr):
        return True
    # remove leading and trailing : characters
    emoji = wordStr[1:]
    emoji = emoji[:-1]
    # is the text of the emoji valid?
    if not valid_hash_tag(emoji):
        return False
    if not emojiDict.get(emoji):
        return False
    emojiFilename = base_dir + '/emoji/' + emojiDict[emoji] + '.png'
    if not os.path.isfile(emojiFilename):
        return False
    emojiUrl = http_prefix + "://" + domain + \
        "/emoji/" + emojiDict[emoji] + '.png'
    postTags[emoji] = {
        'icon': {
            'mediaType': 'image/png',
            'type': 'Image',
            'url': emojiUrl
        },
        'name': ':' + emoji + ':',
        "updated": file_last_modified(emojiFilename),
        "id": emojiUrl.replace('.png', ''),
        'type': 'Emoji'
    }
    return True


def post_tag_exists(tagType: str, tagName: str, tags: {}) -> bool:
    """Returns true if a tag exists in the given dict
    """
    for tag in tags:
        if tag['name'] == tagName and tag['type'] == tagType:
            return True
    return False


def _add_mention(wordStr: str, http_prefix: str, following: str, petnames: str,
                 replaceMentions: {}, recipients: [], tags: {}) -> bool:
    """Detects mentions and adds them to the replacements dict and
    recipients list
    """
    possibleHandle = wordStr[1:]
    # @nick
    if following and '@' not in possibleHandle:
        # fall back to a best effort match against the following list
        # if no domain was specified. eg. @nick
        possibleNickname = possibleHandle
        for follow in following:
            if '@' not in follow:
                continue
            followNick = follow.split('@')[0]
            if possibleNickname == followNick:
                followStr = follow.replace('\n', '').replace('\r', '')
                replaceDomain = followStr.split('@')[1]
                recipientActor = http_prefix + "://" + \
                    replaceDomain + "/@" + possibleNickname
                if recipientActor not in recipients:
                    recipients.append(recipientActor)
                tags[wordStr] = {
                    'href': recipientActor,
                    'name': wordStr,
                    'type': 'Mention'
                }
                replaceMentions[wordStr] = \
                    "<span class=\"h-card\"><a href=\"" + http_prefix + \
                    "://" + replaceDomain + "/@" + possibleNickname + \
                    "\" class=\"u-url mention\">@<span>" + possibleNickname + \
                    "</span></a></span>"
                return True
        # try replacing petnames with mentions
        followCtr = 0
        for follow in following:
            if '@' not in follow:
                followCtr += 1
                continue
            pet = petnames[followCtr].replace('\n', '')
            if pet:
                if possibleNickname == pet:
                    followStr = follow.replace('\n', '').replace('\r', '')
                    replaceNickname = followStr.split('@')[0]
                    replaceDomain = followStr.split('@')[1]
                    recipientActor = http_prefix + "://" + \
                        replaceDomain + "/@" + replaceNickname
                    if recipientActor not in recipients:
                        recipients.append(recipientActor)
                    tags[wordStr] = {
                        'href': recipientActor,
                        'name': wordStr,
                        'type': 'Mention'
                    }
                    replaceMentions[wordStr] = \
                        "<span class=\"h-card\"><a href=\"" + http_prefix + \
                        "://" + replaceDomain + "/@" + replaceNickname + \
                        "\" class=\"u-url mention\">@<span>" + \
                        replaceNickname + "</span></a></span>"
                    return True
            followCtr += 1
        return False
    possibleNickname = None
    possibleDomain = None
    if '@' not in possibleHandle:
        return False
    possibleNickname = possibleHandle.split('@')[0]
    if not possibleNickname:
        return False
    possibleDomain = \
        possibleHandle.split('@')[1].strip('\n').strip('\r')
    if not possibleDomain:
        return False
    if following:
        for follow in following:
            if follow.replace('\n', '').replace('\r', '') != possibleHandle:
                continue
            recipientActor = http_prefix + "://" + \
                possibleDomain + "/@" + possibleNickname
            if recipientActor not in recipients:
                recipients.append(recipientActor)
            tags[wordStr] = {
                'href': recipientActor,
                'name': wordStr,
                'type': 'Mention'
            }
            replaceMentions[wordStr] = \
                "<span class=\"h-card\"><a href=\"" + http_prefix + \
                "://" + possibleDomain + "/@" + possibleNickname + \
                "\" class=\"u-url mention\">@<span>" + possibleNickname + \
                "</span></a></span>"
            return True
    # @nick@domain
    if not (possibleDomain == 'localhost' or '.' in possibleDomain):
        return False
    recipientActor = http_prefix + "://" + \
        possibleDomain + "/@" + possibleNickname
    if recipientActor not in recipients:
        recipients.append(recipientActor)
    tags[wordStr] = {
        'href': recipientActor,
        'name': wordStr,
        'type': 'Mention'
    }
    replaceMentions[wordStr] = \
        "<span class=\"h-card\"><a href=\"" + http_prefix + \
        "://" + possibleDomain + "/@" + possibleNickname + \
        "\" class=\"u-url mention\">@<span>" + possibleNickname + \
        "</span></a></span>"
    return True


def replace_content_duplicates(content: str) -> str:
    """Replaces invalid duplicates within content
    """
    if is_pgp_encrypted(content) or contains_pgp_public_key(content):
        return content
    while '<<' in content:
        content = content.replace('<<', '<')
    while '>>' in content:
        content = content.replace('>>', '>')
    content = content.replace('<\\p>', '')
    return content


def remove_text_formatting(content: str) -> str:
    """Removes markup for bold, italics, etc
    """
    if is_pgp_encrypted(content) or contains_pgp_public_key(content):
        return content
    if '<' not in content:
        return content
    removeMarkup = ('b', 'i', 'ul', 'ol', 'li', 'em', 'strong',
                    'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5')
    for markup in removeMarkup:
        content = content.replace('<' + markup + '>', '')
        content = content.replace('</' + markup + '>', '')
        content = content.replace('<' + markup.upper() + '>', '')
        content = content.replace('</' + markup.upper() + '>', '')
    return content


def remove_long_words(content: str, maxWordLength: int,
                      longWordsList: []) -> str:
    """Breaks up long words so that on mobile screens this doesn't
    disrupt the layout
    """
    if is_pgp_encrypted(content) or contains_pgp_public_key(content):
        return content
    content = replace_content_duplicates(content)
    if ' ' not in content:
        # handle a single very long string with no spaces
        contentStr = content.replace('<p>', '').replace(r'<\p>', '')
        if '://' not in contentStr:
            if len(contentStr) > maxWordLength:
                if '<p>' in content:
                    content = '<p>' + contentStr[:maxWordLength] + r'<\p>'
                else:
                    content = content[:maxWordLength]
                return content
    words = content.split(' ')
    if not longWordsList:
        longWordsList = []
        for wordStr in words:
            if len(wordStr) > maxWordLength:
                if wordStr not in longWordsList:
                    longWordsList.append(wordStr)
    for wordStr in longWordsList:
        if wordStr.startswith('<p>'):
            wordStr = wordStr.replace('<p>', '')
        if wordStr.startswith('<'):
            continue
        if len(wordStr) == 76:
            if wordStr.upper() == wordStr:
                # tox address
                continue
        if '=\"' in wordStr:
            continue
        if '@' in wordStr:
            if '@@' not in wordStr:
                continue
        if '=.ed25519' in wordStr:
            continue
        if '.onion' in wordStr:
            continue
        if '.i2p' in wordStr:
            continue
        if 'https:' in wordStr:
            continue
        elif 'http:' in wordStr:
            continue
        elif 'i2p:' in wordStr:
            continue
        elif 'gnunet:' in wordStr:
            continue
        elif 'dat:' in wordStr:
            continue
        elif 'rad:' in wordStr:
            continue
        elif 'hyper:' in wordStr:
            continue
        elif 'briar:' in wordStr:
            continue
        if '<' in wordStr:
            replaceWord = wordStr.split('<', 1)[0]
            # if len(replaceWord) > maxWordLength:
            #     replaceWord = replaceWord[:maxWordLength]
            content = content.replace(wordStr, replaceWord)
            wordStr = replaceWord
        if '/' in wordStr:
            continue
        if len(wordStr[maxWordLength:]) < maxWordLength:
            content = content.replace(wordStr,
                                      wordStr[:maxWordLength] + '\n' +
                                      wordStr[maxWordLength:])
        else:
            content = content.replace(wordStr,
                                      wordStr[:maxWordLength])
    if content.startswith('<p>'):
        if not content.endswith('</p>'):
            content = content.strip() + '</p>'
    return content


def _load_auto_tags(base_dir: str, nickname: str, domain: str) -> []:
    """Loads automatic tags file and returns a list containing
    the lines of the file
    """
    filename = acct_dir(base_dir, nickname, domain) + '/autotags.txt'
    if not os.path.isfile(filename):
        return []
    try:
        with open(filename, 'r') as f:
            return f.readlines()
    except OSError:
        print('EX: unable to read auto tags ' + filename)
    return []


def _auto_tag(base_dir: str, nickname: str, domain: str,
              wordStr: str, autoTagList: [],
              appendTags: []):
    """Generates a list of tags to be automatically appended to the content
    """
    for tagRule in autoTagList:
        if wordStr not in tagRule:
            continue
        if '->' not in tagRule:
            continue
        rulematch = tagRule.split('->')[0].strip()
        if rulematch != wordStr:
            continue
        tagName = tagRule.split('->')[1].strip()
        if tagName.startswith('#'):
            if tagName not in appendTags:
                appendTags.append(tagName)
        else:
            if '#' + tagName not in appendTags:
                appendTags.append('#' + tagName)


def add_html_tags(base_dir: str, http_prefix: str,
                  nickname: str, domain: str, content: str,
                  recipients: [], hashtags: {},
                  isJsonContent: bool = False) -> str:
    """ Replaces plaintext mentions such as @nick@domain into html
    by matching against known following accounts
    """
    if content.startswith('<p>'):
        content = html_replace_email_quote(content)
        return html_replace_quote_marks(content)
    maxWordLength = 40
    content = content.replace('\r', '')
    content = content.replace('\n', ' --linebreak-- ')
    content = _add_music_tag(content, 'nowplaying')
    contentSimplified = \
        content.replace(',', ' ').replace(';', ' ').replace('- ', ' ')
    contentSimplified = contentSimplified.replace('. ', ' ').strip()
    if contentSimplified.endswith('.'):
        contentSimplified = contentSimplified[:len(contentSimplified)-1]
    words = contentSimplified.split(' ')

    # remove . for words which are not mentions
    newWords = []
    for wordIndex in range(0, len(words)):
        wordStr = words[wordIndex]
        if wordStr.endswith('.'):
            if not wordStr.startswith('@'):
                wordStr = wordStr[:-1]
        if wordStr.startswith('.'):
            wordStr = wordStr[1:]
        newWords.append(wordStr)
    words = newWords

    replaceMentions = {}
    replaceHashTags = {}
    replaceEmoji = {}
    emojiDict = {}
    originalDomain = domain
    domain = remove_domain_port(domain)
    followingFilename = acct_dir(base_dir, nickname, domain) + '/following.txt'

    # read the following list so that we can detect just @nick
    # in addition to @nick@domain
    following = None
    petnames = None
    if '@' in words:
        if os.path.isfile(followingFilename):
            following = []
            try:
                with open(followingFilename, 'r') as f:
                    following = f.readlines()
            except OSError:
                print('EX: unable to read ' + followingFilename)
            for handle in following:
                pet = get_pet_name(base_dir, nickname, domain, handle)
                if pet:
                    petnames.append(pet + '\n')

    # extract mentions and tags from words
    longWordsList = []
    prevWordStr = ''
    autoTagsList = _load_auto_tags(base_dir, nickname, domain)
    appendTags = []
    for wordStr in words:
        wordLen = len(wordStr)
        if wordLen > 2:
            if wordLen > maxWordLength:
                longWordsList.append(wordStr)
            firstChar = wordStr[0]
            if firstChar == '@':
                if _add_mention(wordStr, http_prefix, following, petnames,
                                replaceMentions, recipients, hashtags):
                    prevWordStr = ''
                    continue
            elif firstChar == '#':
                # remove any endings from the hashtag
                hashTagEndings = ('.', ':', ';', '-', '\n')
                for ending in hashTagEndings:
                    if wordStr.endswith(ending):
                        wordStr = wordStr[:len(wordStr) - 1]
                        break

                if _add_hash_tags(wordStr, http_prefix, originalDomain,
                                  replaceHashTags, hashtags):
                    prevWordStr = ''
                    continue
            elif ':' in wordStr:
                wordStr2 = wordStr.split(':')[1]
#                print('TAG: emoji located - ' + wordStr)
                if not emojiDict:
                    # emoji.json is generated so that it can be customized and
                    # the changes will be retained even if default_emoji.json
                    # is subsequently updated
                    if not os.path.isfile(base_dir + '/emoji/emoji.json'):
                        copyfile(base_dir + '/emoji/default_emoji.json',
                                 base_dir + '/emoji/emoji.json')
                emojiDict = load_json(base_dir + '/emoji/emoji.json')

                # append custom emoji to the dict
                if os.path.isfile(base_dir + '/emojicustom/emoji.json'):
                    customEmojiDict = \
                        load_json(base_dir + '/emojicustom/emoji.json')
                    if customEmojiDict:
                        emojiDict = dict(emojiDict, **customEmojiDict)

#                print('TAG: looking up emoji for :' + wordStr2 + ':')
                _add_emoji(base_dir, ':' + wordStr2 + ':', http_prefix,
                           originalDomain, replaceEmoji, hashtags,
                           emojiDict)
            else:
                if _auto_tag(base_dir, nickname, domain, wordStr,
                             autoTagsList, appendTags):
                    prevWordStr = ''
                    continue
                if prevWordStr:
                    if _auto_tag(base_dir, nickname, domain,
                                 prevWordStr + ' ' + wordStr,
                                 autoTagsList, appendTags):
                        prevWordStr = ''
                        continue
            prevWordStr = wordStr

    # add any auto generated tags
    for appended in appendTags:
        content = content + ' ' + appended
        _add_hash_tags(appended, http_prefix, originalDomain,
                       replaceHashTags, hashtags)

    # replace words with their html versions
    for wordStr, replaceStr in replaceMentions.items():
        content = content.replace(wordStr, replaceStr)
    for wordStr, replaceStr in replaceHashTags.items():
        content = content.replace(wordStr, replaceStr)
    if not isJsonContent:
        for wordStr, replaceStr in replaceEmoji.items():
            content = content.replace(wordStr, replaceStr)

    content = add_web_links(content)
    if longWordsList:
        content = remove_long_words(content, maxWordLength, longWordsList)
    content = limit_repeated_words(content, 6)
    content = content.replace(' --linebreak-- ', '</p><p>')
    content = html_replace_email_quote(content)
    return '<p>' + html_replace_quote_marks(content) + '</p>'


def get_mentions_from_html(htmlText: str,
                           matchStr="<span class=\"h-card\"><a href=\"") -> []:
    """Extracts mentioned actors from the given html content string
    """
    mentions = []
    if matchStr not in htmlText:
        return mentions
    mentionsList = htmlText.split(matchStr)
    for mentionStr in mentionsList:
        if '"' not in mentionStr:
            continue
        actorStr = mentionStr.split('"')[0]
        if actorStr.startswith('http') or \
           actorStr.startswith('gnunet') or \
           actorStr.startswith('i2p') or \
           actorStr.startswith('hyper') or \
           actorStr.startswith('dat:'):
            if actorStr not in mentions:
                mentions.append(actorStr)
    return mentions


def extract_media_in_form_post(postBytes, boundary, name: str):
    """Extracts the binary encoding for image/video/audio within a http
    form POST
    Returns the media bytes and the remaining bytes
    """
    imageStartBoundary = b'Content-Disposition: form-data; name="' + \
        name.encode('utf8', 'ignore') + b'";'
    imageStartLocation = postBytes.find(imageStartBoundary)
    if imageStartLocation == -1:
        return None, postBytes

    # bytes after the start boundary appears
    mediaBytes = postBytes[imageStartLocation:]

    # look for the next boundary
    imageEndBoundary = boundary.encode('utf8', 'ignore')
    imageEndLocation = mediaBytes.find(imageEndBoundary)
    if imageEndLocation == -1:
        # no ending boundary
        return mediaBytes, postBytes[:imageStartLocation]

    # remaining bytes after the end of the image
    remainder = mediaBytes[imageEndLocation:]

    # remove bytes after the end boundary
    mediaBytes = mediaBytes[:imageEndLocation]

    # return the media and the before+after bytes
    return mediaBytes, postBytes[:imageStartLocation] + remainder


def save_media_in_form_post(mediaBytes, debug: bool,
                            filenameBase: str = None) -> (str, str):
    """Saves the given media bytes extracted from http form POST
    Returns the filename and attachment type
    """
    if not mediaBytes:
        if filenameBase:
            # remove any existing files
            extensionTypes = get_image_extensions()
            for ex in extensionTypes:
                possibleOtherFormat = filenameBase + '.' + ex
                if os.path.isfile(possibleOtherFormat):
                    try:
                        os.remove(possibleOtherFormat)
                    except OSError:
                        if debug:
                            print('EX: save_media_in_form_post ' +
                                  'unable to delete other ' +
                                  str(possibleOtherFormat))
            if os.path.isfile(filenameBase):
                try:
                    os.remove(filenameBase)
                except OSError:
                    if debug:
                        print('EX: save_media_in_form_post ' +
                              'unable to delete ' +
                              str(filenameBase))

        if debug:
            print('DEBUG: No media found within POST')
        return None, None

    mediaLocation = -1
    searchStr = ''
    filename = None

    # directly search the binary array for the beginning
    # of an image
    extensionList = {
        'png': 'image/png',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'svg': 'image/svg+xml',
        'webp': 'image/webp',
        'avif': 'image/avif',
        'mp4': 'video/mp4',
        'ogv': 'video/ogv',
        'mp3': 'audio/mpeg',
        'ogg': 'audio/ogg',
        'flac': 'audio/flac',
        'zip': 'application/zip'
    }
    detectedExtension = None
    for extension, content_type in extensionList.items():
        searchStr = b'Content-Type: ' + content_type.encode('utf8', 'ignore')
        mediaLocation = mediaBytes.find(searchStr)
        if mediaLocation > -1:
            # image/video/audio binaries
            if extension == 'jpeg':
                extension = 'jpg'
            elif extension == 'mpeg':
                extension = 'mp3'
            if filenameBase:
                filename = filenameBase + '.' + extension
            attachmentMediaType = \
                searchStr.decode().split('/')[0].replace('Content-Type: ', '')
            detectedExtension = extension
            break

    if not filename:
        return None, None

    # locate the beginning of the image, after any
    # carriage returns
    startPos = mediaLocation + len(searchStr)
    for offset in range(1, 8):
        if mediaBytes[startPos+offset] != 10:
            if mediaBytes[startPos+offset] != 13:
                startPos += offset
                break

    # remove any existing image files with a different format
    if detectedExtension != 'zip':
        extensionTypes = get_image_extensions()
        for ex in extensionTypes:
            if ex == detectedExtension:
                continue
            possibleOtherFormat = \
                filename.replace('.temp', '').replace('.' +
                                                      detectedExtension, '.' +
                                                      ex)
            if os.path.isfile(possibleOtherFormat):
                try:
                    os.remove(possibleOtherFormat)
                except OSError:
                    if debug:
                        print('EX: save_media_in_form_post ' +
                              'unable to delete other 2 ' +
                              str(possibleOtherFormat))

    # don't allow scripts within svg files
    if detectedExtension == 'svg':
        svgStr = mediaBytes[startPos:]
        svgStr = svgStr.decode()
        if dangerous_svg(svgStr, False):
            return None, None

    try:
        with open(filename, 'wb') as fp:
            fp.write(mediaBytes[startPos:])
    except OSError:
        print('EX: unable to write media')

    if not os.path.isfile(filename):
        print('WARN: Media file could not be written to file: ' + filename)
        return None, None
    print('Uploaded media file written: ' + filename)

    return filename, attachmentMediaType


def extract_text_fields_in_post(postBytes, boundary: str, debug: bool,
                                unit_testData: str = None) -> {}:
    """Returns a dictionary containing the text fields of a http form POST
    The boundary argument comes from the http header
    """
    if not unit_testData:
        msgBytes = email.parser.BytesParser().parsebytes(postBytes)
        messageFields = msgBytes.get_payload(decode=True).decode('utf-8')
    else:
        messageFields = unit_testData

    if debug:
        print('DEBUG: POST arriving ' + messageFields)

    messageFields = messageFields.split(boundary)
    fields = {}
    fieldsWithSemicolonAllowed = (
        'message', 'bio', 'autoCW', 'password', 'passwordconfirm',
        'instanceDescription', 'instanceDescriptionShort',
        'subject', 'location', 'imageDescription'
    )
    # examine each section of the POST, separated by the boundary
    for f in messageFields:
        if f == '--':
            continue
        if ' name="' not in f:
            continue
        postStr = f.split(' name="', 1)[1]
        if '"' not in postStr:
            continue
        postKey = postStr.split('"', 1)[0]
        postValueStr = postStr.split('"', 1)[1]
        if ';' in postValueStr:
            if postKey not in fieldsWithSemicolonAllowed and \
               not postKey.startswith('edited'):
                continue
        if '\r\n' not in postValueStr:
            continue
        postLines = postValueStr.split('\r\n')
        postValue = ''
        if len(postLines) > 2:
            for line in range(2, len(postLines)-1):
                if line > 2:
                    postValue += '\n'
                postValue += postLines[line]
        fields[postKey] = urllib.parse.unquote(postValue)
    return fields


def limit_repeated_words(text: str, maxRepeats: int) -> str:
    """Removes words which are repeated many times
    """
    words = text.replace('\n', ' ').split(' ')
    repeatCtr = 0
    repeatedText = ''
    replacements = {}
    prevWord = ''
    for word in words:
        if word == prevWord:
            repeatCtr += 1
            if repeatedText:
                repeatedText += ' ' + word
            else:
                repeatedText = word + ' ' + word
        else:
            if repeatCtr > maxRepeats:
                newText = ((prevWord + ' ') * maxRepeats).strip()
                replacements[prevWord] = [repeatedText, newText]
            repeatCtr = 0
            repeatedText = ''
        prevWord = word

    if repeatCtr > maxRepeats:
        newText = ((prevWord + ' ') * maxRepeats).strip()
        replacements[prevWord] = [repeatedText, newText]

    for word, item in replacements.items():
        text = text.replace(item[0], item[1])
    return text


def get_price_from_string(priceStr: str) -> (str, str):
    """Returns the item price and currency
    """
    currencies = get_currencies()
    for symbol, name in currencies.items():
        if symbol in priceStr:
            price = priceStr.replace(symbol, '')
            if is_float(price):
                return price, name
        elif name in priceStr:
            price = priceStr.replace(name, '')
            if is_float(price):
                return price, name
    if is_float(priceStr):
        return priceStr, "EUR"
    return "0.00", "EUR"


def _words_similarity_histogram(words: []) -> {}:
    """Returns a histogram for word combinations
    """
    histogram = {}
    for index in range(1, len(words)):
        combinedWords = words[index - 1] + words[index]
        if histogram.get(combinedWords):
            histogram[combinedWords] += 1
        else:
            histogram[combinedWords] = 1
    return histogram


def _words_similarity_words_list(content: str) -> []:
    """Returns a list of words for the given content
    """
    removePunctuation = ('.', ',', ';', '-', ':', '"')
    content = remove_html(content).lower()
    for p in removePunctuation:
        content = content.replace(p, ' ')
        content = content.replace('  ', ' ')
    return content.split(' ')


def words_similarity(content1: str, content2: str, minWords: int) -> int:
    """Returns percentage similarity
    """
    if content1 == content2:
        return 100

    words1 = _words_similarity_words_list(content1)
    if len(words1) < minWords:
        return 0

    words2 = _words_similarity_words_list(content2)
    if len(words2) < minWords:
        return 0

    histogram1 = _words_similarity_histogram(words1)
    histogram2 = _words_similarity_histogram(words2)

    diff = 0
    for combinedWords, hits in histogram1.items():
        if not histogram2.get(combinedWords):
            diff += 1
        else:
            diff += abs(histogram2[combinedWords] - histogram1[combinedWords])
    return 100 - int(diff * 100 / len(histogram1.items()))


def contains_invalid_local_links(content: str) -> bool:
    """Returns true if the given content has invalid links
    """
    invalidStrings = (
        'mute', 'unmute', 'editeventpost', 'notifypost',
        'delete', 'options', 'page', 'repeat',
        'bm', 'tl', 'actor', 'unrepeat', 'eventid',
        'unannounce', 'like', 'unlike', 'bookmark',
        'unbookmark', 'likedBy', 'time',
        'year', 'month', 'day', 'editnewpost',
        'graph', 'showshare', 'category', 'showwanted',
        'rmshare', 'rmwanted', 'repeatprivate',
        'unrepeatprivate', 'replyto',
        'replyfollowers', 'replydm', 'editblogpost',
        'handle', 'blockdomain'
    )
    for invStr in invalidStrings:
        if '?' + invStr + '=' in content:
            return True
    return False
