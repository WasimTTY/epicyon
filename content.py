__filename__ = "content.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.1.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@freedombone.net"
__status__ = "Production"

import os
import email.parser
from shutil import copyfile
from utils import loadJson
from utils import fileLastModified


def switchWords(baseDir: str, nickname: str, domain: str, content: str) -> str:
    """Performs word replacements. eg. Trump -> The Orange Menace
    """
    switchWordsFilename = baseDir + '/accounts/' + \
        nickname + '@' + domain + '/replacewords.txt'
    if not os.path.isfile(switchWordsFilename):
        return content
    with open(switchWordsFilename, 'r') as fp:
        for line in fp:
            replaceStr = line.replace('\n', '').replace('\r', '')
            wordTransform = None
            if '->' in replaceStr:
                wordTransform = replaceStr.split('->')
            elif ':' in replaceStr:
                wordTransform = replaceStr.split(':')
            elif ',' in replaceStr:
                wordTransform = replaceStr.split(',')
            elif ';' in replaceStr:
                wordTransform = replaceStr.split(';')
            elif '-' in replaceStr:
                wordTransform = replaceStr.split('-')
            if not wordTransform:
                continue
            if len(wordTransform) == 2:
                replaceStr1 = wordTransform[0].strip().replace('"', '')
                replaceStr2 = wordTransform[1].strip().replace('"', '')
                content = content.replace(replaceStr1, replaceStr2)
    return content


def replaceEmojiFromTags(content: str, tag: [], messageType: str) -> str:
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
                            try:
                                replaceChar = chr(int("0x" + iconName, 16))
                                content = content.replace(tagItem['name'],
                                                          replaceChar)
                            except BaseException:
                                pass
                        else:
                            # sequence of codes
                            iconCodes = iconName.split('-')
                            iconCodeSequence = ''
                            for icode in iconCodes:
                                try:
                                    iconCodeSequence += chr(int("0x" +
                                                                icode, 16))
                                except BaseException:
                                    iconCodeSequence = ''
                                    break
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


def addMusicTag(content: str, tag: str) -> str:
    """If a music link is found then ensure that the post is
    tagged appropriately
    """
    if '#' not in tag:
        tag = '#'+tag
    if tag in content:
        return content
    musicSites = ['soundcloud.com', 'bandcamp.com']
    musicSiteFound = False
    for site in musicSites:
        if site+'/' in content:
            musicSiteFound = True
            break
    if not musicSiteFound:
        return content
    return ':music: ' + content + ' ' + tag + ' '


def addWebLinks(content: str) -> str:
    """Adds markup for web links
    """
    if not ('https://' in content or 'http://' in content):
        return content

    maxLinkLength = 40
    content = content.replace('\r', '')
    words = content.replace('\n', ' --linebreak-- ').split(' ')
    replaceDict = {}
    for w in words:
        if w.startswith('https://') or \
           w.startswith('http://') or \
           w.startswith('i2p://') or \
           w.startswith('gemini://') or \
           w.startswith('gopher://') or \
           w.startswith('hyper://') or \
           w.startswith('dat://'):
            if w.endswith('.') or w.endswith(';'):
                w = w[:-1]
            markup = '<a href="' + w + \
                '" rel="nofollow noopener" target="_blank">'
            if w.startswith('https://'):
                markup += '<span class="invisible">https://</span>'
            elif w.startswith('http://'):
                markup += '<span class="invisible">http://</span>'
            elif w.startswith('i2p://'):
                markup += '<span class="invisible">i2p://</span>'
            elif w.startswith('dat://'):
                markup += '<span class="invisible">dat://</span>'
            elif w.startswith('hyper://'):
                markup += '<span class="invisible">hyper://</span>'
            elif w.startswith('gemini://'):
                markup += '<span class="invisible">gemini://</span>'
            elif w.startswith('gopher://'):
                markup += '<span class="invisible">gopher://</span>'
            linkText = w.replace('https://', '').replace('http://', '')
            linkText = linkText.replace('dat://', '').replace('i2p://', '')
            linkText = linkText.replace('hyper://', '')
            linkText = linkText.replace('gemini://', '')
            linkText = linkText.replace('gopher://', '')
            # prevent links from becoming too long
            if len(linkText) > maxLinkLength:
                markup += '<span class="ellipsis">' + \
                    linkText[:maxLinkLength] + '</span>'
                markup += '<span class="invisible">' + \
                    linkText[maxLinkLength:] + '</span></a>'
            else:
                markup += '<span class="ellipsis">' + linkText + '</span></a>'
            replaceDict[w] = markup
    for url, markup in replaceDict.items():
        content = content.replace(url, markup)
    content = content.replace(' --linebreak-- ', '<br>')
    return content


