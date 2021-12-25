__filename__ = "socnet.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Moderation"

from session import createSession
from webfinger import webfingerHandle
from posts import getPersonBox
from posts import getPostDomains
from utils import getFullDomain


def instancesGraph(base_dir: str, handles: str,
                   proxyType: str,
                   port: int, http_prefix: str,
                   debug: bool, projectVersion: str,
                   systemLanguage: str, signingPrivateKeyPem: str) -> str:
    """ Returns a dot graph of federating instances
    based upon a few sample handles.
    The handles argument should contain a comma separated list
    of handles on different instances
    """
    dotGraphStr = 'digraph instances {\n'
    if ',' not in handles:
        return dotGraphStr + '}\n'
    session = createSession(proxyType)
    if not session:
        return dotGraphStr + '}\n'

    personCache = {}
    cachedWebfingers = {}
    federationList = []
    maxMentions = 99
    maxEmoji = 99
    maxAttachments = 5

    personHandles = handles.split(',')
    for handle in personHandles:
        handle = handle.strip()
        if handle.startswith('@'):
            handle = handle[1:]
        if '@' not in handle:
            continue

        nickname = handle.split('@')[0]
        domain = handle.split('@')[1]

        domainFull = getFullDomain(domain, port)
        handle = http_prefix + "://" + domainFull + "/@" + nickname
        wfRequest = \
            webfingerHandle(session, handle, http_prefix,
                            cachedWebfingers,
                            domain, projectVersion, debug, False,
                            signingPrivateKeyPem)
        if not wfRequest:
            return dotGraphStr + '}\n'
        if not isinstance(wfRequest, dict):
            print('Webfinger for ' + handle + ' did not return a dict. ' +
                  str(wfRequest))
            return dotGraphStr + '}\n'

        originDomain = None
        (personUrl, pubKeyId, pubKey, personId, shaedInbox, avatarUrl,
         displayName, _) = getPersonBox(signingPrivateKeyPem,
                                        originDomain,
                                        base_dir, session, wfRequest,
                                        personCache,
                                        projectVersion, http_prefix,
                                        nickname, domain, 'outbox',
                                        27261)
        wordFrequency = {}
        postDomains = \
            getPostDomains(session, personUrl, 64, maxMentions, maxEmoji,
                           maxAttachments, federationList,
                           personCache, debug,
                           projectVersion, http_prefix, domain,
                           wordFrequency, [], systemLanguage,
                           signingPrivateKeyPem)
        postDomains.sort()
        for fedDomain in postDomains:
            dotLineStr = '    "' + domain + '" -> "' + fedDomain + '";\n'
            if dotLineStr not in dotGraphStr:
                dotGraphStr += dotLineStr
    return dotGraphStr + '}\n'
