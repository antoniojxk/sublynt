from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .analyzer import _words
from .models import AnalysisConfig, Change, Cue, SubtitleDocument, SubtitleFormat


@dataclass(slots=True)
class TransformConfig:
    output_format: SubtitleFormat | None = None
    shift_ms: int = 0
    speed_factor: Decimal = Decimal("1")
    prevent_negative: bool = True
    sort_cues: bool = False
    renumber_srt: bool = False
    remove_empty: bool = False
    remove_duplicates: bool = False
    repair_invalid_timing: bool = False
    enforce_gap: bool = False
    resolve_overlaps: bool = False
    enforce_durations: bool = False
    split_long: bool = False
    merge_short: bool = False
    merge_max_gap_ms: int = 250
    thresholds: AnalysisConfig | None = None


def _record(
    changes: list[Change], code: str, cue: Cue | None, old: object, new: object, description: str
) -> None:
    changes.append(Change(code, cue.position if cue else None, description, old, new))


def _timing(cue: Cue) -> dict[str, int]:
    return {"start_ms": cue.start_ms, "end_ms": cue.end_ms}


def _split_text(text: str, target: int) -> list[str]:
    """Split using sentence, punctuation, then word boundaries."""
    if len(text) <= target:
        return [text]
    units = re.split(r"(?<=[.!?])\s+", text)
    if len(units) == 1:
        units = re.split(r"(?<=[,;:])\s+", text)
    if len(units) == 1:
        units = text.split()
    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current} {unit}".strip()
        if current and len(candidate) > target:
            chunks.append(current)
            current = unit
        else:
            current = candidate
        while len(current) > target and " " not in current:
            chunks.append(current[:target])
            current = current[target:]
    if current:
        chunks.append(current)
    return chunks


