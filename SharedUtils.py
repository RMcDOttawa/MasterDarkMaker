# Utilities to help program run on multiple OS - for now, windows and mac
# Helps locate resource files, end-running around the problems I've been having
# with the various native bundle packaging utilities that I can't get working
import os
import shutil
import sys
from datetime import datetime
from itertools import groupby

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget

from FileDescriptor import FileDescriptor
from Validators import Validators


class SharedUtils:
    VALID_FIELD_BACKGROUND_COLOUR = "white"
    _error_red = 0xFC  # These RGB values generate a medium red,
    _error_green = 0x84  # not too dark to read black text through
    _error_blue = 0x84
    ERROR_FIELD_BACKGROUND_COLOUR = f"#{_error_red:02X}{_error_green:02X}{_error_blue:02X}"

    @classmethod
    def valid_or_error_field_color(cls, validity: bool) -> QColor:
        if validity:
            result = QColor(Qt.white)
        else:
            result = QColor(cls._error_red, cls._error_green, cls._error_blue)
        return result

    # Generate a file's full path, given the file name, and having the
    # file reside in the same directory where the running program resides

    @classmethod
    def path_for_file_in_program_directory(cls, file_name: str) -> str:
        program_full_path = os.path.realpath(__file__)
        directory_name = os.path.dirname(program_full_path)
        path_to_file = f"{directory_name}/{file_name}"
        return path_to_file

    @classmethod
    def background_validity_color(cls, field: QWidget, is_valid: bool):
        field_color = SharedUtils.VALID_FIELD_BACKGROUND_COLOUR \
            if is_valid else SharedUtils.ERROR_FIELD_BACKGROUND_COLOUR
        css_color_item = f"background-color:{field_color};"
        existing_style_sheet = field.styleSheet()
        field.setStyleSheet(existing_style_sheet + css_color_item)

    @classmethod
    def validate_folder_name(cls, proposed: str):
        """Validate the proposed file name.  It must be a legit system file name, except
        it can also contain the strings %d or %t or %f zero or more times each.  We'll
        just remove those temporarily for purposes of validation."""
        upper = proposed.upper()
        specials_removed = upper.replace("%D", "").replace("%T", "").replace("%F", "")
        return Validators.valid_file_name(specials_removed, 1, 31)

    # In given string, replace all occurrences of %d with date and %t with time
    # In YYYY-MM-DD  and HH-MM-SS formats
    @classmethod
    def substitute_date_time_filter_in_string(cls, output_path: str) -> str:
        now = datetime.now()
        year = now.strftime("%Y-%m-%d")
        time = now.strftime("%H-%M-%S")
        return output_path.replace("%d", year).replace("%D", year).replace("%t", time).replace("%T", time) \


    # Find the most common filter name in the given collection
    @classmethod
    def most_common_filter_name(cls, descriptors: [FileDescriptor]) -> str:
        filter_counts: {str, int} = {}
        for descriptor in descriptors:
            name = descriptor.get_filter_name()
            if name in filter_counts:
                filter_counts[name] += 1
            else:
                filter_counts[name] = 1
        maximum_key = max(filter_counts, key=filter_counts.get)
        return maximum_key if maximum_key is not None else ""

    # Move the processed input files to a sub-folder with the given name (after substituting
    # special markers in the folder name).  If the folder exists, just use it.  If it doesn't
    # exist, create it.

    @classmethod
    def dispose_files_to_sub_folder(cls, descriptors: [FileDescriptor], sub_folder_name: str):

        # Get folder name with special values substituted
        actual_folder_name = SharedUtils.substitute_date_time_filter_in_string(sub_folder_name)
        subfolder_located_directory = cls.make_name_a_subfolder(descriptors[0], actual_folder_name)

        # Create the folder if it doesn't already exist (and make sure we're not clobbering a file)
        if cls.ensure_directory_exists(subfolder_located_directory):
            # Move the files to that folder
            cls.move_files_to_sub_folder(descriptors, subfolder_located_directory)

    # Given a desired sub-directory name, make it a sub-directory of the location of the input files
    # by putting the path to a sample input file on the front of the name
    @classmethod
    def make_name_a_subfolder(cls, sample_input_file: FileDescriptor, sub_directory_name: str) -> str:
        parent_path = os.path.dirname(sample_input_file.get_absolute_path())
        return parent_path + "/" + sub_directory_name

    # Make sure the given directory exists, as a directory.
    #   - No non-directory file of that name (fail if so)
    #   - If directory already exists as a directory, all good; succeed
    #   - If no such directory exists, create it

    @classmethod
    def ensure_directory_exists(cls, directory_name) -> bool:
        success: bool
        if os.path.exists(directory_name):
            # There is something there with this name.  That's OK if it's a directory.
            if os.path.isdir(directory_name):
                # The directory exists, this is OK, no need to create it
                success = True
            else:
                # A file exists that conflicts with the desired directory
                # Display an error and fail
                print("A file (not a directory) already exists with the name and location "
                      "you specified. Choose a different name or location.")
                success = False
        else:
            # Nothing of that name exists.  Make a directory
            os.mkdir(directory_name)
            success = True

        return success

    # Move files to given sub-folder
    @classmethod
    def move_files_to_sub_folder(cls, descriptors: [FileDescriptor], sub_folder_name: str):
        for descriptor in descriptors:
            source_path = descriptor.get_absolute_path()
            source_name = descriptor.get_name()
            destination_path = cls.unique_destination_file(sub_folder_name, source_name)
            shutil.move(source_path, destination_path)

    # In case the disposition directory already existed and has files in it, ensure the
    # given file would be unique in the directory, by appending a number to it if necessary
    @classmethod
    def unique_destination_file(cls, directory_path: str, file_name: str) -> str:
        unique_counter = 0

        destination_path = directory_path + "/" + file_name
        while os.path.exists(destination_path):
            unique_counter += 1
            if unique_counter > 5000:
                print("Unable to find a unique file name after 5000 tries.")
                sys.exit(1)
            destination_path = directory_path + "/" + str(unique_counter) + "-" + file_name

        return destination_path

    # Given list of file descriptors, return a list of lists, where each outer list is all the
    # file descriptors with the same size (dimensions and binning)

    @classmethod
    def get_groups_by_size(cls, selected_files: [FileDescriptor], is_grouped: bool) -> [[FileDescriptor]]:
        if is_grouped:
            descriptors_sorted = sorted(selected_files, key=FileDescriptor.get_size_key)
            descriptors_grouped = groupby(descriptors_sorted, FileDescriptor.get_size_key)
            result: [[FileDescriptor]] = []
            for key, sub_group in descriptors_grouped:
                sub_list = list(sub_group)
                result.append(sub_list)
            return result
        else:
            return [selected_files]   # One group with all the files

    # Given list of file descriptors, return a list of lists, where each outer list is all the
    # file descriptors with the same exposure within a given tolerance.
    # Note that, because of the "tolerance" comparison, we need to process the list manually,
    # not with the "groupby" function.

    @classmethod
    def get_groups_by_exposure(cls, selected_files: [FileDescriptor], is_grouped: bool, tolerance: float) -> [[FileDescriptor]]:
        if is_grouped:
            result: [[FileDescriptor]] = []
            files_sorted: [FileDescriptor] = sorted(selected_files, key=FileDescriptor.get_exposure)
            current_exposure: float = files_sorted[0].get_exposure()
            current_list: [FileDescriptor] = []
            for next_file in files_sorted:
                this_exposure = next_file.get_exposure()
                if cls.values_same_within_tolerance(current_exposure, this_exposure, tolerance):
                    current_list.append(next_file)
                else:
                    result.append(current_list)
                    current_list = [next_file]
                    current_exposure = this_exposure
            result.append(current_list)
            return result
        else:
            return [selected_files]   # One group with all the files

    # Given list of file descriptors, return a list of lists, where each outer list is all the
    # file descriptors with the same temperature within a given tolerance
    # Note that, because of the "tolerance" comparison, we need to process the list manually,
    # not with the "groupby" function.

    @classmethod
    def get_groups_by_temperature(cls, selected_files: [FileDescriptor], is_grouped: bool, tolerance: float) -> [[FileDescriptor]]:
        if is_grouped:
            result: [[FileDescriptor]] = []
            files_sorted: [FileDescriptor] = sorted(selected_files, key=FileDescriptor.get_temperature)
            current_temperature: float = files_sorted[0].get_temperature()
            current_list: [FileDescriptor] = []
            for next_file in files_sorted:
                this_temperature = next_file.get_temperature()
                if cls.values_same_within_tolerance(current_temperature, this_temperature, tolerance):
                    current_list.append(next_file)
                else:
                    result.append(current_list)
                    current_list = [next_file]
                    current_temperature = this_temperature
            result.append(current_list)
            return result
        else:
            return [selected_files]   # One group with all the files

    # Determine if two values are the same within a given tolerance.
    # Careful - either value might be zero, so divide only after checking
    @classmethod
    def values_same_within_tolerance(cls, first_value: float, second_value: float, tolerance: float):
        difference = abs(first_value - second_value)
        if first_value == 0.0:
            if second_value == 0.0:
                return True
            else:
                percent_difference = difference / second_value
        else:
            percent_difference = difference / first_value
        return percent_difference <= tolerance
