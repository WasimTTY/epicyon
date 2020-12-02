__filename__ = "webapp_hashtagswarm.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.1.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@freedombone.net"
__status__ = "Production"

import os
from datetime import datetime
from utils import getHashtagCategories


def getHashtagCategoriesFeed(baseDir: str,
                             hashtagCategories=None) -> str:
    """Returns an rss feed for hashtag categories
    """
    if not hashtagCategories:
        hashtagCategories = getHashtagCategories(baseDir)
    if not hashtagCategories:
        return None

    rssStr = "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>\n"
    rssStr += "<rss version=\"2.0\">\n"
    rssStr += '<channel>\n'
    rssStr += '    <title>#categories</title>\n'

    rssDateStr = \
        datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S UT")

    for categoryStr, hashtagList in hashtagCategories.items():
        rssStr += '<item>\n'
        rssStr += '  <title>' + categoryStr + '</title>\n'
        listStr = ''
        for hashtag in hashtagList:
            listStr += hashtag + ' '
        rssStr += '  <description>' + listStr.strip() + '</description>\n'
        rssStr += '  <link></link>\n'
        rssStr += '  <pubDate>' + rssDateStr + '</pubDate>\n'
        rssStr += '</item>\n'

    rssStr = '</channel>'
    rssStr += '</rss>'
    return rssStr


def getHashtagDomainMax(domainHistogram: {}) -> str:
    """Returns the domain with the maximum number of hashtags
    """
    maxCount = 1
    maxDomain = None
    for domain, count in domainHistogram.items():
        if count > maxCount:
            maxDomain = domain
            maxCount = count
    return maxDomain


def getHashtagDomainHistogram(domainHistogram: {}, translate: {}) -> str:
    """Returns the html for a histogram of domains
    from which hashtags are coming
    """
    totalCount = 0
    for domain, count in domainHistogram.items():
        totalCount += count
    if totalCount == 0:
        return ''

    htmlStr = ''
    histogramHeaderStr = '<br><br><center>\n'
    histogramHeaderStr += '  <h1>' + translate['Hashtag origins'] + '</h1>\n'
    histogramHeaderStr += '  <table class="domainHistogram">\n'
    histogramHeaderStr += '    <colgroup>\n'
    histogramHeaderStr += '      <col span="1" class="domainHistogramLeft">\n'
    histogramHeaderStr += '      <col span="1" class="domainHistogramRight">\n'
    histogramHeaderStr += '    </colgroup>\n'
    histogramHeaderStr += '    <tbody>\n'
    histogramHeaderStr += '      <tr>\n'

    leftColStr = ''
    rightColStr = ''

    for i in range(len(domainHistogram)):
        domain = getHashtagDomainMax(domainHistogram)
        if not domain:
            break
        percent = int(domainHistogram[domain] * 100 / totalCount)
        if histogramHeaderStr:
            htmlStr += histogramHeaderStr
            histogramHeaderStr = None
        leftColStr += str(percent) + '%<br>'
        rightColStr += domain + '<br>'
        del domainHistogram[domain]

    if htmlStr:
        htmlStr += '        <td>' + leftColStr + '</td>\n'
        htmlStr += '        <td>' + rightColStr + '</td>\n'
        htmlStr += '      </tr>\n'
        htmlStr += '    </tbody>\n'
        htmlStr += '  </table>\n'
        htmlStr += '</center>\n'

    return htmlStr


def htmlHashTagSwarm(baseDir: str, actor: str, translate: {}) -> str:
    """Returns a tag swarm of today's hashtags
    """
    currTime = datetime.utcnow()
    daysSinceEpoch = (currTime - datetime(1970, 1, 1)).days
    daysSinceEpochStr = str(daysSinceEpoch) + ' '
    daysSinceEpochStr2 = str(daysSinceEpoch - 1) + ' '
    recently = daysSinceEpoch - 1
    tagSwarm = []
    domainHistogram = {}

    # Load the blocked hashtags into memory.
    # This avoids needing to repeatedly load the blocked file for each hashtag
    blockedStr = ''
    globalBlockingFilename = baseDir + '/accounts/blocking.txt'
    if os.path.isfile(globalBlockingFilename):
        with open(globalBlockingFilename, 'r') as fp:
            blockedStr = fp.read()

    for subdir, dirs, files in os.walk(baseDir + '/tags'):
        for f in files:
            if not f.endswith('.txt'):
                continue
            tagsFilename = os.path.join(baseDir + '/tags', f)
            if not os.path.isfile(tagsFilename):
                continue

            # get last modified datetime
            modTimesinceEpoc = os.path.getmtime(tagsFilename)
            lastModifiedDate = datetime.fromtimestamp(modTimesinceEpoc)
            fileDaysSinceEpoch = (lastModifiedDate - datetime(1970, 1, 1)).days

            # check if the file was last modified within the previous
            # two days
            if fileDaysSinceEpoch < recently:
                continue

            hashTagName = f.split('.')[0]
            if '#' + hashTagName + '\n' in blockedStr:
                continue
            with open(tagsFilename, 'r') as fp:
                # only read one line, which saves time and memory
                lastTag = fp.readline()
                if not lastTag.startswith(daysSinceEpochStr):
                    if not lastTag.startswith(daysSinceEpochStr2):
                        continue
            with open(tagsFilename, 'r') as tagsFile:
                while True:
                    line = tagsFile.readline()
                    if not line:
                        break
                    elif '  ' not in line:
                        break
                    sections = line.split('  ')
                    if len(sections) != 3:
                        break
                    postDaysSinceEpochStr = sections[0]
                    if not postDaysSinceEpochStr.isdigit():
                        break
                    postDaysSinceEpoch = int(postDaysSinceEpochStr)
                    if postDaysSinceEpoch < recently:
                        break
                    else:
                        postUrl = sections[2]
                        if '##' not in postUrl:
                            break
                        postDomain = postUrl.split('##')[1]
                        if '#' in postDomain:
                            postDomain = postDomain.split('#')[0]

                        if domainHistogram.get(postDomain):
                            domainHistogram[postDomain] = \
                                domainHistogram[postDomain] + 1
                        else:
                            domainHistogram[postDomain] = 1
                        tagSwarm.append(hashTagName)
                        break

    if not tagSwarm:
        return ''
    tagSwarm.sort()
    tagSwarmStr = ''
    ctr = 0
    for tagName in tagSwarm:
        tagSwarmStr += \
            '<a href="' + actor + '/tags/' + tagName + \
            '" class="hashtagswarm">' + tagName + '</a>\n'
        ctr += 1
    tagSwarmHtml = tagSwarmStr.strip() + '\n'
    tagSwarmHtml += getHashtagDomainHistogram(domainHistogram, translate)
    return tagSwarmHtml
