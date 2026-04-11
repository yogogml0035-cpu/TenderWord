import importlib


word_util_module = importlib.import_module(
    "backend.util.word_util.word_insert_text"
)


def test_normalize_word_insert_text_converts_html_breaks() -> None:
    actual = word_util_module.normalize_word_insert_text("甲<br>乙<BR/>丙<br />丁")
    assert actual == word_util_module.WORD_MANUAL_LINE_BREAK.join(
        ["甲", "乙", "丙", "丁"]
    )


def test_normalize_word_insert_text_supports_cell_breaks() -> None:
    actual = word_util_module.normalize_word_insert_text("甲<br>乙\n丙", break_char="\r")
    assert actual == "\r".join(["甲", "乙", "丙"])


def test_normalize_word_insert_text_converts_escaped_newlines() -> None:
    actual = word_util_module.normalize_word_insert_text("甲\\n乙\\r\\n丙\\r丁")
    assert actual == word_util_module.WORD_MANUAL_LINE_BREAK.join(
        ["甲", "乙", "丙", "丁"]
    )


def test_normalize_word_insert_text_converts_escaped_newlines_in_cells() -> None:
    actual = word_util_module.normalize_word_insert_text("甲\\n乙", break_char="\r")
    assert actual == "\r".join(["甲", "乙"])
