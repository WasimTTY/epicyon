__filename__ = "availability.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Profile Metadata"

import os
from webfinger import webfingerHandle
from auth import createBasicAuthHeader
from posts import getPersonBox
from session import postJson
from utils import hasObjectString
from utils import getFullDomain
from utils import getNicknameFromActor
from utils import getDomainFromActor
from utils import loadJson
from utils import saveJson
from utils import acctDir
from utils import localActorUrl
from utils import hasActor


def setAvailability(base_dir: str, nickname: str, domain: str,
                    status: str) -> bool:
    """Set an availability status
    """
    # avoid giant strings
    if len(status) > 128:
        return False
    actorFilename = acctDir(base_dir, nickname, domain) + '.json'
    if not os.path.isfile(actorFilename):
        return False
    actorJson = loadJson(actorFilename)
    if actorJson:
        actorJson['availability'] = status
        saveJson(actorJson, actorFilename)
    return True


def getAvailability(base_dir: str, nickname: str, domain: str) -> str:
    """Returns the availability for a given person
    """
    actorFilename = acctDir(base_dir, nickname, domain) + '.json'
    if not os.path.isfile(actorFilename):
        return False
    actorJson = loadJson(actorFilename)
    if actorJson:
        if not actorJson.get('availability'):
            return None
        return actorJson['availability']
    return None


def outboxAvailability(base_dir: str, nickname: str, messageJson: {},
                       debug: bool) -> bool:
    """Handles receiving an availability update
    """
    if not messageJson.get('type'):
        return False
    if not messageJson['type'] == 'Availability':
        return False
    if not hasActor(messageJson, debug):
        return False
    if not hasObjectString(messageJson, debug):
        return False

    actorNickname = getNicknameFromActor(messageJson['actor'])
    if actorNickname != nickname:
        return False
    domain, port = getDomainFromActor(messageJson['actor'])
    status = messageJson['object'].replace('"', '')

    return setAvailability(base_dir, nickname, domain, status)


def sendAvailabilityViaServer(base_dir: str, session,
                              nickname: str, password: str,
                              domain: str, port: int,
                              http_prefix: str,
                              status: str,
                              cachedWebfingers: {}, person_cache: {},
                              debug: bool, project_version: str,
                              signingPrivateKeyPem: str) -> {}:
    """Sets the availability for a person via c2s
    """
    if not session:
        print('WARN: No session for sendAvailabilityViaServer')
        return 6

    domainFull = getFullDomain(domain, port)

    toUrl = localActorUrl(http_prefix, nickname, domainFull)
    ccUrl = toUrl + '/followers'

    newAvailabilityJson = {
        'type': 'Availability',
        'actor': toUrl,
        'object': '"' + status + '"',
        'to': [toUrl],
        'cc': [ccUrl]
    }

    handle = http_prefix + '://' + domainFull + '/@' + nickname

    # lookup the inbox for the To handle
    wfRequest = webfingerHandle(session, handle, http_prefix,
                                cachedWebfingers,
                                domain, project_version, debug, False,
                                signingPrivateKeyPem)
    if not wfRequest:
        if debug:
            print('DEBUG: availability webfinger failed for ' + handle)
        return 1
    if not isinstance(wfRequest, dict):
        print('WARN: availability webfinger for ' + handle +
              ' did not return a dict. ' + str(wfRequest))
        return 1

    postToBox = 'outbox'

    # get the actor inbox for the To handle
    originDomain = domain
    (inboxUrl, pubKeyId, pubKey, fromPersonId, sharedInbox, avatarUrl,
     displayName, _) = getPersonBox(signingPrivateKeyPem,
                                    originDomain,
                                    base_dir, session, wfRequest,
                                    person_cache, project_version,
                                    http_prefix, nickname,
                                    domain, postToBox, 57262)

    if not inboxUrl:
        if debug:
            print('DEBUG: availability no ' + postToBox +
                  ' was found for ' + handle)
        return 3
    if not fromPersonId:
        if debug:
            print('DEBUG: availability no actor was found for ' + handle)
        return 4

    authHeader = createBasicAuthHeader(nickname, password)

    headers = {
        'host': domain,
        'Content-type': 'application/json',
        'Authorization': authHeader
    }
    postResult = postJson(http_prefix, domainFull,
                          session, newAvailabilityJson, [],
                          inboxUrl, headers, 30, True)
    if not postResult:
        print('WARN: availability failed to post')

    if debug:
        print('DEBUG: c2s POST availability success')

    return newAvailabilityJson
