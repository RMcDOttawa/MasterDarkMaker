from PyQt5.QtCore import QSettings, QSize

from Constants import Constants


class Preferences(QSettings):
    # The following are the preferences available

    # How should frames be combined?  Stored as an integer corresponding to one of
    # the COMBINE_xxx constants in the Constants class
    MASTER_COMBINE_METHOD = "master_combine_method"

    # If the Min-Max method is used, how many points are dropped from each end (min and max)
    # before the remaining points are Mean-combined?  Returns an integer > 0.
    MIN_MAX_NUMBER_CLIPPED_PER_END = "min_max_number_clipped_per_end"

    # If Sigma-Clip method is used, what is the threshold sigma score?
    # Data farther than this many standard deviations from the sample mean are rejected,
    # the the remaining points are mean-combined.  Floating point number > 0.
    SIGMA_CLIP_THRESHOLD = "sigma_clip_threshold"

    # What do we do with the input files after a successful combine?
    # Gives an integer from the constants class DISPOSITION_xxx
    INPUT_FILE_DISPOSITION = "input_file_disposition"

    # Folder name to move input files if DISPOSITION is SUBFOLDER
    DISPOSITION_SUBFOLDER_NAME = "disposition_subfolder_name"

    # Main window size - so last window resizing is remembered
    MAIN_WINDOW_SIZE = "main_window_size"

    # What kind of precalibration is done to images before combining
    # Gives an integer from the constants class CALIBRATION_
    IMAGE_PRE_CALIBRATION = "image_pre_calibration"
    # Pedestal value if pedestal option chosen
    PRE_CALIBRATION_PEDESTAL = "pre_calibration_pedestal"
    # File path if bias/dark file is to be subtracted
    PRE_CALIBRATION_FILE = "pre_calibration_file"

    # Are we processing multiple file sets at once using grouping?
    GROUP_BY_SIZE = "group_by_size"
    GROUP_BY_EXPOSURE = "group_by_exposure"
    GROUP_BY_TEMPERATURE = "group_by_temperature"

    # How much, as a percentage, can exposures vary before the files are considered to be in a different group?
    EXPOSURE_GROUP_TOLERANCE = "exposure_group_tolerance"

    # How much, as a percentage, can temperatures vary before being considered a different group?
    TEMPERATURE_GROUP_TOLERANCE = "temperature_group_tolerance"

    def __init__(self):
        QSettings.__init__(self, "EarwigHavenObservatory.com", "MasterDarkMaker_b")
        # print(f"Preferences file path: {self.fileName()}")

    # Getters and setters for preferences values

    # How should frames be combined?  Stored as an integer corresponding to one of
    # the COMBINE_xxx constants in the Constants class

    def get_master_combine_method(self) -> int:
        result = int(self.value(self.MASTER_COMBINE_METHOD, defaultValue=Constants.COMBINE_SIGMA_CLIP))
        assert (result == Constants.COMBINE_SIGMA_CLIP) \
               or (result == Constants.COMBINE_MINMAX) \
               or (result == Constants.COMBINE_MEDIAN) \
               or (result == Constants.COMBINE_MEAN)
        return result

    def set_master_combine_method(self, value: int):
        assert (value == Constants.COMBINE_SIGMA_CLIP) or (value == Constants.COMBINE_MINMAX) \
               or (value == Constants.COMBINE_MEDIAN) or (value == Constants.COMBINE_MEAN)
        self.setValue(self.MASTER_COMBINE_METHOD, value)

    # If the Min-Max method is used, how many points are dropped from each end (min and max)
    # before the remaining points are Mean-combined?  Returns an integer > 0.

    def get_min_max_number_clipped_per_end(self) -> int:
        result = int(self.value(self.MIN_MAX_NUMBER_CLIPPED_PER_END, defaultValue=2))
        assert result > 0
        return result

    def set_min_max_number_clipped_per_end(self, value: int):
        assert value > 0
        self.setValue(self.MIN_MAX_NUMBER_CLIPPED_PER_END, value)

    # If Sigma-Clip method is used, what is the threshold sigma score?
    # Data farther than this many sigmas (ratio of value and std deviation of set) from the sample mean
    # are rejected, the the remaining points are mean-combined.  Floating point number > 0.

    def get_sigma_clip_threshold(self) -> float:
        result = float(self.value(self.SIGMA_CLIP_THRESHOLD, defaultValue=2.0))
        assert result > 0.0
        return result

    def set_sigma_clip_threshold(self, value: float):
        assert value > 0.0
        self.setValue(self.SIGMA_CLIP_THRESHOLD, value)

    # What to do with input files after a successful combine

    def get_input_file_disposition(self):
        result = int(self.value(self.INPUT_FILE_DISPOSITION, defaultValue=Constants.INPUT_DISPOSITION_NOTHING))
        assert (result == Constants.INPUT_DISPOSITION_NOTHING) or (result == Constants.INPUT_DISPOSITION_SUBFOLDER)
        return result

    def set_input_file_disposition(self, value: int):
        assert (value == Constants.INPUT_DISPOSITION_NOTHING) or (value == Constants.INPUT_DISPOSITION_SUBFOLDER)
        self.setValue(self.INPUT_FILE_DISPOSITION, value)

    # Where to move input files if disposition "subfolder" is chosen

    def get_disposition_subfolder_name(self):
        return self.value(self.DISPOSITION_SUBFOLDER_NAME, defaultValue="originals-%d-%t")

    def set_disposition_subfolder_name(self, value: str):
        self.setValue(self.DISPOSITION_SUBFOLDER_NAME, value)

    # Main window size when resized

    def get_main_window_size(self) -> QSize:
        return self.value(self.MAIN_WINDOW_SIZE, defaultValue=None)

    def set_main_window_size(self, size: QSize):
        self.setValue(self.MAIN_WINDOW_SIZE, size)

    # Pre-calibration method

    def get_precalibration_type(self) -> int:
        result = int(self.value(self.IMAGE_PRE_CALIBRATION, defaultValue=Constants.CALIBRATION_NONE))
        assert (result == Constants.CALIBRATION_NONE) \
               or (result == Constants.CALIBRATION_FIXED_FILE) \
               or (result == Constants.CALIBRATION_PROMPT) \
               or (result == Constants.CALIBRATION_PEDESTAL)
        return result

    def set_precalibration_type(self, value: int):
        assert (value == Constants.CALIBRATION_NONE) \
               or (value == Constants.CALIBRATION_FIXED_FILE) \
               or (value == Constants.CALIBRATION_PROMPT) \
               or (value == Constants.CALIBRATION_PEDESTAL)
        self.setValue(self.IMAGE_PRE_CALIBRATION, value)

    # Pedestal value used if pre-calibration option "pedestal" is chosen

    def get_precalibration_pedestal(self) -> int:
        return int(self.value(self.PRE_CALIBRATION_PEDESTAL, defaultValue=Constants.DEFAULT_CALIBRATION_PEDESTAL))

    def set_precalibration_pedestal(self, value: int):
        self.setValue(self.PRE_CALIBRATION_PEDESTAL, value)

    # File path if fixed bias/dark file is to be subtracted

    def get_precalibration_fixed_path(self) -> str:
        return str(self.value(self.PRE_CALIBRATION_FILE, defaultValue=""))

    def set_precalibration_fixed_path(self, path: str):
        self.setValue(self.PRE_CALIBRATION_FILE, path)

    # Are we processing multiple file sets at once using grouping?

    def get_group_by_size(self) -> bool:
        return bool(self.value(self.GROUP_BY_SIZE, defaultValue=False))

    def set_group_by_size(self, isGrouped: bool):
        self.setValue(self.GROUP_BY_SIZE, isGrouped)

    def get_group_by_exposure(self) -> bool:
        return bool(self.value(self.GROUP_BY_EXPOSURE, defaultValue=False))

    def set_group_by_exposure(self, isGrouped: bool):
        self.setValue(self.GROUP_BY_EXPOSURE, isGrouped)

    def get_group_by_temperature(self) -> bool:
        return bool(self.value(self.GROUP_BY_TEMPERATURE, defaultValue=False))

    def set_group_by_temperature(self, isGrouped: bool):
        self.setValue(self.GROUP_BY_TEMPERATURE, isGrouped)

    # How much, as a percentage, can exposures vary before the files are considered to be in a different group?

    def get_exposure_group_tolerance(self) -> float:
        percentage: float = float(self.value(self.EXPOSURE_GROUP_TOLERANCE, defaultValue=0.05))
        assert 0.0 <= percentage < 1.0
        return percentage

    def set_exposure_group_tolerance(self, percentage: float):
        assert 0.0 <= percentage < 1.0
        self.setValue(self.EXPOSURE_GROUP_TOLERANCE, percentage)

    # How much, as a percentage, can temperatures vary before being considered a different group?

    def get_temperature_group_tolerance(self) -> float:
        percentage: float = float(self.value(self.TEMPERATURE_GROUP_TOLERANCE, defaultValue=0.10))
        assert 0 <= percentage < 1
        return percentage

    def set_temperature_group_tolerance(self, percentage: float):
        assert 0 <= percentage < 1
        self.setValue(self.TEMPERATURE_GROUP_TOLERANCE, percentage)
