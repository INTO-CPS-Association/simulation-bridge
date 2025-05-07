
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from src.utils.create_response import create_response

# Test basic success response for batch simulation
def test_create_response_success_batch():
    response_templates = {
        'success': {
            'status': 'success',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
            'include_metadata': False
        }
    }
    
    outputs = {'result': 42, 'status': 'done'}
    
    result = create_response(
        template_type='success',
        sim_file='test_sim.mat',
        sim_type='batch',
        response_templates=response_templates,
        outputs=outputs
    )
    
    assert result['status'] == 'completed'
    assert result['simulation']['name'] == 'test_sim.mat'
    assert result['simulation']['type'] == 'batch'
    assert result['simulation']['outputs'] == outputs
    assert 'timestamp' in result

# Test success response for streaming simulation
def test_create_response_success_streaming():
    response_templates = {
        'success': {
            'status': 'success',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
            'include_metadata': False
        }
    }
    
    data = {'result': 42, 'status': 'done'}
    
    result = create_response(
        template_type='success',
        sim_file='test_sim.mat',
        sim_type='streaming',
        response_templates=response_templates,
        data=data
    )
    
    assert result['status'] == 'completed'
    assert result['simulation']['name'] == 'test_sim.mat'
    assert result['simulation']['type'] == 'streaming'
    assert result['simulation']['outputs'] == data
    assert 'timestamp' in result

# Test error response with basic error info
def test_create_response_error_basic():
    response_templates = {
        'error': {
            'status': 'error',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
            'error_codes': {
                'validation_error': 400,
                'execution_error': 500
            },
            'include_stacktrace': False
        }
    }
    
    error_info = {
        'message': 'Something went wrong',
        'type': 'execution_error'
    }
    
    result = create_response(
        template_type='error',
        sim_file='test_sim.mat',
        sim_type='batch',
        response_templates=response_templates,
        error=error_info
    )
    
    assert result['status'] == 'error'
    assert result['simulation']['name'] == 'test_sim.mat'
    assert result['simulation']['type'] == 'batch'
    assert result['error']['message'] == 'Something went wrong'
    assert result['error']['code'] == 500
    assert result['error']['type'] == 'execution_error'
    assert 'traceback' not in result['error']

# Test error response with stacktrace included
def test_create_response_error_with_stacktrace():
    response_templates = {
        'error': {
            'status': 'error',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
            'error_codes': {
                'validation_error': 400,
                'execution_error': 500
            },
            'include_stacktrace': True
        }
    }
    
    traceback = "Traceback (most recent call last):\n  File 'test.py', line 10"
    error_info = {
        'message': 'Something went wrong',
        'type': 'validation_error',
        'traceback': traceback
    }
    
    result = create_response(
        template_type='error',
        sim_file='test_sim.mat',
        sim_type='batch',
        response_templates=response_templates,
        error=error_info
    )
    
    assert result['status'] == 'error'
    assert result['error']['message'] == 'Something went wrong'
    assert result['error']['code'] == 400
    assert result['error']['traceback'] == traceback

# Test progress response with percentage
def test_create_response_progress_with_percentage():
    response_templates = {
        'progress': {
            'status': 'in_progress',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
            'include_percentage': True
        }
    }
    
    result = create_response(
        template_type='progress',
        sim_file='test_sim.mat',
        sim_type='batch',
        response_templates=response_templates,
        percentage=75,
        message='Processing data'
    )
    
    assert result['status'] == 'in_progress'
    assert result['simulation']['name'] == 'test_sim.mat'
    assert result['simulation']['type'] == 'batch'
    assert result['progress']['percentage'] == 75
    assert result['progress']['message'] == 'Processing data'

