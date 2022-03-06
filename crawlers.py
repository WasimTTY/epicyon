__filename__ = "crawlers.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.3.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Core"

import os
import time
from utils import save_json
from utils import user_agent_domain
from blocking import update_blocked_cache
from blocking import is_blocked_domain

default_user_agent_blocks = [
    'fedilist'
]


def update_known_crawlers(ua_str: str,
                          base_dir: str, known_crawlers: {},
                          last_known_crawler: int):
    """Updates a dictionary of known crawlers accessing nodeinfo
    or the masto API
    """
    if not ua_str:
        return None

    curr_time = int(time.time())
    if known_crawlers.get(ua_str):
        known_crawlers[ua_str]['hits'] += 1
        known_crawlers[ua_str]['lastseen'] = curr_time
    else:
        known_crawlers[ua_str] = {
            "lastseen": curr_time,
            "hits": 1
        }

    if curr_time - last_known_crawler >= 30:
        # remove any old observations
        remove_crawlers = []
        for uagent, item in known_crawlers.items():
            if curr_time - item['lastseen'] >= 60 * 60 * 24 * 30:
                remove_crawlers.append(uagent)
        for uagent in remove_crawlers:
            del known_crawlers[uagent]
        # save the list of crawlers
        save_json(known_crawlers,
                  base_dir + '/accounts/knownCrawlers.json')
    return curr_time


def load_known_web_crawlers(base_dir: str) -> []:
    """Returns a list of known web crawlers
    """
    known_crawlers_filename = base_dir + '/accounts/known_web_bots.txt'
    if not os.path.isfile(known_crawlers_filename):
        return []
    crawlers_str = None
    try:
        with open(known_crawlers_filename, 'r') as fp_crawlers:
            crawlers_str = fp_crawlers.read()
    except OSError:
        print('EX: unable to load web crawlers from ' +
              known_crawlers_filename)
    if not crawlers_str:
        return []
    known_crawlers = []
    crawlers_list = crawlers_str.split('\n')
    for crawler in crawlers_list:
        if not crawler:
            continue
        crawler = crawler.replace('\n', '').strip()
        if not crawler:
            continue
        if crawler not in known_crawlers:
            known_crawlers.append(crawler)
    return known_crawlers


def _save_known_web_crawlers(base_dir: str, known_crawlers: []) -> bool:
    """Saves a list of known web crawlers
    """
    known_crawlers_filename = base_dir + '/accounts/known_web_bots.txt'
    known_crawlers_str = ''
    for crawler in known_crawlers:
        known_crawlers_str += crawler.strip() + '\n'
    try:
        with open(known_crawlers_filename, 'w+') as fp_crawlers:
            fp_crawlers.write(known_crawlers_str)
    except OSError:
        print("EX: unable to save known web crawlers to " +
              known_crawlers_filename)
        return False
    return True


def blocked_user_agent(calling_domain: str, agent_str: str,
                       news_instance: bool, debug: bool,
                       user_agents_blocked: [],
                       blocked_cache_last_updated,
                       base_dir: str,
                       blocked_cache: [],
                       blocked_cache_update_secs: int,
                       crawlers_allowed: [],
                       known_crawlers: []):
    """Should a GET or POST be blocked based upon its user agent?
    """
    if not agent_str:
        return False, blocked_cache_last_updated

    agent_str_lower = agent_str.lower()
    for ua_block in default_user_agent_blocks:
        if ua_block in agent_str_lower:
            print('Blocked User agent: ' + ua_block)
            return True, blocked_cache_last_updated

    agent_domain = None

    if agent_str:
        # is this a web crawler? If so then block it by default
        # unless this is a news instance or if it is in the allowed list
        if 'bot/' in agent_str_lower or 'bot-' in agent_str_lower:
            if agent_str_lower not in known_crawlers:
                known_crawlers.append(agent_str_lower)
                known_crawlers.sort()
                _save_known_web_crawlers(base_dir, known_crawlers)
            # if this is a news instance then we want it
            # to be indexed by search engines
            if news_instance:
                return False, blocked_cache_last_updated
            # is this crawler allowed?
            for crawler in crawlers_allowed:
                if crawler.lower() in agent_str_lower:
                    return False, blocked_cache_last_updated
            print('Blocked Crawler: ' + agent_str)
            return True, blocked_cache_last_updated
        # get domain name from User-Agent
        agent_domain = user_agent_domain(agent_str, debug)
    else:
        # no User-Agent header is present
        return True, blocked_cache_last_updated

    # is the User-Agent type blocked? eg. "Mastodon"
    if user_agents_blocked:
        blocked_ua = False
        for agent_name in user_agents_blocked:
            if agent_name in agent_str:
                blocked_ua = True
                break
        if blocked_ua:
            return True, blocked_cache_last_updated

    if not agent_domain:
        return False, blocked_cache_last_updated

    # is the User-Agent domain blocked
    blocked_ua = False
    if not agent_domain.startswith(calling_domain):
        blocked_cache_last_updated = \
            update_blocked_cache(base_dir, blocked_cache,
                                 blocked_cache_last_updated,
                                 blocked_cache_update_secs)

        blocked_ua = \
            is_blocked_domain(base_dir, agent_domain, blocked_cache)
        # if self.server.debug:
        if blocked_ua:
            print('Blocked User agent: ' + agent_domain)
    return blocked_ua, blocked_cache_last_updated
