#
#   Window containing a console pane, used to display output messages in the GUI version.
#   (In the command-line version such messages are simply written to standard output)
#
from PyQt5 import uic
from PyQt5.QtCore import QThread, QMutex, QObject, QEvent
from PyQt5.QtWidgets import QDialog, QListWidgetItem

from CombineThreadWorker import CombineThreadWorker
from DataModel import DataModel
from FileDescriptor import FileDescriptor
from MultiOsUtil import MultiOsUtil
from Preferences import Preferences


class ConsoleWindow(QDialog):
    def __init__(self, preferences: Preferences, data_model: DataModel, descriptors: [FileDescriptor], output_path: str):
        print("ConsoleWindow/init entered")
        QDialog.__init__(self)
        self._data_model = data_model
        self._descriptors = descriptors
        self._output_path = output_path
        self._preferences = preferences
        # Mutex to serialize signal handling from thread
        self._signal_mutex = QMutex()
        self.ui = uic.loadUi(MultiOsUtil.path_for_file_in_program_directory("ConsoleWindow.ui"))

        # If a window size is saved, set the window size
        window_size = self._preferences.get_console_window_size()
        if window_size is not None:
            self.ui.resize(window_size)

        self.buttons_active_state(False)

        # Create thread to run the processing
        self._worker_object = CombineThreadWorker(self._data_model, descriptors, output_path)

        # Create and run the processing thread
        self._qthread = QThread()
        self._worker_object.moveToThread(self._qthread)

        # Have the thread-started signal invoke the actual worker object
        self._qthread.started.connect(self._worker_object.run_combination_session)

        # Have the worker finished signal tell the thread to quit
        self._worker_object.finished.connect(self._qthread.quit)

        # Receive signal when the thread has finished
        self._qthread.finished.connect(self.worker_thread_finished)

        # Other signals of interest
        self._worker_object.console_line.connect(self.add_to_console)

        print("About to start worker thread")
        self.buttons_active_state(True)
        self._qthread.start()
        print("ConsoleWindow/init exits")

    def set_up_ui(self):
        self.ui.installEventFilter(self)

    # Catch window resizing so we can record the changed size

    def eventFilter(self, triggering_object: QObject, event: QEvent) -> bool:
        """Event filter, looking for window resize events so we can remember the new size"""
        if event.type() == QEvent.Resize:
            window_size = event.size()
            self._preferences.set_console_window_size(window_size)
        return False  # Didn't handle event

    def worker_thread_finished(self):
        self.buttons_active_state(False)

    def add_to_console(self, message: str):
        self._signal_mutex.lock()
        # Create the text line to go in the console
        list_item: QListWidgetItem = QListWidgetItem(message)

        # Add to bottom of console and scroll to it
        self.ui.consoleList.addItem(list_item)
        self.ui.consoleList.scrollToItem(list_item)
        self._signal_mutex.unlock()

    def buttons_active_state(self, active: bool):
        self.ui.cancelButton.setEnabled(active)
        self.ui.closeButton.setEnabled(not active)

    # todo catch window resize and remember size in preferences
    # todo catch window move and remember position in preferences
    # todo implement close button
    # todo implement Cancel button - set cancel flag in (create) thread controller