"""Unit tests for create_response module."""

import pytest
from unittest.mock import MagicMock, patch

from src.utils.create_response import create_response


@pytest.fixture
def base_response_templates():
    """Fixture providing standard response templates for testing."""
    return {
        'success': {
            'status': 'success',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
            'include_metadata': False
        },
        'error': {
            'status': 'error',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
            'error_codes': {
                'validation_error': 400,
                'execution_error': 500
            },
            'include_stacktrace': False
        },
        'progress': {
            'status': 'in_progress',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ',
            'include_percentage': True
        },
        'streaming': {
            'status': 'streaming',
            'timestamp_format': '%Y-%m-%dT%H:%M:%SZ'
        }
    }


@pytest.fixture
def response_templates_with_metadata(base_response_templates):
    """Fixture providing response templates with metadata enabled."""
    templates = base_response_templates.copy()
    templates['success']['include_metadata'] = True
    return templates


@pytest.fixture
def response_templates_with_stacktrace(base_response_templates):
    """Fixture providing response templates with stacktrace enabled."""
    templates = base_response_templates.copy()
    templates['error']['include_stacktrace'] = True
    return templates


@pytest.fixture
def fixed_datetime():
    """Fixture that patches datetime.now() to return a fixed value."""
    with patch('src.utils.create_response.datetime') as mock_datetime:
        mock_now = MagicMock()
        mock_now.strftime.return_value = '2023-01-01T12:00:00Z'
        mock_datetime.now.return_value = mock_now
        yield mock_datetime


class TestSuccessResponses:
    """Test suite for success response creation."""

    def test_create_response_success_batch(self, base_response_templates):
        """
        Test creating a success response for batch simulation.

        Args:
            base_response_templates: The base response templates fixture
        """
        outputs = {'result': 42, 'status': 'done'}

        result = create_response(
            template_type='success',
            sim_file='test_sim.mat',
            sim_type='batch',
            response_templates=base_response_templates,
            bridge_meta='test_bridge',
            outputs=outputs
        )

        assert result['status'] == 'completed'
        assert result['simulation']['name'] == 'test_sim.mat'
        assert result['simulation']['type'] == 'batch'
        assert result['simulation']['outputs'] == outputs
        assert result['bridge_meta'] == 'test_bridge'
        assert 'timestamp' in result

    def test_create_response_success_streaming(self, base_response_templates):
        """
        Test creating a success response for streaming simulation.

        Args:
            base_response_templates: The base response templates fixture
        """
        data = {'result': 42, 'status': 'done'}

        result = create_response(
            template_type='success',
            sim_file='test_sim.mat',
            sim_type='streaming',
            response_templates=base_response_templates,
            bridge_meta='test_bridge',
            data=data
        )

        assert result['status'] == 'completed'
        assert result['simulation']['name'] == 'test_sim.mat'
        assert result['simulation']['type'] == 'streaming'
        assert result['simulation']['outputs'] == data
        assert result['bridge_meta'] == 'test_bridge'
        assert 'timestamp' in result

    def test_create_response_with_metadata(
            self, response_templates_with_metadata):
        """
        Test creating a success response with metadata.

        Args:
            response_templates_with_metadata: The response templates with metadata fixture
        """
        metadata = {
            'execution_time': 1.23,
            'memory_usage': '128MB',
            'matlab_version': 'R2023a'
        }

        result = create_response(
            template_type='success',
            sim_file='test_sim.mat',
            sim_type='batch',
            response_templates=response_templates_with_metadata,
            bridge_meta='test_bridge',
            outputs={'result': 42},
            metadata=metadata
        )

        assert result['status'] == 'completed'
        assert result['metadata'] == metadata
        assert result['bridge_meta'] == 'test_bridge'


class TestErrorResponses:
    """Test suite for error response creation."""

    def test_create_response_error_basic(self, base_response_templates):
        """
        Test creating a basic error response.

        Args:
            base_response_templates: The base response templates fixture
        """
        error_info = {
            'message': 'Something went wrong',
            'type': 'execution_error'
        }

        result = create_response(
            template_type='error',
            sim_file='test_sim.mat',
            sim_type='batch',
            response_templates=base_response_templates,
            bridge_meta='test_bridge',
            error=error_info
        )

        assert result['status'] == 'error'
        assert result['simulation']['name'] == 'test_sim.mat'
        assert result['simulation']['type'] == 'batch'
        assert result['error']['message'] == 'Something went wrong'
        assert result['error']['code'] == 500
        assert result['error']['type'] == 'execution_error'
        assert result['bridge_meta'] == 'test_bridge'
        assert 'traceback' not in result['error']

    def test_create_response_error_with_stacktrace(
            self, response_templates_with_stacktrace):
        """
        Test creating an error response with stacktrace.

        Args:
            response_templates_with_stacktrace: The response templates with stacktrace fixture
        """
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
            response_templates=response_templates_with_stacktrace,
            bridge_meta='test_bridge',
            error=error_info
        )

        assert result['status'] == 'error'
        assert result['error']['message'] == 'Something went wrong'
        assert result['error']['code'] == 400
        assert result['error']['traceback'] == traceback
        assert result['bridge_meta'] == 'test_bridge'


