"""Headless smoke tests for MiiiBrowser core (no Tk display required).

Covers the pure logic behind the six requirements that can be exercised without
a GUI: charset detection/decoding (Req 1), the <img>/link sentinels (Req 2/4),
and parser resilience to malformed input (Req 6).

Run with either:  python -m pytest tests/      or      python tests/test_core.py
"""

import os
import sys

# Make the repo root importable when run as a plain script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miiibrowser.charset_parser import decode_html, sniff_encoding
from miiibrowser.dom_html_parser import (
    _IMG_END,
    _IMG_SEP,
    _IMG_START,
    _LINK_END,
    _LINK_START,
    _image_marker,
    render_html,
)


# ── Req 1: encoding detection + decoding ────────────────────────────
def test_decode_meta_charset_iso8859():
    raw = b'<html><head><meta charset="iso-8859-1"></head><body>caf\xe9</body></html>'
    out = decode_html(raw)
    assert isinstance(out, str)
    assert "café" in out


def test_decode_http_equiv_charset():
    raw = (
        b'<html><head><meta http-equiv="Content-Type" '
        b'content="text/html; charset=windows-1252"></head><body>\x93hi\x94</body></html>'
    )
    out = decode_html(raw)
    assert isinstance(out, str)
    assert "“hi”" in out  # curly quotes from cp1252 0x93/0x94


def test_decode_missing_meta_never_raises():
    # Invalid UTF-8, no declaration: must fall back, not raise.
    out = decode_html(b"<html><body>\xff\xfe broken bytes</body></html>")
    assert isinstance(out, str)


def test_sniff_is_head_scoped():
    # A charset declared in <body> must be ignored (default utf-8).
    raw = b"<html><head></head><body><meta charset='utf-16'>x</body></html>"
    assert sniff_encoding(raw) == "utf-8"


def test_sniff_bom_wins():
    import codecs
    assert sniff_encoding(codecs.BOM_UTF8 + b"<html></html>") == "utf-8-sig"


# ── Req 6: parser never crashes on malformed input ──────────────────
def test_render_malformed_inputs_return_str():
    samples = [
        "",
        "<p><b>unclosed tags",
        "a < b & c > d",
        "<div><span>nested</div></span>",
        "<ul><li>one<li>two",
        "<img src=>",
        "<!DOCTYPE html><html><body><h1>Title</h1><p>ok</p>",
        b"\xff\xfe\x00 garbage",
        "<div>" * 2000 + "deep" + "</div>" * 2000,  # exceeds recursion cap
    ]
    for sample in samples:
        out = render_html(sample)
        assert isinstance(out, str)


def test_render_extracts_text():
    out = render_html("<html><body><p>Hello world</p></body></html>")
    assert "Hello world" in out


# ── Req 2/4: image + link sentinels ─────────────────────────────────
def test_img_sentinel_resolves_src_and_keeps_alt():
    out = render_html('<img src="pic.png" alt="a cat">', base_url="http://example.com/dir/")
    assert _IMG_START in out
    assert _IMG_END in out
    assert "http://example.com/dir/pic.png" in out
    assert "a cat" in out


def test_link_sentinel_resolves_href():
    out = render_html('<a href="/x">click</a>', base_url="http://e.com/")
    assert _LINK_START in out
    assert _LINK_END in out
    assert "http://e.com/x" in out
    assert "click" in out


def test_image_marker_no_src_is_placeholder():
    assert _image_marker("", "alt text", None) == "[image: alt text]"


def test_image_marker_strips_sentinel_chars_from_alt():
    out = _image_marker("p.png", "a\x1eb\x1fc", "http://e.com/")
    alt_part = out.split(_IMG_SEP, 1)[1]
    assert alt_part.startswith("a b c")  # control chars replaced with spaces


# ── data: URI decoding used by inline image loading ─────────────────
def test_decode_data_uri():
    # Imported lazily: pulls in tkinter/PIL but needs no display.
    from miiibrowser.BrowserWindow import BrowserWindow
    assert BrowserWindow._decode_data_uri("data:image/png;base64,aGVsbG8=") == b"hello"
    assert BrowserWindow._decode_data_uri("data:text/plain,Hello%20World") == b"Hello World"


if __name__ == "__main__":
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001 - report and continue
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc!r}")
    print(f"\n{len(funcs) - failed}/{len(funcs)} passed")
    sys.exit(1 if failed else 0)
