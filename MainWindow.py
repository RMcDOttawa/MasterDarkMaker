import os

import numpy
from PyQt5 import uic
from PyQt5.QtCore import QObject, QEvent, QModelIndex
from PyQt5.QtWidgets import QMainWindow, QDialog, QHeaderView, QFileDialog, QMessageBox

from CommandLineHandler import CommandLineHandler
from Constants import Constants
from FileDescriptor import FileDescriptor
from FitsFileTableModel import FitsFileTableModel
from MultiOsUtil import MultiOsUtil
from Preferences import Preferences
from PreferencesWindow import PreferencesWindow
from RmFitsUtil import RmFitsUtil
from SharedUtils import SharedUtils
from Validators import Validators


class MainWindow(QMainWindow):

    def __init__(self, preferences: Preferences):
        """Initialize MainWindow class"""
        self._preferences = preferences
        QMainWindow.__init__(self)
        self.ui = uic.loadUi(MultiOsUtil.path_for_file_in_program_directory("MainWindow.ui"))
        self._field_validity: {object, bool} = {}
        self._table_model: FitsFileTableModel
        self._precalibration_file_full_path: str = ""

        # Load algorithm from preferences

        algorithm = preferences.get_master_combine_method()
        if algorithm == Constants.COMBINE_MEAN:
            self.ui.combineMeanRB.setChecked(True)
        elif algorithm == Constants.COMBINE_MEDIAN:
            self.ui.combineMedianRB.setChecked(True)
        elif algorithm == Constants.COMBINE_MINMAX:
            self.ui.combineMinMaxRB.setChecked(True)
        else:
            assert (algorithm == Constants.COMBINE_SIGMA_CLIP)
            self.ui.combineSigmaRB.setChecked(True)

        self.ui.minMaxNumDropped.setText(str(preferences.get_min_max_number_clipped_per_end()))
        self.ui.sigmaThreshold.setText(str(preferences.get_sigma_clip_threshold()))

        # Load disposition from preferences

        disposition = preferences.get_input_file_disposition()
        if disposition == Constants.INPUT_DISPOSITION_SUBFOLDER:
            self.ui.dispositionSubFolderRB.setChecked(True)
        else:
            assert (disposition == Constants.INPUT_DISPOSITION_NOTHING)
            self.ui.dispositionNothingRB.setChecked(True)
        self.ui.subFolderName.setText(preferences.get_disposition_subfolder_name())

        # Pre-calibration options

        precalibration_option = preferences.get_precalibration_type()
        if precalibration_option == Constants.CALIBRATION_PROMPT:
            self.ui.promptPreCalFileRB.setChecked(True)
        elif precalibration_option == Constants.CALIBRATION_FIXED_FILE:
            self.ui.fixedPreCalFileRB.setChecked(True)
        elif precalibration_option == Constants.CALIBRATION_NONE:
            self.ui.noPreClalibrationRB.setChecked(True)
        else:
            assert precalibration_option == Constants.CALIBRATION_PEDESTAL
            self.ui.fixedPedestalRB.setChecked(True)
        self.ui.fixedPedestalAmount.setText(str(preferences.get_precalibration_pedestal()))
        self.set_fixed_precal_file_name_display(preferences.get_precalibration_fixed_path())

        # Grouping boxes and parameters

        self.ui.groupBySizeCB.setChecked(preferences.get_group_by_size())
        self.ui.groupByExposureCB.setChecked(preferences.get_group_by_exposure())
        self.ui.groupByTemperatureCB.setChecked(preferences.get_group_by_temperature())

        self.ui.exposureGroupTolerance.setText(f"{100 * preferences.get_exposure_group_tolerance():.0f}")
        self.ui.temperatureGroupTolerance.setText(f"{100 * preferences.get_temperature_group_tolerance():.0f}")

        # Set up the file table
        self._table_model = FitsFileTableModel(self.ui.ignoreFileType.isChecked())
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

    def set_fixed_precal_file_name_display(self, full_path: str):
        self._precalibration_file_full_path = full_path
        name_only = os.path.basename(full_path)
        self.ui.precalibrationPathDisplay.setText(name_only)

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
        self.ui.promptPreCalFileRB.clicked.connect(self.precalibration_radio_group_clicked)
        self.ui.fixedPreCalFileRB.clicked.connect(self.precalibration_radio_group_clicked)
        self.ui.selectPreCalFile.clicked.connect(self.select_precalibration_file_clicked)
        self.ui.fixedPedestalAmount.editingFinished.connect(self.pedestal_amount_changed)

        # Grouping controls
        self.ui.groupBySizeCB.clicked.connect(self.group_by_size_clicked)
        self.ui.groupByExposureCB.clicked.connect(self.group_by_exposure_clicked)
        self.ui.groupByTemperatureCB.clicked.connect(self.group_by_temperature_clicked)
        self.ui.exposureGroupTolerance.editingFinished.connect(self.exposure_group_tolerance_changed)
        self.ui.temperatureGroupTolerance.editingFinished.connect(self.temperature_group_tolerance_changed)

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
        self._table_model.set_ignore_file_type(self.ui.ignoreFileType.isChecked())

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
        self.enable_fields()
        self.enable_buttons()

    def group_by_size_clicked(self):
        self.enable_fields()
        self.enable_buttons()

    def group_by_exposure_clicked(self):
        self.enable_fields()
        self.enable_buttons()

    def group_by_temperature_clicked(self):
        self.enable_fields()
        self.enable_buttons()

    def disposition_button_clicked(self):
        """ One of the disposition buttons is clicked.  Change what fields are enabled"""
        self.enable_fields()
        self.enable_buttons()

    def pedestal_amount_changed(self):
        """the field giving the fixed calibration pedestal amount has been changed.
        Validate it (integer > 0) and store if valid"""
        proposed_new_number: str = self.ui.fixedPedestalAmount.text()
        new_number = Validators.valid_int_in_range(proposed_new_number, 0, 32767)
        valid = new_number is not None
        SharedUtils.background_validity_color(self.ui.fixedPedestalAmount, valid)
        self._field_validity[self.ui.fixedPedestalAmount] = valid
        self.enable_buttons()

    def min_max_drop_changed(self):
        """the field giving the number of minimum and maximum values to drop has been changed.
        Validate it (integer > 0) and store if valid"""
        proposed_new_number: str = self.ui.minMaxNumDropped.text()
        new_number = Validators.valid_int_in_range(proposed_new_number, 0, 256)
        valid = new_number is not None
        SharedUtils.background_validity_color(self.ui.minMaxNumDropped, valid)
        self._field_validity[self.ui.minMaxNumDropped] = valid
        self.enable_buttons()

    def sigma_threshold_changed(self):
        """the field giving the sigma limit beyond which values are ignored has changed
        Validate it (floating point > 0) and store if valid"""
        proposed_new_number: str = self.ui.sigmaThreshold.text()
        new_number = Validators.valid_float_in_range(proposed_new_number, 0.01, 100.0)
        valid = new_number is not None
        SharedUtils.background_validity_color(self.ui.sigmaThreshold, valid)
        self._field_validity[self.ui.sigmaThreshold] = valid
        self.enable_buttons()

    def sub_folder_name_changed(self):
        """the field giving the name of the sub-folder to be created or used has changed.
        Validate that it is an acceptable folder name and store if valid"""
        proposed_new_name: str = self.ui.subFolderName.text()
        # valid = Validators.valid_file_name(proposed_new_name, 1, 31)
        valid = SharedUtils.validate_folder_name(proposed_new_name)
        SharedUtils.background_validity_color(self.ui.subFolderName, valid)
        self._field_validity[self.ui.subFolderName] = valid
        self.enable_buttons()

    def exposure_group_tolerance_changed(self):
        """User has entered value in exposure group tolerance field.  Validate and save"""
        proposed_new_number: str = self.ui.exposureGroupTolerance.text()
        new_number = Validators.valid_float_in_range(proposed_new_number, 0.0, 99.999)
        valid = new_number is not None
        SharedUtils.background_validity_color(self.ui.exposureGroupTolerance, valid)

    def temperature_group_tolerance_changed(self):
        """User has entered value in temperature group tolerance field.  Validate and save"""
        proposed_new_number: str = self.ui.temperatureGroupTolerance.text()
        new_number = Validators.valid_float_in_range(proposed_new_number, 0.0, 99.999)
        valid = new_number is not None
        SharedUtils.background_validity_color(self.ui.temperatureGroupTolerance, valid)

    def enable_fields(self):
        """Enable text fields depending on state of various radio buttons"""

        self.ui.fixedPedestalAmount.setEnabled(self.ui.fixedPedestalRB.isChecked())

        # Enable Algorithm fields depending on which algorithm is selected
        self.ui.minMaxNumDropped.setEnabled(self.ui.combineMinMaxRB.isChecked())
        self.ui.sigmaThreshold.setEnabled(self.ui.combineSigmaRB.isChecked())

        # Enable Disposition fields depending on which disposition is selected
        self.ui.subFolderName.setEnabled(self.ui.dispositionSubFolderRB.isChecked())

        # Grouping parameters go with their corresponding checkbox
        self.ui.exposureGroupTolerance.setEnabled(self.ui.groupByExposureCB.isChecked())
        self.ui.temperatureGroupTolerance.setEnabled(self.ui.groupByTemperatureCB.isChecked())

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
            self._table_model.set_file_descriptors(file_descriptions)
        self.enable_buttons()

    def table_selection_changed(self):
        """Rows selected in the file table have changed; check for button enablement"""
        selected = self.ui.filesTable.selectionModel().selectedRows()
        self.ui.selectedLabel.setText(f"{len(selected)} rows selected")
        self.enable_buttons()
        self.enable_fields()

    def precalibration_radio_group_clicked(self):
        self.enable_buttons()
        self.enable_fields()

    def select_precalibration_file_clicked(self):
        (file_name, _) = QFileDialog.getOpenFileName(parent=self, caption="Select dark or bias file",
                                                     filter="FITS files(*.fit *.fits)",
                                                     options=QFileDialog.ReadOnly)
        if len(file_name) > 0:
            self.set_fixed_precal_file_name_display(file_name)
        self.enable_fields()
        self.enable_buttons()

    def enable_buttons(self):
        """Enable buttons on the main window depending on validity and settings
        of other controls"""

        self.ui.selectPreCalFile.setEnabled(self.ui.fixedPreCalFileRB.isChecked())

        # "combineSelectedButton" is enabled only if
        #   - No text fields are in error state
        #   - At least one row in the file table is selected
        #   - If Min/Max algorithm selected with count "n", > 2n files selected
        #   - If sigma-clip algorithm selected, >= 3 files selected
        #   - If fixed precalibration file option selected, path must exist
        #   - All files must be same dimensions and binning (unless grouping by size)

        # We'll say why it's disabled in the tool tip

        tool_tip_text: str = "Combined the selected files into a master bias"

        text_fields_valid = self.all_text_fields_valid()
        if not text_fields_valid:
            tool_tip_text = "Disabled because of invalid text fields (shown in red)"
        selected = self.ui.filesTable.selectionModel().selectedRows()
        if len(selected) == 0:
            tool_tip_text = "Disabled because no files are selected"
        calibration_path_ok = True
        dimensions_ok = True
        sigma_clip_enough_files = (not self.ui.combineSigmaRB.isChecked()) or len(selected) >= 3
        if not sigma_clip_enough_files:
            tool_tip_text = "Disabled because not enough files selected for sigma-clip method"
        if self.ui.fixedPreCalFileRB.isChecked():
            calibration_path_ok = os.path.isfile(self._precalibration_file_full_path)
            if not calibration_path_ok:
                tool_tip_text = "Disabled because specified calibration file does not exist"
        if calibration_path_ok:
            dimensions_ok = self.ui.groupBySizeCB.isChecked() or self.validate_file_dimensions()
            if not dimensions_ok:
                tool_tip_text = "Disabled because all files (including bias file if selected)" \
                                " do not have the same dimensions and binning and Group by Size not selected"
        self.ui.combineSelectedButton.setEnabled(text_fields_valid
                                                 and len(selected) > 0
                                                 and self.min_max_enough_files(len(selected))
                                                 and sigma_clip_enough_files
                                                 and dimensions_ok
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
        all_fields_good = all(val for val in self._field_validity.values())
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
        if self.ui.groupByExposureCB.isChecked() or self.ui.groupBySizeCB.isChecked() or self.ui.groupByTemperatureCB.isChecked():
            self.process_groups(selected_files)
        else:
            self.original_non_grouped_processing(selected_files)

    def process_groups(self, selected_files: [FileDescriptor]):
        print("process_groups")
        # todo process_groups
        # todo Get directory where output master darks will go (one directory, file names will distinguish them)
        suggested_output_directory = CommandLineHandler.create_output_directory(selected_files[0],
                                                                                self.get_combine_method())
        output_directory = self.get_group_output_directory(suggested_output_directory)
        if not SharedUtils.ensure_directory_exists(output_directory):
            no_directory = QMessageBox()
            no_directory.setText("Unable to create output directory.")
            no_directory.setInformativeText("The output directory you specified does not exist and we are"
                                            " unable to create it because of file system permissions or a "
                                            "conflicting file name.")
            no_directory.setStandardButtons(QMessageBox.Ok)
            no_directory.setDefaultButton(QMessageBox.Ok)
            _ = no_directory.exec_()

        exposure_tolerance = float(self.ui.exposureGroupTolerance.text()) / 100.0
        temperature_tolerance = float(self.ui.temperatureGroupTolerance.text()) / 100.0
        if output_directory is not None:
            print("Process groups into output directory: " + output_directory)

        #  Process size groups, or all sizes if not grouping
        groups_by_size = SharedUtils.get_groups_by_size(selected_files, self.ui.groupBySizeCB.isChecked())
        for size_group in groups_by_size:
            # print(f"Processing one size group: {len(size_group)} files sized {size_group[0].get_size_key()}")
            # Within this size group, process exposure groups, or all exposures if not grouping
            groups_by_exposure = SharedUtils.get_groups_by_exposure(size_group,
                                                                    self.ui.groupByExposureCB.isChecked(),
                                                                    exposure_tolerance)
            for exposure_group in groups_by_exposure:
                # print(f"Processing one exposure group: {len(exposure_group)} files exposed {size_group[0].get_exposure()}")
                # Within this exposure group, process temperature groups, or all temperatures if not grouping
                groups_by_temperature = SharedUtils.get_groups_by_temperature(exposure_group,
                                                                              self.ui.groupByTemperatureCB.isChecked(),
                                                                              temperature_tolerance)
                for temperature_group in groups_by_temperature:
                    # print(f"Processing one temperature group: "
                    #       f"{len(temperature_group)} files at temp {size_group[0].get_temperature()}")
                    # Now we have a list of descriptors, grouped as appropriate, to process
                    self.process_one_group(temperature_group, output_directory, self.get_combine_method())

        self.ui.message.setText("Combination complete")

    def get_group_output_directory(self, suggested_directory: str) -> str:
        dialog = QFileDialog()
        testdialog = QFileDialog()
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        (file_name, _) = dialog.getSaveFileName(parent=None, caption="Output Directory", directory=suggested_directory)
        return None if len(file_name.strip()) == 0 else file_name

    # Process one set of files.  Output to the given path, if provided.  If not provided, prompt the user for it.

    def original_non_grouped_processing(self, selected_files: [FileDescriptor]):
        # Confirm that these are all dark frames, and can be combined (same binning and dimensions)
        if RmFitsUtil.all_compatible_sizes(selected_files):
            if self.ui.ignoreFileType.isChecked() \
                    or RmFitsUtil.all_of_type(selected_files, FileDescriptor.FILE_TYPE_DARK):
                # Get output file location
                output_file = self.get_output_file(suggested_output_path)
                if output_file is not None:
                    # Get (most common) filter name in the set
                    # Since these are darks, the filter is meaningless, but we need the value
                    # for the shared "create file" routine
                    filter_name = SharedUtils.most_common_filter_name(selected_files)
                    # Do the combination
                    self.combine_files(selected_files, filter_name, output_file)
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
    def combine_files(self, input_files: [FileDescriptor], filter_name: str, output_path: str):
        substituted_file_name = SharedUtils.substitute_date_time_filter_in_string(output_path)
        file_names = [d.get_absolute_path() for d in input_files]
        # Get info about any precalibration that is to be done
        # If precalibration wanted, uses image file unless it's None, then use pedestal
        pre_calibrate: bool
        pedestal_value: int
        calibration_image: numpy.ndarray
        assert len(input_files) > 0
        binning: int = input_files[0].get_binning()
        (pre_calibrate, pedestal_value, calibration_image) = (Constants.CALIBRATION_NONE, 0, None)
        method = self.get_combine_method()
        if method == Constants.COMBINE_MEAN:
            mean_data = RmFitsUtil.combine_mean(file_names, pre_calibrate, pedestal_value, calibration_image)
            if mean_data is not None:
                (mean_exposure, mean_temperature) = RmFitsUtil.mean_exposure_and_temperature(file_names)
                RmFitsUtil.create_combined_fits_file(substituted_file_name, mean_data,
                                                     FileDescriptor.FILE_TYPE_DARK,
                                                     "Dark Frame",
                                                     mean_exposure, mean_temperature, filter_name, binning,
                                                     "Master Dark MEAN combined")
        elif method == Constants.COMBINE_MEDIAN:
            median_data = RmFitsUtil.combine_median(file_names, pre_calibrate, pedestal_value, calibration_image)
            if median_data is not None:
                (mean_exposure, mean_temperature) = RmFitsUtil.mean_exposure_and_temperature(file_names)
                RmFitsUtil.create_combined_fits_file(substituted_file_name, median_data,
                                                     FileDescriptor.FILE_TYPE_DARK,
                                                     "Dark Frame",
                                                     mean_exposure, mean_temperature, filter_name, binning,
                                                     "Master Dark MEDIAN combined")
        elif method == Constants.COMBINE_MINMAX:
            number_dropped_points = int(self.ui.minMaxNumDropped.text())
            min_max_clipped_mean = RmFitsUtil.combine_min_max_clip(file_names, number_dropped_points,
                                                                   pre_calibrate, pedestal_value, calibration_image)
            if min_max_clipped_mean is not None:
                (mean_exposure, mean_temperature) = RmFitsUtil.mean_exposure_and_temperature(file_names)
                RmFitsUtil.create_combined_fits_file(substituted_file_name, min_max_clipped_mean,
                                                     FileDescriptor.FILE_TYPE_DARK,
                                                     "Dark Frame",
                                                     mean_exposure, mean_temperature, filter_name, binning,
                                                     f"Master Dark Min/Max Clipped "
                                                     f"(drop {number_dropped_points}) Mean combined")
        else:
            assert method == Constants.COMBINE_SIGMA_CLIP
            sigma_threshold = float(self.ui.sigmaThreshold.text())
            sigma_clipped_mean = RmFitsUtil.combine_sigma_clip(file_names, sigma_threshold,
                                                               pre_calibrate, pedestal_value, calibration_image)
            if sigma_clipped_mean is not None:
                (mean_exposure, mean_temperature) = RmFitsUtil.mean_exposure_and_temperature(file_names)
                RmFitsUtil.create_combined_fits_file(substituted_file_name, sigma_clipped_mean,
                                                     FileDescriptor.FILE_TYPE_DARK,
                                                     "Dark Frame",
                                                     mean_exposure, mean_temperature, filter_name, binning,
                                                     f"Master Dark Sigma Clipped "
                                                     f"(threshold {sigma_threshold}) Mean combined")

    # Determine which combination method is selected in the UI
    def get_combine_method(self) -> int:
        if self.ui.combineMeanRB.isChecked():
            return Constants.COMBINE_MEAN
        elif self.ui.combineMedianRB.isChecked():
            return Constants.COMBINE_MEDIAN
        elif self.ui.combineMinMaxRB.isChecked():
            return Constants.COMBINE_MINMAX
        else:
            assert self.ui.combineSigmaRB.isChecked()
            return Constants.COMBINE_SIGMA_CLIP

    # We're done combining files.  The user may want us to do something with the original input files
    def handle_input_files_disposition(self, descriptors: [FileDescriptor]):
        if self.ui.dispositionNothingRB.isChecked():
            # User doesn't want us to do anything with the input files
            pass
        else:
            assert (self.ui.dispositionSubFolderRB.isChecked())
            # User wants us to move the input files into a sub-folder
            SharedUtils.dispose_files_to_sub_folder(descriptors, self.ui.subFolderName.text())
            # Remove the files from the table since those paths are no longer valid
            self._table_model.remove_files(descriptors)
            self.ui.filesTable.scrollToTop()

    # Determine if there are enough files selected for the Min-Max algorithm
    # If that algorithm isn't selected, then return True
    # Otherwise there should be more files selected than 2*n, where n is the
    # min-max clipping value
    def min_max_enough_files(self, num_selected: int) -> bool:
        if not self.ui.combineMinMaxRB.isChecked():
            return True
        else:
            return num_selected > (2 * int(self.ui.minMaxNumDropped.text()))

    # Determine if all the dimensions are OK to proceed.
    #   All selected files must be the same size and the same binning
    #   Include the precalibration bias file in this test if that method is selected

    def validate_file_dimensions(self) -> bool:
        # Get list of paths of selected files
        descriptors: [FileDescriptor] = self.get_selected_file_descriptors()
        if len(descriptors) > 0:

            # If precalibration file is in use, add that name to the list
            if self.ui.fixedPreCalFileRB.isChecked():
                calibration_descriptor = RmFitsUtil.make_file_descriptor(self._precalibration_file_full_path)
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

        # Make up a file name for this group's output, into the given directory
        file_name = CommandLineHandler.get_file_name_portion(combine_method, sample_file)
        output_file = f"{output_directory}/{file_name}"

        # Confirm that these are all dark frames, and can be combined (same binning and dimensions)
        if RmFitsUtil.all_compatible_sizes(descriptor_list):
            if self.ui.ignoreFileType.isChecked() \
                    or RmFitsUtil.all_of_type(descriptor_list, FileDescriptor.FILE_TYPE_DARK):
                # Get (most common) filter name in the set
                # Since these are darks, the filter is meaningless, but we need the value
                # for the shared "create file" routine
                filter_name = SharedUtils.most_common_filter_name(descriptor_list)

                # Do the combination
                self.combine_files(descriptor_list, filter_name, output_file)

                # Optionally do something with the original input files
                self.handle_input_files_disposition(descriptor_list)
                self.ui.message.setText("Combine completed")
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
