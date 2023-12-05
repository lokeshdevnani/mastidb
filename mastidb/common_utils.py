import bisect
import logging
import math
import os
from functools import reduce
from typing import Callable, Any

# Configure the logger
logger = logging.getLogger(__name__)


def map_reduce_op(args, map_fn: Callable[[Any], Any], reduce_fn: Callable[[Any, Any], Any]):
    mapped_results = map(map_fn, args)
    reduced_output = reduce(reduce_fn, mapped_results)
    return reduced_output


def find_column_files(data_dir: str):
    files = os.listdir(data_dir)
    matching_files = [file for file in files if file.endswith(".mastidb")]
    columns = [os.path.basename(file).replace('.mastidb', '') for file in matching_files]
    return columns


def ensure_directory_exists(directory_path):
    # Check if the directory exists
    if not os.path.exists(directory_path):
        # If not, create it
        os.makedirs(directory_path)
        logger.info(f"Directory '{directory_path}' does not exist. Creating")
    else:
        logger.info(f"Directory '{directory_path}' already exists. Proceeding")


def binary_search(arr: list[str], x: str):
    index = bisect.bisect_left(arr, x)
    if index != len(arr) and arr[index] == x:
        return index
    else:
        return -1


def binary_search_with_reader(n: int, target: str, read_value_fn: Callable[[int], str]):
    low = 0
    high = n - 1

    while low <= high:
        mid = (low + high) // 2
        mid_element = read_value_fn(mid)

        if mid_element == target:
            return mid  # Target found
        elif mid_element > target:
            high = mid - 1
        else:
            low = mid + 1

    return -1

def parse_int(val) -> int:
  float_val: float = float(val)
  if math.isnan(float_val):
      return 0

  return int(float_val)