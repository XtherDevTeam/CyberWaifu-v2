import os
import sys
from typing import TextIO

from joblib import Logger

import models

class _Logger():
    def __init__(self, name: str, file: str):
        self.name: str = name
        self.filename: str = file
        self.io: TextIO = self.file()
        print(self.io)

    def file(self) -> TextIO:
        if self.filename == 'stdout':
            print('Logger: using stdout')
            return sys.stdout
        else:
            return open(self.filename, "a")

    def log(self, message, *args):
        self.io.write(f'[{self.name}][{models.TimeProider()}] {message} {" ".join(str(arg) for arg in args)}\n')
        self.io.flush()
        
Logger = _Logger('CyberWaifu V2 backend', 'stdout')