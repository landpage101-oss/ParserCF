"""Shared validator helpers for schema modules.

Centralises placeholder/error detection so all schemas (docs, article, reference,
product) share one source of truth.
"""

from __future__ import annotations

_HARD_PLACEHOLDER_MARKERS: frozenset[str] = frozenset({"lorem ipsum"})

_ERROR_STATE_MARKERS: frozenset[str] = frozenset(
    {
        "page not found",
        "access denied",
        "404 not found",
        "403 forbidden",
        "are you a robot",
    }
)

_ERROR_STATE_MAX_BODY_LEN: int = 500
"""Pages legitimately documenting error states are longer than this.

Real placeholder/anti-bot/error pages are typically <500 chars. Long content
mentioning these phrases (e.g. MDN docs for HTTP 404) is treated as legitimate.
"""


def detect_placeholder_marker(text: str) -> str | None:
    """Return the marker string if text looks like placeholder/error, else None.

    - Hard markers (lorem ipsum) reject at any length.
    - Soft markers (error/anti-bot indicators) reject only when text is short
      (< _ERROR_STATE_MAX_BODY_LEN), to avoid false positives on legitimate
      content documenting these topics.
    """
    low = text.lower()
    for marker in _HARD_PLACEHOLDER_MARKERS:
        if marker in low:
            return marker
    if len(text) < _ERROR_STATE_MAX_BODY_LEN:
        for marker in _ERROR_STATE_MARKERS:
            if marker in low:
                return marker
    return None
