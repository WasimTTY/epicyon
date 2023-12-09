__filename__ = "maps.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.4.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Core"


import os
from utils import get_url_from_post
from utils import is_float
from utils import acct_dir
from utils import load_json
from utils import save_json
from utils import locate_post
from utils import remove_html
from utils import has_object_dict
from utils import date_utcnow
from utils import date_epoch
from utils import date_from_string_format


def _geocoords_to_osm_link(osm_domain: str, zoom: int,
                           latitude: float, longitude: float) -> str:
    """Returns an OSM link for the given geocoordinates
    """
    return 'https://www.' + osm_domain + '/#map=' + \
        str(zoom) + '/' + str(latitude) + '/' + str(longitude)


def get_location_dict_from_tags(tags: []) -> str:
    """Returns the location from the tags list
    """
    for tag_item in tags:
        if not tag_item.get('type'):
            continue
        if tag_item['type'] != 'Place':
            continue
        if not tag_item.get('name'):
            continue
        if not isinstance(tag_item['name'], str):
            continue
        return tag_item
    return None


def _get_location_from_tags(tags: []) -> str:
    """Returns the location from the tags list
    """
    locn = get_location_dict_from_tags(tags)
    if locn:
        location_str = locn['name'].replace('\n', ' ')
        return remove_html(location_str)
    return None


def get_location_from_post(post_json_object: {}) -> str:
    """Returns the location for the given post
    """
    locn = None

    # location represented via a tag
    post_obj = post_json_object
    if has_object_dict(post_json_object):
        post_obj = post_json_object['object']
    if post_obj.get('tag'):
        if isinstance(post_obj['tag'], list):
            locn = _get_location_from_tags(post_obj['tag'])

    # location representation used by pixelfed
    locn_exists = False
    if post_obj.get('location'):
        if isinstance(post_obj['location'], dict):
            if post_obj['location'].get('longitude') and \
               post_obj['location'].get('latitude'):
                if isinstance(post_obj['location']['longitude'], str) and \
                   isinstance(post_obj['location']['latitude'], str):
                    if is_float(post_obj['location']['longitude']) and \
                       is_float(post_obj['location']['latitude']):
                        locn_exists = True
            if not locn_exists:
                if post_obj['location'].get('name'):
                    if isinstance(post_obj['location']['name'], str):
                        locn = post_obj['location']['name']
    if locn_exists:
        osm_domain = 'osm.org'
        zoom = 17
        locn = _geocoords_to_osm_link(osm_domain, zoom,
                                      post_obj['location']['latitude'],
                                      post_obj['location']['longitude'])

    return locn


def _geocoords_from_osm_link(url: str, osm_domain: str) -> (int, float, float):
    """Returns geocoordinates from an OSM map link
    """
    if osm_domain not in url:
        return None, None, None
    if '#map=' not in url:
        return None, None, None

    coords_str = url.split('#map=')[1]
    if '/' not in coords_str:
        return None, None, None

    coords = coords_str.split('/')
    if len(coords) != 3:
        return None, None, None
    zoom = coords[0]
    if not zoom.isdigit():
        return None, None, None
    latitude = coords[1]
    if not is_float(latitude):
        return None, None, None
    longitude = coords[2]
    if not is_float(longitude):
        return None, None, None
    zoom = int(zoom)
    latitude = float(latitude)
    longitude = float(longitude)
    return zoom, latitude, longitude


def _geocoords_from_osmorg_link(url: str) -> (int, float, float):
    """Returns geocoordinates from an OSM map link
    """
    osm_domain = 'osm.org'
    if osm_domain not in url:
        return None, None, None
    if 'mlat=' not in url:
        return None, None, None
    if 'mlon=' not in url:
        return None, None, None
    if 'zoom=' not in url:
        return None, None, None

    latitude = url.split('mlat=')[1]
    if '&' in latitude:
        latitude = latitude.split('&')[0]
    if not is_float(latitude):
        return None, None, None

    longitude = url.split('mlon=')[1]
    if '&' in longitude:
        longitude = longitude.split('&')[0]
    if not is_float(longitude):
        return None, None, None

    zoom = url.split('zoom=')[1]
    if '&' in zoom:
        zoom = zoom.split('&')[0]
    if not zoom.isdigit():
        return None, None, None
    zoom = int(zoom)
    latitude = float(latitude)
    longitude = float(longitude)
    return zoom, latitude, longitude


