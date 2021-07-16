__filename__ = "feeds.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@freedombone.net"
__status__ = "Production"
__module_group__ = "RSS Feeds"


def rss2TagHeader(hashtag: str, httpPrefix: str, domainFull: str) -> str:
    return \
        "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>" + \
        "<rss version=\"2.0\">" + \
        '<channel>' + \
        '    <title>#' + hashtag + '</title>' + \
        '    <link>' + httpPrefix + '://' + domainFull + \
        '/tags/rss2/' + hashtag + '</link>'


def rss2TagFooter() -> str:
    return '</channel></rss>'
