from backend.util.word_util.word_symbol_tokens import (
    build_word_symbol_token,
    decode_word_symbol_tokens,
)


def test_unknown_word_symbol_round_trips_font_and_character_code() -> None:
    token = build_word_symbol_token("Example Symbols", "F042")

    text, spans = decode_word_symbol_tokens(f"前{token}后")

    assert text == "前\uf042后"
    assert [(span.start, span.end, span.font_name) for span in spans] == [
        (1, 2, "Example Symbols")
    ]
