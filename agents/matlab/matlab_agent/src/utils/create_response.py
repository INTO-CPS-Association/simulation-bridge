"""
create_response.py

This module provides a shared utility for creating standardized response objects
based on templates defined in configuration. It supports various response types
including success, error, progress, and streaming messages.

Used by both batch and streaming simulation processors to ensure consistent
response formatting across the simulation service.
"""

from typing import Dict, Any, Optional, Union
from datetime import datetime


def create_response(
    template_type: str, 
    sim_file: str, 
    sim_type: str,
    response_templates: Dict[str, Any],
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Create a response based on the template defined in the configuration.
    
    Args:
        template_type: Type of template to use ('success', 'error', 'progress', 'streaming')
        sim_file: Name of the simulation file
        sim_type: Type of simulation ('batch' or 'streaming')
        response_templates: Dictionary containing response template configurations
        **kwargs: Additional fields to include in the response
        
    Returns:
        Formatted response dictionary
    """
    template: Dict[str, Any] = response_templates.get(template_type, {})
    
    # Create base response structure
    response: Dict[str, Any] = {
        'simulation': {
            'name': sim_file,
            'type': sim_type
        },
        'status': 'completed' if template_type == 'success' else template.get('status', template_type)
    }
    
    # Add timestamp according to configured format
    timestamp_format: str = template.get('timestamp_format', '%Y-%m-%dT%H:%M:%SZ')
    response['timestamp'] = datetime.now().strftime(timestamp_format)
    
    # Add sequence number if available (for streaming)
    if 'sequence' in kwargs:
        response['sequence'] = kwargs['sequence']
    
    # Add metadata if configured
    if template.get('include_metadata', False) and 'metadata' in kwargs:
        response['metadata'] = kwargs.get('metadata')
    
    # Handle specific template types
    if template_type == 'success':
        # For batch, this is 'outputs', for streaming this is 'data'
        if sim_type == 'batch':
            response['simulation']['outputs'] = kwargs.get('outputs', {})
        else:
            response['simulation']['outputs'] = kwargs.get('data', {})
    
    elif template_type == 'error':
        error_info: Dict[str, Any] = kwargs.get('error', {})
        response['error'] = {
            'message': error_info.get('message', 'Unknown error'),
            'code': template.get('error_codes', {}).get(
                error_info.get('type', 'execution_error'), 500)
        }
        
        # Add error type if available
        if 'type' in error_info:
            response['error']['type'] = error_info['type']
        
        # Add details if available
        if 'details' in error_info:
            response['error']['details'] = error_info['details']
            
        # Add stack trace if configured
        if template.get('include_stacktrace', False) and 'traceback' in error_info:
            response['error']['traceback'] = error_info['traceback']

    
    elif template_type == 'progress':
        if template.get('include_percentage', False) and 'percentage' in kwargs:
            response['progress'] = {
                'percentage': kwargs['percentage']
            }
            
        # Add message if available
        if 'message' in kwargs:
            if 'progress' not in response:
                response['progress'] = {}
            response['progress']['message'] = kwargs['message']
            
        # Add streaming data if available (for streaming mode)
        if 'data' in kwargs and kwargs['data']:
            response['data'] = kwargs['data']
    
    elif template_type == 'streaming':
        # Add streaming data
        if 'data' in kwargs:
            response['data'] = kwargs['data']
    
    # Add any additional keys passed in kwargs that aren't handled by specific cases
    for key, value in kwargs.items():
        if key not in ['outputs', 'data', 'error', 'metadata', 'percentage', 'sequence', 'message']:
            response[key] = value
            
    return response