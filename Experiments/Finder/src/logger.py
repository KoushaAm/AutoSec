import datetime
import os 

class Logger:
    def __init__(self, logdir):
        self.logdir = logdir
        os.makedirs(self.logdir, exist_ok=True)
        t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._logfile=f"{self.logdir}/log{t}.txt"

    def log(self, message, logtype="info", phase="", no_new_line=False, printonly=False):
        message=str(message)
        if len(phase) > 0:
            phase=f" [{phase}]"
        t=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        s=f"[{logtype.upper()}] [{t}]{phase} {message}"
        if no_new_line:
            print(s, end="")
        else:
            print(s)
        if not printonly:
            with open(self._logfile, 'a') as f:
                f.write(s)
                f.write("\n")

    def info(self, message, phase="", no_new_line=False):
        self.log(message, "info", phase, no_new_line=no_new_line)

    def error(self, message, phase=""):
        self.log(message, "error", phase)

    def print(self, message, end=None):
        print(message, end=end)