def _geocoords_from_gmaps_link(url: str) -> (int, float, float):
    """Returns geocoordinates from a Gmaps link
    """
    if '/maps/' not in url:
        return None, None, None
    coords_str = url.split('/maps', 1)[1]
    if '/@' not in coords_str:
        return None, None, None

    coords_str = coords_str.split('/@', 1)[1]
    if 'z' not in coords_str:
        return None, None, None
    coords_str = coords_str.split('z', 1)[0]

    if ',' not in coords_str:
        return None, None, None

    coords = coords_str.split(',')
    if len(coords) != 3:
        return None, None, None
    zoom = coords[2]
    if not zoom.isdigit():
        if is_float(str(zoom)):
            zoom = int(float(str(zoom)))
        else:
            return None, None, None
    latitude = coords[0]
    if not is_float(latitude):
        return None, None, None
    longitude = coords[1]
    if not is_float(longitude):
        return None, None, None
    zoom = int(zoom)
    latitude = float(latitude)
    longitude = float(longitude)
    return zoom, latitude, longitude


def _geocoords_from_bmaps_link(url: str) -> (int, float, float):
    """Returns geocoordinates from a bing map link
    """
    prefixes = ('/maps?cp=', '/maps/directions?cp=')
    map_prefix = None
    for prefix in prefixes:
        if prefix in url:
            map_prefix = prefix
            break
    if not map_prefix:
        return None, None, None

    coords_str = url.split(map_prefix)[1]
    if '~' not in coords_str:
        return None, None, None
    orig_coords_str = coords_str
    if '&' in coords_str:
        coords_str = coords_str.split('&')[0]
    if ';' in coords_str:
        coords_str = coords_str.split(';')[0]

    coords = coords_str.split('~')
    if len(coords) != 2:
        return None, None, None
    latitude = coords[0]
    if not is_float(latitude):
        return None, None, None
    longitude = coords[1]
    if not is_float(longitude):
        return None, None, None
    zoom = 17
    if 'lvl=' in orig_coords_str:
        zoom = orig_coords_str.split('lvl=')[1]
        if '&' in zoom:
            zoom = zoom.split('&')[0]
        if ';' in zoom:
            zoom = zoom.split(';')[0]
    if not zoom.isdigit():
        return None, None, None
    zoom = int(zoom)
    latitude = float(latitude)
    longitude = float(longitude)
    return zoom, latitude, longitude


def _geocoords_from_waze_link(url: str) -> (int, float, float):
    """Returns geocoordinates from a waze map link
    """
    prefixes = ['/ul?ll=']
    map_prefix = None
    for prefix in prefixes:
        if prefix in url:
            map_prefix = prefix
            break
    if not map_prefix:
        return None, None, None

    coords_str = url.split(map_prefix)[1]
    orig_coords_str = coords_str
    if '&' in coords_str:
        coords_str = coords_str.split('&')[0]
    if '%2C' not in coords_str and ',' not in coords_str:
        return None, None, None

    if '%2C' in coords_str:
        coords = coords_str.split('%2C')
    else:
        coords = coords_str.split(',')
    if len(coords) != 2:
        return None, None, None
    latitude = coords[0]
    if not is_float(latitude):
        return None, None, None
    longitude = coords[1]
    if not is_float(longitude):
        return None, None, None
    zoom = 17
    if 'zoom=' in orig_coords_str:
        zoom = orig_coords_str.split('zoom=')[1]
        if '&' in zoom:
            zoom = zoom.split('&')[0]
    if not zoom.isdigit():
        return None, None, None
    zoom = int(zoom)
    latitude = float(latitude)
    longitude = float(longitude)
    return zoom, latitude, longitude


def _geocoords_from_wego_link(url: str) -> (int, float, float):
    """Returns geocoordinates from a wego map link
    """
    prefixes = ['/?map=']
    map_prefix = None
    for prefix in prefixes:
        if prefix in url:
            map_prefix = prefix
            break
    if not map_prefix:
        return None, None, None

    coords_str = url.split(map_prefix)[1]
    if ',' not in coords_str:
        return None, None, None

    coords = coords_str.split(',')
    if len(coords) < 3:
        return None, None, None
    latitude = coords[0]
    if not is_float(latitude):
        return None, None, None
    longitude = coords[1]
    if not is_float(longitude):
        return None, None, None
    zoom = coords[2]
    if not zoom.isdigit():
        return None, None, None
    zoom = int(zoom)
    latitude = float(latitude)
    longitude = float(longitude)
    return zoom, latitude, longitude


