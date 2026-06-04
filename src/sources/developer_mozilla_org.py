from __future__ import annotations

from collections.abc import Iterable

_BASE = "https://developer.mozilla.org/en-US/docs/"

_SEEDS = [
    # CSS Properties
    _BASE + "Web/CSS/z-index",
    _BASE + "Web/CSS/flex-wrap",
    _BASE + "Web/CSS/justify-content",
    _BASE + "Web/CSS/display",
    _BASE + "Web/CSS/position",
    _BASE + "Web/CSS/grid-template-columns",
    _BASE + "Web/CSS/flex",
    _BASE + "Web/CSS/transform",
    _BASE + "Web/CSS/transition",
    _BASE + "Web/CSS/gap",
    # JavaScript Built-in Objects
    _BASE + "Web/JavaScript/Reference/Global_Objects/String/replace",
    _BASE + "Web/JavaScript/Reference/Global_Objects/ReferenceError",
    _BASE + "Web/JavaScript/Reference/Global_Objects/Array/map",
    _BASE + "Web/JavaScript/Reference/Global_Objects/Array/reduce",
    _BASE + "Web/JavaScript/Reference/Global_Objects/Promise",
    _BASE + "Web/JavaScript/Reference/Global_Objects/Promise/all",
    _BASE + "Web/JavaScript/Reference/Global_Objects/Object/keys",
    _BASE + "Web/JavaScript/Reference/Global_Objects/JSON/parse",
    _BASE + "Web/JavaScript/Reference/Global_Objects/Map",
    _BASE + "Web/JavaScript/Reference/Global_Objects/Set",
    # Web API
    _BASE + "Web/API/EventSource",
    _BASE + "Web/API/View_Transition_API",
    _BASE + "Web/API/Fetch_API/Using_Fetch",
    _BASE + "Web/API/WebSocket",
    _BASE + "Web/API/IntersectionObserver",
    _BASE + "Web/API/History_API",
    _BASE + "Web/API/Web_Storage_API",
    # HTTP
    _BASE + "Web/HTTP/Methods/GET",
    _BASE + "Web/HTTP/Methods/POST",
    _BASE + "Web/HTTP/Methods/PUT",
    _BASE + "Web/HTTP/Status/200",
    _BASE + "Web/HTTP/Status/404",
    _BASE + "Web/HTTP/CORS",
    _BASE + "Web/HTTP/Headers/Cache-Control",
]


class DeveloperMozillaOrgAdapter:
    page_type = "docs"
    domain = "developer.mozilla.org"
    name = "developer_mozilla_org"

    def list_urls(self, since: str | None = None) -> Iterable[str]:  # noqa: ARG002
        return list(_SEEDS)

    def parse_id(self, url: str) -> str:
        # Strip base prefix and anchor fragment (e.g. autocomplete#values -> autocomplete)
        return url.split("#", maxsplit=1)[0].removeprefix(_BASE)
