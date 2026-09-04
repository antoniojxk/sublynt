import pytest

from sublynt_core.models import SubtitleFormat
from sublynt_core.timecodes import format_timestamp, parse_timestamp


@pytest.mark.parametrize(
    ("value", "fmt", "expected"),
    [
        ("01:02:03,045", SubtitleFormat.SRT, 3_723_045),
        ("02:03.045", SubtitleFormat.VTT, 123_045),
        ("01:02:03.045", SubtitleFormat.VTT, 3_723_045),
    ],
)
def test_parse_timestamp(value: str, fmt: SubtitleFormat, expected: int) -> None:
    assert parse_timestamp(value, fmt) == expected


def test_timestamp_rejects_malformed_values() -> None:
    with pytest.raises(ValueError):
        parse_timestamp("00:99:00,000", SubtitleFormat.SRT)


def test_format_timestamp_uses_format_separator() -> None:
    assert format_timestamp(3_723_045, SubtitleFormat.SRT) == "01:02:03,045"
    assert format_timestamp(3_723_045, SubtitleFormat.VTT) == "01:02:03.045"
