#
#   Window controller for the main window
#   Manages the UI and initiates a combination action if all is well
#

import os
from datetime import datetime
from typing import Optional

from PyQt5 import uic
from PyQt5.QtCore import QObject, QEvent, QModelIndex, QThread
from PyQt5.QtWidgets import QMainWindow, QDialog, QHeaderView, QFileDialog, QMessageBox

import MasterMakerExceptions
from CombineThreadWorker import CombineThreadWorker
from Console import Console
from ConsoleWindow import ConsoleWindow
from Constants import Constants
from DataModel import DataModel
from FileCombiner import FileCombiner
from FileDescriptor import FileDescriptor
from FitsFileTableModel import FitsFileTableModel
from MultiOsUtil import MultiOsUtil
from Preferences import Preferences
from PreferencesWindow import PreferencesWindow
from RmFitsUtil import RmFitsUtil
from SharedUtils import SharedUtils
from Validators import Validators


class MainWindow(QMainWindow):

    def __init__(self, preferences: Preferences, data_model: DataModel):
        """Initialize MainWindow class"""
        self._preferences = preferences
        self._data_model = data_model
        QMainWindow.__init__(self)
        self.ui = uic.loadUi(MultiOsUtil.path_for_file_in_program_directory("MainWindow.ui"))
        self._field_validity: {object, bool} = {}
        self._table_model: FitsFileTableModel
        self._indent_level = 0

        # Load algorithm from preferences

        algorithm = data_model.get_master_combine_method()
        if algorithm == Constants.COMBINE_MEAN:
            self.ui.combineMeanRB.setChecked(True)
        elif algorithm == Constants.COMBINE_MEDIAN:
            self.ui.combineMedianRB.setChecked(True)
        elif algorithm == Constants.COMBINE_MINMAX:
            self.ui.combineMinMaxRB.setChecked(True)
        else:
            assert (algorithm == Constants.COMBINE_SIGMA_CLIP)
            self.ui.combineSigmaRB.setChecked(True)

        self.ui.minMaxNumDropped.setText(str(data_model.get_min_max_number_clipped_per_end()))
        self.ui.sigmaThreshold.setText(str(data_model.get_sigma_clip_threshold()))

        # Load disposition from preferences

        disposition = data_model.get_input_file_disposition()
        if disposition == Constants.INPUT_DISPOSITION_SUBFOLDER:
            self.ui.dispositionSubFolderRB.setChecked(True)
        else:
            assert (disposition == Constants.INPUT_DISPOSITION_NOTHING)
            self.ui.dispositionNothingRB.setChecked(True)
        self.ui.subFolderName.setText(data_model.get_disposition_subfolder_name())

        # Pre-calibration options

        precalibration_option = data_model.get_precalibration_type()
        if precalibration_option == Constants.CALIBRATION_FIXED_FILE:
            self.ui.fixedPreCalFileRB.setChecked(True)
        elif precalibration_option == Constants.CALIBRATION_NONE:
            self.ui.noPreClalibrationRB.setChecked(True)
        elif precalibration_option == Constants.CALIBRATION_AUTO_DIRECTORY:
            self.ui.autoPreCalibrationRB.setChecked(True)
        else:
            assert precalibration_option == Constants.CALIBRATION_PEDESTAL
            self.ui.fixedPedestalRB.setChecked(True)
        self.ui.fixedPedestalAmount.setText(str(data_model.get_precalibration_pedestal()))
        self.ui.precalibrationPathDisplay.setText(os.path.basename(data_model.get_precalibration_fixed_path()))
        self.ui.autoDirectoryName.setText(os.path.basename(data_model.get_precalibration_auto_directory()))

        # Grouping boxes and parameters

        self.ui.groupBySizeCB.setChecked(data_model.get_group_by_size())
        self.ui.groupByExposureCB.setChecked(data_model.get_group_by_exposure())
        self.ui.groupByTemperatureCB.setChecked(data_model.get_group_by_temperature())
        self.ui.ignoreSmallGroupsCB.setChecked(data_model.get_ignore_groups_fewer_than())

        self.ui.exposureGroupTolerance.setText(f"{100 * data_model.get_exposure_group_tolerance():.0f}")
        self.ui.temperatureGroupTolerance.setText(f"{100 * data_model.get_temperature_group_tolerance():.0f}")
        self.ui.minimumGroupSize.setText(str(data_model.get_minimum_group_size()))

        # Set up the file table
        self._table_model = FitsFileTableModel(data_model.get_ignore_file_type())
        self.ui.filesTable.setModel(self._table_model)
        # Columns should resize to best fit their contents
        self.ui.filesTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.connect_responders()

        # If a window size is saved, set the window size
        window_size = self._preferences.get_main_window_size()
        if window_size is not None:
            self.ui.resize(window_size)

        self.enable_fields()
        self.enable_buttons()

    # Connect UI controls to methods here for response
    def connect_responders(self):
        """Connect UI fields and controls to the methods that respond to them"""

        # Menu items
        self.ui.actionPreferences.triggered.connect(self.preferences_menu_triggered)
        self.ui.actionOpen.triggered.connect(self.pick_files_button_clicked)
        self.ui.actionSelectAll.triggered.connect(self.select_all_clicked)

        #  Responder for algorithm buttons
        self.ui.combineMeanRB.clicked.connect(self.algorithm_button_clicked)
        self.ui.combineMedianRB.clicked.connect(self.algorithm_button_clicked)
        self.ui.combineMinMaxRB.clicked.connect(self.algorithm_button_clicked)
        self.ui.combineSigmaRB.clicked.connect(self.algorithm_button_clicked)

        # Responders for algorithm fields
        self.ui.minMaxNumDropped.editingFinished.connect(self.min_max_drop_changed)
        self.ui.sigmaThreshold.editingFinished.connect(self.sigma_threshold_changed)

        # Responder for disposition buttons
        self.ui.dispositionNothingRB.clicked.connect(self.disposition_button_clicked)
        self.ui.dispositionSubFolderRB.clicked.connect(self.disposition_button_clicked)

        # Responder for disposition subfolder name
        self.ui.subFolderName.editingFinished.connect(self.sub_folder_name_changed)

        # Responder for "Pick Files" button
        self.ui.pickFilesButton.clicked.connect(self.pick_files_button_clicked)

        # React to changed selection in file table
        table_selection_model = self.ui.filesTable.selectionModel()
        table_selection_model.selectionChanged.connect(self.table_selection_changed)

        # Responders for select all and select none
        self.ui.selectAllButton.clicked.connect(self.select_all_clicked)
        self.ui.selectNoneButton.clicked.connect(self.select_none_clicked)

        # "Ignore file type" checkbox
        self.ui.ignoreFileType.clicked.connect(self.ignore_file_type_clicked)

        # Main "combine" button
        self.ui.combineSelectedButton.clicked.connect(self.combine_selected_clicked)

        # Buttons and fields in precalibration area
        self.ui.noPreClalibrationRB.clicked.connect(self.precalibration_radio_group_clicked)
        self.ui.fixedPedestalRB.clicked.connect(self.precalibration_radio_group_clicked)
        self.ui.autoPreCalibrationRB.clicked.connect(self.precalibration_radio_group_clicked)
        self.ui.fixedPreCalFileRB.clicked.connect(self.precalibration_radio_group_clicked)
        self.ui.selectPreCalFile.clicked.connect(self.select_precalibration_file_clicked)
        self.ui.setAutoDirectory.clicked.connect(self.select_auto_calibration_directory_clicked)
        self.ui.fixedPedestalAmount.editingFinished.connect(self.pedestal_amount_changed)

        # Grouping controls
        self.ui.groupBySizeCB.clicked.connect(self.group_by_size_clicked)
        self.ui.groupByExposureCB.clicked.connect(self.group_by_exposure_clicked)
        self.ui.groupByTemperatureCB.clicked.connect(self.group_by_temperature_clicked)
        self.ui.ignoreSmallGroupsCB.clicked.connect(self.ignore_small_groups_clicked)
        self.ui.exposureGroupTolerance.editingFinished.connect(self.exposure_group_tolerance_changed)
        self.ui.temperatureGroupTolerance.editingFinished.connect(self.temperature_group_tolerance_changed)
        self.ui.minimumGroupSize.editingFinished.connect(self.minimum_group_size_changed)

        # Tiny fonts in path display fields
        tiny_font = self.ui.precalibrationPathDisplay.font()
        tiny_font.setPointSize(10)
        self.ui.precalibrationPathDisplay.setFont(tiny_font)
        self.ui.autoDirectoryName.setFont(tiny_font)

    # Certain initialization must be done after "__init__" is finished.
    def set_up_ui(self):
        """Perform initialization that requires class init to be finished"""
        # Catch events so we can see window resizing
        self.ui.installEventFilter(self)

    # Catch window resizing so we can record the changed size

    def eventFilter(self, triggering_object: QObject, event: QEvent) -> bool:
        """Event filter, looking for window resize events so we can remember the new size"""
        if event.type() == QEvent.Resize:
            window_size = event.size()
            self._preferences.set_main_window_size(window_size)
        return False  # Didn't handle event

    # "Ignore file type" button clicked.  Tell the data model the new value.
    def ignore_file_type_clicked(self):
        """Respond to clicking 'ignore file type' button"""
        self._data_model.set_ignore_file_type(self.ui.ignoreFileType.isChecked())
        self._table_model.set_ignore_file_type(self._data_model.get_ignore_file_type())

    # Select-all button has been clicked

    def select_all_clicked(self):
        """Select all the rows in the files table"""
        self.ui.filesTable.selectAll()
        self.enable_buttons()
        self.enable_fields()

    # Select-None button has been clicked

    def select_none_clicked(self):
        """Clear the table selection, leaving no rows selected"""
        self.ui.filesTable.clearSelection()
        self.enable_buttons()
        self.enable_fields()

    def algorithm_button_clicked(self):
        """ One of the algorithm buttons is clicked.  Change what fields are enabled"""
        algorithm: int
        if self.ui.combineMeanRB.isChecked():
            algorithm = Constants.COMBINE_MEAN
        elif self.ui.combineMedianRB.isChecked():
            algorithm = Constants.COMBINE_MEDIAN
        elif self.ui.combineMinMaxRB.isChecked():
            algorithm = Constants.COMBINE_MINMAX
        else:
            assert self.ui.combineSigmaRB.isChecked()
            algorithm = Constants.COMBINE_SIGMA_CLIP
        self._data_model.set_master_combine_method(algorithm)
        self.enable_fields()
        self.enable_buttons()

    def group_by_size_clicked(self):
        self._data_model.set_group_by_size(self.ui.groupBySizeCB.isChecked())
        self.enable_fields()
        self.enable_buttons()

    def group_by_exposure_clicked(self):
        self._data_model.set_group_by_exposure(self.ui.groupByExposureCB.isChecked())
        self.enable_fields()
        self.enable_buttons()

    def group_by_temperature_clicked(self):
        self._data_model.set_group_by_temperature(self.ui.groupByTemperatureCB.isChecked())
        self.enable_fields()
        self.enable_buttons()

    def ignore_small_groups_clicked(self):
        self._data_model.set_ignore_groups_fewer_than(self.ui.ignoreSmallGroupsCB.isChecked())
        self.enable_fields()
        self.enable_buttons()

    def disposition_button_clicked(self):
        """ One of the disposition buttons is clicked.  Change what fields are enabled"""
        disposition: int
        if self.ui.dispositionNothingRB.isChecked():
            disposition = Constants.INPUT_DISPOSITION_NOTHING
        else:
            assert(self.ui.dispositionSubFolderRB.isChecked())
            disposition = Constants.INPUT_DISPOSITION_SUBFOLDER
        self._data_model.set_input_file_disposition(disposition)
        self.enable_fields()
        self.enable_buttons()

    def pedestal_amount_changed(self):
        """the field giving the fixed calibration pedestal amount has been changed.
        Validate it (integer > 0) and store if valid"""
        proposed_new_number: str = self.ui.fixedPedestalAmount.text()
        new_number = Validators.valid_int_in_range(proposed_new_number, 0, 32767)
        valid = new_number is not None
        if valid:
            self._data_model.set_precalibration_pedestal(new_number)
        SharedUtils.background_validity_color(self.ui.fixedPedestalAmount, valid)
        self._field_validity[self.ui.fixedPedestalAmount] = valid
        self.enable_buttons()

    def minimum_group_size_changed(self):
        """the field giving the minimum group size to recognize has been changed.
        Validate it (integer > 1) and store if valid"""
        proposed_new_number: str = self.ui.minimumGroupSize.text()
        new_number = Validators.valid_int_in_range(proposed_new_number, 1, 32767)
        valid = new_number is not None
        if valid:
            self._data_model.set_minimum_group_size(new_number)
        SharedUtils.background_validity_color(self.ui.minimumGroupSize, valid)
        self._field_validity[self.ui.minimumGroupSize] = valid
        self.enable_buttons()

    def min_max_drop_changed(self):
        """the field giving the number of minimum and maximum values to drop has been changed.
        Validate it (integer > 0) and store if valid"""
        proposed_new_number: str = self.ui.minMaxNumDropped.text()
        new_number = Validators.valid_int_in_range(proposed_new_number, 0, 256)
        valid = new_number is not None
        if valid:
            self._data_model.set_min_max_number_clipped_per_end(new_number)
        SharedUtils.background_validity_color(self.ui.minMaxNumDropped, valid)
        self._field_validity[self.ui.minMaxNumDropped] = valid
        self.enable_buttons()

    def sigma_threshold_changed(self):
        """the field giving the sigma limit beyond which values are ignored has changed
        Validate it (floating point > 0) and store if valid"""
        proposed_new_number: str = self.ui.sigmaThreshold.text()
        new_number = Validators.valid_float_in_range(proposed_new_number, 0.01, 100.0)
        valid = new_number is not None
        if valid:
            self._data_model.set_sigma_clip_threshold(new_number)
        SharedUtils.background_validity_color(self.ui.sigmaThreshold, valid)
        self._field_validity[self.ui.sigmaThreshold] = valid
        self.enable_buttons()

    def sub_folder_name_changed(self):
        """the field giving the name of the sub-folder to be created or used has changed.
        Validate that it is an acceptable folder name and store if valid"""
        proposed_new_name: str = self.ui.subFolderName.text()
        # valid = Validators.valid_file_name(proposed_new_name, 1, 31)
        valid = SharedUtils.validate_folder_name(proposed_new_name)
        if valid:
            self._data_model.set_disposition_subfolder_name(proposed_new_name)
        SharedUtils.background_validity_color(self.ui.subFolderName, valid)
        self._field_validity[self.ui.subFolderName] = valid
        self.enable_buttons()

    def exposure_group_tolerance_changed(self):
        """User has entered value in exposure group tolerance field.  Validate and save"""
        proposed_new_number: str = self.ui.exposureGroupTolerance.text()
        new_number = Validators.valid_float_in_range(proposed_new_number, 0.0, 99.999)
        valid = new_number is not None
        if valid:
            self._data_model.set_exposure_group_tolerance(new_number / 100.0)
        SharedUtils.background_validity_color(self.ui.exposureGroupTolerance, valid)
        self._field_validity[self.ui.exposureGroupTolerance] = valid

    def temperature_group_tolerance_changed(self):
        """User has entered value in temperature group tolerance field.  Validate and save"""
        proposed_new_number: str = self.ui.temperatureGroupTolerance.text()
        new_number = Validators.valid_float_in_range(proposed_new_number, 0.0, 99.999)
        valid = new_number is not None
        if valid:
            self._data_model.set_temperature_group_tolerance(new_number / 100.0)
        SharedUtils.background_validity_color(self.ui.temperatureGroupTolerance, valid)
        self._field_validity[self.ui.temperatureGroupTolerance] = valid

    def enable_fields(self):
        """Enable text fields depending on state of various radio buttons"""

        precalibration_type = self._data_model.get_precalibration_type()
        self.ui.fixedPedestalAmount.setEnabled(precalibration_type == Constants.CALIBRATION_PEDESTAL)

        # Enable Algorithm fields depending on which algorithm is selected
        combination_type = self._data_model.get_master_combine_method()
        self.ui.minMaxNumDropped.setEnabled(combination_type == Constants.COMBINE_MINMAX)
        self.ui.sigmaThreshold.setEnabled(combination_type == Constants.COMBINE_SIGMA_CLIP)

        # Enable Disposition fields depending on which disposition is selected
        self.ui.subFolderName.setEnabled(self._data_model.get_input_file_disposition()
                                         == Constants.INPUT_DISPOSITION_SUBFOLDER)

        # Grouping parameters go with their corresponding checkbox
        self.ui.exposureGroupTolerance.setEnabled(self._data_model.get_group_by_exposure())
        self.ui.temperatureGroupTolerance.setEnabled(self._data_model.get_group_by_temperature())

    # Open a file dialog to pick files to be processed

    def pick_files_button_clicked(self):
        """'Pick Files' button or 'Open' menu item are selected.  Get the input files from the user."""
        dialog = QFileDialog()
        file_names, _ = QFileDialog.getOpenFileNames(dialog, "Pick Files", "",
                                                     f"FITS files(*.fit)",
                                                     # options=QFileDialog.ReadOnly | QFileDialog.DontUseNativeDialog)
                                                     options=QFileDialog.ReadOnly)
        if len(file_names) == 0:
            # User clicked "cancel"
            pass
        else:
            try:
                file_descriptions = RmFitsUtil.make_file_descriptions(file_names)
                self._table_model.set_file_descriptors(file_descriptions)
            except FileNotFoundError as exception:
                self.error_dialog("File Not Found", f"File \"{exception.filename}\" was not found or not readable")
        self.enable_buttons()

    def error_dialog(self, brief_message: str, long_message: str, detailed_text: str = ""):
        dialog = QMessageBox()
        dialog.setText(brief_message)
        if len(long_message) > 0:
            if not long_message.endswith("."):
                long_message += "."
        dialog.setInformativeText(long_message)
        if len(detailed_text) > 0:
            dialog.setDetailedText(detailed_text)
        dialog.setIcon(QMessageBox.Critical)
        dialog.setStandardButtons(QMessageBox.Ok)
        dialog.setDefaultButton(QMessageBox.Ok)
        dialog.exec_()

    def table_selection_changed(self):
        """Rows selected in the file table have changed; check for button enablement"""
        selected = self.ui.filesTable.selectionModel().selectedRows()
        self.ui.selectedLabel.setText(f"{len(selected)} rows selected")
        self.enable_buttons()
        self.enable_fields()

    def precalibration_radio_group_clicked(self):
        calibration_type: int
        if self.ui.noPreClalibrationRB.isChecked():
            calibration_type = Constants.CALIBRATION_NONE
        elif self.ui.fixedPreCalFileRB.isChecked():
            calibration_type = Constants.CALIBRATION_FIXED_FILE
        elif self.ui.autoPreCalibrationRB.isChecked():
            calibration_type = Constants.CALIBRATION_AUTO_DIRECTORY
        else:
            assert self.ui.fixedPedestalRB.isChecked()
            calibration_type = Constants.CALIBRATION_PEDESTAL
        self._data_model.set_precalibration_type(calibration_type)
        self.enable_buttons()
        self.enable_fields()

    def select_precalibration_file_clicked(self):
        (file_name, _) = QFileDialog.getOpenFileName(parent=self, caption="Select dark or bias file",
                                                     filter="FITS files(*.fit *.fits)",
                                                     options=QFileDialog.ReadOnly)
        if len(file_name) > 0:
            self._data_model.set_precalibration_fixed_path(file_name)
            self.ui.precalibrationPathDisplay.setText(os.path.basename(file_name))
        self.enable_fields()
        self.enable_buttons()

    def select_auto_calibration_directory_clicked(self):
        file_name = QFileDialog.getExistingDirectory(parent=None, caption="Calibration File Directory")
        if len(file_name) > 0:
            self._data_model.set_precalibration_auto_directory(file_name)
            self.ui.autoDirectoryName.setText(os.path.basename(file_name))
        self.enable_fields()
        self.enable_buttons()

    def enable_buttons(self):
        """Enable buttons on the main window depending on validity and settings
        of other controls"""

        calibration_type = self._data_model.get_precalibration_type()
        self.ui.selectPreCalFile.setEnabled(calibration_type == Constants.CALIBRATION_FIXED_FILE)
        self.ui.setAutoDirectory.setEnabled(calibration_type == Constants.CALIBRATION_AUTO_DIRECTORY)
        self.ui.minimumGroupSize.setEnabled(self._data_model.get_ignore_groups_fewer_than())

        # "combineSelectedButton" is enabled only if
        #   - No text fields are in error state
        #   - At least one row in the file table is selected
        #   - If Min/Max algorithm selected with count "n", > 2n files selected
        #   - If sigma-clip algorithm selected, >= 3 files selected
        #   - If fixed precalibration file option selected, path must exist
        #   - If precalibration auto-directory is selected, directory must exist
        #   - All files must be same dimensions and binning (unless grouping by size)

        # We'll say why it's disabled in the tool tip

        tool_tip_text: str = "Combined the selected files into a master bias"

        combination_type = self._data_model.get_master_combine_method()
        calibration_type = self._data_model.get_precalibration_type()

        calibration_path_ok = True
        calibration_directory_ok = True
        dimensions_ok = True

        text_fields_valid = self.all_text_fields_valid()
        if not text_fields_valid:
            tool_tip_text = "Disabled because of invalid text fields (shown in red)"

        selected_row_indices = self.ui.filesTable.selectionModel().selectedRows()
        if len(selected_row_indices) == 0:
            tool_tip_text = "Disabled because more than one file needs to be selected"

        sigma_clip_enough_files = (combination_type != Constants.COMBINE_SIGMA_CLIP) or len(selected_row_indices) >= 3
        if not sigma_clip_enough_files:
            tool_tip_text = "Disabled because not enough files selected for sigma-clip method"

        if calibration_type == Constants.CALIBRATION_FIXED_FILE:
            calibration_path_ok = os.path.isfile(self._data_model.get_precalibration_fixed_path())
            if not calibration_path_ok:
                tool_tip_text = "Disabled because specified calibration file does not exist"

        if calibration_path_ok:
            dimensions_ok = self._data_model.get_group_by_size() \
                            or FileCombiner.validate_file_dimensions(self.get_selected_file_descriptors(),
                                                                     self._data_model)
            if not dimensions_ok:
                tool_tip_text = "Disabled because all files (including bias file if selected)" \
                                " do not have the same dimensions and binning and Group by Size not selected"

        if calibration_type == Constants.CALIBRATION_AUTO_DIRECTORY:

            directory_name = self._data_model.get_precalibration_auto_directory()
            calibration_directory_ok = os.path.isdir(directory_name)
            if not calibration_directory_ok:
                tool_tip_text = f"Auto-precalibration directory {directory_name}" \
                                f" does not exist."

        self.ui.combineSelectedButton.setEnabled(text_fields_valid
                                                 and len(selected_row_indices) > 1
                                                 and self.min_max_enough_files(len(selected_row_indices))
                                                 and sigma_clip_enough_files
                                                 and dimensions_ok
                                                 and calibration_directory_ok
                                                 and calibration_path_ok)
        self.ui.combineSelectedButton.setToolTip(tool_tip_text)

        # Enable select all and none only if rows in table
        any_rows = self._table_model.rowCount(QModelIndex()) > 0
        self.ui.selectNoneButton.setEnabled(any_rows)
        self.ui.selectAllButton.setEnabled(any_rows)

    def preferences_menu_triggered(self):
        """Respond to preferences menu by opening preferences dialog"""
        dialog: PreferencesWindow = PreferencesWindow()
        dialog.set_up_ui(self._preferences)
        QDialog.DialogCode = dialog.ui.exec_()

    def all_text_fields_valid(self):
        """Return whether all text fields are valid.  (In fact, returns that
        no text fields are invalid - not necessarily the same, since it is possible that
        a text field has not been tested.)"""
        all_fields_good = all(valid for valid in self._field_validity.values())
        return all_fields_good

    #
    #   The user has clicked "Combine", which is the "go ahead and do the work" button.
    #   The actual work is done as a thread hanging under a console window.  So all we do here
    #   is create and run the console window.
    #
    def combine_selected_clicked(self):
        if self.commit_fields_continue():
            # Get the list of selected files
            selected_files: [FileDescriptor] = self.get_selected_file_descriptors()
            assert len(selected_files) > 0  # Or else the button would have been disabled
            # remove_from_ui: [FileDescriptor] = []
            # Open console window, which will create and run the worker thread
            console_window: ConsoleWindow = ConsoleWindow(self._data_model, selected_files)
            console_window.ui.exec_()
            # We get here when the worker task has finished or been cancelled, and the console window closed.
            print("Session thread has ended")
        else:
            # Something in the input field commit was invalid; if they had hit return
            # the Combine button would have been disabled and we would never have come here.
            # So we'll exit now to encourage them to fix the error.
            pass

    # Run the "editing finished" methods on all the inputs in case they have typed
    # something but not hit tab or return to commit it - they will expect what they
    # see to be what gets processed.  Then re-check if the Commit button is still enabled.

    def commit_fields_continue(self) -> bool:
        self.exposure_group_tolerance_changed()
        self.min_max_drop_changed()
        self.minimum_group_size_changed()
        self.pedestal_amount_changed()
        self.sigma_threshold_changed()
        self.sub_folder_name_changed()
        self.temperature_group_tolerance_changed()
        self.enable_buttons()
        return self.ui.combineSelectedButton.isEnabled()

    def get_group_output_directory(self) -> str:
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        (file_name, _) = dialog.getSaveFileName(parent=None, caption="Output Directory")
        return None if len(file_name.strip()) == 0 else file_name

    # Get the file descriptors corresponding to the selected table rows
    def get_selected_file_descriptors(self) -> [FileDescriptor]:
        table_descriptors: [FileDescriptor] = self._table_model.get_file_descriptors()
        selected_rows: [int] = self.ui.filesTable.selectionModel().selectedRows()
        result: [FileDescriptor] = []
        for next_selected in selected_rows:
            row_index = next_selected.row()
            result.append(table_descriptors[row_index])
        return result

    # Prompt user for output file to receive combined file
    def get_output_file(self, suggested_file_path: str) -> str:
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.AnyFile)
        (file_name, _) = dialog.getSaveFileName(parent=None, caption="Master File", directory=suggested_file_path,
                                                filter="FITS files (*.FIT)")
        return None if len(file_name.strip()) == 0 else file_name

    # Determine if there are enough files selected for the Min-Max algorithm
    # If that algorithm isn't selected, then return True
    # Otherwise there should be more files selected than 2*n, where n is the
    # min-max clipping value
    def min_max_enough_files(self, num_selected: int) -> bool:
        return True if self._data_model.get_master_combine_method() != Constants.COMBINE_MINMAX \
            else num_selected > (2 * self._data_model.get_min_max_number_clipped_per_end())

