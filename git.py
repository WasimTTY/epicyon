__filename__ = "git.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.1.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@freedombone.net"
__status__ = "Production"

import os
import html


def gitFormatContent(content: str) -> str:
    """ replace html formatting, so that it's more
    like the original patch file
    """
    patchStr = content.replace('<br>', '\n').replace('<br />', '\n')
    patchStr = patchStr.replace('<p>', '').replace('</p>', '\n')
    patchStr = html.unescape(patchStr)
    if 'From ' in patchStr:
        patchStr = 'From ' + patchStr.split('From ', 1)[1]
    return patchStr


def getGitProjectName(baseDir: str, nickname: str, domain: str,
                      subject: str) -> str:
    """Returns the project name for a git patch
    The project name should be contained within the subject line
    and should match against a list of projects which the account
    holder wants to receive
    """
    gitProjectsFilename = \
        baseDir + '/accounts/' + nickname + '@' + domain + '/gitprojects.txt'
    if not os.path.isfile(gitProjectsFilename):
        return None
    subjectLineWords = subject.lower().split(' ')
    for word in subjectLineWords:
        if word in open(gitProjectsFilename).read():
            return word
    return None


def isGitPatch(baseDir: str, nickname: str, domain: str,
               messageType: str,
               subject: str, content: str,
               checkProjectName=True) -> bool:
    """Is the given post content a git patch?
    """
    if messageType != 'Note' and \
       messageType != 'Commit':
        return False
    # must have a subject line
    if not subject:
        return False
    if '[PATCH]' not in content:
        return False
    if '---' not in content:
        return False
    if 'diff ' not in content:
        return False
    if 'From ' not in content:
        return False
    if 'From:' not in content:
        return False
    if 'Date:' not in content:
        return False
    if 'Subject:' not in content:
        return False
    if '<br>' not in content:
        if '<br />' not in content:
            return False
    if checkProjectName:
        projectName = \
            getGitProjectName(baseDir, nickname, domain, subject)
        if not projectName:
            return False
    return True


def getGitHash(patchStr: str) -> str:
    """Returns the commit hash from a given patch
    """
    patchLines = patchStr.split('\n')
    for line in patchLines:
        if line.startswith('From '):
            words = line.split(' ')
            if len(words) > 1:
                if len(words[1]) > 20:
                    return words[1]
            break
    return None


def convertPostToCommit(baseDir: str, nickname: str, domain: str,
                        postJsonObject: {}) -> bool:
    """Detects whether the given post contains a patch
    and if so then converts it to a Commit ActivityPub type
    """
    if not postJsonObject.get('object'):
        return False
    if not isinstance(postJsonObject['object'], dict):
        return False
    if not postJsonObject['object'].get('type'):
        return False
    if postJsonObject['object']['type'] == 'Commit':
        return True
    if not postJsonObject['object'].get('summary'):
        return False
    if not postJsonObject['object'].get('content'):
        return False
    if not postJsonObject['object'].get('attributedTo'):
        return False
    if not isGitPatch(baseDir, nickname, domain,
                      postJsonObject['object']['type'],
                      postJsonObject['object']['summary'],
                      postJsonObject['object']['content'],
                      False):
        return False
    postJsonObject['object']['type'] = 'Commit'
    # add a commitedBy parameter
    if not postJsonObject['object'].get('committedBy'):
        postJsonObject['object']['committedBy'] = \
            postJsonObject['object']['attributedTo']
    patchStr = gitFormatContent(postJsonObject['object']['content'])
    commitHash = getGitHash(patchStr)
    if commitHash:
        postJsonObject['object']['hash'] = commitHash
    postJsonObject['object']['description'] = {
        "mediaType": "text/plain",
        "content": patchStr
    }
    print('Converted post to Commit type')
    return True


def gitAddFromHandle(patchStr: str, handle: str) -> str:
    """Adds the activitypub handle of the sender to the patch
    """
    fromStr = 'AP-signed-off-by: '
    if fromStr in patchStr:
        return patchStr

    patchLines = patchStr.split('\n')
    patchStr = ''
    for line in patchLines:
        patchStr += line + '\n'
        if line.startswith('From:'):
            if fromStr not in patchStr:
                patchStr += fromStr + handle + '\n'
    return patchStr


def receiveGitPatch(baseDir: str, nickname: str, domain: str,
                    subject: str, content: str,
                    fromNickname: str, fromDomain: str) -> bool:
    """Receive a git patch
    """
    if not isGitPatch(baseDir, nickname, domain,
                      subject, content):
        return False

    patchStr = gitFormatContent(content)

    patchLines = patchStr.split('\n')
    patchFilename = None
    projectDir = None
    patchesDir = \
        baseDir + '/accounts/' + nickname + '@' + domain + \
        '/patches'
    # get the subject line and turn it into a filename
    for line in patchLines:
        if line.startswith('Subject:'):
            patchSubject = \
                line.replace('Subject:', '').replace('/', '|')
            patchSubject = patchSubject.replace('[PATCH]', '').strip()
            patchSubject = patchSubject.replace(' ', '_')
            projectName = \
                getGitProjectName(baseDir, nickname, domain, subject)
            if not os.path.isdir(patchesDir):
                os.mkdir(patchesDir)
            projectDir = patchesDir + '/' + projectName
            if not os.path.isdir(projectDir):
                os.mkdir(projectDir)
            patchFilename = \
                projectDir + '/' + patchSubject + '.patch'
            break
    if not patchFilename:
        return False
    patchStr = \
        gitAddFromHandle(patchStr, '@' + fromNickname + '@' + fromDomain)
    with open(patchFilename, "w") as patchFile:
        patchFile.write(patchStr)
        patchNotifyFilename = \
            baseDir + '/accounts/' + \
            nickname + '@' + domain + '/.newPatchContent'
        with open(patchNotifyFilename, "w") as patchFile:
            patchFile.write(patchStr)
            return True
    return False
