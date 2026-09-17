"""MusicXML semantic edit metrics based on the project's canonical ScoreIR."""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from reader import read_score


SEMANTIC_METRICS = (
    "token", "note", "rhythm", "pitch", "accidental",
    "orderedPitch", "orderedAccidental", "normalizedRhythm",
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


def _sequences(path: Path) -> dict[str, list[Any]]:
    score_ir = read_score(path)["scoreIr"]
    sequences: dict[str, list[Any]] = {
        "token": [], "note": [], "rhythm": [], "pitch": [], "accidental": [],
        "orderedPitch": [], "orderedAccidental": [], "normalizedRhythm": [],
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
                elif kind == "rest":
                    sequences["note"].append((position, duration, "rest"))
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
