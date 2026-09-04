from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Thresholds(BaseModel):
    min_duration_ms: int = Field(1_000, ge=100, le=60_000)
    max_duration_ms: int = Field(7_000, ge=500, le=120_000)
    min_gap_ms: int = Field(80, ge=0, le=5_000)
    max_cps: float = Field(20.0, gt=0, le=200)
    max_wpm: float = Field(180.0, gt=0, le=2_000)
    max_chars_per_line: int = Field(42, ge=10, le=200)
    max_lines: int = Field(2, ge=1, le=10)

    @model_validator(mode="after")
    def validate_duration_range(self) -> Thresholds:
        if self.min_duration_ms > self.max_duration_ms:
            raise ValueError("Minimum duration cannot exceed maximum duration.")
        return self


class TransformRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"preset": "safe", "output_format": "vtt"}}
    )

    preset: Literal["none", "safe"] = "none"
    output_format: Literal["srt", "vtt"] | None = None
    shift_ms: int = Field(0, ge=-86_400_000, le=86_400_000)
    speed_factor: Decimal = Field(Decimal("1"), gt=Decimal("0.1"), le=Decimal("10"))
    prevent_negative: bool = True
    sort_cues: bool = False
    renumber_srt: bool = False
    remove_empty: bool = False
    remove_duplicates: bool = False
    enforce_gap: bool = False
    resolve_overlaps: bool = False
    enforce_durations: bool = False
    split_long: bool = False
    merge_short: bool = False
    merge_max_gap_ms: int = Field(250, ge=0, le=5_000)
    thresholds: Thresholds = Field(default_factory=Thresholds)

    @property
    def safe_enabled(self) -> bool:
        return self.preset == "safe"


class CueResponse(BaseModel):
    index: int
    identifier: str | None
    start_ms: int
    end_ms: int
    text: str
    lines: list[str]
    settings: str | None


class JobResponse(BaseModel):
    id: str
    filename: str
    created_at: str
    analysis: dict[str, Any]
    transformed_analysis: dict[str, Any] | None = None
    has_transformation: bool
    output_format: str | None


class TransformResponse(BaseModel):
    file_id: str
    output_format: str
    change_count: int
    changes: list[dict[str, Any]]
    analysis: dict[str, Any]


class PreviewResponse(BaseModel):
    original: list[CueResponse]
    transformed: list[CueResponse] | None
    changes: list[dict[str, Any]]