class TestProgressResponses:
    """Test suite for progress response creation."""

    def test_create_response_progress_with_percentage(
            self, base_response_templates):
        """
        Test creating a progress response with percentage.

        Args:
            base_response_templates: The base response templates fixture
        """
        result = create_response(
            template_type='progress',
            sim_file='test_sim.mat',
            sim_type='batch',
            response_templates=base_response_templates,
            bridge_meta='test_bridge',
            percentage=75,
            message='Processing data'
        )

        assert result['status'] == 'in_progress'
        assert result['simulation']['name'] == 'test_sim.mat'
        assert result['simulation']['type'] == 'batch'
        assert result['progress']['percentage'] == 75
        assert result['progress']['message'] == 'Processing data'
        assert result['bridge_meta'] == 'test_bridge'

    def test_create_response_progress_without_percentage(
            self, base_response_templates):
        """
        Test creating a progress response without percentage.

        Args:
            base_response_templates: The base response templates fixture
        """
        # Modify template to disable percentage inclusion
        templates = base_response_templates.copy()
        templates['progress']['include_percentage'] = False

        result = create_response(
            template_type='progress',
            sim_file='test_sim.mat',
            sim_type='batch',
            response_templates=templates,
            bridge_meta='test_bridge',
            percentage=75,  # This should be ignored
            message='Processing data'
        )

        assert result['status'] == 'in_progress'
        assert result['simulation']['name'] == 'test_sim.mat'
        assert result['simulation']['type'] == 'batch'
        assert 'percentage' not in result.get('progress', {})
        assert result['progress']['message'] == 'Processing data'
        assert result['bridge_meta'] == 'test_bridge'

    def test_create_response_progress_with_data(self, base_response_templates):
        """
        Test creating a progress response with streaming data.

        Args:
            base_response_templates: The base response templates fixture
        """
        stream_data = {'partial_result': 21}

        result = create_response(
            template_type='progress',
            sim_file='test_sim.mat',
            sim_type='streaming',
            response_templates=base_response_templates,
            bridge_meta='test_bridge',
            percentage=50,
            message='Halfway there',
            data=stream_data
        )

        assert result['status'] == 'in_progress'
        assert result['progress']['percentage'] == 50
        assert result['progress']['message'] == 'Halfway there'
        assert result['data'] == stream_data
        assert result['bridge_meta'] == 'test_bridge'


class TestStreamingResponses:
    """Test suite for streaming response creation."""

    def test_create_response_streaming(self, base_response_templates):
        """
        Test creating a streaming response.

        Args:
            base_response_templates: The base response templates fixture
        """
        stream_data = {'partial_result': 21}

        result = create_response(
            template_type='streaming',
            sim_file='test_sim.mat',
            sim_type='streaming',
            response_templates=base_response_templates,
            bridge_meta='test_bridge',
            data=stream_data,
            sequence=3
        )

        assert result['status'] == 'streaming'
        assert result['simulation']['name'] == 'test_sim.mat'
        assert result['simulation']['type'] == 'streaming'
        assert result['data'] == stream_data
        assert result['sequence'] == 3
        assert result['bridge_meta'] == 'test_bridge'


class TestMiscellaneousFeatures:
    """Test suite for miscellaneous response creation features."""

    def test_create_response_timestamp_format(
            self, fixed_datetime, base_response_templates):
        """
        Test timestamp formatting in responses.

        Args:
            fixed_datetime: The fixed datetime fixture
            base_response_templates: The base response templates fixture
        """
        result = create_response(
            template_type='success',
            sim_file='test_sim.mat',
            sim_type='batch',
            response_templates=base_response_templates,
            bridge_meta='test_bridge',
            outputs={}
        )

        assert result['timestamp'] == '2023-01-01T12:00:00Z'
        assert result['bridge_meta'] == 'test_bridge'
        fixed_datetime.now.return_value.strftime.assert_called_once_with(
            '%Y-%m-%dT%H:%M:%SZ')

    def test_create_response_nonexistent_template(
            self, base_response_templates):
        """
        Test creating a response with a non-existent template type.

        Args:
            base_response_templates: The base response templates fixture
        """
        result = create_response(
            template_type='nonexistent',
            sim_file='test_sim.mat',
            sim_type='batch',
            response_templates=base_response_templates,
            bridge_meta='test_bridge'
        )

        assert result['status'] == 'nonexistent'
        assert result['simulation']['name'] == 'test_sim.mat'
        assert result['simulation']['type'] == 'batch'
        assert result['bridge_meta'] == 'test_bridge'
        assert 'timestamp' in result

    def test_create_response_additional_kwargs(self, base_response_templates):
        """
        Test that additional keyword arguments are included in the response.

        Args:
            base_response_templates: The base response templates fixture
        """
        result = create_response(
            template_type='success',
            sim_file='test_sim.mat',
            sim_type='batch',
            response_templates=base_response_templates,
            bridge_meta='test_bridge',
            outputs={},
            custom_field='custom_value',
            another_field=123
        )

        assert result['status'] == 'completed'
        assert result['custom_field'] == 'custom_value'
        assert result['another_field'] == 123
        assert result['bridge_meta'] == 'test_bridge'
