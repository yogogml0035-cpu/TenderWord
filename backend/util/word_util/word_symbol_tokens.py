"""Lossless transport for legacy Word symbol-font glyphs.

``w:sym`` and text runs in Wingdings/Symbol fonts carry a character code plus
font, not a Unicode character.  A plain-text generation context cannot render
that pair faithfully, so keep it as a stable token until Word writeback.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass


WORD_SYMBOL_TOKEN_RE = re.compile(
    r"\[\[WORD_SYMBOL:(?P<font>[A-Za-z0-9_-]*):(?P<char>[0-9A-Fa-f]{1,6})\]\]"
)
LEGACY_SYMBOL_FONTS = frozenset(
    {"symbol", "wingdings", "wingdings 2", "wingdings 3", "webdings", "marlett"}
)


@dataclass(frozen=True)
class WordSymbolSpan:
    start: int
    end: int
    font_name: str


def normalize_symbol_font_name(font_name: str | None) -> str:
    return " ".join(str(font_name or "").split()).casefold()


def is_legacy_symbol_font(font_name: str | None) -> bool:
    return normalize_symbol_font_name(font_name) in LEGACY_SYMBOL_FONTS


def build_word_symbol_token(font_name: str | None, char_code: str | int) -> str:
    """Encode the original font/code pair without silently dropping a glyph."""
    font_bytes = str(font_name or "").encode("utf-8")
    font_token = base64.urlsafe_b64encode(font_bytes).decode("ascii").rstrip("=")
    try:
        code = int(str(char_code), 16)
    except (TypeError, ValueError):
        code = -1
    if not 0 <= code <= 0x10FFFF:
        return f"[[WORD_SYMBOL:{font_token}:000000]]"
    return f"[[WORD_SYMBOL:{font_token}:{code:04X}]]"


def decode_word_symbol_tokens(value: str) -> tuple[str, list[WordSymbolSpan]]:
    """Restore token code points and report the font spans Word must apply."""
    result: list[str] = []
    spans: list[WordSymbolSpan] = []
    cursor = 0
    for match in WORD_SYMBOL_TOKEN_RE.finditer(str(value or "")):
        result.append(str(value)[cursor : match.start()])
        try:
            font_token = match.group("font")
            padding = "=" * (-len(font_token) % 4)
            font_name = base64.urlsafe_b64decode(font_token + padding).decode("utf-8")
            code = int(match.group("char"), 16)
            if 0xD800 <= code <= 0xDFFF:
                raise ValueError("surrogate code point")
            character = chr(code)
        except (UnicodeDecodeError, ValueError):
            result.append(match.group(0))
            cursor = match.end()
            continue
        start = len("".join(result))
        result.append(character)
        spans.append(WordSymbolSpan(start=start, end=start + len(character), font_name=font_name))
        cursor = match.end()
    result.append(str(value or "")[cursor:])
    return "".join(result), spans


__all__ = [
    "LEGACY_SYMBOL_FONTS",
    "WORD_SYMBOL_TOKEN_RE",
    "WordSymbolSpan",
    "build_word_symbol_token",
    "decode_word_symbol_tokens",
    "is_legacy_symbol_font",
    "normalize_symbol_font_name",
]
