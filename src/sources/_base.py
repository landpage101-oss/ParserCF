from collections.abc import Iterable
from typing import Protocol


class SourceAdapter(Protocol):
    page_type: str
    domain: str
    name: str

    def list_urls(self, since: str | None = None) -> Iterable[str]: ...

    def parse_id(self, url: str) -> str: ...
