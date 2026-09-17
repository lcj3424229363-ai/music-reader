"""MusicXML semantic edit metrics based on the project's canonical ScoreIR."""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from reader import read_score


SEMANTIC_METRICS = (
    "token", "note", "rhythm", "pitch", "accidental",
    "orderedPitch", "orderedAccidental", "normalizedRhythm",
    "voicePitch", "voiceRhythm",
)


def _distance(left: list[Any], right: list[Any]) -> int:
    if len(left) > len(right):
        left, right = right, left
    previous = list(range(len(left) + 1))
    for row, right_value in enumerate(right, start=1):
        current = [row]
        for column, left_value in enumerate(left, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (left_value != right_value),
            ))
        previous = current
    return previous[-1]


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    return next((item for item in element if _tag(item) == name), None)


def _text(element: ET.Element, name: str, default: str = "") -> str:
    item = _child(element, name)
    return (item.text or default).strip() if item is not None else default


def _xml_voice_sequences(path: Path) -> dict[str, list[Any]] | None:
    """Read raw MusicXML staff/voice identities before music21 normalizes them."""
    if path.suffix.lower() not in {".xml", ".musicxml"}:
        return None
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None
    if _tag(root) != "score-partwise":
        return None

    result: dict[str, list[Any]] = {"voicePitch": [], "voiceRhythm": []}
    natural_pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    parts = [item for item in root if _tag(item) == "part"]
    for part_index, part in enumerate(parts):
        divisions = 1
        measures = [item for item in part if _tag(item) == "measure"]
        for measure_index, measure in enumerate(measures):
            attributes = _child(measure, "attributes")
            if attributes is not None:
                try:
                    divisions = max(1, int(_text(attributes, "divisions", str(divisions))))
                except ValueError:
                    pass
            cursor = 0
            previous_onset = 0
            for element in measure:
                name = _tag(element)
                if name in {"backup", "forward"}:
                    try:
                        amount = int(_text(element, "duration", "0"))
                    except ValueError:
                        amount = 0
                    cursor += -amount if name == "backup" else amount
                    cursor = max(0, cursor)
                    continue
                if name != "note" or _child(element, "grace") is not None:
                    continue
                try:
                    duration_divisions = int(_text(element, "duration", "0"))
                except ValueError:
                    duration_divisions = 0
                is_chord = _child(element, "chord") is not None
                onset_divisions = previous_onset if is_chord else cursor
                if not is_chord:
                    previous_onset = onset_divisions
                    cursor += duration_divisions
                onset = str(Fraction(onset_divisions, divisions * 4))
                duration = str(Fraction(duration_divisions, divisions * 4))
                position = (
                    part_index, measure_index, _text(element, "staff", "1"),
                    _text(element, "voice", "1"), onset,
                )
                kind = "rest" if _child(element, "rest") is not None else "note"
                result["voiceRhythm"].append((position, duration, kind))
                pitch = _child(element, "pitch")
                if pitch is None:
                    continue
                step = _text(pitch, "step")
                try:
                    octave = int(_text(pitch, "octave"))
                    alter = int(_text(pitch, "alter", "0"))
                except ValueError:
                    continue
                if step in natural_pc:
                    midi = (octave + 1) * 12 + natural_pc[step] + alter
                    result["voicePitch"].append((position, duration, midi))
    return result


def _sequences(path: Path) -> dict[str, list[Any]]:
    score_ir = read_score(path)["scoreIr"]
    sequences: dict[str, list[Any]] = {
        "token": [], "note": [], "rhythm": [], "pitch": [], "accidental": [],
        "orderedPitch": [], "orderedAccidental": [], "normalizedRhythm": [],
        "voicePitch": [], "voiceRhythm": [],
    }
    for part_index, part in enumerate(score_ir.get("parts", []) or []):
        for measure_index, measure in enumerate(part.get("measures", []) or []):
            events = measure.get("events", []) or []
            timed_events = [event for event in events if not event.get("grace")]
            measure_span = max((
                Fraction(str(event.get("onset") or "0/1"))
                + Fraction(str(event.get("duration") or "0/1"))
                for event in timed_events
            ), default=Fraction(0))
            for event in events:
                kind = str(event.get("kind") or "unknown")
                onset = str(event.get("onset") or "0/1")
                duration = str(event.get("duration") or "0/1")
                position = (part_index, measure_index, onset)
                staff_voice_position = (
                    part_index,
                    measure_index,
                    str(event.get("staff") or "1"),
                    str(event.get("voice") or "1"),
                    onset,
                )
                pitches = tuple(sorted(
                    (
                        int(pitch.get("pitchClass")) + 12 * (int(pitch.get("octave")) + 1),
                        int(pitch.get("alter") or 0),
                    )
                    for pitch in (event.get("pitches", []) or [])
                    if pitch.get("pitchClass") is not None and isinstance(pitch.get("octave"), int)
                ))
                sequences["token"].append((position, duration, kind, pitches))
                sequences["rhythm"].append((position, duration, kind))
                sequences["voiceRhythm"].append((staff_voice_position, duration, kind))
                if not event.get("grace") and measure_span > 0:
                    sequences["normalizedRhythm"].append((
                        part_index,
                        measure_index,
                        str(Fraction(onset) / measure_span),
                        str(Fraction(duration) / measure_span),
                        kind,
                    ))
                if pitches:
                    for midi, alter in pitches:
                        sequences["note"].append((position, duration, midi))
                        sequences["pitch"].append((position, midi))
                        sequences["accidental"].append((position, alter))
                        sequences["orderedPitch"].append((part_index, midi))
                        sequences["orderedAccidental"].append((part_index, alter))
                        sequences["voicePitch"].append((staff_voice_position, duration, midi))
                elif kind == "rest":
                    sequences["note"].append((position, duration, "rest"))
    raw_voice_sequences = _xml_voice_sequences(path)
    if raw_voice_sequences is not None:
        sequences.update(raw_voice_sequences)
    return sequences


def score_musicxml_semantics(reference: Path, prediction: Path) -> dict[str, float | int]:
    expected = _sequences(reference)
    actual = _sequences(prediction)
    result: dict[str, float | int] = {}
    for name in expected:
        distance = _distance(expected[name], actual[name])
        denominator = max(len(expected[name]), len(actual[name]))
        title = name.title()
        result[f"{name}Distance"] = distance
        result[f"{name}Ned"] = round(distance / denominator if denominator else 0.0, 6)
        result[f"{name}EditRecognitionRate"] = round(
            max(0.0, 1.0 - distance / denominator), 6,
        ) if denominator else 1.0
        result[f"reference{title}Count"] = len(expected[name])
        result[f"prediction{title}Count"] = len(actual[name])
    return result
