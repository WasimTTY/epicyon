__filename__ = "daemon_get_css.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.5.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Core"

import os
import time
from httpcodes import http_304
from httpcodes import http_404
from httpcodes import write2
from httpheaders import set_headers_etag
from httpheaders import set_headers
from utils import get_css
from fitnessFunctions import fitness_performance
from daemon_utils import etag_exists


def get_style_sheet(self, base_dir: str, calling_domain: str, path: str,
                    getreq_start_time) -> bool:
    """Returns the content of a css file
    """
    # get the last part of the path
    # eg. /my/path/file.css becomes file.css
    if '/' in path:
        path = path.split('/')[-1]
    path = base_dir + '/' + path
    css = None
    if self.server.css_cache.get(path):
        css = self.server.css_cache[path]
    elif os.path.isfile(path):
        tries = 0
        while tries < 5:
            try:
                css = get_css(self.server.base_dir, path)
                if css:
                    self.server.css_cache[path] = css
                    break
            except BaseException as ex:
                print('EX: _get_style_sheet ' + path + ' ' +
                      str(tries) + ' ' + str(ex))
                time.sleep(1)
                tries += 1
    if css:
        msg = css.encode('utf-8')
        msglen = len(msg)
        set_headers(self, 'text/css', msglen,
                    None, calling_domain, False)
        write2(self, msg)
        fitness_performance(getreq_start_time,
                            self.server.fitness,
                            '_GET', '_get_style_sheet',
                            self.server.debug)
        return True
    http_404(self, 92)
    return True


def get_fonts(self, calling_domain: str, path: str,
              base_dir: str, debug: bool,
              getreq_start_time) -> None:
    """Returns a font
    """
    font_str = path.split('/fonts/')[1]
    if font_str.endswith('.otf') or \
       font_str.endswith('.ttf') or \
       font_str.endswith('.woff') or \
       font_str.endswith('.woff2'):
        if font_str.endswith('.otf'):
            font_type = 'font/otf'
        elif font_str.endswith('.ttf'):
            font_type = 'font/ttf'
        elif font_str.endswith('.woff'):
            font_type = 'font/woff'
        else:
            font_type = 'font/woff2'
        font_filename = \
            base_dir + '/fonts/' + font_str
        if etag_exists(self, font_filename):
            # The file has not changed
            http_304(self)
            return
        if self.server.fontsCache.get(font_str):
            font_binary = self.server.fontsCache[font_str]
            set_headers_etag(self, font_filename,
                             font_type,
                             font_binary, None,
                             self.server.domain_full, False, None)
            write2(self, font_binary)
            if debug:
                print('font sent from cache: ' +
                      path + ' ' + calling_domain)
            fitness_performance(getreq_start_time, self.server.fitness,
                                '_GET', '_get_fonts cache',
                                debug)
            return
        if os.path.isfile(font_filename):
            font_binary = None
            try:
                with open(font_filename, 'rb') as fontfile:
                    font_binary = fontfile.read()
            except OSError:
                print('EX: unable to load font ' + font_filename)
            if font_binary:
                set_headers_etag(self, font_filename,
                                 font_type,
                                 font_binary, None,
                                 self.server.domain_full,
                                 False, None)
                write2(self, font_binary)
                self.server.fontsCache[font_str] = font_binary
            if debug:
                print('font sent from file: ' +
                      path + ' ' + calling_domain)
            fitness_performance(getreq_start_time, self.server.fitness,
                                '_GET', '_get_fonts', debug)
            return
    if debug:
        print('font not found: ' + path + ' ' + calling_domain)
    http_404(self, 21)