def _wrap(text: str, width: int, max_lines: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and len(candidate) > width and len(lines) + 1 < max_lines:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    return lines


def _split_cues(document: SubtitleDocument, cfg: AnalysisConfig, changes: list[Change]) -> None:
    result: list[Cue] = []
    target = cfg.max_chars_per_line * cfg.max_lines
    for cue in document.cues:
        text = " ".join(cue.lines).strip()
        parts = _split_text(text, target)
        if len(parts) == 1:
            result.append(cue)
            continue
        duration = max(0, cue.duration_ms)
        weights = [max(1, len(part)) for part in parts]
        total_weight = sum(weights)
        cursor = cue.start_ms
        replacements: list[Cue] = []
        for part_index, (part, weight) in enumerate(zip(parts, weights, strict=True)):
            if part_index == len(parts) - 1:
                end = cue.end_ms
            else:
                share = round(duration * weight / total_weight)
                remaining = len(parts) - part_index - 1
                max_end = cue.end_ms - remaining * cfg.min_duration_ms
                end = min(max_end, max(cursor + cfg.min_duration_ms, cursor + share))
            replacement = Cue(
                cue.identifier if part_index == 0 else None,
                cursor,
                max(cursor, end),
                _wrap(part, cfg.max_chars_per_line, cfg.max_lines),
                cue.position,
                cue.settings,
            )
            replacements.append(replacement)
            cursor = replacement.end_ms
        result.extend(replacements)
        _record(
            changes,
            "split_cue",
            cue,
            cue.text,
            [part.text for part in replacements],
            "Split long caption text.",
        )
    document.cues = result


def _can_merge(first: Cue, second: Cue, cfg: AnalysisConfig, max_gap: int) -> bool:
    gap = second.start_ms - first.end_ms
    duration = second.end_ms - first.start_ms
    text = f"{first.text} {second.text}".strip()
    cps = len(text) * 1000 / duration if duration > 0 else float("inf")
    wpm = _words(text) * 60_000 / duration if duration > 0 else float("inf")
    return (
        0 <= gap <= max_gap
        and first.duration_ms < cfg.min_duration_ms
        and second.duration_ms < cfg.min_duration_ms
        and duration <= cfg.max_duration_ms
        and len(text) <= cfg.max_chars_per_line * cfg.max_lines
        and cps <= cfg.max_cps
        and wpm <= cfg.max_wpm
    )


def _merge_cues(
    document: SubtitleDocument, cfg: AnalysisConfig, max_gap: int, changes: list[Change]
) -> None:
    result: list[Cue] = []
    index = 0
    while index < len(document.cues):
        current = document.cues[index]
        if index + 1 < len(document.cues) and _can_merge(
            current, document.cues[index + 1], cfg, max_gap
        ):
            following = document.cues[index + 1]
            old = [current.text, following.text]
            current.end_ms = following.end_ms
            current.lines = _wrap(
                f"{current.text} {following.text}", cfg.max_chars_per_line, cfg.max_lines
            )
            _record(
                changes,
                "merge_cues",
                current,
                old,
                current.text,
                "Merged compatible short neighboring captions.",
            )
            index += 2
        else:
            index += 1
        result.append(current)
    document.cues = result


def transform(
    document: SubtitleDocument, options: TransformConfig
) -> tuple[SubtitleDocument, list[Change]]:
    result = document.clone()
    cfg = options.thresholds or AnalysisConfig()
    changes: list[Change] = []

    if options.shift_ms:
        for cue in result.cues:
            old = _timing(cue)
            cue.start_ms += options.shift_ms
            cue.end_ms += options.shift_ms
            if options.prevent_negative and cue.start_ms < 0:
                cue.end_ms -= cue.start_ms
                cue.start_ms = 0
            _record(
                changes,
                "shift_timing",
                cue,
                old,
                _timing(cue),
                f"Shifted timing by {options.shift_ms} ms.",
            )
    if options.speed_factor != Decimal("1"):
        for cue in result.cues:
            old = _timing(cue)
            cue.start_ms = int(
                (Decimal(cue.start_ms) / options.speed_factor).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            cue.end_ms = int(
                (Decimal(cue.end_ms) / options.speed_factor).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            _record(
                changes,
                "scale_timing",
                cue,
                old,
                _timing(cue),
                f"Scaled timing for {options.speed_factor}x playback.",
            )
    if options.sort_cues:
        old_order = [cue.position for cue in result.cues]
        result.cues.sort(key=lambda cue: (cue.start_ms, cue.end_ms, cue.position))
        new_order = [cue.position for cue in result.cues]
        if old_order != new_order:
            _record(
                changes, "sort_cues", None, old_order, new_order, "Sorted captions chronologically."
            )
    if options.remove_empty:
        retained: list[Cue] = []
        for cue in result.cues:
            if cue.text.strip():
                retained.append(cue)
            else:
                _record(changes, "remove_empty", cue, cue.text, None, "Removed empty caption.")
        result.cues = retained
    if options.remove_duplicates:
        retained = []
        for cue in result.cues:
            if (
                retained
                and cue.text.strip() == retained[-1].text.strip()
                and cue.start_ms == retained[-1].start_ms
                and cue.end_ms == retained[-1].end_ms
            ):
                _record(
                    changes,
                    "remove_duplicate",
                    cue,
                    cue.text,
                    None,
                    "Removed exact consecutive duplicate.",
                )
            else:
                retained.append(cue)
        result.cues = retained
    if options.repair_invalid_timing:
        for cue in result.cues:
            if cue.end_ms < cue.start_ms:
                old = _timing(cue)
                cue.end_ms = cue.start_ms + cfg.min_duration_ms
                _record(
                    changes,
                    "repair_invalid_timing",
                    cue,
                    old,
                    _timing(cue),
                    "Replaced end-before-start timing with the minimum valid duration.",
                )
    if options.enforce_durations:
        for cue in result.cues:
            duration = cue.duration_ms
            corrected = min(cfg.max_duration_ms, max(cfg.min_duration_ms, duration))
            if corrected != duration:
                old = _timing(cue)
                cue.end_ms = cue.start_ms + corrected
                _record(
                    changes,
                    "enforce_duration",
                    cue,
                    old,
                    _timing(cue),
                    "Clamped caption duration to configured limits.",
                )
    if options.resolve_overlaps or options.enforce_gap:
        for previous, cue in zip(result.cues, result.cues[1:], strict=False):
            required_start = previous.end_ms + (cfg.min_gap_ms if options.enforce_gap else 0)
            if cue.start_ms < required_start:
                old = _timing(cue)
                duration = max(cfg.min_duration_ms, cue.duration_ms)
                cue.start_ms = required_start
                cue.end_ms = cue.start_ms + duration
                _record(
                    changes,
                    "adjust_gap",
                    cue,
                    old,
                    _timing(cue),
                    "Moved cue to remove overlap or enforce the minimum gap.",
                )
    if options.split_long:
        _split_cues(result, cfg, changes)
    if options.merge_short:
        _merge_cues(result, cfg, options.merge_max_gap_ms, changes)
    if options.renumber_srt or (
        options.output_format is SubtitleFormat.SRT and result.format is not SubtitleFormat.SRT
    ):
        for index, cue in enumerate(result.cues, start=1):
            old_identifier = cue.identifier
            cue.identifier = str(index)
            if old_identifier != cue.identifier:
                _record(
                    changes,
                    "renumber_cue",
                    cue,
                    old_identifier,
                    cue.identifier,
                    "Assigned sequential SRT cue number.",
                )
    if options.output_format and options.output_format is not result.format:
        old_format = result.format.value
        result.format = options.output_format
        _record(
            changes,
            "convert_format",
            None,
            old_format,
            result.format.value,
            "Converted subtitle format.",
        )
    return result, changes
