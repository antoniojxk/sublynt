from decimal import Decimal

from sublynt_core import AnalysisConfig, TransformConfig, parse_subtitle, transform
from sublynt_core.models import SubtitleFormat


def test_shift_prevents_negative_and_speed_scaling() -> None:
    document = parse_subtitle("1\n00:00:01,000 --> 00:00:02,000\nHello\n", "srt")
    result, changes = transform(
        document, TransformConfig(shift_ms=-1_500, speed_factor=Decimal("2"))
    )
    assert (result.cues[0].start_ms, result.cues[0].end_ms) == (0, 500)
    assert [change.code for change in changes] == ["shift_timing", "scale_timing"]


def test_sort_renumber_remove_empty_and_exact_duplicates() -> None:
    source = (
        "1\n00:00:03,000 --> 00:00:04,000\nLater\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\n\n"
        "3\n00:00:05,000 --> 00:00:06,000\nSame\n\n"
        "4\n00:00:05,000 --> 00:00:06,000\nSame\n"
    )
    document = parse_subtitle(
        source,
        "srt",
    )
    result, _ = transform(
        document,
        TransformConfig(
            sort_cues=True, renumber_srt=True, remove_empty=True, remove_duplicates=True
        ),
    )
    assert [cue.text for cue in result.cues] == ["Later", "Same"]
    assert [cue.identifier for cue in result.cues] == ["1", "2"]


def test_resolve_overlap_enforce_gap_and_durations() -> None:
    document = parse_subtitle(
        "1\n00:00:01,000 --> 00:00:01,200\nA\n\n2\n00:00:01,100 --> 00:00:02,000\nB\n", "srt"
    )
    result, _ = transform(
        document, TransformConfig(resolve_overlaps=True, enforce_gap=True, enforce_durations=True)
    )
    assert result.cues[1].start_ms >= result.cues[0].end_ms + 80
    assert all(cue.duration_ms >= 1_000 for cue in result.cues)


def test_safe_invalid_timing_repair_is_narrow() -> None:
    document = parse_subtitle("1\n00:00:03,000 --> 00:00:02,000\nWrong order\n", "srt")
    result, changes = transform(document, TransformConfig(repair_invalid_timing=True))
    assert result.cues[0].end_ms == 4_000
    assert [change.code for change in changes] == ["repair_invalid_timing"]


def test_split_long_cue_at_word_boundaries() -> None:
    text = "This is sentence one. This is sentence two, with several words. This is sentence three."
    document = parse_subtitle(f"1\n00:00:00,000 --> 00:00:09,000\n{text}\n", "srt")
    cfg = AnalysisConfig(max_chars_per_line=20, max_lines=2, min_duration_ms=500)
    result, changes = transform(document, TransformConfig(split_long=True, thresholds=cfg))
    assert len(result.cues) >= 2
    joined = " ".join(cue.text.replace("\n", " ") for cue in result.cues).replace("  ", " ")
    assert joined == text
    assert any(change.code == "split_cue" for change in changes)


def test_merge_compatible_short_cues_and_convert() -> None:
    document = parse_subtitle(
        "1\n00:00:00,000 --> 00:00:00,800\nHi\n\n2\n00:00:00,900 --> 00:00:01,700\nthere\n", "srt"
    )
    result, changes = transform(
        document, TransformConfig(merge_short=True, output_format=SubtitleFormat.VTT)
    )
    assert len(result.cues) == 1
    assert result.cues[0].text == "Hi there"
    assert result.format is SubtitleFormat.VTT
    assert {change.code for change in changes} >= {"merge_cues", "convert_format"}