def validHashTag(hashtag: str) -> bool:
    """Returns true if the give hashtag contains valid characters
    """
    validChars = set('0123456789' +
                     'abcdefghijklmnopqrstuvwxyz' +
                     'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    if set(hashtag).issubset(validChars):
        return True
    return False


def addHashTags(wordStr: str, httpPrefix: str, domain: str,
                replaceHashTags: {}, postHashtags: {}) -> bool:
    """Detects hashtags and adds them to the replacements dict
    Also updates the hashtags list to be added to the post
    """
    if replaceHashTags.get(wordStr):
        return True
    hashtag = wordStr[1:]
    if not validHashTag(hashtag):
        return False
    hashtagUrl = httpPrefix + "://" + domain + "/tags/" + hashtag
    postHashtags[hashtag] = {
        'href': hashtagUrl,
        'name': '#'+hashtag,
        'type': 'Hashtag'
    }
    replaceHashTags[wordStr] = "<a href=\"" + hashtagUrl + \
        "\" class=\"mention hashtag\" rel=\"tag\">#<span>" + \
        hashtag + "</span></a>"
    return True


def loadEmojiDict(emojiDataFilename: str, emojiDict: {}) -> None:
    """Creates an emoji dictionary based on emoji/emoji-data.txt
    """
    if not os.path.isfile(emojiDataFilename):
        return
    with open(emojiDataFilename, "r") as fileHandler:
        for line in fileHandler:
            if len(line) < 5:
                continue
            if line.startswith('#'):
                continue
            if '; Emoji' not in line:
                continue
            if ')' not in line:
                continue
            emojiUnicode = line.split(' ')[0]
            if len(emojiUnicode) < 4:
                continue
            if '..' in emojiUnicode:
                emojiUnicode = emojiUnicode.split('..')[0]
            emojiName = line.split(')', 1)[1].strip()
            emojiName = emojiName.replace('\n', '').replace('\r', '')
            emojiName = emojiName.replace(' ', '').replace('-', '')
            if '..' in emojiName:
                emojiName = emojiName.split('..')[0]
            emojiDict[emojiName.lower()] = emojiUnicode


def addEmoji(baseDir: str, wordStr: str,
             httpPrefix: str, domain: str,
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
    if not validHashTag(emoji):
        return False
    if not emojiDict.get(emoji):
        return False
    emojiFilename = baseDir + '/emoji/' + emojiDict[emoji] + '.png'
    if not os.path.isfile(emojiFilename):
        return False
    emojiUrl = httpPrefix + "://" + domain + \
        "/emoji/" + emojiDict[emoji] + '.png'
    postTags[emoji] = {
        'icon': {
            'mediaType': 'image/png',
            'type': 'Image',
            'url': emojiUrl
        },
        'name': ':'+emoji+':',
        "updated": fileLastModified(emojiFilename),
        "id": emojiUrl.replace('.png', ''),
        'type': 'Emoji'
    }
    return True


def addMention(wordStr: str, httpPrefix: str, following: str,
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
            if follow.startswith(possibleNickname + '@'):
                replaceDomain = \
                    follow.replace('\n', '').replace('\r', '').split('@')[1]
                recipientActor = httpPrefix + "://" + \
                    replaceDomain + "/users/" + possibleNickname
                if recipientActor not in recipients:
                    recipients.append(recipientActor)
                tags[wordStr] = {
                    'href': recipientActor,
                    'name': wordStr,
                    'type': 'Mention'
                }
                replaceMentions[wordStr] = \
                    "<span class=\"h-card\"><a href=\"" + httpPrefix + \
                    "://" + replaceDomain + "/@" + possibleNickname + \
                    "\" class=\"u-url mention\">@<span>" + possibleNickname + \
                    "</span></a></span>"
                return True
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
            recipientActor = httpPrefix + "://" + \
                possibleDomain + "/users/" + possibleNickname
            if recipientActor not in recipients:
                recipients.append(recipientActor)
            tags[wordStr] = {
                'href': recipientActor,
                'name': wordStr,
                'type': 'Mention'
            }
            replaceMentions[wordStr] = \
                "<span class=\"h-card\"><a href=\"" + httpPrefix + \
                "://" + possibleDomain + "/@" + possibleNickname + \
                "\" class=\"u-url mention\">@<span>" + possibleNickname + \
                "</span></a></span>"
            return True
    # @nick@domain
    if not (possibleDomain == 'localhost' or '.' in possibleDomain):
        return False
    recipientActor = httpPrefix + "://" + \
        possibleDomain + "/users/" + possibleNickname
    if recipientActor not in recipients:
        recipients.append(recipientActor)
    tags[wordStr] = {
        'href': recipientActor,
        'name': wordStr,
        'type': 'Mention'
    }
    replaceMentions[wordStr] = \
        "<span class=\"h-card\"><a href=\"" + httpPrefix + \
        "://" + possibleDomain + "/@" + possibleNickname + \
        "\" class=\"u-url mention\">@<span>" + possibleNickname + \
        "</span></a></span>"
    return True


def replaceContentDuplicates(content: str) -> str:
    """Replaces invalid duplicates within content
    """
    while '<<' in content:
        content = content.replace('<<', '<')
    while '>>' in content:
        content = content.replace('>>', '>')
    content = content.replace('<\\p>', '')
    return content


def removeLongWords(content: str, maxWordLength: int,
                    longWordsList: []) -> str:
    """Breaks up long words so that on mobile screens this doesn't
    disrupt the layout
    """
    content = replaceContentDuplicates(content)
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
        elif 'dat:' in wordStr:
            continue
        elif 'hyper:' in wordStr:
            continue
        elif 'briar:' in wordStr:
            continue
        if '<' in wordStr:
            replaceWord = wordStr.split('<', 1)[0]
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
            content = content.strip()+'</p>'
    return content


def addHtmlTags(baseDir: str, httpPrefix: str,
                nickname: str, domain: str, content: str,
                recipients: [], hashtags: {}, isJsonContent=False) -> str:
    """ Replaces plaintext mentions such as @nick@domain into html
    by matching against known following accounts
    """
    if content.startswith('<p>'):
        return content
    maxWordLength = 40
    content = content.replace('\r', '')
    content = content.replace('\n', ' --linebreak-- ')
    content = addMusicTag(content, 'nowplaying')
    words = content.replace(',', ' ').replace(';', ' ').split(' ')

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
    if ':' in domain:
        domain = domain.split(':')[0]
    followingFilename = baseDir + '/accounts/' + \
        nickname + '@' + domain + '/following.txt'

    # read the following list so that we can detect just @nick
    # in addition to @nick@domain
    following = None
    if '@' in words:
        if os.path.isfile(followingFilename):
            with open(followingFilename, "r") as f:
                following = f.readlines()

    # extract mentions and tags from words
    longWordsList = []
    for wordStr in words:
        wordLen = len(wordStr)
        if wordLen > 2:
            if wordLen > maxWordLength:
                longWordsList.append(wordStr)
            firstChar = wordStr[0]
            if firstChar == '@':
                if addMention(wordStr, httpPrefix, following,
                              replaceMentions, recipients, hashtags):
                    continue
            elif firstChar == '#':
                if addHashTags(wordStr, httpPrefix, originalDomain,
                               replaceHashTags, hashtags):
                    continue
            elif ':' in wordStr:
                wordStr2 = wordStr.split(':')[1]
#                print('TAG: emoji located - '+wordStr)
                if not emojiDict:
                    # emoji.json is generated so that it can be customized and
                    # the changes will be retained even if default_emoji.json
                    # is subsequently updated
                    if not os.path.isfile(baseDir + '/emoji/emoji.json'):
                        copyfile(baseDir + '/emoji/default_emoji.json',
                                 baseDir + '/emoji/emoji.json')
                emojiDict = loadJson(baseDir + '/emoji/emoji.json')

#                print('TAG: looking up emoji for :'+wordStr2+':')
                addEmoji(baseDir, ':' + wordStr2 + ':', httpPrefix,
                         originalDomain, replaceEmoji, hashtags,
                         emojiDict)

    # replace words with their html versions
    for wordStr, replaceStr in replaceMentions.items():
        content = content.replace(wordStr, replaceStr)
    for wordStr, replaceStr in replaceHashTags.items():
        content = content.replace(wordStr, replaceStr)
    if not isJsonContent:
        for wordStr, replaceStr in replaceEmoji.items():
            content = content.replace(wordStr, replaceStr)

    content = addWebLinks(content)
    if longWordsList:
        content = removeLongWords(content, maxWordLength, longWordsList)
    content = content.replace(' --linebreak-- ', '</p><p>')
    return '<p>' + content + '</p>'


def getMentionsFromHtml(htmlText: str,
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
           actorStr.startswith('i2p') or \
           actorStr.startswith('hyper') or \
           actorStr.startswith('dat:'):
            if actorStr not in mentions:
                mentions.append(actorStr)
    return mentions


def extractMediaInFormPOST(postBytes, boundary, name: str):
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


def saveMediaInFormPOST(mediaBytes, debug: bool,
                        filenameBase=None) -> (str, str):
    """Saves the given media bytes extracted from http form POST
    Returns the filename and attachment type
    """
    if not mediaBytes:
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
        'webp': 'image/webp',
        'mp4': 'video/mp4',
        'ogv': 'video/ogv',
        'mp3': 'audio/mpeg',
        'ogg': 'audio/ogg'
    }
    detectedExtension = None
    for extension, contentType in extensionList.items():
        searchStr = b'Content-Type: ' + contentType.encode('utf8', 'ignore')
        mediaLocation = mediaBytes.find(searchStr)
        if mediaLocation > -1:
            # image/video/audio binaries
            if extension == 'jpeg':
                extension = 'jpg'
            elif extension == 'mpeg':
                extension = 'mp3'
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
    extensionTypes = ('png', 'jpg', 'jpeg', 'gif', 'webp')
    for ex in extensionTypes:
        if ex == detectedExtension:
            continue
        possibleOtherFormat = \
            filename.replace('.temp', '').replace('.' +
                                                  detectedExtension, '.' +
                                                  ex)
        if os.path.isfile(possibleOtherFormat):
            os.remove(possibleOtherFormat)

    fd = open(filename, 'wb')
    fd.write(mediaBytes[startPos:])
    fd.close()

    return filename, attachmentMediaType


def extractTextFieldsInPOST(postBytes, boundary, debug: bool) -> {}:
    """Returns a dictionary containing the text fields of a http form POST
    The boundary argument comes from the http header
    """
    msg = email.parser.BytesParser().parsebytes(postBytes)
    if debug:
        print('DEBUG: POST arriving ' +
              msg.get_payload(decode=True).decode('utf-8'))
    messageFields = msg.get_payload(decode=True)
    messageFields = messageFields.decode('utf-8').split(boundary)
    fields = {}
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
        fields[postKey] = postValue
    return fields
