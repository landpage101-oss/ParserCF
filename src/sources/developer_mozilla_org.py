from __future__ import annotations

from collections.abc import Iterable

_BASE = "https://developer.mozilla.org/en-US/docs/"

_SEEDS = [
    _BASE + "Web/CSS/Reference/Properties/z-index",
    _BASE + "Web/CSS/Reference/Properties/flex-wrap",
    _BASE + "Web/CSS/Reference/Properties/justify-content",
    _BASE + "Web/JavaScript/Reference/Global_Objects/String/replace",
    _BASE + "Web/JavaScript/Reference/Global_Objects/ReferenceError",
    _BASE + "Web/API/EventSource",
    _BASE + "Web/API/View_Transition_API",
    _BASE + "Web/HTTP/Methods/GET",
]


class DeveloperMozillaOrgAdapter:
    page_type = "docs"
    domain = "developer.mozilla.org"
    name = "developer_mozilla_org"

    def list_urls(self, since: str | None = None) -> Iterable[str]:  # noqa: ARG002
        return list(_SEEDS)

    def parse_id(self, url: str) -> str:
        # Strip base prefix and anchor fragment (e.g. autocomplete#values → autocomplete)
        return url.split("#", maxsplit=1)[0].removeprefix(_BASE)
