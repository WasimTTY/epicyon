__filename__ = "webapp_about.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.3.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Web Interface"

import os
from shutil import copyfile
from utils import get_config_param
from webapp_utils import html_header_with_website_markup
from webapp_utils import html_footer
from markdown import markdown_example_numbers
from markdown import markdown_to_html


def html_specification(css_cache: {}, base_dir: str, http_prefix: str,
                       domain_full: str, onion_domain: str, translate: {},
                       system_language: str) -> str:
    """Show the specification screen
    """
    specification_filename = base_dir + '/specification/activitypub.md'
    admin_nickname = get_config_param(base_dir, 'admin')
    if os.path.isfile(base_dir + '/accounts/activitypub.md'):
        specification_filename = base_dir + '/accounts/activitypub.md'

    if os.path.isfile(base_dir + '/accounts/login-background-custom.jpg'):
        if not os.path.isfile(base_dir + '/accounts/login-background.jpg'):
            copyfile(base_dir + '/accounts/login-background-custom.jpg',
                     base_dir + '/accounts/login-background.jpg')

    specification_text = 'ActivityPub Protocol Specification.'
    if os.path.isfile(specification_filename):
        with open(specification_filename, 'r',
                  encoding='utf-8') as fp_specification:
            md_text = markdown_example_numbers(fp_specification.read())
            specification_text = markdown_to_html(md_text)

    specification_form = ''
    css_filename = base_dir + '/epicyon-profile.css'
    if os.path.isfile(base_dir + '/epicyon.css'):
        css_filename = base_dir + '/epicyon.css'

    instance_title = \
        get_config_param(base_dir, 'instanceTitle')
    specification_form = \
        html_header_with_website_markup(css_filename, instance_title,
                                        http_prefix, domain_full,
                                        system_language)
    specification_form += \
        '<div class="container">' + specification_text + '</div>'
    if onion_domain:
        specification_form += \
            '<div class="container"><center>\n' + \
            '<p class="administeredby">' + \
            'http://' + onion_domain + '</p>\n</center></div>\n'
    if admin_nickname:
        admin_actor = '/users/' + admin_nickname
        specification_form += \
            '<div class="container"><center>\n' + \
            '<p class="administeredby">' + \
            translate['Administered by'] + ' <a href="' + \
            admin_actor + '">' + admin_nickname + '</a>. ' + \
            translate['Version'] + ' ' + __version__ + \
            '</p>\n</center></div>\n'
    specification_form += html_footer()
    return specification_form
