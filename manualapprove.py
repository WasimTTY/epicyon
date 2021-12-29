__filename__ = "manualapprove.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "ActivityPub"

import os
from follow import followed_account_accepts
from follow import followed_account_rejects
from follow import remove_from_follow_requests
from utils import load_json
from utils import remove_domain_port
from utils import get_port_from_domain
from utils import get_user_paths
from utils import acct_dir
from threads import thread_with_trace


def manual_deny_follow_request(session, base_dir: str,
                               http_prefix: str,
                               nickname: str, domain: str, port: int,
                               denyHandle: str,
                               federation_list: [],
                               send_threads: [], postLog: [],
                               cached_webfingers: {}, person_cache: {},
                               debug: bool,
                               project_version: str,
                               signing_priv_key_pem: str) -> None:
    """Manually deny a follow request
    """
    accountsDir = acct_dir(base_dir, nickname, domain)

    # has this handle already been rejected?
    rejectedFollowsFilename = accountsDir + '/followrejects.txt'
    if os.path.isfile(rejectedFollowsFilename):
        if denyHandle in open(rejectedFollowsFilename).read():
            remove_from_follow_requests(base_dir, nickname, domain,
                                        denyHandle, debug)
            print(denyHandle + ' has already been rejected as a follower of ' +
                  nickname)
            return

    remove_from_follow_requests(base_dir, nickname, domain, denyHandle, debug)

    # Store rejected follows
    try:
        with open(rejectedFollowsFilename, 'a+') as rejectsFile:
            rejectsFile.write(denyHandle + '\n')
    except OSError:
        print('EX: unable to append ' + rejectedFollowsFilename)

    denyNickname = denyHandle.split('@')[0]
    denyDomain = \
        denyHandle.split('@')[1].replace('\n', '').replace('\r', '')
    denyPort = port
    if ':' in denyDomain:
        denyPort = get_port_from_domain(denyDomain)
        denyDomain = remove_domain_port(denyDomain)
    followed_account_rejects(session, base_dir, http_prefix,
                             nickname, domain, port,
                             denyNickname, denyDomain, denyPort,
                             federation_list,
                             send_threads, postLog,
                             cached_webfingers, person_cache,
                             debug, project_version,
                             signing_priv_key_pem)

    print('Follow request from ' + denyHandle + ' was denied.')


def manual_deny_follow_request_thread(session, base_dir: str,
                                      http_prefix: str,
                                      nickname: str, domain: str, port: int,
                                      denyHandle: str,
                                      federation_list: [],
                                      send_threads: [], postLog: [],
                                      cached_webfingers: {}, person_cache: {},
                                      debug: bool,
                                      project_version: str,
                                      signing_priv_key_pem: str) -> None:
    """Manually deny a follow request, within a thread so that the
    user interface doesn't lag
    """
    thr = \
        thread_with_trace(target=manual_deny_follow_request,
                          args=(session, base_dir,
                                http_prefix,
                                nickname, domain, port,
                                denyHandle,
                                federation_list,
                                send_threads, postLog,
                                cached_webfingers, person_cache,
                                debug,
                                project_version,
                                signing_priv_key_pem), daemon=True)
    thr.start()
    send_threads.append(thr)


def _approve_follower_handle(accountDir: str, approveHandle: str) -> None:
    """ Record manually approved handles so that if they unfollow and then
     re-follow later then they don't need to be manually approved again
    """
    approvedFilename = accountDir + '/approved.txt'
    if os.path.isfile(approvedFilename):
        if approveHandle not in open(approvedFilename).read():
            try:
                with open(approvedFilename, 'a+') as approvedFile:
                    approvedFile.write(approveHandle + '\n')
            except OSError:
                print('EX: unable to append ' + approvedFilename)
    else:
        try:
            with open(approvedFilename, 'w+') as approvedFile:
                approvedFile.write(approveHandle + '\n')
        except OSError:
            print('EX: unable to write ' + approvedFilename)


