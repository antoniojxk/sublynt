from __future__ import annotations

import re
from collections import Counter
from typing import Any, TypedDict

from .models import AnalysisConfig, Issue, Severity, SubtitleDocument


class _IssueContext(TypedDict):
    cue_index: int
    cue_identifier: str | None
    timestamp_ms: int


def _words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text, re.UNICODE))


def analyze(document: SubtitleDocument, config: AnalysisConfig | None = None) -> dict[str, Any]:
    cfg = config or AnalysisConfig()
    issues = document.parse_issues.copy()
    identifiers = Counter(c.identifier for c in document.cues if c.identifier)

    previous = None
    total_chars = total_words = total_duration = 0
    for list_index, cue in enumerate(document.cues, start=1):
        label = cue.identifier
        common: _IssueContext = {
            "cue_index": list_index,
            "cue_identifier": label,
            "timestamp_ms": cue.start_ms,
        }
        duration = cue.duration_ms
        chars = len(" ".join(cue.lines))
        words = _words(cue.text)
        total_chars += chars
        total_words += words
        total_duration += max(0, duration)
        if duration < 0:
            issues.append(
                Issue(
                    "end_before_start",
                    Severity.ERROR,
                    "Cue ends before it starts.",
                    **common,
                    repairable=True,
                )
            )
        elif duration < cfg.min_duration_ms:
            issues.append(
                Issue(
                    "duration_too_short",
                    Severity.WARNING,
                    f"Cue is shorter than {cfg.min_duration_ms} ms.",
                    **common,
                    repairable=True,
                )
            )
        elif duration > cfg.max_duration_ms:
            issues.append(
                Issue(
                    "duration_too_long",
                    Severity.WARNING,
                    f"Cue is longer than {cfg.max_duration_ms} ms.",
                    **common,
                    repairable=True,
                )
            )
        if not cue.text.strip():
            issues.append(
                Issue(
                    "empty_caption",
                    Severity.WARNING,
                    "Caption text is empty.",
                    **common,
                    repairable=True,
                )
            )
        if label and identifiers[label] > 1:
            issues.append(
                Issue(
                    "duplicate_identifier",
                    Severity.WARNING,
                    f"Cue identifier {label!r} is duplicated.",
                    **common,
                    repairable=True,
                )
            )
        if len(cue.lines) > cfg.max_lines:
            issues.append(
                Issue(
                    "too_many_lines",
                    Severity.WARNING,
                    f"Caption has more than {cfg.max_lines} lines.",
                    **common,
                    repairable=True,
                )
            )
        if any(len(line) > cfg.max_chars_per_line for line in cue.lines):
            issues.append(
                Issue(
                    "line_too_long",
                    Severity.WARNING,
                    f"A line exceeds {cfg.max_chars_per_line} characters.",
                    **common,
                    repairable=True,
                )
            )
        if duration > 0:
            cps = chars * 1000 / duration
            wpm = words * 60_000 / duration
            if cps > cfg.max_cps:
                issues.append(
                    Issue(
                        "excessive_cps",
                        Severity.WARNING,
                        f"Reading speed is {cps:.1f} characters/second.",
                        **common,
                    )
                )
            if wpm > cfg.max_wpm:
                issues.append(
                    Issue(
                        "excessive_wpm",
                        Severity.WARNING,
                        f"Reading speed is {wpm:.0f} words/minute.",
                        **common,
                    )
                )
        if previous is not None:
            gap = cue.start_ms - previous.end_ms
            if cue.start_ms < previous.start_ms:
                issues.append(
                    Issue(
                        "out_of_order",
                        Severity.ERROR,
                        "Cue is out of chronological order.",
                        **common,
                        repairable=True,
                    )
                )
            if gap < 0:
                issues.append(
                    Issue(
                        "overlap",
                        Severity.WARNING,
                        f"Cue overlaps the previous cue by {-gap} ms.",
                        **common,
                        repairable=True,
                    )
                )
            elif gap < cfg.min_gap_ms:
                issues.append(
                    Issue(
                        "insufficient_gap",
                        Severity.INFO,
                        f"Gap before cue is less than {cfg.min_gap_ms} ms.",
                        **common,
                        repairable=True,
                    )
                )
            if cue.text.strip() and cue.text.strip() == previous.text.strip():
                issues.append(
                    Issue(
                        "duplicate_consecutive",
                        Severity.WARNING,
                        "Caption duplicates the previous caption.",
                        **common,
                        repairable=True,
                    )
                )
        previous = cue

    count = len(document.cues)
    first_start = min((cue.start_ms for cue in document.cues), default=0)
    last_end = max((cue.end_ms for cue in document.cues), default=0)
    return {
        "format": document.format.value,
        "caption_count": count,
        "total_duration_ms": max(0, last_end - first_start),
        "average_caption_duration_ms": round(total_duration / count) if count else 0,
        "average_cps": round(total_chars * 1000 / total_duration, 2) if total_duration else 0,
        "average_wpm": round(total_words * 60_000 / total_duration, 2) if total_duration else 0,
        "issue_count": len(issues),
        "issue_counts": dict(Counter(issue.severity.value for issue in issues)),
        "issues": [issue.as_dict() for issue in issues],
    }
