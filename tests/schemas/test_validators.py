from src.schemas._validators import detect_placeholder_marker


def test_lorem_ipsum_rejected_short() -> None:
    assert detect_placeholder_marker("lorem ipsum dolor sit amet") == "lorem ipsum"


def test_lorem_ipsum_rejected_long() -> None:
    text = "lorem ipsum " * 100  # >1000 chars
    assert detect_placeholder_marker(text) == "lorem ipsum"


def test_error_marker_rejected_when_short() -> None:
    assert detect_placeholder_marker("404 Not Found — page is gone.") == "404 not found"


def test_error_marker_accepted_when_long() -> None:
    text = (
        "The HTTP 404 Not Found client error response status code indicates "
        "that the server cannot find the requested resource. " * 10
    )
    assert len(text) >= 500
    assert detect_placeholder_marker(text) is None


def test_anti_bot_marker_rejected_when_short() -> None:
    assert detect_placeholder_marker("Bot check: are you a robot?") == "are you a robot"


def test_clean_text_accepted() -> None:
    assert detect_placeholder_marker("The json module exposes an API.") is None


def test_empty_text_accepted() -> None:
    assert detect_placeholder_marker("") is None


def test_case_insensitive_match() -> None:
    assert detect_placeholder_marker("LOREM IPSUM short stub") == "lorem ipsum"
