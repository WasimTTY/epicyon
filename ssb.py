__filename__ = "ssb.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Profile Metadata"


def getSSBAddress(actor_json: {}) -> str:
    """Returns ssb address for the given actor
    """
    if not actor_json.get('attachment'):
        return ''
    for property_value in actor_json['attachment']:
        if not property_value.get('name'):
            continue
        if not property_value['name'].lower().startswith('ssb'):
            continue
        if not property_value.get('type'):
            continue
        if not property_value.get('value'):
            continue
        if property_value['type'] != 'PropertyValue':
            continue
        property_value['value'] = property_value['value'].strip()
        if not property_value['value'].startswith('@'):
            continue
        if '=.' not in property_value['value']:
            continue
        if '"' in property_value['value']:
            continue
        if ' ' in property_value['value']:
            continue
        if ',' in property_value['value']:
            continue
        return property_value['value']
    return ''


def setSSBAddress(actor_json: {}, ssbAddress: str) -> None:
    """Sets an ssb address for the given actor
    """
    notSSBAddress = False
    if not ssbAddress.startswith('@'):
        notSSBAddress = True
    if '=.' not in ssbAddress:
        notSSBAddress = True
    if '"' in ssbAddress:
        notSSBAddress = True
    if ' ' in ssbAddress:
        notSSBAddress = True
    if ',' in ssbAddress:
        notSSBAddress = True
    if '<' in ssbAddress:
        notSSBAddress = True

    if not actor_json.get('attachment'):
        actor_json['attachment'] = []

    # remove any existing value
    propertyFound = None
    for property_value in actor_json['attachment']:
        if not property_value.get('name'):
            continue
        if not property_value.get('type'):
            continue
        if not property_value['name'].lower().startswith('ssb'):
            continue
        propertyFound = property_value
        break
    if propertyFound:
        actor_json['attachment'].remove(propertyFound)
    if notSSBAddress:
        return

    for property_value in actor_json['attachment']:
        if not property_value.get('name'):
            continue
        if not property_value.get('type'):
            continue
        if not property_value['name'].lower().startswith('ssb'):
            continue
        if property_value['type'] != 'PropertyValue':
            continue
        property_value['value'] = ssbAddress
        return

    newSSBAddress = {
        "name": "SSB",
        "type": "PropertyValue",
        "value": ssbAddress
    }
    actor_json['attachment'].append(newSSBAddress)
