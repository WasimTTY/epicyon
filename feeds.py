__filename__ = "feeds.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.3.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "RSS Feeds"


def rss2tag_header(hashtag: str, http_prefix: str, domain_full: str) -> str:
    """Header for rss 2
    """
    return \
        "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>" + \
        "<rss version=\"2.0\">" + \
        '<channel>' + \
        '    <title>#' + hashtag + '</title>' + \
        '    <link>' + http_prefix + '://' + domain_full + \
        '/tags/rss2/' + hashtag + '</link>'


def rss2tag_footer() -> str:
    """Footer for rss 2
    """
    return '</channel></rss>'
