from .models import SubtitleDocument, SubtitleFormat
from .timecodes import format_timestamp


def serialize_subtitle(
    document: SubtitleDocument, output_format: SubtitleFormat | str | None = None
) -> str:
    fmt = SubtitleFormat(output_format) if output_format is not None else document.format
    output: list[str] = []
    if fmt is SubtitleFormat.VTT:
        output.extend(["WEBVTT", ""])
    for index, cue in enumerate(document.cues, start=1):
        if fmt is SubtitleFormat.SRT:
            output.append(str(index))
        elif cue.identifier:
            output.append(cue.identifier)
        timing = f"{format_timestamp(cue.start_ms, fmt)} --> {format_timestamp(cue.end_ms, fmt)}"
        if fmt is SubtitleFormat.VTT and cue.settings:
            timing += f" {cue.settings}"
        output.extend([timing, *cue.lines, ""])
    return "\n".join(output).rstrip() + "\n"
