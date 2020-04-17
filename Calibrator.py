#
#   Class to handle calibration of images using specified method (including none)
#
from numpy import ndarray

import MasterMakerExceptions
from Constants import Constants
from DataModel import DataModel
from FileDescriptor import FileDescriptor
from RmFitsUtil import RmFitsUtil


class Calibrator:
    #
    #   Create calibration object against the given data model's settings
    #
    def __init__(self, data_model: DataModel):
        self._data_model = data_model

    def calibrate_images(self, file_data: [ndarray], sample_file: FileDescriptor) -> [ndarray]:
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
                                                      sample_file)

    def calibrate_with_pedestal(self, file_data: [ndarray], pedestal: int) -> [ndarray]:
        print(f"calibrate_with_pedestal({pedestal})")
        result = file_data.copy()
        for index in range(len(result)):
            reduced_by_pedestal: ndarray = result[index] - pedestal
            result[index] = reduced_by_pedestal.clip(0, 0xFFFF)
        return result

    def calibrate_with_file(self, file_data: [ndarray], calibration_file_path: str) -> [ndarray]:
        print(f"calibrate_with_file({calibration_file_path}) STUB")
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
                                      sample_file: FileDescriptor) -> [ndarray]:
        print(f"calibrate_with_auto_directory({auto_directory_path}) STUB")
        calibration_file = self.get_best_calibration_file(auto_directory_path, sample_file)
        return self.calibrate_with_file(file_data, calibration_file)

    #
    # Get the best matched calibration file in the auto directory
    # If no suitable file, raise exception
    #
    #   Exceptions thrown:
    #       NoSuitableAutoBias

    @classmethod
    def get_best_calibration_file(cls, directory_path: str, sample_file: FileDescriptor) -> str:
        print(f"get_best_calibration_file({directory_path})")
        print(sample_file)
        # todo get_best_calibration_file
        raise MasterMakerExceptions.NoSuitableAutoBias
        raise MasterMakerExceptions.NoAutoCalibrationDirectory("fart auto dir name")
        return "fart"
