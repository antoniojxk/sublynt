from __future__ import annotations

import re

from .models import Cue, Issue, Severity, SubtitleDocument, SubtitleFormat
from .timecodes import parse_timestamp


class ParseError(ValueError):
    """Raised when content cannot be safely interpreted as subtitles."""


def decode_subtitle(data: bytes) -> str:
    if b"\x00" in data:
        raise ParseError("The uploaded file appears to be binary.")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParseError("Only UTF-8 encoded subtitle files are supported.") from exc


def parse_subtitle(text: str, subtitle_format: SubtitleFormat | str) -> SubtitleDocument:
    try:
        fmt = SubtitleFormat(subtitle_format)
    except ValueError as exc:
        raise ParseError("Only SRT and WebVTT subtitle formats are supported.") from exc
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    return _parse_srt(normalized) if fmt is SubtitleFormat.SRT else _parse_vtt(normalized)


def _blocks(text: str) -> list[list[str]]:
    return [block.split("\n") for block in re.split(r"\n[ \t]*\n", text.strip()) if block.strip()]


def _parse_timing(
    line: str, fmt: SubtitleFormat, index: int, issues: list[Issue]
) -> tuple[int, int, str | None] | None:
    if "-->" not in line:
        issues.append(
            Issue(
                "missing_timestamp",
                Severity.ERROR,
                "Cue has no timestamp line.",
                index,
                repairable=False,
            )
        )
        return None
    left, right = (part.strip() for part in line.split("-->", 1))
    right_parts = right.split(maxsplit=1)
    end_value = right_parts[0] if right_parts else ""
    settings = right_parts[1] if len(right_parts) > 1 else None
    if left.startswith("-") or end_value.startswith("-"):
        issues.append(
            Issue("negative_timestamp", Severity.ERROR, "Cue contains a negative timestamp.", index)
        )
        return None
    try:
        return parse_timestamp(left, fmt), parse_timestamp(end_value, fmt), settings
    except ValueError:
        issues.append(
            Issue("invalid_timestamp", Severity.ERROR, "Cue contains an invalid timestamp.", index)
        )
        return None


def _parse_srt(text: str) -> SubtitleDocument:
    cues: list[Cue] = []
    issues: list[Issue] = []
    for block_index, lines in enumerate(_blocks(text), start=1):
        if not lines:
            continue
        identifier: str | None = None
        timing_at = 0
        if "-->" not in lines[0]:
            identifier = lines[0].strip() or None
            timing_at = 1
            if identifier is None or not identifier.isdigit() or int(identifier) != block_index:
                issues.append(
                    Issue(
                        "malformed_srt_numbering",
                        Severity.WARNING,
                        "SRT cue numbering is missing or non-sequential.",
                        block_index,
                        identifier,
                        repairable=True,
                    )
                )
        else:
            issues.append(
                Issue(
                    "malformed_srt_numbering",
                    Severity.WARNING,
                    "SRT cue number is missing.",
                    block_index,
                    repairable=True,
                )
            )
        if timing_at >= len(lines):
            issues.append(
                Issue(
                    "missing_timestamp", Severity.ERROR, "Cue has no timestamp line.", block_index
                )
            )
            continue
        timing = _parse_timing(lines[timing_at], SubtitleFormat.SRT, block_index, issues)
        if timing is None:
            continue
        start, end, _ = timing
        cues.append(Cue(identifier, start, end, lines[timing_at + 1 :], block_index))
    if not cues:
        raise ParseError("No valid subtitle cues were found in the SRT file.")
    return SubtitleDocument(SubtitleFormat.SRT, cues, issues)


def _parse_vtt(text: str) -> SubtitleDocument:
    issues: list[Issue] = []
    raw = text
    if not re.match(r"^WEBVTT(?:[ \t].*)?(?:\n|$)", raw):
        issues.append(
            Issue("malformed_vtt_header", Severity.ERROR, "WebVTT file must begin with WEBVTT.")
        )
        body = raw
    else:
        body = raw.split("\n", 1)[1] if "\n" in raw else ""

    cues: list[Cue] = []
    for block in _blocks(body):
        if block[0].startswith(("NOTE", "STYLE", "REGION")):
            continue
        position = len(cues) + 1
        timing_at = 0 if "-->" in block[0] else 1
        identifier = None if timing_at == 0 else block[0].strip() or None
        if timing_at >= len(block):
            issues.append(
                Issue("missing_timestamp", Severity.ERROR, "Cue has no timestamp line.", position)
            )
            continue
        timing = _parse_timing(block[timing_at], SubtitleFormat.VTT, position, issues)
        if timing is None:
            continue
        start, end, settings = timing
        cues.append(Cue(identifier, start, end, block[timing_at + 1 :], position, settings))
    if not cues:
        raise ParseError("No valid subtitle cues were found in the WebVTT file.")
    return SubtitleDocument(SubtitleFormat.VTT, cues, issues)
