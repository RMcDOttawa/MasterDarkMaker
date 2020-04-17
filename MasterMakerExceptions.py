
#
#   Auto-bias from directory is selected, but we were unable to find a suitable bias file
#   Either the directory is empty or it contains no files of the right size (dimensions and binning)
#


class NoSuitableAutoBias(Exception):
    pass


#
#   Group processing is selected, which puts created files in a directory
#   The specified directory does not exist
#


class NoGroupOutputDirectory(Exception):
    def __init__(self, directory_name: str):
        self._directory_name = directory_name

    def get_directory_name(self) -> str:
        return self._directory_name

#
#   The selected files are not all Dark frames and "ignore type" option is not selected
#


class NotAllDarkFrames(Exception):
    pass

#
#   Files to be combined have different dimensions or binning
#


class IncompatibleSizes(Exception):
    pass


class TestException(Exception):
    pass


class NoAutoCalibrationDirectory(Exception):
    def __init__(self, directory_name: str):
        self._directory_name = directory_name

    def get_directory_name(self) -> str:
        return self._directory_name
