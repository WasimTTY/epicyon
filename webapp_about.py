__filename__ = "webapp_about.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Web Interface"

import os
from shutil import copyfile
from utils import get_config_param
from webapp_utils import html_header_with_website_markup
from webapp_utils import html_footer
from markdown import markdown_to_html


def html_about(css_cache: {}, base_dir: str, http_prefix: str,
               domain_full: str, onion_domain: str, translate: {},
               system_language: str) -> str:
    """Show the about screen
    """
    adminNickname = get_config_param(base_dir, 'admin')
    if not os.path.isfile(base_dir + '/accounts/about.md'):
        copyfile(base_dir + '/default_about.md',
                 base_dir + '/accounts/about.md')

    if os.path.isfile(base_dir + '/accounts/login-background-custom.jpg'):
        if not os.path.isfile(base_dir + '/accounts/login-background.jpg'):
            copyfile(base_dir + '/accounts/login-background-custom.jpg',
                     base_dir + '/accounts/login-background.jpg')

    aboutText = 'Information about this instance goes here.'
    if os.path.isfile(base_dir + '/accounts/about.md'):
        with open(base_dir + '/accounts/about.md', 'r') as aboutFile:
            aboutText = markdown_to_html(aboutFile.read())

    aboutForm = ''
    cssFilename = base_dir + '/epicyon-profile.css'
    if os.path.isfile(base_dir + '/epicyon.css'):
        cssFilename = base_dir + '/epicyon.css'

    instanceTitle = \
        get_config_param(base_dir, 'instanceTitle')
    aboutForm = \
        html_header_with_website_markup(cssFilename, instanceTitle,
                                        http_prefix, domain_full,
                                        system_language)
    aboutForm += '<div class="container">' + aboutText + '</div>'
    if onion_domain:
        aboutForm += \
            '<div class="container"><center>\n' + \
            '<p class="administeredby">' + \
            'http://' + onion_domain + '</p>\n</center></div>\n'
    if adminNickname:
        adminActor = '/users/' + adminNickname
        aboutForm += \
            '<div class="container"><center>\n' + \
            '<p class="administeredby">' + \
            translate['Administered by'] + ' <a href="' + \
            adminActor + '">' + adminNickname + '</a>. ' + \
            translate['Version'] + ' ' + __version__ + \
            '</p>\n</center></div>\n'
    aboutForm += html_footer()
    return aboutForm
