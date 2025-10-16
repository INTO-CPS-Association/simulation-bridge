"""Unit tests for the CSV parser module."""

import os
import pytest
import tempfile
from pathlib import Path

from src.utils.csv_parser import (
    validate_csv_structure,
    yaml_csv_to_file,
    read_csv_to_dict,
    CSVFormatError
)


class TestValidateCSVStructure:
    """Tests for validate_csv_structure function."""

    def test_valid_structure(self):
        """Test validation with valid CSV structure."""
        csv_data = {
            'columns': ['energy', 'co2', 'units'],
            'r1': ['23', '10.5', '20'],
            'r2': ['9', '2.3', '30']
        }
        # Should not raise any exception
        validate_csv_structure(csv_data)

    def test_empty_data(self):
        """Test validation with empty data."""
        with pytest.raises(CSVFormatError, match="No CSV data provided"):
            validate_csv_structure({})

    def test_missing_columns_key(self):
        """Test validation with missing 'columns' key."""
        csv_data = {'r1': ['23', '10.5', '20']}
        with pytest.raises(CSVFormatError, match="CSV data must contain 'columns' key"):
            validate_csv_structure(csv_data)

    def test_columns_not_list(self):
        """Test validation when 'columns' is not a list."""
        csv_data = {
            'columns': 'energy,co2',
            'r1': ['23', '10.5']
        }
        with pytest.raises(CSVFormatError, match="'columns' must be a list"):
            validate_csv_structure(csv_data)

    def test_empty_columns(self):
        """Test validation with empty columns list."""
        csv_data = {
            'columns': [],
            'r1': []
        }
        with pytest.raises(CSVFormatError, match="'columns' cannot be empty"):
            validate_csv_structure(csv_data)

    def test_no_row_data(self):
        """Test validation with no row data."""
        csv_data = {'columns': ['energy', 'co2']}
        with pytest.raises(CSVFormatError, match="No row data found"):
            validate_csv_structure(csv_data)

    def test_row_not_list(self):
        """Test validation when row data is not a list."""
        csv_data = {
            'columns': ['energy', 'co2'],
            'r1': '23,10.5'
        }
        with pytest.raises(CSVFormatError, match="Row 'r1' must be a list"):
            validate_csv_structure(csv_data)

    def test_mismatched_row_length(self):
        """Test validation when row length doesn't match columns."""
        csv_data = {
            'columns': ['energy', 'co2', 'units'],
            'r1': ['23', '10.5']  # Missing one value
        }
        with pytest.raises(CSVFormatError, match="Row 'r1' has 2 values but 3 columns expected"):
            validate_csv_structure(csv_data)


class TestYamlCSVToFile:
    """Tests for yaml_csv_to_file function."""

    def test_create_csv_with_valid_data(self, tmp_path):
        """Test creating CSV file with valid data."""
        csv_data = {
            'columns': ['energy', 'co2', 'units'],
            'r1': ['23', '10.5', '20'],
            'r2': ['9', '2.3', '30']
        }
        output_file = tmp_path / "test_output.csv"
        
        result_path = yaml_csv_to_file(csv_data, str(output_file))
        
        assert os.path.exists(result_path)
        assert result_path == str(output_file)
        
        # Verify contents
        with open(result_path, 'r') as f:
            lines = f.readlines()
            assert lines[0].strip() == 'energy,co2,units'
            assert lines[1].strip() == '23,10.5,20'
            assert lines[2].strip() == '9,2.3,30'

    def test_create_csv_without_filepath(self):
        """Test creating CSV file in temp directory when no path provided."""
        csv_data = {
            'columns': ['energy', 'co2'],
            'r1': ['23', '10.5']
        }
        
        result_path = yaml_csv_to_file(csv_data)
        
        assert os.path.exists(result_path)
        assert result_path.startswith(tempfile.gettempdir())
        
        # Clean up
        os.remove(result_path)

    def test_create_csv_with_custom_delimiter(self, tmp_path):
        """Test creating CSV file with custom delimiter."""
        csv_data = {
            'columns': ['energy', 'co2'],
            'r1': ['23', '10.5']
        }
        output_file = tmp_path / "test_semicolon.csv"
        
        result_path = yaml_csv_to_file(csv_data, str(output_file), delimiter=';')
        
        with open(result_path, 'r') as f:
            lines = f.readlines()
            assert lines[0].strip() == 'energy;co2'
            assert lines[1].strip() == '23;10.5'

    def test_create_csv_with_multiple_rows(self, tmp_path):
        """Test creating CSV file with multiple rows in correct order."""
        csv_data = {
            'columns': ['a', 'b'],
            'r3': ['3', '30'],
            'r1': ['1', '10'],
            'r2': ['2', '20']
        }
        output_file = tmp_path / "test_order.csv"
        
        result_path = yaml_csv_to_file(csv_data, str(output_file))
        
        with open(result_path, 'r') as f:
            lines = f.readlines()
            # Should be sorted: r1, r2, r3
            assert lines[1].strip() == '1,10'
            assert lines[2].strip() == '2,20'
            assert lines[3].strip() == '3,30'

    def test_create_csv_with_invalid_data(self, tmp_path):
        """Test creating CSV file with invalid data raises error."""
        csv_data = {'columns': ['energy']}  # No row data
        output_file = tmp_path / "test_invalid.csv"
        
        with pytest.raises(CSVFormatError):
            yaml_csv_to_file(csv_data, str(output_file))