# Test progress response without percentage
def test_create_response_progress_without_percentage():
    response_templates = {
        'progress': {
            'status': 'in_progress',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
            'include_percentage': False
        }
    }
    
    result = create_response(
        template_type='progress',
        sim_file='test_sim.mat',
        sim_type='batch',
        response_templates=response_templates,
        percentage=75,  # This should be ignored
        message='Processing data'
    )
    
    assert result['status'] == 'in_progress'
    assert result['simulation']['name'] == 'test_sim.mat'
    assert result['simulation']['type'] == 'batch'
    assert 'percentage' not in result.get('progress', {})
    assert result['progress']['message'] == 'Processing data'

# Test streaming response
def test_create_response_streaming():
    response_templates = {
        'streaming': {
            'status': 'streaming',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ'
        }
    }
    
    stream_data = {'partial_result': 21}
    
    result = create_response(
        template_type='streaming',
        sim_file='test_sim.mat',
        sim_type='streaming',
        response_templates=response_templates,
        data=stream_data,
        sequence=3
    )
    
    assert result['status'] == 'streaming'
    assert result['simulation']['name'] == 'test_sim.mat'
    assert result['simulation']['type'] == 'streaming'
    assert result['data'] == stream_data
    assert result['sequence'] == 3

# Test response with metadata
def test_create_response_with_metadata():
    response_templates = {
        'success': {
            'status': 'success',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
            'include_metadata': True
        }
    }
    
    metadata = {
        'execution_time': 1.23,
        'memory_usage': '128MB',
        'matlab_version': 'R2023a'
    }
    
    result = create_response(
        template_type='success',
        sim_file='test_sim.mat',
        sim_type='batch',
        response_templates=response_templates,
        outputs={'result': 42},
        metadata=metadata
    )
    
    assert result['status'] == 'completed'
    assert result['metadata'] == metadata

# Test timestamp formatting
@patch('src.utils.create_response.datetime')
def test_create_response_timestamp_format(mock_datetime):
    # Set up a fixed datetime for testing
    mock_now = MagicMock()
    mock_now.strftime.return_value = '2023-01-01T12:00:00Z'
    mock_datetime.now.return_value = mock_now
    
    response_templates = {
        'success': {
            'status': 'success',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ'
        }
    }
    
    result = create_response(
        template_type='success',
        sim_file='test_sim.mat',
        sim_type='batch',
        response_templates=response_templates,
        outputs={}
    )
    
    assert result['timestamp'] == '2023-01-01T12:00:00Z'
    mock_now.strftime.assert_called_once_with('%Y-%m-%dT%H:%M:%SZ')

# Test with non-existent template
def test_create_response_nonexistent_template():
    response_templates = {
        'success': {
            'status': 'success',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ'
        }
    }
    
    result = create_response(
        template_type='nonexistent',
        sim_file='test_sim.mat',
        sim_type='batch',
        response_templates=response_templates
    )
    
    assert result['status'] == 'nonexistent'
    assert result['simulation']['name'] == 'test_sim.mat'
    assert result['simulation']['type'] == 'batch'
    assert 'timestamp' in result

# Test additional kwargs are included in response
def test_create_response_additional_kwargs():
    response_templates = {
        'success': {
            'status': 'success',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ'
        }
    }
    
    result = create_response(
        template_type='success',
        sim_file='test_sim.mat',
        sim_type='batch',
        response_templates=response_templates,
        outputs={},
        custom_field='custom_value',
        another_field=123
    )
    
    assert result['status'] == 'completed'
    assert result['custom_field'] == 'custom_value'
    assert result['another_field'] == 123

# Test progress response with streaming data
def test_create_response_progress_with_data():
    response_templates = {
        'progress': {
            'status': 'in_progress',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
            'include_percentage': True
        }
    }
    
    stream_data = {'partial_result': 21}
    
    result = create_response(
        template_type='progress',
        sim_file='test_sim.mat',
        sim_type='streaming',
        response_templates=response_templates,
        percentage=50,
        message='Halfway there',
        data=stream_data
    )
    
    assert result['status'] == 'in_progress'
    assert result['progress']['percentage'] == 50
    assert result['progress']['message'] == 'Halfway there'
    assert result['data'] == stream_data