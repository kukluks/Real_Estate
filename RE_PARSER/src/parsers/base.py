from abc import ABC, abstractmethod

from src.schemas.raw_post import RawPostAddSchema


class BasePropertyParser(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def parse(self, profile_username: str) -> list[RawPostAddSchema]:
        raise NotImplementedError
