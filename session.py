__filename__ = "session.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "0.0.1"
__maintainer__ = "Bob Mottram"
__email__ = "bob@freedombone.net"
__status__ = "Production"

import requests
import json

def createSession(onionRoute: bool):
    session = requests.session()
    if onionRoute:
        session.proxies = {}
        session.proxies['http'] = 'socks5h://localhost:9050'
        session.proxies['https'] = 'socks5h://localhost:9050'
    return session

def getJson(session,url: str,headers,params):
    sessionParams={}
    sessionHeaders={}
    if headers:
        sessionHeaders=headers
    if params:
        sessionParams=params
    sessionHeaders['User-agent'] = "HotJava/1.1.2 FCS"
    session.cookies.clear()
    return session.get(url, headers=sessionHeaders, params=sessionParams).json()

def postJson(session,postJson,inboxUrl: str):
    """Post a json message to the inbox of another person
    """
    postResult = session.post(url = inboxUrl, data = postJson) 
    return postResult.text
