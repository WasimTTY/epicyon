__filename__ = "skills.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Profile Metadata"

import os
from webfinger import webfinger_handle
from auth import create_basic_auth_header
from posts import get_person_box
from session import post_json
from utils import has_object_string
from utils import get_full_domain
from utils import get_nickname_from_actor
from utils import get_domain_from_actor
from utils import load_json
from utils import get_occupation_skills
from utils import set_occupation_skills_list
from utils import acct_dir
from utils import local_actor_url
from utils import has_actor


def set_skills_from_dict(actor_json: {}, skillsDict: {}) -> []:
    """Converts a dict containing skills to a list
    Returns the string version of the dictionary
    """
    skillsList = []
    for name, value in skillsDict.items():
        skillsList.append(name + ':' + str(value))
    set_occupation_skills_list(actor_json, skillsList)
    return skillsList


def get_skills_from_list(skillsList: []) -> {}:
    """Returns a dict of skills from a list
    """
    if isinstance(skillsList, list):
        skillsList2 = skillsList
    else:
        skillsList2 = skillsList.split(',')
    skillsDict = {}
    for skill in skillsList2:
        if ':' not in skill:
            continue
        name = skill.split(':')[0].strip().lower()
        valueStr = skill.split(':')[1]
        if not valueStr.isdigit():
            continue
        skillsDict[name] = int(valueStr)
    return skillsDict


def actor_skill_value(actor_json: {}, skillName: str) -> int:
    """Returns The skill level from an actor
    """
    ocSkillsList = get_occupation_skills(actor_json)
    skillsDict = get_skills_from_list(ocSkillsList)
    if not skillsDict:
        return 0
    skillName = skillName.lower()
    if skillsDict.get(skillName):
        return skillsDict[skillName]
    return 0


def no_of_actor_skills(actor_json: {}) -> int:
    """Returns the number of skills that an actor has
    """
    if actor_json.get('hasOccupation'):
        skillsList = get_occupation_skills(actor_json)
        return len(skillsList)
    return 0


def set_actor_skill_level(actor_json: {},
                          skill: str, skillLevelPercent: int) -> bool:
    """Set a skill level for a person
    Setting skill level to zero removes it
    """
    if skillLevelPercent < 0 or skillLevelPercent > 100:
        return False

    if not actor_json:
        return True
    if not actor_json.get('hasOccupation'):
        actor_json['hasOccupation'] = [{
            '@type': 'Occupation',
            'name': '',
            "occupationLocation": {
                "@type": "City",
                "name": "Fediverse"
            },
            'skills': []
        }]
    ocSkillsList = get_occupation_skills(actor_json)
    skillsDict = get_skills_from_list(ocSkillsList)
    if not skillsDict.get(skill):
        if len(skillsDict.items()) >= 32:
            print('WARN: Maximum number of skills reached for ' +
                  actor_json['id'])
            return False
    if skillLevelPercent > 0:
        skillsDict[skill] = skillLevelPercent
    else:
        if skillsDict.get(skill):
            del skillsDict[skill]
    set_skills_from_dict(actor_json, skillsDict)
    return True


def set_skill_level(base_dir: str, nickname: str, domain: str,
                    skill: str, skillLevelPercent: int) -> bool:
    """Set a skill level for a person
    Setting skill level to zero removes it
    """
    if skillLevelPercent < 0 or skillLevelPercent > 100:
        return False
    actorFilename = acct_dir(base_dir, nickname, domain) + '.json'
    if not os.path.isfile(actorFilename):
        return False

    actor_json = load_json(actorFilename)
    return set_actor_skill_level(actor_json,
                                 skill, skillLevelPercent)


def get_skills(base_dir: str, nickname: str, domain: str) -> []:
    """Returns the skills for a given person
    """
    actorFilename = acct_dir(base_dir, nickname, domain) + '.json'
    if not os.path.isfile(actorFilename):
        return False

    actor_json = load_json(actorFilename)
    if actor_json:
        if not actor_json.get('hasOccupation'):
            return None
        ocSkillsList = get_occupation_skills(actor_json)
        return get_skills_from_list(ocSkillsList)
    return None


