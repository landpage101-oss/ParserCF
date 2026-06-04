from src.sources.developer_mozilla_org import DeveloperMozillaOrgAdapter


def test_list_urls_returns_seeds() -> None:
    adapter = DeveloperMozillaOrgAdapter()
    urls = list(adapter.list_urls())
    assert len(urls) >= 5
    assert all(u.startswith("https://developer.mozilla.org/en-US/docs/Web/") for u in urls)


def test_parse_id_strips_prefix_and_extension() -> None:
    adapter = DeveloperMozillaOrgAdapter()
    assert (
        adapter.parse_id("https://developer.mozilla.org/en-US/docs/Web/CSS/z-index")
        == "Web/CSS/z-index"
    )
    assert (
        adapter.parse_id(
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/replace"
        )
        == "Web/JavaScript/Reference/Global_Objects/String/replace"
    )
    # anchor fragment must be stripped
    assert (
        adapter.parse_id(
            "https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/autocomplete#values"
        )
        == "Web/HTML/Reference/Attributes/autocomplete"
    )


def test_page_type_is_docs() -> None:
    adapter = DeveloperMozillaOrgAdapter()
    assert adapter.page_type == "docs"
