from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SubtitleFormat(StrEnum):
    SRT = "srt"
    VTT = "vtt"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class Cue:
    identifier: str | None
    start_ms: int
    end_ms: int
    lines: list[str]
    position: int
    settings: str | None = None

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def clone(self) -> Cue:
        return Cue(
            self.identifier,
            self.start_ms,
            self.end_ms,
            self.lines.copy(),
            self.position,
            self.settings,
        )


@dataclass(slots=True)
class Issue:
    code: str
    severity: Severity
    message: str
    cue_index: int | None = None
    cue_identifier: str | None = None
    timestamp_ms: int | None = None
    repairable: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "cue_index": self.cue_index,
            "cue_identifier": self.cue_identifier,
            "timestamp_ms": self.timestamp_ms,
            "repairable": self.repairable,
        }


@dataclass(slots=True)
class SubtitleDocument:
    format: SubtitleFormat
    cues: list[Cue]
    parse_issues: list[Issue] = field(default_factory=list)

    def clone(self) -> SubtitleDocument:
        return SubtitleDocument(
            self.format, [cue.clone() for cue in self.cues], self.parse_issues.copy()
        )


@dataclass(slots=True)
class AnalysisConfig:
    min_duration_ms: int = 1_000
    max_duration_ms: int = 7_000
    min_gap_ms: int = 80
    max_cps: float = 20.0
    max_wpm: float = 180.0
    max_chars_per_line: int = 42
    max_lines: int = 2


@dataclass(slots=True)
class Change:
    code: str
    cue_index: int | None
    description: str
    old_value: Any
    new_value: Any

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "cue_index": self.cue_index,
            "description": self.description,
            "old_value": self.old_value,
            "new_value": self.new_value,
        }
