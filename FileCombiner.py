#
#   Static methods for combining FITS files using different algorithms
#
from itertools import groupby

import MasterMakerExceptions
from Calibrator import Calibrator
from Constants import Constants
from DataModel import DataModel
from FileDescriptor import FileDescriptor
from ImageMath import ImageMath
from RmFitsUtil import RmFitsUtil
from SharedUtils import SharedUtils


class FileCombiner:

    # Process one set of files.  Output to the given path, if provided.  If not provided, prompt the user for it.
    @classmethod
    def original_non_grouped_processing(cls, selected_files: [FileDescriptor],
                                        data_model: DataModel,
                                        output_file: str
                                        ):
        # We'll use the first file in the list as a sample for things like image size
        assert len(selected_files) > 0
        # Confirm that these are all dark frames, and can be combined (same binning and dimensions)
        if FileCombiner.all_compatible_sizes(selected_files):
            if data_model.get_ignore_file_type() \
                    or FileCombiner.all_of_type(selected_files, FileDescriptor.FILE_TYPE_DARK):
                # Get (most common) filter name in the set
                # Since these are darks, the filter is meaningless, but we need the value
                # for the shared "create file" routine
                filter_name = SharedUtils.most_common_filter_name(selected_files)

                # Do the combination
                FileCombiner.combine_files(selected_files, data_model, filter_name, output_file)
                # Optionally do something with the original input files
            else:
                raise MasterMakerExceptions.NotAllDarkFrames
        else:
            raise MasterMakerExceptions.IncompatibleSizes

    #
    #   Process the given selected files in groups by size, exposure, or temperature (or any combination)
    #
    #   Exceptions thrown:
    #       NoGroupOutputDirectory      Output directory does not exist and unable to create it
    @classmethod
    def process_groups(cls, data_model: DataModel, selected_files: [FileDescriptor], output_directory: str):
        print("process_groups")
        # todo process_groups

        exposure_tolerance = data_model.get_exposure_group_tolerance()
        temperature_tolerance = data_model.get_temperature_group_tolerance()
        print("Process groups into output directory: " + output_directory)
        if not SharedUtils.ensure_directory_exists(output_directory):
            raise MasterMakerExceptions.NoGroupOutputDirectory(output_directory)

        #  Process size groups, or all sizes if not grouping
        groups_by_size = FileCombiner.get_groups_by_size(selected_files, data_model.get_group_by_size())
        for size_group in groups_by_size:
            print(f"Processing one size group: {len(size_group)} files sized {size_group[0].get_size_key()}")
            # Within this size group, process exposure groups, or all exposures if not grouping
            groups_by_exposure = FileCombiner.get_groups_by_exposure(size_group,
                                                                     data_model.get_group_by_exposure(),
                                                                     exposure_tolerance)
            for exposure_group in groups_by_exposure:
                print(f"Processing one exposure group: {len(exposure_group)} "
                      f"files exposed {size_group[0].get_exposure()}")
                # Within this exposure group, process temperature groups, or all temperatures if not grouping
                groups_by_temperature = FileCombiner.get_groups_by_temperature(exposure_group,
                                                                               data_model.get_group_by_temperature(),
                                                                               temperature_tolerance)
                for temperature_group in groups_by_temperature:
                    # print(f"Processing one temperature group: "
                    #       f"{len(temperature_group)} files at temp {size_group[0].get_temperature()}")
                    # Now we have a list of descriptors, grouped as appropriate, to process
                    cls.process_one_group(data_model, temperature_group, output_directory,
                                           data_model.get_master_combine_method())

    # Process one group of files, output to the given directory
    #
    #   Exceptions thrown:
    #       NotAllDarkFrames        The given files are not all dark frames
    #       IncompatibleSizes       The given files are not all the same dimensions
    @classmethod
    def process_one_group(cls,
                          data_model: DataModel,
                          descriptor_list: [FileDescriptor],
                          output_directory: str,
                          combine_method: int):
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
        file_name = SharedUtils.get_file_name_portion(combine_method, sample_file)
        output_file = f"{output_directory}/{file_name}"

        # Confirm that these are all dark frames, and can be combined (same binning and dimensions)
        if cls.all_compatible_sizes(descriptor_list):
            if data_model.get_ignore_file_type() \
                    or cls.all_of_type(descriptor_list, FileDescriptor.FILE_TYPE_DARK):
                # Get (most common) filter name in the set
                # Since these are darks, the filter is meaningless, but we need the value
                # for the shared "create file" routine
                filter_name = SharedUtils.most_common_filter_name(descriptor_list)

                # Do the combination
                cls.combine_files(descriptor_list, data_model, filter_name, output_file,)
            else:
                raise MasterMakerExceptions.NotAllDarkFrames
        else:
            raise MasterMakerExceptions.IncompatibleSizes

    # Determine if all the files in the list are of the given type
    @classmethod
    def all_of_type(cls, selected_files: [FileDescriptor], type_code: int):
        for descriptor in selected_files:
            if descriptor.get_type() != type_code:
                return False
        return True

    # Confirm that the given list of files are combinable by being compatible sizes
    # This means their x,y dimensions are the same and their binning is the same
    @classmethod
    def all_compatible_sizes(cls, selected_files: [FileDescriptor]):
        if len(selected_files) == 0:
            return True
        (x_dimension, y_dimension) = selected_files[0].get_dimensions()
        binning = selected_files[0].get_binning()
        for descriptor in selected_files:
            (this_x, this_y) = descriptor.get_dimensions()
            if this_x != x_dimension or this_y != y_dimension or descriptor.get_binning() != binning:
                return False
        return True

    # Determine if all the files in the list have the same filter name
    @classmethod
    def all_same_filter(cls, selected_files: [FileDescriptor]) -> bool:
        if len(selected_files) == 0:
            return True
        filter_name = selected_files[0].get_filter_name()
        for descriptor in selected_files:
            if descriptor.get_filter_name() != filter_name:
                return False
        return True

    # Determine if all the dimensions are OK to proceed.
    #   All selected files must be the same size and the same binning
    #   Include the precalibration bias file in this test if that method is selected

    @classmethod
    def validate_file_dimensions(cls, descriptors: [FileDescriptor], data_model: DataModel) -> bool:
        # Get list of paths of selected files
        if len(descriptors) > 0:

            # If precalibration file is in use, add that name to the list
            if data_model.get_precalibration_type() == Constants.CALIBRATION_FIXED_FILE:
                calibration_descriptor = \
                    RmFitsUtil.make_file_descriptor(data_model.get_precalibration_fixed_path())
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
    def get_groups_by_exposure(cls,
                               selected_files: [FileDescriptor],
                               is_grouped: bool,
                               tolerance: float) -> [[FileDescriptor]]:
        if is_grouped:
            result: [[FileDescriptor]] = []
            files_sorted: [FileDescriptor] = sorted(selected_files, key=FileDescriptor.get_exposure)
            current_exposure: float = files_sorted[0].get_exposure()
            current_list: [FileDescriptor] = []
            for next_file in files_sorted:
                this_exposure = next_file.get_exposure()
                if SharedUtils.values_same_within_tolerance(current_exposure, this_exposure, tolerance):
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
    def get_groups_by_temperature(cls,
                                  selected_files: [FileDescriptor],
                                  is_grouped: bool,
                                  tolerance: float) -> [[FileDescriptor]]:
        if is_grouped:
            result: [[FileDescriptor]] = []
            files_sorted: [FileDescriptor] = sorted(selected_files, key=FileDescriptor.get_temperature)
            current_temperature: float = files_sorted[0].get_temperature()
            current_list: [FileDescriptor] = []
            for next_file in files_sorted:
                this_temperature = next_file.get_temperature()
                if SharedUtils.values_same_within_tolerance(current_temperature, this_temperature, tolerance):
                    current_list.append(next_file)
                else:
                    result.append(current_list)
                    current_list = [next_file]
                    current_temperature = this_temperature
            result.append(current_list)
            return result
        else:
            return [selected_files]   # One group with all the files

    # Combine the given files, output to the given output file
    # Use the combination algorithm given by the radio buttons on the main window
    @classmethod
    def combine_files(cls, input_files: [FileDescriptor],
                      data_model: DataModel,
                      filter_name: str, output_path: str):
        substituted_file_name = SharedUtils.substitute_date_time_filter_in_string(output_path)
        file_names = [d.get_absolute_path() for d in input_files]
        combine_method = data_model.get_master_combine_method()
        # Get info about any precalibration that is to be done
        calibrator = Calibrator(data_model)
        assert len(input_files) > 0
        binning: int = input_files[0].get_binning()
        (mean_exposure, mean_temperature) = ImageMath.mean_exposure_and_temperature(input_files)
        if combine_method == Constants.COMBINE_MEAN:
            mean_data = ImageMath.combine_mean(file_names, calibrator)
            RmFitsUtil.create_combined_fits_file(substituted_file_name, mean_data,
                                                 FileDescriptor.FILE_TYPE_DARK,
                                                 "Dark Frame",
                                                 mean_exposure, mean_temperature, filter_name, binning,
                                                 "Master Dark MEAN combined")
        elif combine_method == Constants.COMBINE_MEDIAN:
            median_data = ImageMath.combine_median(file_names, calibrator)
            RmFitsUtil.create_combined_fits_file(substituted_file_name, median_data,
                                                 FileDescriptor.FILE_TYPE_DARK,
                                                 "Dark Frame",
                                                 mean_exposure, mean_temperature, filter_name, binning,
                                                 "Master Dark MEDIAN combined")
        elif combine_method == Constants.COMBINE_MINMAX:
            number_dropped_points = data_model.get_min_max_number_clipped_per_end()
            min_max_clipped_mean = ImageMath.combine_min_max_clip(file_names, number_dropped_points,
                                                                   calibrator)
            RmFitsUtil.create_combined_fits_file(substituted_file_name, min_max_clipped_mean,
                                                 FileDescriptor.FILE_TYPE_DARK,
                                                 "Dark Frame",
                                                 mean_exposure, mean_temperature, filter_name, binning,
                                                 f"Master Dark Min/Max Clipped "
                                                 f"(drop {number_dropped_points}) Mean combined")
        else:
            assert combine_method == Constants.COMBINE_SIGMA_CLIP
            sigma_threshold = data_model.get_sigma_clip_threshold()
            sigma_clipped_mean = ImageMath.combine_sigma_clip(file_names, sigma_threshold,
                                                               calibrator)
            RmFitsUtil.create_combined_fits_file(substituted_file_name, sigma_clipped_mean,
                                                 FileDescriptor.FILE_TYPE_DARK,
                                                 "Dark Frame",
                                                 mean_exposure, mean_temperature, filter_name, binning,
                                                 f"Master Dark Sigma Clipped "
                                                 f"(threshold {sigma_threshold}) Mean combined")
