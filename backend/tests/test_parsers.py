from pathlib import Path

import pytest

from sublynt_core import ParseError, SubtitleFormat, parse_subtitle, serialize_subtitle
from sublynt_core.parsers import decode_subtitle

FIXTURES = Path(__file__).parent / "fixtures"


def test_srt_parse_multiline_bom_and_windows_endings() -> None:
    data = "\ufeff1\r\n00:00:01,000 --> 00:00:02,000\r\nLine one\r\nLine two\r\n".encode()
    document = parse_subtitle(decode_subtitle(data), SubtitleFormat.SRT)
    assert document.cues[0].lines == ["Line one", "Line two"]
    assert document.cues[0].start_ms == 1_000


def test_vtt_identifier_settings_and_round_trip() -> None:
    source = (FIXTURES / "sample.vtt").read_text()
    document = parse_subtitle(source, "vtt")
    assert document.cues[0].identifier == "intro"
    assert document.cues[0].settings == "align:start position:10%"
    reparsed = parse_subtitle(serialize_subtitle(document), "vtt")
    assert [(c.start_ms, c.end_ms, c.text) for c in reparsed.cues] == [
        (c.start_ms, c.end_ms, c.text) for c in document.cues
    ]


def test_malformed_timestamp_is_reported_when_other_cues_are_valid() -> None:
    source = "1\nBAD --> 00:00:02,000\nBroken\n\n2\n00:00:03,000 --> 00:00:04,000\nGood\n"
    document = parse_subtitle(source, "srt")
    assert any(issue.code == "invalid_timestamp" for issue in document.parse_issues)
    assert len(document.cues) == 1


def test_rejects_binary_unsupported_encoding_and_no_valid_cues() -> None:
    with pytest.raises(ParseError, match="binary"):
        decode_subtitle(b"WEBVTT\x00bad")
    with pytest.raises(ParseError, match="UTF-8"):
        decode_subtitle(b"\xff\xfe")
    with pytest.raises(ParseError, match="No valid"):
        parse_subtitle("not subtitles", "srt")


def test_format_conversion() -> None:
    source = (FIXTURES / "sample.srt").read_text()
    srt = parse_subtitle(source, "srt")
    vtt_text = serialize_subtitle(srt, "vtt")
    assert vtt_text.startswith("WEBVTT")
    assert parse_subtitle(vtt_text, "vtt").cues[0].text == "Welcome to SubLynt."