def geocoords_from_map_link(url: str,
                            osm_domain: str = 'openstreetmap.org') -> (int,
                                                                       float,
                                                                       float):
    """Returns geocoordinates from a map link url
    """
    if osm_domain in url:
        return _geocoords_from_osm_link(url, osm_domain)
    if 'osm.org' in url and 'mlat=' in url:
        return _geocoords_from_osmorg_link(url)
    if '.google.co' in url:
        return _geocoords_from_gmaps_link(url)
    if '.bing.co' in url:
        return _geocoords_from_bmaps_link(url)
    if '.waze.co' in url:
        return _geocoords_from_waze_link(url)
    if 'wego.here.co' in url:
        return _geocoords_from_wego_link(url)
    return None, None, None


def html_open_street_map(url: str,
                         bounding_box_degrees: float,
                         translate: {},
                         width: str = "725",
                         height: str = "650") -> str:
    """Returns embed html for an OSM link
    """
    osm_domain = 'openstreetmap.org'
    zoom, latitude, longitude = geocoords_from_map_link(url, osm_domain)
    if not latitude:
        return ''
    if not longitude:
        return ''
    if not zoom:
        return ''
    osm_url = _geocoords_to_osm_link(osm_domain, zoom, latitude, longitude)
    html_str = \
        '<iframe width="' + width + '" height="' + height + \
        '" frameborder="0" ' + \
        'scrolling="no" marginheight="0" marginwidth="0" ' + \
        'src="https://www.' + osm_domain + '/export/embed.html?' + \
        'bbox=' + str(longitude - bounding_box_degrees) + \
        '%2C' + \
        str(latitude - bounding_box_degrees) + \
        '%2C' + \
        str(longitude + bounding_box_degrees) + \
        '%2C' + \
        str(latitude + bounding_box_degrees) + \
        '&amp;layer=mapnik" style="border: 1px solid black" ' + \
        'sandbox="allow-scripts allow-same-origin">' + \
        '</iframe><br/><small><a href="' + osm_url + \
        '">' + translate['View Larger Map'] + '</a></small>\n'
    return html_str


def set_map_preferences_url(base_dir: str, nickname: str, domain: str,
                            maps_website_url: str) -> None:
    """Sets the preferred maps website for an account
    """
    maps_filename = \
        acct_dir(base_dir, nickname, domain) + '/map_preferences.json'
    if os.path.isfile(maps_filename):
        maps_json = load_json(maps_filename)
        maps_json['url'] = maps_website_url
    else:
        maps_json = {
            'url': maps_website_url
        }
    save_json(maps_json, maps_filename)


def get_map_preferences_url(base_dir: str, nickname: str, domain: str) -> str:
    """Gets the preferred maps website for an account
    """
    maps_filename = \
        acct_dir(base_dir, nickname, domain) + '/map_preferences.json'
    if os.path.isfile(maps_filename):
        maps_json = load_json(maps_filename)
        if maps_json.get('url'):
            url_str = get_url_from_post(maps_json['url'])
            return remove_html(url_str)
    return None


def set_map_preferences_coords(base_dir: str, nickname: str, domain: str,
                               latitude: float, longitude: float,
                               zoom: int) -> None:
    """Sets the preferred maps website coordinates for an account
    """
    maps_filename = \
        acct_dir(base_dir, nickname, domain) + '/map_preferences.json'
    if os.path.isfile(maps_filename):
        maps_json = load_json(maps_filename)
        maps_json['latitude'] = latitude
        maps_json['longitude'] = longitude
        maps_json['zoom'] = zoom
    else:
        maps_json = {
            'latitude': latitude,
            'longitude': longitude,
            'zoom': zoom
        }
    save_json(maps_json, maps_filename)


def get_map_preferences_coords(base_dir: str, nickname: str,
                               domain: str) -> (float, float, int):
    """Gets the preferred maps website coordinates for an account
    """
    maps_filename = \
        acct_dir(base_dir, nickname, domain) + '/map_preferences.json'
    if os.path.isfile(maps_filename):
        maps_json = load_json(maps_filename)
        if maps_json.get('latitude') and \
           maps_json.get('longitude') and \
           maps_json.get('zoom'):
            return maps_json['latitude'], \
                maps_json['longitude'], \
                maps_json['zoom']
    return None, None, None


def get_map_links_from_post_content(content: str) -> []:
    """Returns a list of map links
    """
    osm_domain = 'openstreetmap.org'
    sections = content.split('://')
    map_links = []
    ctr = 0
    for link_str in sections:
        if ctr == 0:
            ctr += 1
            continue
        url = link_str
        if '"' in url:
            url = url.split('"')[0]
        if '<' in url:
            url = url.split('<')[0]
        if not url:
            continue
        zoom, latitude, longitude = geocoords_from_map_link(url, osm_domain)
        if not latitude:
            continue
        if not longitude:
            continue
        if not zoom:
            continue
        if url not in map_links:
            map_links.append(url)
        ctr += 1
    return map_links


