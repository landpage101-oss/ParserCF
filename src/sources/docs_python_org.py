from collections.abc import Iterable

_BASE = "https://docs.python.org/3/"

_SEEDS = [
    _BASE + "library/json.html",
    _BASE + "library/typing.html",
    _BASE + "library/asyncio.html",
    _BASE + "library/sqlite3.html",
    _BASE + "library/re.html",
    _BASE + "library/pathlib.html",
    _BASE + "library/dataclasses.html",
]


class DocsPythonOrgAdapter:
    domain = "docs.python.org"
    name = "docs_python_org"

    def list_urls(self, since: str | None = None) -> Iterable[str]:  # noqa: ARG002
        return list(_SEEDS)

    def parse_id(self, url: str) -> str:
        return url.removeprefix(_BASE).removesuffix(".html")
