import re

from .models import SubtitleFormat

_SRT_TIME = re.compile(r"^(?P<h>\d{1,3}):(?P<m>[0-5]\d):(?P<s>[0-5]\d),(?P<ms>\d{3})$")
_VTT_TIME = re.compile(r"^(?:(?P<h>\d{1,3}):)?(?P<m>[0-5]\d):(?P<s>[0-5]\d)\.(?P<ms>\d{3})$")


def parse_timestamp(value: str, subtitle_format: SubtitleFormat) -> int:
    match = (_SRT_TIME if subtitle_format is SubtitleFormat.SRT else _VTT_TIME).fullmatch(
        value.strip()
    )
    if not match:
        raise ValueError(f"Invalid {subtitle_format.value.upper()} timestamp: {value!r}")
    hours = int(match.group("h") or 0)
    return ((hours * 60 + int(match.group("m"))) * 60 + int(match.group("s"))) * 1000 + int(
        match.group("ms")
    )


def format_timestamp(milliseconds: int, subtitle_format: SubtitleFormat) -> str:
    milliseconds = max(0, milliseconds)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    separator = "," if subtitle_format is SubtitleFormat.SRT else "."
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"
