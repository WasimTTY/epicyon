__filename__ = "threads.py"
__author__ = "Bob Mottram"
__license__ = "AGPL3+"
__version__ = "1.2.0"
__maintainer__ = "Bob Mottram"
__email__ = "bob@libreserver.org"
__status__ = "Production"
__module_group__ = "Core"

import threading
import sys
import time
import datetime


class thread_with_trace(threading.Thread):
    def __init__(self, *args, **keywords):
        self.startTime = datetime.datetime.utcnow()
        self.isStarted = False
        tries = 0
        while tries < 3:
            try:
                self._args, self._keywords = args, keywords
                threading.Thread.__init__(self, *self._args, **self._keywords)
                self.killed = False
                break
            except Exception as ex:
                print('ERROR: threads.py/__init__ failed - ' + str(ex))
                time.sleep(1)
                tries += 1

    def start(self):
        tries = 0
        while tries < 3:
            try:
                self.__run_backup = self.run
                self.run = self.__run
                threading.Thread.start(self)
                break
            except Exception as ex:
                print('ERROR: threads.py/start failed - ' + str(ex))
                time.sleep(1)
                tries += 1
        # note that this is set True even if all tries failed
        self.isStarted = True

    def __run(self):
        sys.settrace(self.globaltrace)
        try:
            self.__run_backup()
            self.run = self.__run_backup
        except Exception as ex:
            print('ERROR: threads.py/__run failed - ' + str(ex))
            pass

    def globaltrace(self, frame, event, arg):
        if event == 'call':
            return self.localtrace
        else:
            return None

    def localtrace(self, frame, event, arg):
        if self.killed:
            if event == 'line':
                raise SystemExit()
        return self.localtrace

    def kill(self):
        self.killed = True

    def clone(self, fn):
        return thread_with_trace(target=fn,
                                 args=self._args,
                                 daemon=True)


def remove_dormant_threads(base_dir: str, threadsList: [], debug: bool,
                           timeoutMins: int) -> None:
    """Removes threads whose execution has completed
    """
    if len(threadsList) == 0:
        return

    timeoutSecs = int(timeoutMins * 60)
    dormantThreads = []
    curr_time = datetime.datetime.utcnow()
    changed = False

    # which threads are dormant?
    noOfActiveThreads = 0
    for th in threadsList:
        removeThread = False

        if th.isStarted:
            if not th.is_alive():
                if (curr_time - th.startTime).total_seconds() > 10:
                    if debug:
                        print('DEBUG: ' +
                              'thread is not alive ten seconds after start')
                    removeThread = True
            # timeout for started threads
            if (curr_time - th.startTime).total_seconds() > timeoutSecs:
                if debug:
                    print('DEBUG: started thread timed out')
                removeThread = True
        else:
            # timeout for threads which havn't been started
            if (curr_time - th.startTime).total_seconds() > timeoutSecs:
                if debug:
                    print('DEBUG: unstarted thread timed out')
                removeThread = True

        if removeThread:
            dormantThreads.append(th)
        else:
            noOfActiveThreads += 1
    if debug:
        print('DEBUG: ' + str(noOfActiveThreads) +
              ' active threads out of ' + str(len(threadsList)))

    # remove the dormant threads
    dormantCtr = 0
    for th in dormantThreads:
        if debug:
            print('DEBUG: Removing dormant thread ' + str(dormantCtr))
        dormantCtr += 1
        threadsList.remove(th)
        th.kill()
        changed = True

    # start scheduled threads
    if len(threadsList) < 10:
        ctr = 0
        for th in threadsList:
            if not th.isStarted:
                print('Starting new send thread ' + str(ctr))
                th.start()
                changed = True
                break
            ctr += 1

    if not changed:
        return

    if debug:
        sendLogFilename = base_dir + '/send.csv'
        try:
            with open(sendLogFilename, 'a+') as logFile:
                logFile.write(curr_time.strftime("%Y-%m-%dT%H:%M:%SZ") +
                              ',' + str(noOfActiveThreads) +
                              ',' + str(len(threadsList)) + '\n')
        except OSError:
            print('EX: remove_dormant_threads unable to write ' +
                  sendLogFilename)