def add_tag_map_links(tag_maps_dir: str, tag_name: str,
                      map_links: [], published: str, post_url: str) -> None:
    """Appends to a hashtag file containing map links
    This is used to show a map for a particular hashtag
    """
    tag_map_filename = tag_maps_dir + '/' + tag_name + '.txt'
    post_url = post_url.replace('#', '/')

    # read the existing map links
    existing_map_links = []
    if os.path.isfile(tag_map_filename):
        try:
            with open(tag_map_filename, 'r', encoding='utf-8') as fp_tag:
                existing_map_links = fp_tag.read().split('\n')
        except OSError:
            print('EX: error reading tag map ' + tag_map_filename)

    # combine map links with the existing list
    secs_since_epoch = \
        int((date_from_string_format(published, ['%Y-%m-%dT%H:%M:%S%z']) -
             date_epoch()).total_seconds())
    links_changed = False
    for link in map_links:
        line = str(secs_since_epoch) + ' ' + link + ' ' + post_url
        if line in existing_map_links:
            continue
        links_changed = True
        existing_map_links = [line] + existing_map_links
    if not links_changed:
        return

    # sort the list of map links
    existing_map_links.sort(reverse=True)
    map_links_str = ''
    ctr = 0
    for link in existing_map_links:
        if not link:
            continue
        map_links_str += link + '\n'
        ctr += 1
        # don't allow the list to grow indefinitely
        if ctr >= 2000:
            break

    # save the tag
    try:
        with open(tag_map_filename, 'w+', encoding='utf-8') as fp_tag:
            fp_tag.write(map_links_str)
    except OSError:
        print('EX: error writing tag map ' + tag_map_filename)


def _gpx_location(latitude: float, longitude: float, post_id: str) -> str:
    """Returns a gpx waypoint
    """
    map_str = '<wpt lat="' + str(latitude) + \
        '" lon="' + str(longitude) + '">\n'
    map_str += '  <name>' + post_id + '</name>\n'
    map_str += '  <link href="' + post_id + '"/>\n'
    map_str += '</wpt>\n'
    return map_str


def _kml_location(place_ctr: int,
                  latitude: float, longitude: float, post_id: str) -> str:
    """Returns a kml placemark
    """
    map_str = '<Placemark id="' + str(place_ctr) + '">\n'
    map_str += '  <name>' + str(place_ctr) + '</name>\n'
    map_str += '  <description><![CDATA[\n'
    map_str += '<a href="' + post_id + '">' + \
        post_id + '</a>\n]]>\n'
    map_str += '  </description>\n'
    map_str += '  <Point>\n'
    map_str += '    <coordinates>' + str(longitude) + ',' + \
        str(latitude) + ',0</coordinates>\n'
    map_str += '  </Point>\n'
    map_str += '</Placemark>\n'
    return map_str


def _hashtag_map_to_format(base_dir: str, tag_name: str,
                           start_hours_since_epoch: int,
                           end_hours_since_epoch: int,
                           nickname: str, domain: str,
                           map_format: str) -> str:
    """Returns the KML/GPX for a given hashtag between the given times
    """
    place_ctr = 0
    osm_domain = 'openstreetmap.org'
    tag_map_filename = base_dir + '/tagmaps/' + tag_name + '.txt'

    if map_format == 'gpx':
        map_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
        map_str += '<gpx version="1.0">\n'
    else:
        map_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
        map_str += '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
        map_str += '<Document>\n'

    if os.path.isfile(tag_map_filename):
        map_links = []
        try:
            with open(tag_map_filename, 'r', encoding='utf-8') as fp_tag:
                map_links = fp_tag.read().split('\n')
        except OSError:
            print('EX: unable to read tag map links ' + tag_map_filename)
        if map_links:
            start_secs_since_epoch = int(start_hours_since_epoch * 60 * 60)
            end_secs_since_epoch = int(end_hours_since_epoch * 60 * 60)
            for link_line in map_links:
                link_line = link_line.strip().split(' ')
                if len(link_line) < 3:
                    continue
                # is this geocoordinate within the time range?
                secs_since_epoch = int(link_line[0])
                if secs_since_epoch < start_secs_since_epoch or \
                   secs_since_epoch > end_secs_since_epoch:
                    continue
                # get the geocoordinates from the map link
                map_link = link_line[1]
                zoom, latitude, longitude = \
                    geocoords_from_map_link(map_link, osm_domain)
                if not zoom:
                    continue
                if not latitude:
                    continue
                if not longitude:
                    continue
                post_id = link_line[2]
                # check if the post is muted, and exclude the
                # geolocation if it is
                if nickname:
                    post_filename = \
                        locate_post(base_dir, nickname, domain, post_id)
                    if post_filename:
                        if os.path.isfile(post_filename + '.muted'):
                            continue
                place_ctr += 1
                if map_format == 'gpx':
                    map_str += _gpx_location(latitude, longitude, post_id)
                else:
                    map_str += \
                        _kml_location(place_ctr, latitude, longitude, post_id)

    if map_format == 'gpx':
        map_str += '</gpx>'
    else:
        map_str += '</Document>\n'
        map_str += '</kml>'
    if place_ctr == 0:
        return None
    return map_str


