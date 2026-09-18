from abc import ABC, abstractmethod

from src.schemas.property import PropertySchema


class BasePropertyParser(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def parse(self, profile_username: str) -> list[PropertySchema]:
        raise NotImplementedError
