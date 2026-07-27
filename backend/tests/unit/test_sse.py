"""SSE framing for /query/stream (CLAUDE.md §7 Query).

The reveal must reproduce the graded answer byte-for-byte: an earlier
implementation appended a space to every token, silently rewriting the answer's
whitespace and dropping newlines from what the user saw.
"""

from __future__ import annotations

from app.api.v1.routes.query import _reveal_chunks, _sse_frame


def _decode(frame: str) -> str:
    """Decode a frame the way an EventSource consumer does."""
    lines = [line for line in frame.split("\n") if line.startswith("data:")]
    return "\n".join(line[5:].removeprefix(" ") for line in lines)


def test_reveal_chunks_reassemble_exactly() -> None:
    answer = "Retention is 7 years [1].\n\nSee also [2].\n  indented\ttabbed"
    assert "".join(_reveal_chunks(answer, size=7)) == answer


def test_reveal_chunks_of_empty_answer() -> None:
    assert _reveal_chunks("") == []


def test_frame_roundtrips_multiline_payload() -> None:
    payload = "line one\nline two\n\nline four"
    assert _decode(_sse_frame(payload)) == payload


def test_frame_preserves_leading_and_repeated_whitespace() -> None:
    payload = "  two leading spaces and  a double space"
    assert _decode(_sse_frame(payload)) == payload


def test_frame_ends_with_blank_line_separator() -> None:
    # A frame must terminate with a blank line or consumers never dispatch it.
    assert _sse_frame("x").endswith("\n\n")


def test_named_event_is_emitted_before_data() -> None:
    frame = _sse_frame('{"answer":"x"}', event="done")
    assert frame.startswith("event: done\n")
    assert _decode(frame) == '{"answer":"x"}'


def test_full_stream_reassembles_into_the_answer() -> None:
    answer = "Grounded claim [1].\nSecond line [2]."
    streamed = "".join(_decode(_sse_frame(p)) for p in _reveal_chunks(answer))
    assert streamed == answer
