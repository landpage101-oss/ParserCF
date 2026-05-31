from collections.abc import Iterable

_BASE = "https://docs.python.org/3/"

_SEEDS = [
    # --- already canonical ---
    _BASE + "library/json.html",
    _BASE + "library/typing.html",
    _BASE + "library/asyncio.html",
    _BASE + "library/sqlite3.html",
    _BASE + "library/re.html",
    _BASE + "library/pathlib.html",
    _BASE + "library/dataclasses.html",
    # --- concurrency ---
    _BASE + "library/threading.html",
    _BASE + "library/multiprocessing.html",
    _BASE + "library/concurrent.futures.html",
    _BASE + "library/queue.html",
    # --- data structures & functional ---
    _BASE + "library/collections.html",
    _BASE + "library/itertools.html",
    _BASE + "library/functools.html",
    _BASE + "library/heapq.html",
    # --- file & os ---
    _BASE + "library/os.html",
    _BASE + "library/shutil.html",
    _BASE + "library/io.html",
    _BASE + "library/contextlib.html",
    # --- serialization & config ---
    _BASE + "library/csv.html",
    _BASE + "library/pickle.html",
    _BASE + "library/configparser.html",
    # --- date/time & numeric ---
    _BASE + "library/datetime.html",
    _BASE + "library/decimal.html",
    _BASE + "library/statistics.html",
    # --- introspection & testing ---
    _BASE + "library/inspect.html",
    _BASE + "library/unittest.html",
]


class DocsPythonOrgAdapter:
    page_type = "docs"
    domain = "docs.python.org"
    name = "docs_python_org"

    def list_urls(self, since: str | None = None) -> Iterable[str]:  # noqa: ARG002
        return list(_SEEDS)

    def parse_id(self, url: str) -> str:
        return url.removeprefix(_BASE).removesuffix(".html")
