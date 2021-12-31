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
    accountPath = acct_dir(base_dir, nickname, domain)
    if not os.path.isdir(accountPath):
        return
    completeFilename = accountPath + '/.welcome_complete'
    return os.path.isfile(completeFilename)


def welcome_screen_is_complete(base_dir: str,
                               nickname: str, domain: str) -> None:
    """Indicates that the welcome screen has been shown for a given account
    """
    accountPath = acct_dir(base_dir, nickname, domain)
    if not os.path.isdir(accountPath):
        return
    completeFilename = accountPath + '/.welcome_complete'
    with open(completeFilename, 'w+') as completeFile:
        completeFile.write('\n')


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

    welcomeText = 'Welcome to Epicyon'
    welcomeFilename = base_dir + '/accounts/' + currScreen + '.md'
    if not os.path.isfile(welcomeFilename):
        defaultFilename = None
        if theme_name:
            defaultFilename = \
                base_dir + '/theme/' + theme_name + '/welcome/' + \
                'welcome_' + language + '.md'
            if not os.path.isfile(defaultFilename):
                defaultFilename = None
        if not defaultFilename:
            defaultFilename = \
                base_dir + '/defaultwelcome/' + \
                currScreen + '_' + language + '.md'
        if not os.path.isfile(defaultFilename):
            defaultFilename = \
                base_dir + '/defaultwelcome/' + currScreen + '_en.md'
        copyfile(defaultFilename, welcomeFilename)

    instanceTitle = \
        get_config_param(base_dir, 'instanceTitle')
    if not instanceTitle:
        instanceTitle = 'Epicyon'

    if os.path.isfile(welcomeFilename):
        with open(welcomeFilename, 'r') as welcomeFile:
            welcomeText = welcomeFile.read()
            welcomeText = welcomeText.replace('INSTANCE', instanceTitle)
            welcomeText = markdown_to_html(remove_html(welcomeText))

    welcomeForm = ''
    css_filename = base_dir + '/epicyon-welcome.css'
    if os.path.isfile(base_dir + '/welcome.css'):
        css_filename = base_dir + '/welcome.css'

    welcomeForm = \
        html_header_with_external_style(css_filename, instanceTitle, None)
    welcomeForm += \
        '<form enctype="multipart/form-data" method="POST" ' + \
        'accept-charset="UTF-8" ' + \
        'action="/users/' + nickname + '/profiledata">\n'
    welcomeForm += '<div class="container">' + welcomeText + '</div>\n'
    welcomeForm += '  <div class="container next">\n'
    welcomeForm += \
        '    <button type="submit" class="button" ' + \
        'name="previewAvatar">' + translate['Next'] + '</button>\n'
    welcomeForm += '  </div>\n'
    welcomeForm += '</div>\n'
    welcomeForm += '</form>\n'
    welcomeForm += html_footer()
    return welcomeForm
