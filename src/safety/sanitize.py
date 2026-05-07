# src/safety/sanitize.py
import re
import unicodedata

# Codepoint-диапазоны zero-width / bidi-control / line-separator символов,
# которые атакующие часто используют для маскировки prompt-injection payload'ов
# в скрапленном контенте.
#
# ВАЖНО: всегда записываем через \u-escape sequences, никогда литералами —
# иначе VS Code и большинство IDE предложат «Remove unusual line terminators»,
# что молча вырежет U+2028/U+2029 из исходника и сломает детектор. Каждый
# диапазон обязан иметь инлайн-комментарий — это требование code review.
INVISIBLE = re.compile(
    "["
    "\u200b-\u200f"  # ZW space, ZWNJ, ZWJ, LRM, RLM
    "\u2028\u2029"  # LINE SEPARATOR, PARAGRAPH SEPARATOR
    "\u202a-\u202e"  # bidi overrides (LRE, RLE, PDF, LRO, RLO)
    "\u2060-\u206f"  # word joiner, invisible operators, deprecated formatters
    "\ufeff"  # BOM / zero-width no-break space
    "]"
)

# Префиксы, которыми атакующие пытаются переключить роль
ROLE_PREFIXES = re.compile(
    r"^\s*(system|assistant|user|developer)\s*:",
    re.IGNORECASE | re.MULTILINE,
)

# Классические injection-маркеры
INJECTION_HINTS = re.compile(
    r"(ignore (all |previous )?instructions|"
    r"disregard (the )?(above|prior)|"
    r"you are now|new instructions:)",
    re.IGNORECASE,
)


def sanitize(text: str) -> tuple[str, list[str]]:
    """Возвращает (clean_text, warnings)."""
    warnings: list[str] = []
    cleaned = unicodedata.normalize("NFKC", text)
    if INVISIBLE.search(cleaned):
        warnings.append("invisible_characters_stripped")
        cleaned = INVISIBLE.sub("", cleaned)
    if ROLE_PREFIXES.search(cleaned):
        warnings.append("role_prefix_neutralized")
        cleaned = ROLE_PREFIXES.sub("[neutralized-role-prefix]:", cleaned)
    if INJECTION_HINTS.search(cleaned):
        warnings.append("injection_hint_detected")
    return cleaned, warnings
