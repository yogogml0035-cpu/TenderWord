import importlib


word_util_module = importlib.import_module(
    "backend.util.word_util.word_insert_text"
)


def test_normalize_word_insert_text_converts_html_breaks() -> None:
    actual = word_util_module.normalize_word_insert_text("甲<br>乙<BR/>丙<br />丁")
    assert actual == "\r".join(["甲", "乙", "丙", "丁"])


def test_normalize_word_insert_text_supports_cell_breaks() -> None:
    actual = word_util_module.normalize_word_cell_text("甲<br>乙\n丙")
    assert actual == "\r".join(["甲", "乙", "丙"])


def test_normalize_word_insert_text_converts_escaped_newlines() -> None:
    actual = word_util_module.normalize_word_insert_text("甲\\n乙\\r\\n丙\\r丁")
    assert actual == "\r".join(["甲", "乙", "丙", "丁"])


def test_normalize_word_insert_text_converts_escaped_newlines_in_cells() -> None:
    actual = word_util_module.normalize_word_cell_text("甲\\n乙")
    assert actual == "\r".join(["甲", "乙"])


def test_normalize_word_body_text_preserves_empty_paragraphs() -> None:
    actual = word_util_module.normalize_word_body_text("甲\n\n乙")
    assert actual == "甲\r\r乙"
