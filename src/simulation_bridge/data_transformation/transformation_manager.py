from typing import Dict, Any
from .base_transformer import BaseTransformer
from ..utils.logger import get_logger
from ..utils.exceptions import DataTransformationError

logger = get_logger(__name__)

class DataTransformationManager:
    def __init__(self):
        self.transformers: Dict[str, BaseTransformer] = {}

    def register_transformer(self, transformer: BaseTransformer):
        for fmt in transformer.supported_formats:
            self.transformers[fmt] = transformer
        logger.info(f"Registered transformer for formats: {transformer.supported_formats}")

    def transform(
        self,
        data: Any,
        source_format: str,
        target_format: str
    ) -> Any:
        try:
            if source_format == target_format:
                return data

            transformer = self.transformers.get(source_format)
            if not transformer:
                raise DataTransformationError(f"No transformer for format: {source_format}", target_format)


            return transformer.transform(data, target_format)
        except Exception as e:
            logger.error(f"Transformation failed: {source_format}->{target_format}")
            raise DataTransformationError(str(e), target_format) from e
