# json_transformer.py
import json
from typing import Any
from .base_transformer import BaseTransformer


class JsonToInternalTransformer(BaseTransformer):
    @property
    def supported_formats(self):
        return ['json']

    def transform(self, data: Any, target_format: str) -> Any:
        if target_format != 'internal':
            raise ValueError("Only 'internal' target format is supported.")
        return json.loads(data) if isinstance(data, str) else data


class InternalToJsonTransformer(BaseTransformer):
    @property
    def supported_formats(self):
        return ['internal']

    def transform(self, data: Any, target_format: str) -> Any:
        if target_format != 'json':
            raise ValueError("Only 'json' target format is supported.")
        return json.dumps(data) if isinstance(data, dict) else data
