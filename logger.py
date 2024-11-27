import os
import sys
from typing import TextIO
import typing

import tools

class _Logger():
    def __init__(self, name: str, file: str):
        self.name: str = name
        self.filename: str = file
        self.io: TextIO = self.file()
        self.callbacks = []
        print(self.io)

    def file(self) -> TextIO:
        if self.filename == 'stdout':
            print('Logger: using stdout')
            return sys.stdout
        else:
            return open(self.filename, "a")

    def log(self, message, *args):
        s = f'[{self.name}][{tools.TimeProvider()}] {message} {" ".join(str(arg) for arg in args)}\n'
        self.io.write(s)
        self.io.flush()
        for callback in self.callbacks:
            callback(s)
        
        
    def registerCallback(self, callback: typing.Callable):
        self.callbacks.append(callback)
        return len(self.callbacks) - 1

    def unregisterCallback(self, index: int):
        if index < len(self.callbacks):
            del self.callbacks[index]
        
Logger = _Logger('CyberWaifu V2 backend', 'stdout')