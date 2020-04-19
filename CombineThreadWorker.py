#
#   Object running the combination routines when running in GUI mode.
#   This object will be run as a sub-thread to leave the UI responsive, both so that
#   Mouse and window responds and so that the user can click a Cancel button up there
#   to stop a long-running process.  There is no good "thread cancel" signal in Python
#   so the "cancel" is implemented by setting a flag which is periodically polled in this thread.
#
from datetime import time
from threading import Thread
from time import sleep

from PyQt5.QtCore import QObject, pyqtSignal

from ConsoleCallback import ConsoleCallback
from DataModel import DataModel


class CombineThreadWorker(QObject):

    #   Signals emitted from the thread

    finished = pyqtSignal()             # Tell interested parties that we are finished
    console_line = pyqtSignal(str)      # Add a line to the console object in the UI

    def __init__(self, data_model: DataModel):
        QObject.__init__(self)
        self._data_model = data_model
        # Create a console object that accepts console output to a local method
        # as a callback.  That will then emit it for the UI to pick up.

    def run_combination_session(self):
        # Create a console output object.  This is passed in to the various math routines
        # to allow them to output progress.  We use this indirect method of getting progress
        # so that it can go to the console window in this case, but the same worker code can send
        # progress lines to the standard system output when being run from the command line
        console = ConsoleCallback(self.console_callback)

        console.message("Starting session", 1)
        # Do actual work
        console.message("Simulating some work", 1)
        for i in range(20):
            sleep(1)
            console.message(f"Step {i+1}", +1, temp=True)
        console.message("Finishing", 1)
        self.finished.emit()

    #
    #   The console object has produced a line it would like displayed.  We'll emit it as a signal
    #   from this sub-thread, so it can be picked up by the main thread and displayed in the console
    #   frame in the user interface.
    #
    def console_callback(self, message: str):
        self.console_line.emit(message)