def outbox_skills(base_dir: str, nickname: str, message_json: {},
                  debug: bool) -> bool:
    """Handles receiving a skills update
    """
    if not message_json.get('type'):
        return False
    if not message_json['type'] == 'Skill':
        return False
    if not has_actor(message_json, debug):
        return False
    if not has_object_string(message_json, debug):
        return False

    actorNickname = get_nickname_from_actor(message_json['actor'])
    if actorNickname != nickname:
        return False
    domain, port = get_domain_from_actor(message_json['actor'])
    skill = message_json['object'].replace('"', '').split(';')[0].strip()
    skillLevelPercentStr = \
        message_json['object'].replace('"', '').split(';')[1].strip()
    skillLevelPercent = 50
    if skillLevelPercentStr.isdigit():
        skillLevelPercent = int(skillLevelPercentStr)

    return set_skill_level(base_dir, nickname, domain,
                           skill, skillLevelPercent)


def send_skill_via_server(base_dir: str, session, nickname: str, password: str,
                          domain: str, port: int,
                          http_prefix: str,
                          skill: str, skillLevelPercent: int,
                          cached_webfingers: {}, person_cache: {},
                          debug: bool, project_version: str,
                          signing_priv_key_pem: str) -> {}:
    """Sets a skill for a person via c2s
    """
    if not session:
        print('WARN: No session for send_skill_via_server')
        return 6

    domain_full = get_full_domain(domain, port)

    actor = local_actor_url(http_prefix, nickname, domain_full)
    toUrl = actor
    ccUrl = actor + '/followers'

    if skillLevelPercent:
        skillStr = skill + ';' + str(skillLevelPercent)
    else:
        skillStr = skill + ';0'

    newSkillJson = {
        'type': 'Skill',
        'actor': actor,
        'object': '"' + skillStr + '"',
        'to': [toUrl],
        'cc': [ccUrl]
    }

    handle = http_prefix + '://' + domain_full + '/@' + nickname

    # lookup the inbox for the To handle
    wfRequest = \
        webfinger_handle(session, handle, http_prefix,
                         cached_webfingers,
                         domain, project_version, debug, False,
                         signing_priv_key_pem)
    if not wfRequest:
        if debug:
            print('DEBUG: skill webfinger failed for ' + handle)
        return 1
    if not isinstance(wfRequest, dict):
        print('WARN: skill webfinger for ' + handle +
              ' did not return a dict. ' + str(wfRequest))
        return 1

    postToBox = 'outbox'

    # get the actor inbox for the To handle
    originDomain = domain
    (inboxUrl, pubKeyId, pubKey, fromPersonId, sharedInbox, avatarUrl,
     displayName, _) = get_person_box(signing_priv_key_pem,
                                      originDomain,
                                      base_dir, session, wfRequest,
                                      person_cache, project_version,
                                      http_prefix, nickname, domain,
                                      postToBox, 76121)

    if not inboxUrl:
        if debug:
            print('DEBUG: skill no ' + postToBox +
                  ' was found for ' + handle)
        return 3
    if not fromPersonId:
        if debug:
            print('DEBUG: skill no actor was found for ' + handle)
        return 4

    authHeader = create_basic_auth_header(nickname, password)

    headers = {
        'host': domain,
        'Content-type': 'application/json',
        'Authorization': authHeader
    }
    postResult = \
        post_json(http_prefix, domain_full,
                  session, newSkillJson, [], inboxUrl,
                  headers, 30, True)
    if not postResult:
        if debug:
            print('DEBUG: POST skill failed for c2s to ' + inboxUrl)
#        return 5

    if debug:
        print('DEBUG: c2s POST skill success')

    return newSkillJson


def actor_has_skill(actor_json: {}, skillName: str) -> bool:
    """Returns true if the given actor has the given skill
    """
    ocSkillsList = get_occupation_skills(actor_json)
    for skillStr in ocSkillsList:
        if skillName + ':' in skillStr:
            return True
    return False
