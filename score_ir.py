"""Canonical, versioned score representation shared by import and solving."""
from __future__ import annotations

from fractions import Fraction
from typing import Any


SCHEMA_VERSION = "score-ir-v1"
_EDITOR_DURATIONS = {
    Fraction(4, 1), Fraction(3, 1), Fraction(2, 1), Fraction(3, 2),
    Fraction(1, 1), Fraction(3, 4), Fraction(1, 2), Fraction(3, 8),
    Fraction(1, 4), Fraction(3, 16), Fraction(1, 8),
}


def fraction_text(value: Any) -> str:
    """Return an exact, JSON-friendly fraction such as ``3/2``."""
    if isinstance(value, Fraction):
        fraction = value
    elif hasattr(value, "numerator") and hasattr(value, "denominator"):
        fraction = Fraction(int(value.numerator), int(value.denominator))
    elif isinstance(value, float):
        fraction = Fraction(str(value)).limit_denominator(4096)
    else:
        fraction = Fraction(value)
    return f"{fraction.numerator}/{fraction.denominator}"


def parse_fraction(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, str):
        return Fraction(value)
    return Fraction(str(value)).limit_denominator(4096)


def score_ir_from_reader_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Build ScoreIR from reader events without copying analysis-only data."""
    summary = payload.get("summary", {}) or {}
    parts = []
    used_part_ids: set[str] = set()
    for part_index, legacy_part in enumerate(payload.get("parts", []) or [], start=1):
        base_part_id = str(legacy_part.get("id") or f"P{part_index}")
        part_id = base_part_id
        suffix = 2
        while part_id in used_part_ids:
            part_id = f"{base_part_id}-{suffix}"
            suffix += 1
        used_part_ids.add(part_id)
        measures = []
        for measure_index, legacy_measure in enumerate(legacy_part.get("measures", []) or [], start=1):
            measure_number = legacy_measure.get("number")
            if measure_number is None:
                measure_number = measure_index
            events = []
            for event_index, legacy_event in enumerate(legacy_measure.get("events", []) or [], start=1):
                kind = str(legacy_event.get("type") or "unknown")
                pitches = _event_pitches(legacy_event)
                events.append({
                    "id": f"{part_id}:mi{measure_index}:e{event_index}",
                    "kind": kind,
                    "voice": str(legacy_event.get("voice") or "1"),
                    "staff": int(legacy_event.get("staff") or 1),
                    "onset": legacy_event.get("offsetFraction") or fraction_text(legacy_event.get("offset", 0)),
                    "duration": legacy_event.get("durationFraction") or fraction_text(legacy_event.get("duration", 0)),
                    "pitches": pitches,
                    "dots": int(legacy_event.get("dots") or 0),
                    "grace": bool(legacy_event.get("grace")),
                    "ties": list(legacy_event.get("ties") or []),
                    "tuplets": list(legacy_event.get("tuplets") or []),
                    "provenance": dict(legacy_event.get("provenance") or {}),
                })
            measures.append({
                "index": measure_index,
                "number": measure_number,
                "implicit": bool(legacy_measure.get("implicit")),
                "timeSignature": legacy_measure.get("timeSignature"),
                "keySignature": legacy_measure.get("keySignature"),
                "clef": legacy_measure.get("clef"),
                "expectedDuration": legacy_measure.get("expectedQuarterFraction"),
                "actualDuration": legacy_measure.get("actualQuarterFraction"),
                "events": events,
            })
        parts.append({
            "id": part_id,
            "index": int(legacy_part.get("index") or part_index),
            "name": str(legacy_part.get("name") or f"Part {part_index}"),
            "staffNumber": int(legacy_part.get("staffNumber") or 1),
            "measures": measures,
        })

    return {
        "schemaVersion": SCHEMA_VERSION,
        "source": dict(payload.get("source", {}) or {}),
        "metadata": {
            "analyzedKey": summary.get("analyzedKey"),
            "partCount": len(parts),
            "measureCount": max((len(part["measures"]) for part in parts), default=0),
        },
        "parts": parts,
    }


def score_ir_to_reader_parts(score_ir: dict[str, Any]) -> list[dict[str, Any]]:
    """Compatibility adapter for the existing editor projection."""
    parts = []
    for part_index, part in enumerate(score_ir.get("parts", []) or [], start=1):
        measures = []
        for measure in part.get("measures", []) or []:
            events = []
            for event in measure.get("events", []) or []:
                pitches = event.get("pitches", []) or []
                legacy: dict[str, Any] = {
                    "type": event.get("kind"),
                    "offset": float(parse_fraction(event.get("onset", "0/1"))),
                    "duration": float(parse_fraction(event.get("duration", "0/1"))),
                    "offsetFraction": event.get("onset"),
                    "durationFraction": event.get("duration"),
                    "voice": event.get("voice"),
                    "staff": event.get("staff", 1),
                    "dots": event.get("dots", 0),
                    "grace": event.get("grace", False),
                    "ties": event.get("ties", []),
                    "tuplets": event.get("tuplets", []),
                }
                if event.get("kind") == "note" and pitches:
                    legacy["pitch"] = pitches[0].get("display")
                    legacy["pitchClass"] = pitches[0].get("pitchClass")
                elif event.get("kind") == "chord":
                    legacy["pitches"] = [pitch.get("display") for pitch in pitches]
                    legacy["pitchClasses"] = sorted({
                        pitch.get("pitchClass") for pitch in pitches
                        if pitch.get("pitchClass") is not None
                    })
                events.append(legacy)
            measures.append({
                "number": measure.get("number"),
                "timeSignature": measure.get("timeSignature"),
                "keySignature": measure.get("keySignature"),
                "clef": measure.get("clef"),
                "events": events,
                "warnings": [],
            })
        parts.append({
            "index": int(part.get("index") or part_index),
            "id": part.get("id") or f"P{part_index}",
            "name": part.get("name") or f"Part {part_index}",
            "staffNumber": int(part.get("staffNumber") or 1),
            "measureCount": len(measures),
            "measures": measures,
        })
    return parts


def validate_score_ir(score_ir: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if score_ir.get("schemaVersion") != SCHEMA_VERSION:
        errors.append({"code": "BAD_SCHEMA_VERSION", "message": "Unsupported ScoreIR schema version."})

    parts = score_ir.get("parts", []) or []
    if not parts:
        errors.append({"code": "NO_PARTS", "message": "ScoreIR must contain at least one part."})

    seen_ids: set[str] = set()
    event_count = 0
    note_count = 0
    measure_counts: list[int] = []
    for part in parts:
        part_id = str(part.get("id") or "")
        if not part_id:
            errors.append({"code": "MISSING_PART_ID", "message": "A part has no id."})
        part_measures = part.get("measures", []) or []
        measure_counts.append(len(part_measures))
        for measure in part_measures:
            measure_number = measure.get("number")
            expected_duration = None
            actual_duration = None
            try:
                if measure.get("expectedDuration"):
                    expected_duration = parse_fraction(measure["expectedDuration"])
                if expected_duration is not None and measure.get("actualDuration"):
                    actual_duration = parse_fraction(measure["actualDuration"])
                    if actual_duration > expected_duration:
                        errors.append({
                            "code": "MEASURE_OVERFLOW",
                            "message": "Measure duration exceeds its time signature.",
                            "part": part_id,
                            "measure": measure_number,
                        })
                    elif actual_duration < expected_duration and not measure.get("implicit"):
                        warnings.append({
                            "code": "MEASURE_UNDERFILLED",
                            "message": "Measure duration is shorter than its time signature.",
                            "part": part_id,
                            "measure": measure_number,
                        })
            except (ValueError, ZeroDivisionError):
                errors.append({
                    "code": "BAD_MEASURE_DURATION",
                    "message": "Invalid expected or actual measure duration.",
                    "part": part_id,
                    "measure": measure_number,
                })
            voice_timelines: dict[str, list[tuple[Fraction, Fraction, dict[str, Any]]]] = {}
            for event in measure.get("events", []) or []:
                event_count += 1
                event_id = str(event.get("id") or "")
                location = {"part": part_id, "measure": measure_number, "event": event_id}
                if not event_id or event_id in seen_ids:
                    errors.append({"code": "BAD_EVENT_ID", "message": "Event ids must be unique.", **location})
                seen_ids.add(event_id)
                try:
                    onset = parse_fraction(event.get("onset", ""))
                    duration = parse_fraction(event.get("duration", ""))
                except (ValueError, ZeroDivisionError):
                    errors.append({"code": "BAD_RATIONAL", "message": "Invalid onset or duration.", **location})
                    continue
                if onset < 0 or duration < 0 or (duration == 0 and not event.get("grace")):
                    errors.append({"code": "BAD_DURATION", "message": "Timed events require non-negative onset and positive duration.", **location})
                if not event.get("grace") and onset >= 0 and duration > 0:
                    voice = str(event.get("voice") or "1")
                    voice_timelines.setdefault(voice, []).append((onset, onset + duration, location))
                if event.get("kind") in {"note", "chord"}:
                    pitches = event.get("pitches", []) or []
                    note_count += len(pitches)
                    if not pitches:
                        errors.append({"code": "MISSING_PITCH", "message": "Pitched event has no pitches.", **location})
                    for pitch in pitches:
                        if pitch.get("step") not in set("ABCDEFG") or not isinstance(pitch.get("octave"), int):
                            errors.append({"code": "BAD_PITCH", "message": "Pitch spelling is invalid.", **location})

            timeline_end = Fraction(0)
            for voice, timeline in voice_timelines.items():
                previous_end = Fraction(0)
                for onset, end, location in sorted(timeline, key=lambda item: (item[0], item[1])):
                    if onset < previous_end:
                        errors.append({
                            "code": "VOICE_OVERLAP",
                            "message": "Events in one voice overlap.",
                            "voice": voice,
                            **location,
                        })
                    previous_end = max(previous_end, end)
                    timeline_end = max(timeline_end, end)
                    if expected_duration is not None and end > expected_duration:
                        errors.append({
                            "code": "EVENT_OUTSIDE_MEASURE",
                            "message": "An event extends beyond the measure boundary.",
                            "voice": voice,
                            **location,
                        })
            if voice_timelines and actual_duration is not None and timeline_end != actual_duration:
                warnings.append({
                    "code": "DECLARED_DURATION_MISMATCH",
                    "message": "Declared measure duration differs from the event timeline.",
                    "part": part_id,
                    "measure": measure_number,
                    "declared": fraction_text(actual_duration),
                    "timeline": fraction_text(timeline_end),
                })

    if measure_counts and len(set(measure_counts)) > 1:
        warnings.append({
            "code": "PART_MEASURE_COUNT_MISMATCH",
            "message": "Parts contain different numbers of measures.",
            "counts": measure_counts,
        })
    if parts and event_count == 0:
        errors.append({"code": "NO_EVENTS", "message": "ScoreIR must contain at least one event."})

    return {
        "valid": not errors,
        "schemaVersion": score_ir.get("schemaVersion"),
        "partCount": len(parts),
        "eventCount": event_count,
        "noteCount": note_count,
        "errors": errors,
        "warnings": warnings,
    }


def analyze_editor_projection(score_ir: dict[str, Any]) -> dict[str, Any]:
    """Describe information the teaching editor cannot represent exactly."""
    losses: list[dict[str, Any]] = []
    parts = score_ir.get("parts", []) or []
    direct_satb = len(parts) == 4 and all(
        max((
            len({str(event.get("voice") or "1") for event in measure.get("events", []) or []})
            for measure in part.get("measures", []) or []
        ), default=0) <= 1
        for part in parts
    )
    if len(parts) > 2 and not direct_satb:
        losses.append({
            "code": "EXTRA_PARTS_IGNORED",
            "message": "The editor uses only the first and last parts for SATB projection.",
            "count": len(parts) - 2,
        })
    for part in parts:
        max_measure_voices = max((
            len({str(event.get("voice") or "1") for event in measure.get("events", []) or []})
            for measure in part.get("measures", []) or []
        ), default=0)
        if max_measure_voices > 2:
            losses.append({
                "code": "EXTRA_VOICES_IGNORED",
                "message": "The editor represents at most two voices per selected part.",
                "part": part.get("id"),
                "count": max_measure_voices - 2,
            })
        chord_count = sum(
            event.get("kind") == "chord" and len(event.get("pitches", []) or []) > 1
            for measure in part.get("measures", []) or []
            for event in measure.get("events", []) or []
        )
        if chord_count:
            losses.append({
                "code": "CHORD_REDUCED_TO_TOP_NOTE",
                "message": "Chord events inside one voice are reduced to their highest pitch.",
                "part": part.get("id"),
                "count": chord_count,
            })
        tuplet_count = sum(
            bool(event.get("tuplets"))
            for measure in part.get("measures", []) or []
            for event in measure.get("events", []) or []
        )
        if tuplet_count:
            losses.append({
                "code": "TUPLET_METADATA_DROPPED",
                "message": "Tuplet ratios are retained in ScoreIR but not in the teaching editor projection.",
                "part": part.get("id"),
                "count": tuplet_count,
            })
        tie_count = sum(
            bool(event.get("ties"))
            for measure in part.get("measures", []) or []
            for event in measure.get("events", []) or []
        )
        if tie_count:
            losses.append({
                "code": "TIE_NOTATION_DROPPED",
                "message": "Tie notation is retained in ScoreIR but not in the teaching editor projection.",
                "part": part.get("id"),
                "count": tie_count,
            })
        grace_count = sum(
            bool(event.get("grace"))
            for measure in part.get("measures", []) or []
            for event in measure.get("events", []) or []
        )
        if grace_count:
            losses.append({
                "code": "GRACE_NOT_PROJECTED",
                "message": "Grace events remain in ScoreIR and are omitted from the solver projection.",
                "part": part.get("id"),
                "count": grace_count,
            })
        unsupported = sum(
            not event.get("grace")
            and parse_fraction(event.get("duration", "0/1")) not in _EDITOR_DURATIONS
            for measure in part.get("measures", []) or []
            for event in measure.get("events", []) or []
        )
        if unsupported:
            losses.append({
                "code": "DURATION_QUANTIZED",
                "message": "Some exact durations are rounded to editor-supported note values.",
                "part": part.get("id"),
                "count": unsupported,
            })
    return {"lossless": not losses, "losses": losses}


def _event_pitches(event: dict[str, Any]) -> list[dict[str, Any]]:
    if event.get("type") == "note":
        values = [event.get("pitch")]
    elif event.get("type") == "chord":
        values = event.get("pitches", []) or []
    else:
        return []
    components = event.get("pitchComponents")
    if isinstance(components, list) and len(components) == len(values):
        return [dict(component) for component in components]
    return [_pitch_from_display(str(value)) for value in values if value]


def _pitch_from_display(display: str) -> dict[str, Any]:
    step = display[:1].upper()
    index = 1
    alter = 0
    if index < len(display) and display[index] in {"#", "b", "-"}:
        alter = 1 if display[index] == "#" else -1
        index += 1
    octave = int(display[index:])
    pitch_class = ({"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[step] + alter) % 12
    return {"step": step, "alter": alter, "octave": octave, "display": display, "pitchClass": pitch_class}
