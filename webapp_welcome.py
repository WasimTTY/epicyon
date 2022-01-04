__filename__ = "webapp_welcome.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Onboarding"

import os
from shutil import copyfile
from utils import get_config_param
from utils import remove_html
from utils import acct_dir
from webapp_utils import html_header_with_external_style
from webapp_utils import html_footer
from markdown import markdown_to_html


def is_welcome_screen_complete(base_dir: str,
                               nickname: str, domain: str) -> bool:
    """Returns true if the welcome screen is complete for the given account
    """
    account_path = acct_dir(base_dir, nickname, domain)
    if not os.path.isdir(account_path):
        return
    complete_filename = account_path + '/.welcome_complete'
    return os.path.isfile(complete_filename)


def welcome_screen_is_complete(base_dir: str,
                               nickname: str, domain: str) -> None:
    """Indicates that the welcome screen has been shown for a given account
    """
    account_path = acct_dir(base_dir, nickname, domain)
    if not os.path.isdir(account_path):
        return
    complete_filename = account_path + '/.welcome_complete'
    with open(complete_filename, 'w+') as fp_comp:
        fp_comp.write('\n')


def html_welcome_screen(base_dir: str, nickname: str,
                        language: str, translate: {},
                        theme_name: str,
                        currScreen='welcome') -> str:
    """Returns the welcome screen
    """
    # set a custom background for the welcome screen
    if os.path.isfile(base_dir + '/accounts/welcome-background-custom.jpg'):
        if not os.path.isfile(base_dir + '/accounts/welcome-background.jpg'):
            copyfile(base_dir + '/accounts/welcome-background-custom.jpg',
                     base_dir + '/accounts/welcome-background.jpg')

    welcome_text = 'Welcome to Epicyon'
    welcome_filename = base_dir + '/accounts/' + currScreen + '.md'
    if not os.path.isfile(welcome_filename):
        default_filename = None
        if theme_name:
            default_filename = \
                base_dir + '/theme/' + theme_name + '/welcome/' + \
                'welcome_' + language + '.md'
            if not os.path.isfile(default_filename):
                default_filename = None
        if not default_filename:
            default_filename = \
                base_dir + '/defaultwelcome/' + \
                currScreen + '_' + language + '.md'
        if not os.path.isfile(default_filename):
            default_filename = \
                base_dir + '/defaultwelcome/' + currScreen + '_en.md'
        copyfile(default_filename, welcome_filename)

    instance_title = \
        get_config_param(base_dir, 'instanceTitle')
    if not instance_title:
        instance_title = 'Epicyon'

    if os.path.isfile(welcome_filename):
        with open(welcome_filename, 'r') as fp_wel:
            welcome_text = fp_wel.read()
            welcome_text = welcome_text.replace('INSTANCE', instance_title)
            welcome_text = markdown_to_html(remove_html(welcome_text))

    welcome_form = ''
    css_filename = base_dir + '/epicyon-welcome.css'
    if os.path.isfile(base_dir + '/welcome.css'):
        css_filename = base_dir + '/welcome.css'

    welcome_form = \
        html_header_with_external_style(css_filename, instance_title, None)
    welcome_form += \
        '<form enctype="multipart/form-data" method="POST" ' + \
        'accept-charset="UTF-8" ' + \
        'action="/users/' + nickname + '/profiledata">\n'
    welcome_form += '<div class="container">' + welcome_text + '</div>\n'
    welcome_form += '  <div class="container next">\n'
    welcome_form += \
        '    <button type="submit" class="button" ' + \
        'name="previewAvatar">' + translate['Next'] + '</button>\n'
    welcome_form += '  </div>\n'
    welcome_form += '</div>\n'
    welcome_form += '</form>\n'
    welcome_form += html_footer()
    return welcome_form
