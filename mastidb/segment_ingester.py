
import json
import logging
import time

import pandas as pd
from .common_utils import ensure_directory_exists
from .data_accessor import DataAccessor

from .segment import Segment
from .segment_column import SegmentColumn


logger = logging.getLogger(__name__)


def _is_newline_separated_json(file_path):
    """
    Determines if a JSON file is newline-separated.

    Parameters:
    file_path (str): The path to the file.

    Returns:
    bool: True if the file is newline-separated JSON, False otherwise.
    """
    try:
        with open(file_path, 'r') as file:
            for line in file:
                line = line.strip()
                if line:  # Check only the first non-empty line
                    json.loads(line)  # Try to parse the line as JSON
                    return True  # Successfully parsed as individual JSON object
            return False  # File is empty or not newline-separated JSON
    except json.JSONDecodeError:
        # Failed to parse as individual JSON objects, so it's not newline-separated JSON
        return False

class SegmentIngester:
  @staticmethod
  def ingest(data_dir: str, file_path: str) -> Segment:
    start_time = time.time()
    df = SegmentIngester.convert_file_to_pandas(file_path)
    segment = SegmentIngester.ingest_from_df(data_dir, df)
    logger.info("[create] Segment created. Took %.2f seconds", time.time() - start_time) 
    return segment
    
  @staticmethod
  def convert_file_to_pandas(file_path: str) -> pd.DataFrame:
    """
    Converts a file of type TSV, CSV, or JSON to a Pandas DataFrame.

    Parameters:
    file_path (str): The path to the file.

    Returns:
    pd.DataFrame: A DataFrame containing the data from the file.
    """
    logger.info(f"Initiating file parsing: {file_path}")

    if file_path.endswith('.tsv'):
        logger.info(f"Detected TSV format for: {file_path}. Proceeding with TSV parsing.")
        df = pd.read_csv(file_path, sep='\t')
    elif file_path.endswith('.csv'):
        logger.info(f"Detected CSV format for: {file_path}. Proceeding with CSV parsing.")
        df = pd.read_csv(file_path)
    elif file_path.endswith('.json'):
        logger.info(f"Detected JSON format for: {file_path}. Determining specific JSON subtype.")
        if _is_newline_separated_json(file_path):
            logger.info("Identified as newline-separated JSON. Parsing accordingly.")
            df = pd.read_json(file_path, lines=True)
        else:
            logger.info("Identified as standard JSON. Parsing accordingly.")
            df = pd.read_json(file_path)
    else:
        error_msg = f"Unsupported file type for: {file_path}. Only TSV, CSV, or JSON formats are accepted."
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(f"Successfully parsed file: {file_path}")
    return df
  
  @staticmethod
  def ingest_from_df(data_dir: str, df: pd.DataFrame) -> Segment:
    logger.info("[create] Creating a segment")
    segment_columns: dict[str, SegmentColumn] = {}

    ensure_directory_exists(data_dir)

    for column in df.columns:
        logger.info(f"[create] Building column: {column}")
        segment_columns[column] = SegmentColumn.create(DataAccessor(f"{data_dir}/{column}").open('wb'),
                                                        df[column].tolist())
    return Segment(segment_columns)
  
  
  
