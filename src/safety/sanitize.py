# src/safety/sanitize.py
import re
import unicodedata

from bs4 import BeautifulSoup

# Codepoint-ranges for zero-width / bidi-control / line-separator chars.
# Attackers embed these to mask prompt-injection payloads in scraped content.
#
# IMPORTANT: \\u-escape sequences only — never write as literals. IDEs with
# auto-fix for "unusual line terminators" silently remove U+2028/U+2029,
# which breaks the detector in exactly the attack case it was written for.
INVISIBLE = re.compile(
    "["
    "\\u200b-\\u200f"  # ZW space, ZWNJ, ZWJ, LRM, RLM
    "\\u2028\\u2029"  # LINE SEPARATOR, PARAGRAPH SEPARATOR
    "\\u202a-\\u202e"  # bidi overrides (LRE, RLE, PDF, LRO, RLO)
    "\\u2060-\\u206f"  # word joiner, invisible operators, deprecated formatters
    "\\ufeff"  # BOM / zero-width no-break space
    "]"
)

# ROLE_PREFIXES relies on MULTILINE so ^ matches start-of-line, not just
# start-of-string.  The html->md converter must preserve <p> as \\n\\n-separated
# paragraphs (standard markdownify behaviour) for this to fire correctly.
ROLE_PREFIXES = re.compile(
    r"^\s*(system|assistant|user|developer)\s*:",
    re.IGNORECASE | re.MULTILINE,
)

INJECTION_HINTS = re.compile(
    r"(ignore (all |previous )?instructions|"
    r"disregard (the )?(above|prior)|"
    r"you are now|new instructions:)",
    re.IGNORECASE,
)

# Inline CSS patterns that visually hide content — a common injection vector.
_HIDE_STYLE_RE = re.compile(
    r"(color\s*:\s*(white|transparent))"
    r"|(display\s*:\s*none)"
    r"|(visibility\s*:\s*hidden)"
    r"|(opacity\s*:\s*0\b)",
    re.IGNORECASE,
)


def _scan_and_strip_hidden_html(html: str) -> tuple[str, list[str]]:
    """Remove style-visually-hidden elements; return (cleaned_html, warnings)."""
    warnings: list[str] = []
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(style=_HIDE_STYLE_RE):
        hidden_text = tag.get_text()
        if ROLE_PREFIXES.search(hidden_text) and "role_prefix_neutralized" not in warnings:
            warnings.append("role_prefix_neutralized")
        if INJECTION_HINTS.search(hidden_text) and "injection_hint_detected" not in warnings:
            warnings.append("injection_hint_detected")
        tag.decompose()
    return str(soup), warnings


def sanitize(text: str) -> tuple[str, list[str]]:
    """Return (clean_text, warnings)."""
    warnings: list[str] = []
    cleaned = unicodedata.normalize("NFKC", text)
    # Strip visually-hidden HTML elements before text processing so their
    # injection payloads do not reach the extraction layer.
    if cleaned.lstrip().startswith("<"):
        cleaned, hidden_warnings = _scan_and_strip_hidden_html(cleaned)
        warnings.extend(hidden_warnings)
    if INVISIBLE.search(cleaned):
        warnings.append("invisible_characters_stripped")
        cleaned = INVISIBLE.sub("", cleaned)
    if ROLE_PREFIXES.search(cleaned):
        if "role_prefix_neutralized" not in warnings:
            warnings.append("role_prefix_neutralized")
        cleaned = ROLE_PREFIXES.sub("[neutralized-role-prefix]:", cleaned)
    if INJECTION_HINTS.search(cleaned) and "injection_hint_detected" not in warnings:
        warnings.append("injection_hint_detected")
    return cleaned, warnings
