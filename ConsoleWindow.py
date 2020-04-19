#
#   Window containing a console pane, used to display output messages in the GUI version.
#   (In the command-line version such messages are simply written to standard output)
#
from PyQt5 import uic
from PyQt5.QtCore import QThread, QMutex
from PyQt5.QtWidgets import QDialog, QListWidgetItem

from CombineThreadWorker import CombineThreadWorker
from DataModel import DataModel
from FileDescriptor import FileDescriptor
from MultiOsUtil import MultiOsUtil


class ConsoleWindow(QDialog):
    def __init__(self, data_model: DataModel, descriptors: [FileDescriptor]):
        print("ConsoleWindow/init entered")
        QDialog.__init__(self)
        self._data_model = data_model
        self._descriptors = descriptors
        # Mutex to serialize signal handling from thread
        self._signal_mutex = QMutex()
        self.ui = uic.loadUi(MultiOsUtil.path_for_file_in_program_directory("ConsoleWindow.ui"))

        self.buttons_active_state(False)


        # Create thread to run the processing
        self._worker_object = CombineThreadWorker(self._data_model)

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


        # return
        # try:
        #     # Are we using grouped processing?
        #     if self._data_model.get_group_by_exposure() \
        #             or self._data_model.get_group_by_size() \
        #             or self._data_model.get_group_by_temperature():
        #         remove_from_ui = FileCombiner.process_groups(self._data_model, selected_files,
        #                                                      self.get_group_output_directory(),
        #                                                      console)
        #     else:
        #         # Not grouped, producing a single output file. Get output file location
        #         suggested_output_path = SharedUtils.create_output_path(selected_files[0],
        #                                                                self._data_model.get_master_combine_method())
        #         output_path = self.get_output_file(suggested_output_path)
        #         if output_path is not None:
        #             remove_from_ui = FileCombiner.original_non_grouped_processing(selected_files, self._data_model,
        #                                                                           output_path,
        #                                                                           console)
        # except FileNotFoundError as exception:
        #     self.error_dialog("File not found", f"File \"{exception.filename}\" not found or not readable")
        # except MasterMakerExceptions.NoGroupOutputDirectory as exception:
        #     self.error_dialog("Group Directory Missing",
        #                       f"The specified output directory \"{exception.get_directory_name()}\""
        #                       f" does not exist and could not be created.")
        # except MasterMakerExceptions.NotAllDarkFrames:
        #     self.error_dialog("The selected files are not all Dark Frames",
        #                       "If you know the files are dark frames, they may not have proper FITS data "
        #                       "internally. Check the \"Ignore FITS file type\" box to proceed anyway.")
        # except MasterMakerExceptions.IncompatibleSizes:
        #     self.error_dialog("The selected files can't be combined",
        #                       "To be combined into a master file, the files must have identical X and Y "
        #                       "dimensions, and identical Binning values.")
        # except MasterMakerExceptions.NoAutoCalibrationDirectory as exception:
        #     self.error_dialog("Auto Calibration Directory Missing",
        #                       f"The specified directory for auto-calibration files, "
        #                       f"\"{exception.get_directory_name()}\","
        #                       f" does not exist or could not be read.")
        # except MasterMakerExceptions.NoSuitableAutoBias:
        #     self.error_dialog("No matching calibration file",
        #                       "No bias or dark file of appropriate size could be found in the provided "
        #                       "calibration file directory.")
        # except PermissionError as exception:
        #     self.error_dialog("Unable to write file",
        #                       f"The specified output file, "
        #                       f"\"{exception.filename}\","
        #                       f" cannot be written or replaced: \"permission error\"")
        #
        # # # Remove moved files from the table since those paths are no longer valid
        # # self._table_model.remove_files(remove_from_ui)
        # # console.verify_done()

    def worker_thread_finished(self):
        print("worker_thread_finished")
        # todo worker_thread_finished
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