def _hashtag_map_within_hours(base_dir: str, tag_name: str,
                              hours: int, map_format: str,
                              nickname: str, domain: str) -> str:
    """Returns gpx/kml for a hashtag containing maps for the
    last number of hours
    """
    secs_since_epoch = \
        int((date_utcnow() -
             date_epoch()).total_seconds())
    curr_hours_since_epoch = int(secs_since_epoch / (60 * 60))
    start_hours_since_epoch = curr_hours_since_epoch - abs(hours)
    end_hours_since_epoch = curr_hours_since_epoch + 2
    map_str = \
        _hashtag_map_to_format(base_dir, tag_name,
                               start_hours_since_epoch,
                               end_hours_since_epoch,
                               nickname, domain, map_format)
    return map_str


def _get_tagmaps_time_periods() -> {}:
    """dict of time periods for map display
    """
    return {
        "Last hour": -1,
        "Last 3 hours": -3,
        "Last 6 hours": -6,
        "Last 12 hours": -12,
        "Last day": -24,
        "Last 2 days": -48,
        "Last week": -24 * 7,
        "Last 2 weeks": -24 * 7 * 2,
        "Last month": -24 * 7 * 4,
        "Last 6 months": -24 * 7 * 4 * 6,
        "Last year": -24 * 7 * 4 * 12
    }


def map_format_from_tagmaps_path(base_dir: str, path: str,
                                 map_format: str,
                                 domain: str) -> str:
    """Returns gpx/kml for a given tagmaps path
    /tagmaps/tagname-time_period
    """
    if '/tagmaps/' not in path:
        return None
    time_period = _get_tagmaps_time_periods()
    tag_name = path.split('/tagmaps/')[1]
    if '-' in tag_name:
        tag_name = tag_name.split('-')[0]
    if not tag_name:
        return None
    for period_str, hours in time_period.items():
        period_str2 = period_str.replace('Last ', '').lower()
        endpoint_str = \
            '/tagmaps/' + tag_name + '-' + period_str2.replace(' ', '_')
        if path == endpoint_str:
            nickname = None
            if '/users/' in path:
                nickname = path.split('/users/')[1]
                if '/' in nickname:
                    nickname = nickname.split('/')[0]
            return _hashtag_map_within_hours(base_dir, tag_name,
                                             hours, map_format,
                                             nickname, domain)
    return None


def html_hashtag_maps(base_dir: str, tag_name: str,
                      translate: {}, map_format: str,
                      nickname: str, domain: str) -> str:
    """Returns html for maps associated with a hashtag
    """
    tag_map_filename = base_dir + '/tagmaps/' + tag_name + '.txt'
    if not os.path.isfile(tag_map_filename):
        return ''

    time_period = _get_tagmaps_time_periods()

    html_str = ''
    map_str = None
    for period_str, hours in time_period.items():
        new_map_str = \
            _hashtag_map_within_hours(base_dir, tag_name, hours,
                                      map_format, nickname, domain)
        if not new_map_str:
            continue
        if new_map_str == map_str:
            continue
        map_str = new_map_str
        period_str2 = period_str.replace('Last ', '').lower()
        endpoint_str = \
            '/tagmaps/' + tag_name + '-' + period_str2.replace(' ', '_')
        download_filename = \
            (tag_name + '-' +
             period_str.lower()).replace(' ', '_') + '.' + map_format
        if html_str:
            html_str += ' '
        description = period_str
        if translate.get(period_str):
            description = translate[period_str]
        html_str += '<a href="' + endpoint_str + \
            '" download="' + download_filename + '">' + \
            description + '</a>'
    if html_str:
        html_str = '📌 ' + html_str
    return html_str
