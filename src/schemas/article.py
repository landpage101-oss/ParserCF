from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator

_HUMAN_DATE_FORMATS = ("%b %d, %Y", "%B %d, %Y")  # "Feb 17, 2026", "January 5, 2025"

_LANG_NAME_TO_ISO: dict[str, str] = {
    "english": "en",
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "italian": "it",
    "portuguese": "pt",
    "russian": "ru",
    "chinese": "zh",
    "japanese": "ja",
    "korean": "ko",
    "arabic": "ar",
    "dutch": "nl",
    "polish": "pl",
    "swedish": "sv",
    "turkish": "tr",
}


class Article(BaseModel):
    source: str = Field(min_length=1, max_length=64)
    source_url: HttpUrl
    source_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=500)
    author: str | None = Field(
        default=None,
        description="Real human author byline only; organisation-level attribution -> None",
    )
    published_at: datetime | None = None
    body_md: str = Field(min_length=10)
    language: str = Field(
        pattern=r"^[a-z]{2}$",
        description="ISO 639-1 two-letter lowercase code, e.g. 'en'",
    )

    @field_validator("language", mode="before")
    @classmethod
    def _normalise_language(cls, v: object) -> object:
        """Map full language names ('English') to ISO 639-1 ('en').

        Already-valid codes pass through unchanged; unknown values fall
        through to Pydantic and surface as a visible ValidationError.
        """
        if not isinstance(v, str):
            return v
        s = v.strip()
        return _LANG_NAME_TO_ISO.get(s.lower(), s)

    @field_validator("published_at", mode="before")
    @classmethod
    def _normalise_published_at(cls, v: object) -> object:
        """Normalise human-readable dates ('Feb 17, 2026') to ISO before Pydantic.

        Blank -> None; known 'Month DD, YYYY' formats -> ISO date string;
        anything else (incl. valid ISO 8601) is returned unchanged so Pydantic
        parses it natively. Unparseable strings fall through and surface as a
        ValidationError (visible in validation_failed), not silently dropped.
        """
        if not isinstance(v, str):
            return v
        s = v.strip()
        if not s:
            return None
        for fmt in _HUMAN_DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).date().isoformat()  # noqa: DTZ007
            except ValueError:
                continue
        return s

    @field_validator("body_md")
    @classmethod
    def reject_placeholder(cls, v: str) -> str:
        markers = {
            "lorem ipsum",
            "page not found",
            "access denied",
            "404 not found",
            "403 forbidden",
            "are you a robot",
        }
        low = v.lower()
        for m in markers:
            if m in low:
                raise ValueError(f"body looks like placeholder/error: '{m}'")
        return v
