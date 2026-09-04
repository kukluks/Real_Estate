from src.parsers.base import BasePropertyParser
from src.parsers.example import ExamplePropertyParser
from src.parsers.lalafo import LalafoPropertyParser
from src.schemas.property import PropertySource


def get_parser(source: PropertySource) -> BasePropertyParser:
    parsers: dict[PropertySource, type[BasePropertyParser]] = {
        PropertySource.EXAMPLE: ExamplePropertyParser,
        PropertySource.LALAFO: LalafoPropertyParser,
    }

    parser_class = parsers.get(source)
    if parser_class is None:
        raise ValueError(f"Parser for source '{source}' is not registered.")

    return parser_class()