class TestReadCSVToDict:
    """Tests for read_csv_to_dict function."""

    def test_read_simple_csv(self, tmp_path):
        """Test reading a simple CSV file."""
        csv_file = tmp_path / "test_read.csv"
        csv_file.write_text("energy,co2,units\n23,10.5,20\n")
        
        result = read_csv_to_dict(str(csv_file))
        
        assert result == {'energy': 23, 'co2': 10.5, 'units': 20}

    def test_read_csv_with_output_mapping(self, tmp_path):
        """Test reading CSV with output mapping."""
        csv_file = tmp_path / "test_mapping.csv"
        csv_file.write_text("Total CO2,Total Energy\n100.5,200.3\n")
        
        output_mapping = {
            'Total CO2': 'total_co2',
            'Total Energy': 'total_energy'
        }
        
        result = read_csv_to_dict(str(csv_file), output_mapping=output_mapping)
        
        assert result == {'total_co2': 100.5, 'total_energy': 200.3}

    def test_read_csv_with_custom_delimiter(self, tmp_path):
        """Test reading CSV with custom delimiter."""
        csv_file = tmp_path / "test_delimiter.csv"
        csv_file.write_text("energy;co2\n23;10.5\n")
        
        result = read_csv_to_dict(str(csv_file), delimiter=';')
        
        assert result == {'energy': 23, 'co2': 10.5}

    def test_read_empty_csv(self, tmp_path):
        """Test reading empty CSV file."""
        csv_file = tmp_path / "test_empty.csv"
        csv_file.write_text("")
        
        result = read_csv_to_dict(str(csv_file))
        
        assert result == {}

    def test_read_csv_with_string_values(self, tmp_path):
        """Test reading CSV with string values."""
        csv_file = tmp_path / "test_strings.csv"
        csv_file.write_text("name,status\nSimulation1,completed\n")
        
        result = read_csv_to_dict(str(csv_file))
        
        assert result == {'name': 'Simulation1', 'status': 'completed'}

    def test_read_csv_with_missing_values(self, tmp_path):
        """Test reading CSV with missing values."""
        csv_file = tmp_path / "test_missing.csv"
        csv_file.write_text("energy,co2,units\n23,,20\n")
        
        result = read_csv_to_dict(str(csv_file))
        
        assert result == {'energy': 23, 'co2': None, 'units': 20}

    def test_read_csv_header_only(self, tmp_path):
        """Test reading CSV with header only (no data row)."""
        csv_file = tmp_path / "test_header_only.csv"
        csv_file.write_text("energy,co2,units\n")
        
        result = read_csv_to_dict(str(csv_file))
        
        assert result == {'energy': None, 'co2': None, 'units': None}

    def test_read_nonexistent_file(self):
        """Test reading non-existent file raises error."""
        with pytest.raises(FileNotFoundError, match="CSV file not found"):
            read_csv_to_dict("/nonexistent/path/file.csv")

    def test_read_csv_with_whitespace(self, tmp_path):
        """Test reading CSV with whitespace in values."""
        csv_file = tmp_path / "test_whitespace.csv"
        csv_file.write_text("energy , co2 \n 23 , 10.5 \n")
        
        result = read_csv_to_dict(str(csv_file))
        
        assert result == {'energy': 23, 'co2': 10.5}

    def test_read_csv_with_mixed_types(self, tmp_path):
        """Test reading CSV with mixed data types."""
        csv_file = tmp_path / "test_mixed.csv"
        csv_file.write_text("count,value,name,ratio\n42,3.14,test,2.5\n")
        
        result = read_csv_to_dict(str(csv_file))
        
        assert result == {
            'count': 42,
            'value': 3.14,
            'name': 'test',
            'ratio': 2.5
        }


class TestCSVFormatError:
    """Tests for CSVFormatError exception."""

    def test_csv_format_error_message(self):
        """Test CSVFormatError can be raised with custom message."""
        with pytest.raises(CSVFormatError, match="Custom error message"):
            raise CSVFormatError("Custom error message")

    def test_csv_format_error_is_exception(self):
        """Test CSVFormatError is an Exception."""
        error = CSVFormatError("test")
        assert isinstance(error, Exception)
