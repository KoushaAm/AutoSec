import os

class MyLogger:
    def __init__(self, logfile):
        self.logfile=logfile
        os.makedirs(os.path.dirname(self.logfile), exist_ok=True)

    
    def log(self, text, do_print=True):
        if do_print:
            print(text)
        with open(self.logfile, 'a') as f:
            f.write(str(text))
            f.write("\n")




