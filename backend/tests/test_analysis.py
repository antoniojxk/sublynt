from sublynt_core import AnalysisConfig, analyze, parse_subtitle


def test_analysis_detects_overlap_gap_speed_order_and_duplicates() -> None:
    source = """1
00:00:03,000 --> 00:00:04,000
Fast words in a very brief caption that is deliberately quite long

2
00:00:02,000 --> 00:00:02,500
Fast words in a very brief caption that is deliberately quite long
"""
    report = analyze(parse_subtitle(source, "srt"), AnalysisConfig(max_chars_per_line=20))
    codes = {issue["code"] for issue in report["issues"]}
    assert {
        "out_of_order",
        "overlap",
        "excessive_cps",
        "line_too_long",
        "duplicate_consecutive",
    } <= codes
    assert report["caption_count"] == 2
    assert report["average_wpm"] > 0


def test_analysis_detects_end_before_start_empty_and_long_duration() -> None:
    source = "1\n00:00:03,000 --> 00:00:02,000\n\n2\n00:00:04,000 --> 00:00:20,000\nHello\n"
    report = analyze(parse_subtitle(source, "srt"))
    codes = {issue["code"] for issue in report["issues"]}
    assert {"end_before_start", "empty_caption", "duration_too_long"} <= codes
