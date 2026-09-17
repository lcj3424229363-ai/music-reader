"""Conservative structural and musical-timing audit for MusicXML."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any


_TYPE_QUARTERS = {
    "maxima": Fraction(32), "long": Fraction(16), "breve": Fraction(8),
    "whole": Fraction(4), "half": Fraction(2), "quarter": Fraction(1),
    "eighth": Fraction(1, 2), "16th": Fraction(1, 4),
    "32nd": Fraction(1, 8), "64th": Fraction(1, 16),
    "128th": Fraction(1, 32), "256th": Fraction(1, 64),
}


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    return next((item for item in element if _tag(item) == name), None)


def _text(element: ET.Element, name: str, default: str = "") -> str:
    item = _child(element, name)
    return (item.text or default).strip() if item is not None else default


def _integer(element: ET.Element, name: str) -> int | None:
    try:
        return int(_text(element, name))
    except ValueError:
        return None


def _issue(
    issues: list[dict[str, Any]], code: str, severity: str, message: str,
    *, part: str | None = None, measure: int | str | None = None,
    voice: str | None = None,
) -> None:
    value: dict[str, Any] = {"code": code, "severity": severity, "message": message}
    if part is not None:
        value["part"] = part
    if measure is not None:
        value["measure"] = measure
    if voice is not None:
        value["voice"] = voice
    issues.append(value)


def audit_musicxml(source: str | Path) -> dict[str, Any]:
    """Audit timing and structure without rewriting the source document."""
    issues: list[dict[str, Any]] = []
    try:
        if isinstance(source, Path) or (isinstance(source, str) and "<" not in source[:200]):
            root = ET.parse(str(source)).getroot()
        else:
            root = ET.fromstring(str(source))
    except (ET.ParseError, OSError) as exc:
        return {
            "status": "invalid", "score": 0, "reviewRequired": True,
            "issues": [{"code": "INVALID_XML", "severity": "error", "message": str(exc)[:300]}],
            "flaggedMeasures": [], "stats": {"partCount": 0, "measureCount": 0, "noteCount": 0},
        }

    if _tag(root) not in {"score-partwise", "score-timewise"}:
        _issue(issues, "BAD_ROOT", "error", "Root must be score-partwise or score-timewise.")
    if _tag(root) == "score-timewise":
        _issue(issues, "TIMEWISE_UNSUPPORTED", "error", "Timewise MusicXML must be converted before audit.")

    parts = [item for item in root if _tag(item) == "part"]
    if not parts:
        _issue(issues, "NO_PARTS", "error", "The score contains no parts.")

    note_count = 0
    measure_counts: list[int] = []
    for part_index, part in enumerate(parts, start=1):
        part_id = part.get("id") or f"P{part_index}"
        measures = [item for item in part if _tag(item) == "measure"]
        measure_counts.append(len(measures))
        divisions: int | None = None
        beats: int | None = None
        beat_type: int | None = None
        for measure_index, measure in enumerate(measures, start=1):
            measure_number: int | str = measure.get("number") or measure_index
            attributes = _child(measure, "attributes")
            if attributes is not None:
                new_divisions = _integer(attributes, "divisions")
                if new_divisions is not None:
                    if new_divisions <= 0:
                        _issue(issues, "BAD_DIVISIONS", "error", "Divisions must be positive.", part=part_id, measure=measure_number)
                    else:
                        divisions = new_divisions
                time = _child(attributes, "time")
                if time is not None:
                    beats, beat_type = _integer(time, "beats"), _integer(time, "beat-type")
            if divisions is None:
                _issue(issues, "MISSING_DIVISIONS", "error", "No active divisions value.", part=part_id, measure=measure_number)
            expected = None
            if divisions and beats and beat_type and beat_type > 0:
                expected = Fraction(divisions * beats * 4, beat_type)

            cursor = Fraction(0)
            previous_onset = Fraction(0)
            max_end = Fraction(0)
            voice_ends: dict[str, Fraction] = defaultdict(Fraction)
            measure_notes = 0
            for element in measure:
                name = _tag(element)
                if name in {"backup", "forward"}:
                    duration = _integer(element, "duration")
                    if duration is None or duration <= 0:
                        _issue(issues, "BAD_TIME_MOVE", "error", f"{name} duration must be positive.", part=part_id, measure=measure_number)
                        continue
                    cursor += Fraction(duration) * (-1 if name == "backup" else 1)
                    if cursor < 0:
                        _issue(issues, "NEGATIVE_CURSOR", "error", "A backup moves before the measure start.", part=part_id, measure=measure_number)
                        cursor = Fraction(0)
                    continue
                if name != "note":
                    continue
                measure_notes += 1
                note_count += 1
                if _child(element, "grace") is not None:
                    continue
                duration = _integer(element, "duration")
                voice = _text(element, "voice", "1")
                if duration is None or duration <= 0:
                    _issue(issues, "BAD_NOTE_DURATION", "error", "A non-grace note needs positive duration.", part=part_id, measure=measure_number, voice=voice)
                    continue
                onset = previous_onset if _child(element, "chord") is not None else cursor
                if _child(element, "chord") is None:
                    previous_onset = onset
                    cursor += duration
                end = onset + duration
                max_end = max(max_end, end)
                voice_ends[voice] = max(voice_ends[voice], end)

                pitch = _child(element, "pitch")
                if pitch is not None:
                    step, octave = _text(pitch, "step"), _integer(pitch, "octave")
                    alter = _integer(pitch, "alter") if _child(pitch, "alter") is not None else 0
                    if step not in set("ABCDEFG") or octave is None or not 0 <= octave <= 9 or alter is None or not -2 <= alter <= 2:
                        _issue(issues, "BAD_PITCH", "error", "Pitch spelling is outside MusicXML bounds.", part=part_id, measure=measure_number, voice=voice)
                elif _child(element, "rest") is None and _child(element, "unpitched") is None:
                    _issue(issues, "MISSING_PITCH", "error", "Note has no pitch, rest, or unpitched value.", part=part_id, measure=measure_number, voice=voice)

                note_type = _text(element, "type")
                if divisions and note_type in _TYPE_QUARTERS:
                    typed = _TYPE_QUARTERS[note_type] * divisions
                    dot_count = sum(1 for item in element if _tag(item) == "dot")
                    if dot_count:
                        typed *= sum(Fraction(1, 2**dot) for dot in range(dot_count + 1))
                    modification = _child(element, "time-modification")
                    if modification is not None:
                        actual = _integer(modification, "actual-notes")
                        normal = _integer(modification, "normal-notes")
                        if actual and normal:
                            typed *= Fraction(normal, actual)
                    # Tuplet exporters commonly round fractional divisions
                    # across sibling notes (for example 85, 85, 86 for 256/3).
                    if abs(typed - duration) > 1:
                        _issue(issues, "TYPE_DURATION_MISMATCH", "warning", f"Written type implies {typed} divisions but duration is {duration}.", part=part_id, measure=measure_number, voice=voice)

            if not measure_notes:
                _issue(issues, "EMPTY_MEASURE", "warning", "Measure contains no notes or rests.", part=part_id, measure=measure_number)
            if expected is not None and max_end > expected:
                _issue(issues, "MEASURE_OVERFLOW", "error", f"Events end at {max_end}, beyond expected {expected} divisions.", part=part_id, measure=measure_number)
            implicit = measure.get("implicit") == "yes"
            if expected is not None and max_end and max_end < expected and not implicit and measure_index not in {1, len(measures)}:
                _issue(issues, "MEASURE_UNDERFILL", "warning", f"Events end at {max_end}, before expected {expected} divisions.", part=part_id, measure=measure_number)

    if measure_counts and len(set(measure_counts)) > 1:
        _issue(issues, "PART_MEASURE_MISMATCH", "error", f"Part measure counts differ: {measure_counts}.")

    weights = {"error": 22, "warning": 6, "info": 1}
    score = max(0, 100 - sum(weights[item["severity"]] for item in issues))
    errors = sum(item["severity"] == "error" for item in issues)
    status = "invalid" if errors else "review" if score < 94 else "clean"
    flagged = sorted({str(item["measure"]) for item in issues if "measure" in item})
    return {
        "status": status, "score": score, "reviewRequired": bool(issues),
        "issues": issues, "flaggedMeasures": flagged,
        "stats": {
            "partCount": len(parts),
            "measureCount": max(measure_counts, default=0),
            "noteCount": note_count,
            "errorCount": errors,
            "warningCount": sum(item["severity"] == "warning" for item in issues),
        },
    }
