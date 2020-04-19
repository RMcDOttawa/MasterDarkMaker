#
#   Class to handle calibration of images using specified method (including none)
#
import sys

from numpy import ndarray

import MasterMakerExceptions
from Console import Console
from Constants import Constants
from DataModel import DataModel
from FileDescriptor import FileDescriptor
from RmFitsUtil import RmFitsUtil
from SharedUtils import SharedUtils


class Calibrator:
    #
    #   Create calibration object against the given data model's settings
    #
    def __init__(self, data_model: DataModel):
        self._data_model = data_model

    def calibrate_images(self, file_data: [ndarray], sample_file: FileDescriptor, console: Console) -> [ndarray]:
        calibration_type = self._data_model.get_precalibration_type()
        if calibration_type == Constants.CALIBRATION_NONE:
            return file_data
        elif calibration_type == Constants.CALIBRATION_PEDESTAL:
            return self.calibrate_with_pedestal(file_data, self._data_model.get_precalibration_pedestal())
        elif calibration_type == Constants.CALIBRATION_FIXED_FILE:
            return self.calibrate_with_file(file_data, self._data_model.get_precalibration_fixed_path())
        else:
            assert calibration_type == Constants.CALIBRATION_AUTO_DIRECTORY
            return self.calibrate_with_auto_directory(file_data, self._data_model.get_precalibration_auto_directory(),
                                                      sample_file, console)

    def calibrate_with_pedestal(self, file_data: [ndarray], pedestal: int) -> [ndarray]:
        result = file_data.copy()
        for index in range(len(result)):
            reduced_by_pedestal: ndarray = result[index] - pedestal
            result[index] = reduced_by_pedestal.clip(0, 0xFFFF)
        return result

    def calibrate_with_file(self, file_data: [ndarray], calibration_file_path: str) -> [ndarray]:
        result = file_data.copy()
        calibration_image = RmFitsUtil.fits_data_from_path(calibration_file_path)
        (calibration_x, calibration_y) = calibration_image.shape
        for index in range(len(result)):
            (layer_x, layer_y) = result[index].shape
            if (layer_x != calibration_x) or (layer_y != calibration_y):
                raise MasterMakerExceptions.IncompatibleSizes
            difference = result[index] - calibration_image
            result[index] = difference.clip(0, 0xFFFF)
        return result

    def calibrate_with_auto_directory(self, file_data: [ndarray], auto_directory_path: str,
                                      sample_file: FileDescriptor, console: Console) -> [ndarray]:
        calibration_file = self.get_best_calibration_file(auto_directory_path, sample_file, console)
        return self.calibrate_with_file(file_data, calibration_file)

    #
    # Get the best matched calibration file in the auto directory
    # If no suitable file, raise exception
    #
    #   Exceptions thrown:
    #       NoSuitableAutoBias

    @classmethod
    def get_best_calibration_file(cls, directory_path: str, sample_file: FileDescriptor, console: Console) -> str:
        # Get all calibration files in the given directory
        all_descriptors = cls.all_descriptors_from_directory(directory_path)
        if len(all_descriptors) == 0:
            # No files in that directory, raise exception
            raise MasterMakerExceptions.AutoCalibrationDirectoryEmpty(directory_path)

        # Get the subset that are the correct size and binning
        correct_size = cls.filter_to_correct_size(all_descriptors, sample_file)
        if len(correct_size) == 0:
            # No files in that directory are the correct size
            raise MasterMakerExceptions.NoSuitableAutoBias

        # From the correct-sized files, find the one closest to the sample file temperature
        closest_match = cls.closest_temperature_match(correct_size, sample_file.get_temperature(), console)
        return closest_match.get_absolute_path()

    @classmethod
    def all_descriptors_from_directory(cls, directory_path: str) -> [FileDescriptor]:
        paths: [str] = SharedUtils.files_in_directory(directory_path)
        descriptors = RmFitsUtil.make_file_descriptions(paths)
        return descriptors

    @classmethod
    def filter_to_correct_size(cls, all_descriptors: [FileDescriptor], sample_file: FileDescriptor) -> [FileDescriptor]:
        x_dimension = sample_file.get_x_dimension()
        y_dimension = sample_file.get_y_dimension()
        binning = sample_file.get_binning()
        d: FileDescriptor
        filtered = [d for d in all_descriptors
                    if d.get_x_dimension() == x_dimension
                    and d.get_y_dimension() == y_dimension
                    and d.get_binning() == binning]
        return filtered

    @classmethod
    def closest_temperature_match(cls, descriptors: [FileDescriptor],
                                  target_temperature: float,
                                  console: Console) -> FileDescriptor:
        best_file_so_far: FileDescriptor = FileDescriptor()
        best_difference_so_far = sys.float_info.max
        for descriptor in descriptors:
            this_difference = abs(descriptor.get_temperature() - target_temperature)
            if this_difference < best_difference_so_far:
                best_difference_so_far = this_difference
                best_file_so_far = descriptor
        assert best_file_so_far is not None
        console.message(f"Selected calibration file {best_file_so_far.get_name()} "
                        f"at temperature {best_file_so_far.get_temperature()}", +1, temp=True)
        return best_file_so_far