def manual_approve_follow_request(session, base_dir: str,
                                  http_prefix: str,
                                  nickname: str, domain: str, port: int,
                                  approveHandle: str,
                                  federation_list: [],
                                  send_threads: [], postLog: [],
                                  cached_webfingers: {}, person_cache: {},
                                  debug: bool,
                                  project_version: str,
                                  signing_priv_key_pem: str) -> None:
    """Manually approve a follow request
    """
    handle = nickname + '@' + domain
    print('Manual follow accept: ' + handle +
          ' approving follow request from ' + approveHandle)
    accountDir = base_dir + '/accounts/' + handle
    approveFollowsFilename = accountDir + '/followrequests.txt'
    if not os.path.isfile(approveFollowsFilename):
        print('Manual follow accept: follow requests file ' +
              approveFollowsFilename + ' not found')
        return

    # is the handle in the requests file?
    approveFollowsStr = ''
    with open(approveFollowsFilename, 'r') as fpFollowers:
        approveFollowsStr = fpFollowers.read()
    exists = False
    approveHandleFull = approveHandle
    if approveHandle in approveFollowsStr:
        exists = True
    elif '@' in approveHandle:
        group_account = False
        if approveHandle.startswith('!'):
            group_account = True
        reqNick = approveHandle.split('@')[0].replace('!', '')
        reqDomain = approveHandle.split('@')[1].strip()
        reqPrefix = http_prefix + '://' + reqDomain
        paths = get_user_paths()
        for userPath in paths:
            if reqPrefix + userPath + reqNick in approveFollowsStr:
                exists = True
                approveHandleFull = reqPrefix + userPath + reqNick
                if group_account:
                    approveHandleFull = '!' + approveHandleFull
                break
    if not exists:
        print('Manual follow accept: ' + approveHandleFull +
              ' not in requests file "' +
              approveFollowsStr.replace('\n', ' ') +
              '" ' + approveFollowsFilename)
        return

    with open(approveFollowsFilename + '.new', 'w+') as approvefilenew:
        updateApprovedFollowers = False
        followActivityfilename = None
        with open(approveFollowsFilename, 'r') as approvefile:
            for handleOfFollowRequester in approvefile:
                # is this the approved follow?
                if handleOfFollowRequester.startswith(approveHandleFull):
                    handleOfFollowRequester = \
                        handleOfFollowRequester.replace('\n', '')
                    handleOfFollowRequester = \
                        handleOfFollowRequester.replace('\r', '')
                    port2 = port
                    if ':' in handleOfFollowRequester:
                        port2 = get_port_from_domain(handleOfFollowRequester)
                    requestsDir = accountDir + '/requests'
                    followActivityfilename = \
                        requestsDir + '/' + handleOfFollowRequester + '.follow'
                    if os.path.isfile(followActivityfilename):
                        followJson = load_json(followActivityfilename)
                        if followJson:
                            approveNickname = approveHandle.split('@')[0]
                            approveDomain = approveHandle.split('@')[1]
                            approveDomain = \
                                approveDomain.replace('\n', '')
                            approveDomain = \
                                approveDomain.replace('\r', '')
                            approvePort = port2
                            if ':' in approveDomain:
                                approvePort = \
                                    get_port_from_domain(approveDomain)
                                approveDomain = \
                                    remove_domain_port(approveDomain)
                            print('Manual follow accept: Sending Accept for ' +
                                  handle + ' follow request from ' +
                                  approveNickname + '@' + approveDomain)
                            followed_account_accepts(session, base_dir,
                                                     http_prefix,
                                                     nickname, domain, port,
                                                     approveNickname,
                                                     approveDomain,
                                                     approvePort,
                                                     followJson['actor'],
                                                     federation_list,
                                                     followJson,
                                                     send_threads, postLog,
                                                     cached_webfingers,
                                                     person_cache,
                                                     debug,
                                                     project_version, False,
                                                     signing_priv_key_pem)
                    updateApprovedFollowers = True
                else:
                    # this isn't the approved follow so it will remain
                    # in the requests file
                    approvefilenew.write(handleOfFollowRequester)

    followersFilename = accountDir + '/followers.txt'
    if updateApprovedFollowers:
        # update the followers
        print('Manual follow accept: updating ' + followersFilename)
        if os.path.isfile(followersFilename):
            if approveHandleFull not in open(followersFilename).read():
                try:
                    with open(followersFilename, 'r+') as followersFile:
                        content = followersFile.read()
                        if approveHandleFull + '\n' not in content:
                            followersFile.seek(0, 0)
                            followersFile.write(approveHandleFull + '\n' +
                                                content)
                except Exception as ex:
                    print('WARN: Manual follow accept. ' +
                          'Failed to write entry to followers file ' + str(ex))
            else:
                print('WARN: Manual follow accept: ' + approveHandleFull +
                      ' already exists in ' + followersFilename)
        else:
            print('Manual follow accept: first follower accepted for ' +
                  handle + ' is ' + approveHandleFull)
            try:
                with open(followersFilename, 'w+') as followersFile:
                    followersFile.write(approveHandleFull + '\n')
            except OSError:
                print('EX: unable to write ' + followersFilename)

    # only update the follow requests file if the follow is confirmed to be
    # in followers.txt
    if approveHandleFull in open(followersFilename).read():
        # mark this handle as approved for following
        _approve_follower_handle(accountDir, approveHandle)
        # update the follow requests with the handles not yet approved
        os.rename(approveFollowsFilename + '.new', approveFollowsFilename)
        # remove the .follow file
        if followActivityfilename:
            if os.path.isfile(followActivityfilename):
                try:
                    os.remove(followActivityfilename)
                except OSError:
                    print('EX: manual_approve_follow_request ' +
                          'unable to delete ' + followActivityfilename)
    else:
        try:
            os.remove(approveFollowsFilename + '.new')
        except OSError:
            print('EX: manual_approve_follow_request unable to delete ' +
                  approveFollowsFilename + '.new')


def manual_approve_follow_request_thread(session, base_dir: str,
                                         http_prefix: str,
                                         nickname: str, domain: str, port: int,
                                         approveHandle: str,
                                         federation_list: [],
                                         send_threads: [], postLog: [],
                                         cached_webfingers: {},
                                         person_cache: {},
                                         debug: bool,
                                         project_version: str,
                                         signing_priv_key_pem: str) -> None:
    """Manually approve a follow request, in a thread so as not to cause
    the UI to lag
    """
    thr = \
        thread_with_trace(target=manual_approve_follow_request,
                          args=(session, base_dir,
                                http_prefix,
                                nickname, domain, port,
                                approveHandle,
                                federation_list,
                                send_threads, postLog,
                                cached_webfingers, person_cache,
                                debug,
                                project_version,
                                signing_priv_key_pem), daemon=True)
    thr.start()
    send_threads.append(thr)
