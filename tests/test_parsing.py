import pytest

from parsing import chunk, enc, parse


@pytest.mark.parametrize("text", ["", " ", "\n\n"])
def test_chunk_empty_text(text):
    assert chunk(text) == []


def test_chunk_preserves_paragraphs_within_token_budget():
    assert chunk("First paragraph.\n\nSecond paragraph.", max_tokens=20) == [
        "First paragraph.\n\nSecond paragraph."
    ]


def test_chunk_splits_oversized_paragraph_without_losing_text():
    text = "documentation " * 100
    chunks = chunk(text, max_tokens=10)
    assert len(chunks) > 1
    assert "".join(chunks) == text.strip()
    assert all(len(enc.encode(part)) <= 10 for part in chunks)


def test_chunk_flushes_previous_paragraph_before_splitting_long_one():
    text = "Short.\n\n" + "documentation " * 100
    chunks = chunk(text, max_tokens=10)
    assert chunks[0] == "Short."
    assert "".join(chunks[1:]) == ("documentation " * 100).strip()


def test_parse_removes_page_chrome_and_preserves_markdown_content():
    html = """
    <html><body>
    <header>header-marker</header><nav>nav-marker</nav>
    <h1>Guide</h1><p>Use a <a href="/api">token</a>.</p>
    <script>script-marker</script><style>style-marker</style>
    <footer>footer-marker</footer>
    </body></html>
    """
    markdown = parse(html)
    assert "# Guide" in markdown
    assert "Use a [token](/api)." in markdown
    assert "marker" not in markdown
