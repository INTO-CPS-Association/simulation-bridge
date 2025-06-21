import os
import csv
import tempfile
from typing import Dict, List, Any, Union, Optional

from .logger import get_logger

logger = get_logger()

class CSVFormatError(Exception):
    """Exception raised when there's an error in CSV formatting or processing."""
    pass

def validate_csv_structure(csv_data: Dict[str, Any]) -> None:
    """
    Validate that the input data has the correct CSV structure for Simul8.
    
    Args:
        csv_data: Dictionary to validate
        
    Raises:
        CSVFormatError: If the structure is invalid
    """
    if not csv_data:
        raise CSVFormatError("No CSV data provided - Simul8 simulation requires input data")
    
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
            raise CSVFormatError(f"Row '{row_key}' must be a list, got {type(row_data)}")
        
        if len(row_data) != len(columns):
            raise CSVFormatError(
                f"Row '{row_key}' has {len(row_data)} values but {len(columns)} columns expected"
            )
    
    logger.debug(f"CSV structure validation passed: {len(columns)} columns, {len(row_keys)} rows")

def yaml_csv_to_file(
    csv_data: Dict[str, Any],
    file_path: Optional[str] = None,
    delimiter: str = ','
) -> str:
    """
    Convert YAML CSV structure to a proper CSV file.
    
    Expected format:
    {
        'columns': ['col1', 'col2', 'col3'],
        'r1': ['val1', 'val2', 'val3'],
        'r2': ['val4', 'val5', 'val6'],
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
    
    logger.debug(f"Converting YAML CSV data to file: {file_path}")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    
    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=delimiter)
            
            # Write header row
            writer.writerow(columns)
            
            # Write data rows - look for keys that start with 'r' (row indicators)
            row_keys = [key for key in csv_data.keys() 
                       if key.startswith('r') and key != 'columns']
            
            # Sort row keys to maintain order (r1, r2, r3, etc.)
            row_keys.sort(key=lambda x: int(x[1:]) if x[1:].isdigit() else float('inf'))
            
            for row_key in row_keys:
                row_data = csv_data[row_key]
                writer.writerow(row_data)
        
        logger.info(f"Successfully created CSV file from YAML data at {file_path}")
        return file_path
        
    except Exception as e:
        logger.error(f"Failed to create CSV file from YAML data: {str(e)}")
        raise CSVFormatError(f"Error creating CSV file from YAML data: {str(e)}")
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
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    
    logger.debug(f"Reading CSV file: {file_path}")
    
    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            # Read all content first to debug
            csvfile.seek(0)
            raw_content = csvfile.read().strip()
            logger.debug(f"Raw CSV content: '{raw_content}'")
            
            if not raw_content:
                logger.warning("CSV file is empty")
                return {}
            
            # Reset file pointer
            csvfile.seek(0)
            reader = csv.reader(csvfile, delimiter=delimiter)
            rows = list(reader)
            
            logger.debug(f"All rows: {rows}")
            
            if not rows:
                logger.warning("No rows found in CSV")
                return {}
            
            # Get the header row (first row)
            header_row = rows[0]
            headers = [str(col).strip() for col in header_row if str(col).strip()]
            
            logger.debug(f"Headers found: {headers}")
            
            if not headers:
                logger.warning("No valid headers found")
                return {}
            
            # Find the data row (first non-empty row after header)
            data_row = None
            for row in rows[1:]:
                if any(str(cell).strip() for cell in row):
                    data_row = row
                    break
            
            if not data_row:
                logger.warning("No data row found")
                return {header: None for header in headers}
            
            logger.debug(f"Data row: {data_row}")
            
            # Create result dictionary
            results = {}
            
            for i, header in enumerate(headers):
                if i < len(data_row):
                    value_str = str(data_row[i]).strip()
                    
                    if not value_str:
                        value = None
                    else:
                        # Try to convert to number
                        try:
                            if '.' in value_str:
                                value = float(value_str)
                            elif value_str.isdigit():
                                value = int(value_str)
                            else:
                                value = value_str
                        except ValueError:
                            value = value_str
                    
                    # Apply output mapping if provided
                    final_key = output_mapping.get(header, header) if output_mapping else header
                    results[final_key] = value
                    logger.debug(f"Added to results: {final_key} = {value}")
                else:
                    # Header exists but no corresponding data
                    final_key = output_mapping.get(header, header) if output_mapping else header
                    results[final_key] = None
                    logger.debug(f"Added to results (no data): {final_key} = None")
            
            logger.info(f"Successfully parsed CSV data: {results}")
            return results
            
    except Exception as e:
        logger.error(f"Failed to read CSV file: {str(e)}")
        raise CSVFormatError(f"Error reading CSV file: {str(e)}")