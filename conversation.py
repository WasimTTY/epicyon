__filename__ = "conversation.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Timeline"

import os
from utils import hasObjectDict
from utils import acctDir


def updateConversation(baseDir: str, nickname: str, domain: str,
                       postJsonObject: {}) -> bool:
    """Ads a post to a conversation index in the /conversation subdirectory
    """
    if not hasObjectDict(postJsonObject):
        return False
    if not postJsonObject['object'].get('conversation'):
        return False
    if not postJsonObject['object'].get('id'):
        return False
    conversationDir = acctDir(baseDir, nickname, domain) + '/conversation'
    if not os.path.isdir(conversationDir):
        os.mkdir(conversationDir)
    conversationId = postJsonObject['object']['conversation']
    conversationId = conversationId.replace('/', '#')
    postId = postJsonObject['object']['id']
    conversationFilename = conversationDir + '/' + conversationId
    if not os.path.isfile(conversationFilename):
        try:
            with open(conversationFilename, 'w+') as fp:
                fp.write(postId + '\n')
                return True
        except BaseException:
            pass
    elif postId + '\n' not in open(conversationFilename).read():
        try:
            with open(conversationFilename, 'a+') as fp:
                fp.write(postId + '\n')
                return True
        except BaseException:
            pass
    return False


def muteConversation(baseDir: str, nickname: str, domain: str,
                     conversationId: str) -> None:
    """Mutes the given conversation
    """
    conversationDir = acctDir(baseDir, nickname, domain) + '/conversation'
    conversationFilename = \
        conversationDir + '/' + conversationId.replace('/', '#')
    if not os.path.isfile(conversationFilename):
        return
    if os.path.isfile(conversationFilename + '.muted'):
        return
    with open(conversationFilename + '.muted', 'w+') as fp:
        fp.write('\n')


def unmuteConversation(baseDir: str, nickname: str, domain: str,
                       conversationId: str) -> None:
    """Unmutes the given conversation
    """
    conversationDir = acctDir(baseDir, nickname, domain) + '/conversation'
    conversationFilename = \
        conversationDir + '/' + conversationId.replace('/', '#')
    if not os.path.isfile(conversationFilename):
        return
    if not os.path.isfile(conversationFilename + '.muted'):
        return
    try:
        os.remove(conversationFilename + '.muted')
    except BaseException:
        pass
