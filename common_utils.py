import bisect
import logging
import os
from functools import reduce


def map_reduce_op(args, map_fn, reduce_fn):
    mapped_results = map(map_fn, args)
    reduced_output = reduce(reduce_fn, mapped_results)
    return reduced_output


def find_column_files(data_dir: str):
    files = os.listdir(data_dir)
    matching_files = [file for file in files if file.endswith(".mastidb")]
    columns = [os.path.basename(file).replace('.mastidb', '') for file in matching_files]
    return columns


def ensure_directory_exists(directory_path):
    # Configure the logger
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Check if the directory exists
    if not os.path.exists(directory_path):
        # If not, create it
        os.makedirs(directory_path)
        logger.info(f"Directory '{directory_path}' does not exist. Creating")
    else:
        logger.info(f"Directory '{directory_path}' already exists. Proceeding")


def binary_search(arr, x):
    index = bisect.bisect_left(arr, x)
    if index != len(arr) and arr[index] == x:
        return index
    else:
        return -1
