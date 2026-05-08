import pytest

from src.sources.docs_python_org import DocsPythonOrgAdapter


@pytest.fixture
def adapter() -> DocsPythonOrgAdapter:
    return DocsPythonOrgAdapter()


def test_list_urls_returns_seeds(adapter: DocsPythonOrgAdapter) -> None:
    urls = list(adapter.list_urls())
    assert len(urls) > 0
    for url in urls:
        assert url.startswith("https://docs.python.org/3/")


def test_parse_id_strips_prefix_and_extension(adapter: DocsPythonOrgAdapter) -> None:
    assert adapter.parse_id("https://docs.python.org/3/library/json.html") == "library/json"
    assert adapter.parse_id("https://docs.python.org/3/tutorial/index.html") == "tutorial/index"
    assert (
        adapter.parse_id("https://docs.python.org/3/reference/expressions.html")
        == "reference/expressions"
    )
