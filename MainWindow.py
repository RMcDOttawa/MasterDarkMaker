#
#   Window controller for the main window
#   Manages the UI and initiates a combination action if all is well
#

import os
from typing import Optional

import numpy
from PyQt5 import uic
from PyQt5.QtCore import QObject, QEvent, QModelIndex
from PyQt5.QtWidgets import QMainWindow, QDialog, QHeaderView, QFileDialog, QMessageBox

from CommandLineHandler import CommandLineHandler
from Constants import Constants
from DataModel import DataModel
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
        if  precalibration_option == Constants.CALIBRATION_FIXED_FILE:
            self.ui.fixedPreCalFileRB.setChecked(True)
        elif precalibration_option == Constants.CALIBRATION_NONE:
            self.ui.noPreClalibrationRB.setChecked(True)
        elif precalibration_option == Constants.CALIBRATION_AUTO_DIRECTORY:
            self.ui.autoPreCalibrationRB.setChecked(True)
        elif precalibration_option == Constants.CALIBRATION_AUTO_DIRECTORY:
            print("Auto precalibration STUB")
            # todo Auto precalibration
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

        self.ui.exposureGroupTolerance.setText(f"{100 * data_model.get_exposure_group_tolerance():.0f}")
        self.ui.temperatureGroupTolerance.setText(f"{100 * data_model.get_temperature_group_tolerance():.0f}")

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
        self.ui.exposureGroupTolerance.editingFinished.connect(self.exposure_group_tolerance_changed)
        self.ui.temperatureGroupTolerance.editingFinished.connect(self.temperature_group_tolerance_changed)

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
            self._data_model.set_exposure_group_tolerance(new_number)
        SharedUtils.background_validity_color(self.ui.exposureGroupTolerance, valid)
        self._field_validity[self.ui.exposureGroupTolerance] = valid

    def temperature_group_tolerance_changed(self):
        """User has entered value in temperature group tolerance field.  Validate and save"""
        proposed_new_number: str = self.ui.temperatureGroupTolerance.text()
        new_number = Validators.valid_float_in_range(proposed_new_number, 0.0, 99.999)
        valid = new_number is not None
        if valid:
            self._data_model.set_temperature_group_tolerance(new_number)
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
            file_descriptions = self.make_file_descriptions(file_names)
            self._data_model.set_file_descriptors(file_descriptions)
            self._table_model.set_file_descriptors(self._data_model.get_file_descriptors())
        self.enable_buttons()

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
            self._data_model.set_precalibration_file_full_path(file_name)
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
            tool_tip_text = "Disabled because no files are selected"

        sigma_clip_enough_files = (combination_type != Constants.COMBINE_SIGMA_CLIP) or len(selected_row_indices) >= 3
        if not sigma_clip_enough_files:
            tool_tip_text = "Disabled because not enough files selected for sigma-clip method"

        if calibration_type == Constants.CALIBRATION_FIXED_FILE:
            calibration_path_ok = os.path.isfile(self._data_model.get_precalibration_fixed_path())
            if not calibration_path_ok:
                tool_tip_text = "Disabled because specified calibration file does not exist"

        if calibration_path_ok:
            dimensions_ok = self._data_model.get_group_by_size() or self.validate_file_dimensions()
            if not dimensions_ok:
                tool_tip_text = "Disabled because all files (including bias file if selected)" \
                                " do not have the same dimensions and binning and Group by Size not selected"

        if calibration_type == Constants.CALIBRATION_AUTO_DIRECTORY:
            calibration_directory_ok = os.path.isdir(self._data_model.get_precalibration_auto_directory())
            if not calibration_directory_ok:
                tool_tip_text = f"Auto-precalibration directory {os.path.basename(self._precalibration_auto_directory)}" \
                                f" does not exist."

        self.ui.combineSelectedButton.setEnabled(text_fields_valid
                                                 and len(selected_row_indices) > 0
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

    def make_file_descriptions(self, file_names: [str]) -> [FileDescriptor]:
        result: [FileDescriptor] = []
        for absolute_path in file_names:
            descriptor = RmFitsUtil.make_file_descriptor(absolute_path)
            result.append(descriptor)
        return result

    def combine_selected_clicked(self):
        # Get the list of selected files
        selected_files: [FileDescriptor] = self.get_selected_file_descriptors()
        assert len(selected_files) > 0  # Or else the button would have been disabled
        if self._data_model.get_group_by_exposure() \
                or self._data_model.get_group_by_size() \
                or self._data_model.get_group_by_temperature():
            self.process_groups(selected_files)
        else:
            self.original_non_grouped_processing(selected_files)

    # Get description of any precalibration to be done
    # Return flag if any precalibration, pedestal value, and image array if image file used.
    # Image file might be read from pre-defined path, or might be read after prompting user
    # Return success, precalibration type code, pedestal, fixed calibration array (or None)

    def get_precalibration_info(self, sample_file: FileDescriptor) -> (bool,  # success
                                                                       Optional[int],  # precal type
                                                                       Optional[int],  # pedestal
                                                                       Optional[numpy.ndarray]):  # Image
        precalibration_code: int = self._data_model.get_precalibration_type()
        pedestal_value = None
        image_data = None
        success = True
        if precalibration_code == Constants.CALIBRATION_PEDESTAL:
            pedestal_value = self._data_model.get_precalibration_pedestal()
        elif precalibration_code == Constants.CALIBRATION_FIXED_FILE:
            image_data = RmFitsUtil.fits_data_from_path(self._data_model.get_precalibration_fixed_path())
        elif precalibration_code == Constants.CALIBRATION_AUTO_DIRECTORY:
            # Get the best matched precalibration file from the directory.  Fail if none
            image_data = self.get_best_calibration_file(self._data_model.get_precalibration_auto_directory(), sample_file)
            success = image_data is not None
            if not success:
                no_directory = QMessageBox()
                no_directory.setText("Unable to find a suitable calibration file.")
                no_directory.setInformativeText("The output directory you specified does not contain any "
                                                "Bias files that are a match (size and binning) to the images needing calibration.")
                no_directory.setStandardButtons(QMessageBox.Ok)
                no_directory.setDefaultButton(QMessageBox.Ok)
                _ = no_directory.exec_()
        else:
            assert precalibration_code == Constants.CALIBRATION_NONE
        return success, precalibration_code, pedestal_value, image_data

    # Get the best matched calibration file in the auto directory
    def get_best_calibration_file(self, directory_path: str, sample_file: FileDescriptor) -> Optional[numpy.ndarray]:
        print("get_best_calibration_file")
        # todo get_best_calibration_file
        return None

    def process_groups(self, selected_files: [FileDescriptor]):
        print("process_groups")
        # todo process_groups
        # todo Get directory where output master darks will go (one directory, file names will distinguish them)
        suggested_output_directory = CommandLineHandler.create_output_directory(selected_files[0],
                                                                                self.get_combine_method())
        output_directory = self.get_group_output_directory(suggested_output_directory)

        exposure_tolerance = self._data_model.get_exposure_group_tolerance()
        temperature_tolerance = self._data_model.get_temperature_group_tolerance()
        if output_directory is not None:
            print("Process groups into output directory: " + output_directory)
            if not SharedUtils.ensure_directory_exists(output_directory):
                no_directory = QMessageBox()
                no_directory.setText("Unable to create output directory.")
                no_directory.setInformativeText("The output directory you specified does not exist and we are"
                                                " unable to create it because of file system permissions or a "
                                                "conflicting file name.")
                no_directory.setStandardButtons(QMessageBox.Ok)
                no_directory.setDefaultButton(QMessageBox.Ok)
                _ = no_directory.exec_()

        #  Process size groups, or all sizes if not grouping
        groups_by_size = SharedUtils.get_groups_by_size(selected_files, self._data_model.get_group_by_size())
        for size_group in groups_by_size:
            print(f"Processing one size group: {len(size_group)} files sized {size_group[0].get_size_key()}")
            # Within this size group, process exposure groups, or all exposures if not grouping
            groups_by_exposure = SharedUtils.get_groups_by_exposure(size_group,
                                                                    self._data_model.get_group_by_exposure(),
                                                                    exposure_tolerance)
            for exposure_group in groups_by_exposure:
                print(f"Processing one exposure group: {len(exposure_group)} files exposed {size_group[0].get_exposure()}")
                # Within this exposure group, process temperature groups, or all temperatures if not grouping
                groups_by_temperature = SharedUtils.get_groups_by_temperature(exposure_group,
                                                                              self._data_model.get_group_by_temperature(),
                                                                              temperature_tolerance)
                for temperature_group in groups_by_temperature:
                    # print(f"Processing one temperature group: "
                    #       f"{len(temperature_group)} files at temp {size_group[0].get_temperature()}")
                    # Now we have a list of descriptors, grouped as appropriate, to process
                    self.process_one_group(temperature_group, output_directory,
                                           self._data_model.get_master_combine_method())

        self.ui.message.setText("Combination complete")

    def get_group_output_directory(self, suggested_directory: str) -> str:
        dialog = QFileDialog()
        testdialog = QFileDialog()
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        (file_name, _) = dialog.getSaveFileName(parent=None, caption="Output Directory", directory=suggested_directory)
        return None if len(file_name.strip()) == 0 else file_name

    # Process one set of files.  Output to the given path, if provided.  If not provided, prompt the user for it.

    def original_non_grouped_processing(self, selected_files: [FileDescriptor]):
        # We'll use the first file in the list as a sample for things like image size
        assert len(selected_files) > 0
        sample_file = selected_files[0]
        # Confirm that these are all dark frames, and can be combined (same binning and dimensions)
        if RmFitsUtil.all_compatible_sizes(selected_files):
            if self._data_model.get_ignore_file_type() \
                    or RmFitsUtil.all_of_type(selected_files, FileDescriptor.FILE_TYPE_DARK):
                # Get calibration info including, if needed, suitable calibration file
                (calibration_info_success, precalibration_code, pedestal_value, calibration_image) \
                    = self.get_precalibration_info(sample_file)
                if calibration_info_success:
                    # Get output file location
                    suggested_output_path = CommandLineHandler.create_output_path(selected_files[0],
                                                                                  self.get_combine_method())
                    output_file = self.get_output_file(suggested_output_path)
                    if output_file is not None:
                        # Get (most common) filter name in the set
                        # Since these are darks, the filter is meaningless, but we need the value
                        # for the shared "create file" routine
                        filter_name = SharedUtils.most_common_filter_name(selected_files)
                        # Do the combination
                        self.combine_files(selected_files, filter_name, output_file, precalibration_code, pedestal_value, calibration_image)
                        # Optionally do something with the original input files
                        self.handle_input_files_disposition(selected_files)
                        self.ui.message.setText("Combine completed")
                    else:
                        # User cancelled from the file dialog
                        pass
            else:
                not_dark_error = QMessageBox()
                not_dark_error.setText("The selected files are not all Dark Frames")
                not_dark_error.setInformativeText("If you know the files are dark frames, they may not have proper FITS"
                                                  + " data internally. Check the \"Ignore FITS file type\" box"
                                                  + " to proceed anyway.")
                not_dark_error.setStandardButtons(QMessageBox.Ok)
                not_dark_error.setDefaultButton(QMessageBox.Ok)
                _ = not_dark_error.exec_()
        else:
            not_compatible = QMessageBox()
            not_compatible.setText("The selected files can't be combined.")
            not_compatible.setInformativeText("To be combined into a master file, the files must have identical"
                                              + " X and Y dimensions, and identical Binning values.")
            not_compatible.setStandardButtons(QMessageBox.Ok)
            not_compatible.setDefaultButton(QMessageBox.Ok)
            _ = not_compatible.exec_()

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

    # Combine the given files, output to the given output file
    # Use the combination algorithm given by the radio buttons on the main window
    def combine_files(self, input_files: [FileDescriptor], filter_name: str, output_path: str,
                      precalibration_code: int, pedestal_value: int, calibration_image: numpy.ndarray):
        substituted_file_name = SharedUtils.substitute_date_time_filter_in_string(output_path)
        file_names = [d.get_absolute_path() for d in input_files]
        # Get info about any precalibration that is to be done
        # If precalibration wanted, uses image file unless it's None, then use pedestal
        assert len(input_files) > 0
        binning: int = input_files[0].get_binning()
        combine_method = self.get_combine_method()
        if combine_method == Constants.COMBINE_MEAN:
            mean_data = RmFitsUtil.combine_mean(file_names, precalibration_code, pedestal_value, calibration_image)
            if mean_data is not None:
                (mean_exposure, mean_temperature) = RmFitsUtil.mean_exposure_and_temperature(file_names)
                RmFitsUtil.create_combined_fits_file(substituted_file_name, mean_data,
                                                     FileDescriptor.FILE_TYPE_DARK,
                                                     "Dark Frame",
                                                     mean_exposure, mean_temperature, filter_name, binning,
                                                     "Master Dark MEAN combined")
        elif combine_method == Constants.COMBINE_MEDIAN:
            median_data = RmFitsUtil.combine_median(file_names, precalibration_code, pedestal_value, calibration_image)
            if median_data is not None:
                (mean_exposure, mean_temperature) = RmFitsUtil.mean_exposure_and_temperature(file_names)
                RmFitsUtil.create_combined_fits_file(substituted_file_name, median_data,
                                                     FileDescriptor.FILE_TYPE_DARK,
                                                     "Dark Frame",
                                                     mean_exposure, mean_temperature, filter_name, binning,
                                                     "Master Dark MEDIAN combined")
        elif combine_method == Constants.COMBINE_MINMAX:
            number_dropped_points = self._data_model._min_max_number_clipped_per_end()
            min_max_clipped_mean = RmFitsUtil.combine_min_max_clip(file_names, number_dropped_points,
                                                                   precalibration_code, pedestal_value, calibration_image)
            if min_max_clipped_mean is not None:
                (mean_exposure, mean_temperature) = RmFitsUtil.mean_exposure_and_temperature(file_names)
                RmFitsUtil.create_combined_fits_file(substituted_file_name, min_max_clipped_mean,
                                                     FileDescriptor.FILE_TYPE_DARK,
                                                     "Dark Frame",
                                                     mean_exposure, mean_temperature, filter_name, binning,
                                                     f"Master Dark Min/Max Clipped "
                                                     f"(drop {number_dropped_points}) Mean combined")
        else:
            assert combine_method == Constants.COMBINE_SIGMA_CLIP
            sigma_threshold = self._data_model.get_sigma_clip_threshold()
            sigma_clipped_mean = RmFitsUtil.combine_sigma_clip(file_names, sigma_threshold,
                                                               precalibration_code, pedestal_value, calibration_image)
            if sigma_clipped_mean is not None:
                (mean_exposure, mean_temperature) = RmFitsUtil.mean_exposure_and_temperature(file_names)
                RmFitsUtil.create_combined_fits_file(substituted_file_name, sigma_clipped_mean,
                                                     FileDescriptor.FILE_TYPE_DARK,
                                                     "Dark Frame",
                                                     mean_exposure, mean_temperature, filter_name, binning,
                                                     f"Master Dark Sigma Clipped "
                                                     f"(threshold {sigma_threshold}) Mean combined")

    # We're done combining files.  The user may want us to do something with the original input files
    def handle_input_files_disposition(self, descriptors: [FileDescriptor]):
        disposition_type = self._data_model.get_input_file_disposition()
        if disposition_type == Constants.INPUT_DISPOSITION_NOTHING:
            # User doesn't want us to do anything with the input files
            pass
        else:
            assert (disposition_type == Constants.INPUT_DISPOSITION_SUBFOLDER)
            # User wants us to move the input files into a sub-folder
            SharedUtils.dispose_files_to_sub_folder(descriptors, self._data_model.get_disposition_subfolder_name())
            # Remove the files from the table since those paths are no longer valid
            self._table_model.remove_files(descriptors)
            self.ui.filesTable.scrollToTop()

    # Determine if there are enough files selected for the Min-Max algorithm
    # If that algorithm isn't selected, then return True
    # Otherwise there should be more files selected than 2*n, where n is the
    # min-max clipping value
    def min_max_enough_files(self, num_selected: int) -> bool:
        return True if self._data_model.get_master_combine_method() != Constants.COMBINE_MINMAX \
            else num_selected > (2 * self._data_model.get_min_max_number_clipped_per_end())

    # Determine if all the dimensions are OK to proceed.
    #   All selected files must be the same size and the same binning
    #   Include the precalibration bias file in this test if that method is selected

    def validate_file_dimensions(self) -> bool:
        # Get list of paths of selected files
        descriptors: [FileDescriptor] = self.get_selected_file_descriptors()
        if len(descriptors) > 0:

            # If precalibration file is in use, add that name to the list
            if self._data_model.get_precalibration_type() == Constants.CALIBRATION_FIXED_FILE:
                calibration_descriptor = RmFitsUtil.make_file_descriptor(self._data_model.get_precalibration_fixed_path())
                descriptors.append(calibration_descriptor)

            # Get binning and dimension of first to use as a reference
            assert len(descriptors) > 0
            reference_file: FileDescriptor = descriptors[0]
            reference_binning = reference_file.get_binning()
            reference_x_size = reference_file.get_x_dimension()
            reference_y_size = reference_file.get_y_dimension()

            # Check all files in the list against these specifications
            descriptor: FileDescriptor
            for descriptor in descriptors:
                if descriptor.get_binning() != reference_binning:
                    return False
                if descriptor.get_x_dimension() != reference_x_size:
                    return False
                if descriptor.get_y_dimension() != reference_y_size:
                    return False

        return True

    # Process one group of files, output to the given directory

    def process_one_group(self, descriptor_list: [FileDescriptor], output_directory: str, combine_method: int):
        # todo process_one_group
        # Descriptive message to the console
        assert len(descriptor_list) > 0
        sample_file: FileDescriptor = descriptor_list[0]
        binning = sample_file.get_binning()
        exposure = sample_file.get_exposure()
        temperature = sample_file.get_temperature()
        print(f"Processing {len(descriptor_list)} files binned {binning} x {binning}, "
              f"{exposure} seconds at {temperature} degrees.")

        # Get calibration info for this group of files
        (calibration_info_success, precalibration_code, pedestal_value, calibration_image) \
            = self.get_precalibration_info(sample_file)
        if calibration_info_success:

            # Make up a file name for this group's output, into the given directory
            file_name = CommandLineHandler.get_file_name_portion(combine_method, sample_file)
            output_file = f"{output_directory}/{file_name}"

            # Confirm that these are all dark frames, and can be combined (same binning and dimensions)
            if RmFitsUtil.all_compatible_sizes(descriptor_list):
                if self._data_model.get_ignore_file_type() \
                        or RmFitsUtil.all_of_type(descriptor_list, FileDescriptor.FILE_TYPE_DARK):
                    # Get (most common) filter name in the set
                    # Since these are darks, the filter is meaningless, but we need the value
                    # for the shared "create file" routine
                    filter_name = SharedUtils.most_common_filter_name(descriptor_list)

                    # Do the combination
                    self.combine_files(descriptor_list, filter_name, output_file,
                                       precalibration_code, pedestal_value, calibration_image)

                    # Optionally do something with the original input files
                    self.handle_input_files_disposition(descriptor_list)
                    self.ui.message.setText("Combine completed")
                else:
                    not_dark_error = QMessageBox()
                    not_dark_error.setText("The selected files are not all Dark Frames")
                    not_dark_error.setInformativeText("If you know the files are dark frames, "
                                                      "they may not have proper FITS"
                                                      + " data internally. Check the \"Ignore FITS file type\" box"
                                                      + " to proceed anyway.")
                    not_dark_error.setStandardButtons(QMessageBox.Ok)
                    not_dark_error.setDefaultButton(QMessageBox.Ok)
                    _ = not_dark_error.exec_()
            else:
                not_compatible = QMessageBox()
                not_compatible.setText("The selected files can't be combined.")
                not_compatible.setInformativeText("To be combined into a master file, the files must have identical"
                                                  + " X and Y dimensions, and identical Binning values.")
                not_compatible.setStandardButtons(QMessageBox.Ok)
                not_compatible.setDefaultButton(QMessageBox.Ok)
                _ = not_compatible.exec_()

