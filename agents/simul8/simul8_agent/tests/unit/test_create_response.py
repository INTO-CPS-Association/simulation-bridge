"""
Test module for create_response.py

This module contains comprehensive tests for the create_response module,
testing all response types and edge cases while ensuring proper error handling
and response formatting.
"""

import unittest
from unittest.mock import patch
from typing import Dict, Any

from src.utils.create_response import (
    create_response,
    _handle_success_response,
    _handle_error_response,
    _handle_progress_response,
    _handle_streaming_response
)


class TestCreateResponse(unittest.TestCase):
    """Test cases for create_response module."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_templates = {
            'success': {
                'status': 'completed',
                'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
                'include_metadata': True
            },
            'error': {
                'status': 'failed',
                'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
                'include_stacktrace': True,
                'error_codes': {
                    'validation_error': 400,
                    'execution_error': 500,
                    'timeout_error': 408
                }
            },
            'progress': {
                'status': 'running',
                'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
                'include_percentage': True
            },
            'streaming': {
                'status': 'streaming',
                'timestamp_format': '%Y-%m-%dT%H:%M:%SZ'
            }
        }
        self.sim_file = 'test_simulation.py'
        self.bridge_meta = 'test_bridge_v1.0'
        self.request_id = 'req_123456'

    @patch('src.utils.create_response.datetime')
    def test_create_success_response_batch(self, mock_datetime):
        """Test creating a success response for batch simulation."""
        mock_datetime.now.return_value.strftime.return_value = '2023-01-01T12:00:00Z'
        outputs = {'result': 'success', 'value': 42}
        metadata = {'duration': 1.5, 'iterations': 100}
        response = create_response(
            template_type='success',
            sim_file=self.sim_file,
            sim_type='batch',
            response_templates=self.sample_templates,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id,
            outputs=outputs,
            metadata=metadata
        )
        expected = {
            'simulation': {
                'name': self.sim_file,
                'type': 'batch',
                'outputs': outputs
            },
            'status': 'completed',
            'bridge_meta': self.bridge_meta,
            'request_id': self.request_id,
            'timestamp': '2023-01-01T12:00:00Z',
            'metadata': metadata
        }
        self.assertEqual(response, expected)

    @patch('src.utils.create_response.datetime')
    def test_create_success_response_streaming(self, mock_datetime):
        """Test creating a success response for streaming simulation."""
        mock_datetime.now.return_value.strftime.return_value = '2023-01-01T12:00:00Z'
        data = {'stream_data': [1, 2, 3, 4, 5]}
        response = create_response(
            template_type='success',
            sim_file=self.sim_file,
            sim_type='streaming',
            response_templates=self.sample_templates,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id,
            data=data
        )
        expected = {
            'simulation': {
                'name': self.sim_file,
                'type': 'streaming',
                'outputs': data
            },
            'status': 'completed',
            'bridge_meta': self.bridge_meta,
            'request_id': self.request_id,
            'timestamp': '2023-01-01T12:00:00Z'
        }
        self.assertEqual(response, expected)

    @patch('src.utils.create_response.datetime')
    def test_create_error_response_with_full_details(self, mock_datetime):
        """Test creating an error response with all details."""
        mock_datetime.now.return_value.strftime.return_value = '2023-01-01T12:00:00Z'
        error_info = {
            'message': 'Validation failed',
            'type': 'validation_error',
            'details': {'field': 'input_param', 'reason': 'invalid_format'},
            'traceback': 'Traceback (most recent call last):\n  File...'
        }
        response = create_response(
            template_type='error',
            sim_file=self.sim_file,
            sim_type='batch',
            response_templates=self.sample_templates,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id,
            error=error_info
        )
        expected = {
            'simulation': {
                'name': self.sim_file,
                'type': 'batch'
            },
            'status': 'failed',
            'bridge_meta': self.bridge_meta,
            'request_id': self.request_id,
            'timestamp': '2023-01-01T12:00:00Z',
            'error': {
                'message': 'Validation failed',
                'code': 400,
                'type': 'validation_error',
                'details': {'field': 'input_param', 'reason': 'invalid_format'},
                'traceback': 'Traceback (most recent call last):\n  File...'
            }
        }
        self.assertEqual(response, expected)

    @patch('src.utils.create_response.datetime')
    def test_create_error_response_minimal(self, mock_datetime):
        """Test creating an error response with minimal information."""
        mock_datetime.now.return_value.strftime.return_value = '2023-01-01T12:00:00Z'
        response = create_response(
            template_type='error',
            sim_file=self.sim_file,
            sim_type='streaming',
            response_templates=self.sample_templates,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id,
            error={}
        )
        expected = {
            'simulation': {
                'name': self.sim_file,
                'type': 'streaming'
            },
            'status': 'failed',
            'bridge_meta': self.bridge_meta,
            'request_id': self.request_id,
            'timestamp': '2023-01-01T12:00:00Z',
            'error': {
                'message': 'Unknown error',
                'code': 500
            }
        }
        self.assertEqual(response, expected)

    @patch('src.utils.create_response.datetime')
    def test_create_progress_response_with_percentage(self, mock_datetime):
        """Test creating a progress response with percentage."""
        mock_datetime.now.return_value.strftime.return_value = '2023-01-01T12:00:00Z'
        response = create_response(
            template_type='progress',
            sim_file=self.sim_file,
            sim_type='batch',
            response_templates=self.sample_templates,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id,
            percentage=75,
            message='Processing data...',
            sequence=10
        )
        expected = {
            'simulation': {
                'name': self.sim_file,
                'type': 'batch'
            },
            'status': 'running',
            'bridge_meta': self.bridge_meta,
            'request_id': self.request_id,
            'timestamp': '2023-01-01T12:00:00Z',
            'sequence': 10,
            'progress': {
                'percentage': 75,
                'message': 'Processing data...'
            }
        }
        self.assertEqual(response, expected)

    @patch('src.utils.create_response.datetime')
    def test_create_progress_response_with_streaming_data(self, mock_datetime):
        """Test creating a progress response with streaming data."""
        mock_datetime.now.return_value.strftime.return_value = '2023-01-01T12:00:00Z'
        streaming_data = {'partial_results': [1, 2, 3]}
        response = create_response(
            template_type='progress',
            sim_file=self.sim_file,
            sim_type='streaming',
            response_templates=self.sample_templates,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id,
            data=streaming_data,
            message='Streaming in progress...'
        )
        expected = {
            'simulation': {
                'name': self.sim_file,
                'type': 'streaming'
            },
            'status': 'running',
            'bridge_meta': self.bridge_meta,
            'request_id': self.request_id,
            'timestamp': '2023-01-01T12:00:00Z',
            'progress': {
                'message': 'Streaming in progress...'
            },
            'data': streaming_data
        }
        self.assertEqual(response, expected)

    @patch('src.utils.create_response.datetime')
    def test_create_streaming_response(self, mock_datetime):
        """Test creating a streaming response."""
        mock_datetime.now.return_value.strftime.return_value = '2023-01-01T12:00:00Z'
        streaming_data = {'chunk': 'data_chunk_1', 'index': 0}
        response = create_response(
            template_type='streaming',
            sim_file=self.sim_file,
            sim_type='streaming',
            response_templates=self.sample_templates,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id,
            data=streaming_data,
            sequence=1
        )
        expected = {
            'simulation': {
                'name': self.sim_file,
                'type': 'streaming'
            },
            'status': 'streaming',
            'bridge_meta': self.bridge_meta,
            'request_id': self.request_id,
            'timestamp': '2023-01-01T12:00:00Z',
            'sequence': 1,
            'data': streaming_data
        }
        self.assertEqual(response, expected)

    @patch('src.utils.create_response.datetime')
    def test_create_response_unknown_template(self, mock_datetime):
        """Test creating a response with unknown template type."""
        mock_datetime.now.return_value.strftime.return_value = '2023-01-01T12:00:00Z'
        response = create_response(
            template_type='unknown',
            sim_file=self.sim_file,
            sim_type='batch',
            response_templates=self.sample_templates,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id
        )
        expected = {
            'simulation': {
                'name': self.sim_file,
                'type': 'batch'
            },
            'status': 'unknown',
            'bridge_meta': self.bridge_meta,
            'request_id': self.request_id,
            'timestamp': '2023-01-01T12:00:00Z'
        }
        self.assertEqual(response, expected)

    @patch('src.utils.create_response.datetime')
    def test_create_response_custom_timestamp_format(self, mock_datetime):
        """Test creating a response with custom timestamp format."""
        mock_datetime.now.return_value.strftime.return_value = '01/01/2023 12:00:00'
        custom_templates = {
            'success': {
                'timestamp_format': '%d/%m/%Y %H:%M:%S'
            }
        }
        response = create_response(
            template_type='success',
            sim_file=self.sim_file,
            sim_type='batch',
            response_templates=custom_templates,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id
        )
        self.assertEqual(response['timestamp'], '01/01/2023 12:00:00')

    @patch('src.utils.create_response.datetime')
    def test_create_response_additional_kwargs(self, mock_datetime):
        """Test creating a response with additional kwargs."""
        mock_datetime.now.return_value.strftime.return_value = '2023-01-01T12:00:00Z'
        response = create_response(
            template_type='success',
            sim_file=self.sim_file,
            sim_type='batch',
            response_templates=self.sample_templates,
            bridge_meta=self.bridge_meta,
            request_id=self.request_id,
            custom_field='custom_value',
            another_field=42
        )
        self.assertEqual(response['custom_field'], 'custom_value')
        self.assertEqual(response['another_field'], 42)

    def test_handle_success_response_batch(self):
        """Test _handle_success_response for batch type."""
        response: Dict[str, Any] = {'simulation': {}}
        kwargs = {'outputs': {'result': 'test'}}
        _handle_success_response(response, 'batch', kwargs)
        self.assertEqual(response['simulation']['outputs'], {'result': 'test'})

    def test_handle_success_response_streaming(self):
        """Test _handle_success_response for streaming type."""
        response: Dict[str, Any] = {'simulation': {}}
        kwargs = {'data': {'stream': 'test_data'}}
        _handle_success_response(response, 'streaming', kwargs)
        self.assertEqual(
            response['simulation']['outputs'], {
                'stream': 'test_data'})

    def test_handle_success_response_no_data(self):
        """Test _handle_success_response with no outputs/data."""
        response: Dict[str, Any] = {'simulation': {}}
        kwargs: Dict[str, Any] = {}
        _handle_success_response(response, 'batch', kwargs)
        self.assertEqual(response['simulation']['outputs'], {})

    def test_handle_error_response_full(self):
        """Test _handle_error_response with full error information."""
        response: Dict[str, Any] = {}
        template = {
            'include_stacktrace': True,
            'error_codes': {'validation_error': 400}
        }
        kwargs = {
            'error': {
                'message': 'Test error',
                'type': 'validation_error',
                'details': {'field': 'test'},
                'traceback': 'Test traceback'
            }
        }
        _handle_error_response(response, template, kwargs)
        expected_error = {
            'message': 'Test error',
            'code': 400,
            'type': 'validation_error',
            'details': {'field': 'test'},
            'traceback': 'Test traceback'
        }
        self.assertEqual(response['error'], expected_error)

    def test_handle_error_response_minimal(self):
        """Test _handle_error_response with minimal information."""
        response: Dict[str, Any] = {}
        template: Dict[str, Any] = {}
        kwargs: Dict[str, Any] = {'error': {}}
        _handle_error_response(response, template, kwargs)
        expected_error = {
            'message': 'Unknown error',
            'code': 500
        }
        self.assertEqual(response['error'], expected_error)

    def test_handle_progress_response_with_percentage(self):
        """Test _handle_progress_response with percentage."""
        response: Dict[str, Any] = {}
        template = {'include_percentage': True}
        kwargs = {'percentage': 50, 'message': 'Test message'}
        _handle_progress_response(response, template, kwargs)
        expected_progress = {
            'percentage': 50,
            'message': 'Test message'
        }
        self.assertEqual(response['progress'], expected_progress)

    def test_handle_progress_response_with_data(self):
        """Test _handle_progress_response with streaming data."""
        response: Dict[str, Any] = {}
        template: Dict[str, Any] = {}
        kwargs = {'data': {'test': 'data'}, 'message': 'Test'}
        _handle_progress_response(response, template, kwargs)
        self.assertEqual(response['progress']['message'], 'Test')
        self.assertEqual(response['data'], {'test': 'data'})

    def test_handle_streaming_response(self):
        """Test _handle_streaming_response."""
        response: Dict[str, Any] = {}
        kwargs = {'data': {'stream': 'test_stream'}}
        _handle_streaming_response(response, kwargs)
        self.assertEqual(response['data'], {'stream': 'test_stream'})

    def test_handle_streaming_response_no_data(self):
        """Test _handle_streaming_response without data."""
        response: Dict[str, Any] = {}
        kwargs: Dict[str, Any] = {}
        _handle_streaming_response(response, kwargs)
        self.assertNotIn('data', response)


if __name__ == '__main__':
    unittest.main()
