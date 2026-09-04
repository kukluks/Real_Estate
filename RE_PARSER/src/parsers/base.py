from abc import ABC, abstractmethod

from src.schemas.property import PropertySchema


class BasePropertyParser(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def parse(self) -> list[PropertySchema]:
        raise NotImplementedError
