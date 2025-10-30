import os
import csv
import tempfile
from typing import Dict, List, Any, Union, Optional

from .logger import get_logger

logger = get_logger()


class CSVFormatError(Exception):
    """Exception raised when there's an error in CSV formatting or processing."""


def validate_csv_structure(csv_data: Dict[str, Any]) -> None:
    """
    Validate that the input data has the correct CSV structure for Simul8.

    Args:
        csv_data: Dictionary to validate

    Raises:
        CSVFormatError: If the structure is invalid
    """
    if not csv_data:
        raise CSVFormatError(
            "No CSV data provided - Simul8 simulation requires input data")

    if 'columns' not in csv_data:
        raise CSVFormatError(
            "CSV data must contain 'columns' key - "
            "Expected format: {'columns': ['col1', 'col2'], 'r1': ['val1', 'val2'], ...}"
        )

    columns = csv_data['columns']
    if not isinstance(columns, list):
        raise CSVFormatError("'columns' must be a list")

    if not columns:
        raise CSVFormatError("'columns' cannot be empty")

    # Check for row data (keys starting with 'r')
    row_keys = [key for key in csv_data.keys()
                if key.startswith('r') and key != 'columns']

    if not row_keys:
        raise CSVFormatError(
            "No row data found - Expected at least one row like 'r1': ['val1', 'val2', ...]"
        )

    # Validate each row
    for row_key in row_keys:
        row_data = csv_data[row_key]
        if not isinstance(row_data, list):
            raise CSVFormatError(
                f"Row '{row_key}' must be a list, got {type(row_data).__name__}"
            )

        if len(row_data) != len(columns):
            raise CSVFormatError(
                f"Row '{row_key}' has {
                    len(row_data)} values but {
                    len(columns)} columns expected"
            )
        logger.debug(
            "CSV structure validation passed: %d columns, %d rows",
            len(columns), len(row_keys)
        )


def yaml_csv_to_file(
    csv_data: Dict[str, Any],
    file_path: Optional[str] = None,
    delimiter: str = ','
) -> str:
    """
    Convert YAML structure to a proper CSV file.

    Expected format (example):
    {
        'columns': ['energy', 'co2', 'units']
        'r1': ['23', '10.5', '20']
        'r2': ['9', '2.3', '30'],
        ...
    }

    Args:
        csv_data: Dictionary containing columns and row data
        file_path: Output CSV file path (creates temp file if None)
        delimiter: CSV delimiter

    Returns:
        Path to the created CSV file
    """
    # Validate the CSV structure first
    validate_csv_structure(csv_data)

    columns = csv_data['columns']

    # Create a temporary file if no file_path is provided
    if not file_path:
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"simul8_yaml_csv_{os.getpid()}.csv")

    logger.debug("Converting YAML data to file: %s", file_path)

    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=delimiter)

            # Write header row
            writer.writerow(columns)

            # Write data rows - look for keys that start with 'r' (row
            # indicators)
            row_keys = [key for key in csv_data.keys()
                        if key.startswith('r') and key != 'columns']

            # Sort row keys to maintain order (r1, r2, r3, etc.)
            row_keys.sort(key=lambda x: int(
                x[1:]) if x[1:].isdigit() else float('inf'))

            for row_key in row_keys:
                row_data = csv_data[row_key]
                writer.writerow(row_data)

        logger.debug(
            "Successfully created CSV file from YAML data at %s", file_path)
        return file_path

    except Exception as e:
        logger.error("Failed to create CSV file from YAML data: %s", str(e))
        raise CSVFormatError(
            "Error creating CSV file from YAML data: %s", str(e)
        )


def read_csv_to_dict(
    file_path: str,
    delimiter: str = ',',
    transpose: bool = False,
    output_mapping: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Read a CSV file into a dictionary.

    Args:
        file_path: Path to the CSV file
        delimiter: CSV delimiter
        transpose: If True, assumes first column contains keys, second contains values
        output_mapping: Dictionary mapping CSV column names to desired output names

    Returns:
        Dictionary containing the CSV data
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError("CSV file not found: %s", file_path)

    logger.debug("Reading CSV file: %s", file_path)

    try:
        rows = _read_csv_rows(file_path, delimiter)
        headers = _extract_headers(rows)
        data_row = _find_first_data_row(rows)
        return _build_result_dict(headers, data_row, output_mapping)

    except Exception as e:
        logger.error("Failed to read CSV file: %s", str(e))
        raise CSVFormatError("Error reading CSV file: %s", str(e))


def _read_csv_rows(file_path: str, delimiter: str) -> List[List[str]]:
    """Read and validate CSV file contents."""
    with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
        raw_content = csvfile.read().strip()
        logger.debug("Raw CSV content: %s", raw_content)

        if not raw_content:
            logger.warning("CSV file is empty")
            return []

        csvfile.seek(0)
        rows = list(csv.reader(csvfile, delimiter=delimiter))
        logger.debug("All rows: %s", rows)

        return rows


def _extract_headers(rows: List[List[str]]) -> List[str]:
    """Extract and validate header row."""
    if not rows:
        logger.warning("No rows found in CSV")
        return []

    headers = [str(col).strip() for col in rows[0] if str(col).strip()]
    logger.debug("Headers found: %s", headers)

    if not headers:
        logger.warning("No valid headers found")

    return headers


def _find_first_data_row(rows: List[List[str]]) -> Optional[List[str]]:
    """Find the first non-empty data row after headers."""
    for row in rows[1:]:
        if any(str(cell).strip() for cell in row):
            logger.debug("Data row: %s", row)
            return row

    logger.warning("No data row found")
    return None


def _build_result_dict(
    headers: List[str],
    data_row: Optional[List[str]],
    output_mapping: Optional[Dict[str, str]]
) -> Dict[str, Any]:
    """Build result dictionary from headers and data."""
    results = {}

    for i, header in enumerate(headers):
        value = _parse_cell_value(data_row, i) if data_row else None
        final_key = output_mapping.get(
            header, header) if output_mapping else header

        results[final_key] = value
        logger.debug("Added to results: %s = %s", final_key, value)

    logger.debug("Successfully parsed CSV data: %s", results)
    return results


def _parse_cell_value(data_row: List[str], index: int) -> Any:
    """Parse a single cell value, converting to appropriate type."""
    if index >= len(data_row):
        logger.debug("Added to results (no data): index %d = None", index)
        return None
    value_str = str(data_row[index]).strip()
    if not value_str:
        return None
    # Try to convert to number
    try:
        if '.' in value_str:
            return float(value_str)
        if value_str.isdigit():
            return int(value_str)
        return value_str
    except ValueError:
        pass
    return value_str
