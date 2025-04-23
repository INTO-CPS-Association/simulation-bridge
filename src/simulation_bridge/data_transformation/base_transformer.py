from abc import ABC, abstractmethod
from typing import Any

class BaseTransformer(ABC):
    @property
    @abstractmethod
    def supported_formats(self):
        """
        Restituisce una lista di formati supportati per la trasformazione.
        """
        pass

    @abstractmethod
    def transform(self, data: Any, target_format: str) -> Any:
        """
        Trasforma i dati nel formato target specificato.

        :param data: I dati da trasformare.
        :param target_format: Il formato verso cui trasformare i dati.
        :return: I dati trasformati nel formato richiesto.
        """
        pass
