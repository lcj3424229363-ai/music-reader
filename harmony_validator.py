"""Independent SATB output validation.

This module deliberately does not import ``solver``.  It checks the solver's
plain dictionary output so a defect in search-time constraint code cannot
automatically make the final acceptance check pass.
"""
from __future__ import annotations

import re
from typing import Any


VOICE_ORDER = ("soprano", "alto", "tenor", "bass")
VOICE_RANGES = {
    "soprano": (57, 86),  # A3..D6
    "alto": (55, 76),     # G3..E5
    "tenor": (48, 69),    # C3..A4
    "bass": (38, 62),     # D2..D4
}
_PITCH_RE = re.compile(r"^([A-Ga-g])([#b-]*)(-?\d+)$")
_NATURAL_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_VOICE_PAIRS = (
    ("soprano", "alto"), ("soprano", "tenor"), ("soprano", "bass"),
    ("alto", "tenor"), ("alto", "bass"), ("tenor", "bass"),
)


def _pitch(name: Any) -> tuple[int, int] | None:
    match = _PITCH_RE.fullmatch(str(name or "").strip())
    if not match:
        return None
    step, accidentals, octave_text = match.groups()
    alter = accidentals.count("#") - accidentals.count("b") - accidentals.count("-")
    octave = int(octave_text)
    pc = (_NATURAL_PC[step.upper()] + alter) % 12
    return ((octave + 1) * 12 + pc, pc)


def _key_tonic_pc(key: str) -> int | None:
    token = str(key or "").strip().split()[0] if str(key or "").strip() else ""
    match = re.fullmatch(r"([A-Ga-g])([#b-]*)", token)
    if not match:
        return None
    step, accidentals = match.groups()
    alter = accidentals.count("#") - accidentals.count("b") - accidentals.count("-")
    return (_NATURAL_PC[step.upper()] + alter) % 12


def _issue(code: str, message: str, severity: str, **location: Any) -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, **location}


def validate_four_part_solution(
    solution: dict[str, Any],
    *,
    key: str,
    question_type: str = "melody",
) -> dict[str, Any]:
    """Validate beat-level SATB output without using solver internals."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    frames: list[dict[str, Any]] = []
    measures = solution.get("measures", []) or []
    anchored_voice = {
        "melody": "soprano",
        "alto": "alto",
        "tenor": "tenor",
        "bass": "bass",
    }.get(question_type, "soprano")

    for measure_index, measure in enumerate(measures, start=1):
        beats = measure.get("beats", []) or []
        if not beats:
            errors.append(_issue(
                "EMPTY_MEASURE", "Solution measure contains no beats.", "error",
                measure=measure_index,
            ))
        for beat_index, beat in enumerate(beats, start=1):
            location = {"measure": measure_index, "beat": beat_index}
            notes: dict[str, tuple[int, int]] = {}
            for voice in VOICE_ORDER:
                parsed = _pitch(beat.get(voice))
                if parsed is None:
                    errors.append(_issue(
                        "INVALID_PITCH", f"{voice} has an invalid pitch.", "error",
                        voice=voice, **location,
                    ))
                    continue
                notes[voice] = parsed
                low, high = VOICE_RANGES[voice]
                if not low <= parsed[0] <= high:
                    errors.append(_issue(
                        "VOICE_OUT_OF_RANGE", f"{voice} is outside the accepted range.", "error",
                        voice=voice, pitch=beat.get(voice), **location,
                    ))

            if len(notes) != 4:
                continue
            for upper, lower in zip(VOICE_ORDER, VOICE_ORDER[1:]):
                if notes[upper][0] < notes[lower][0]:
                    errors.append(_issue(
                        "VOICE_CROSSING", f"{upper} crosses below {lower}.", "error",
                        voices=[upper, lower], **location,
                    ))
            if notes["soprano"][0] - notes["alto"][0] > 12:
                errors.append(_issue(
                    "UPPER_VOICE_SPACING", "Soprano and alto exceed one octave.", "error",
                    voices=["soprano", "alto"], **location,
                ))
            if notes["alto"][0] - notes["tenor"][0] > 12:
                errors.append(_issue(
                    "UPPER_VOICE_SPACING", "Alto and tenor exceed one octave.", "error",
                    voices=["alto", "tenor"], **location,
                ))
            frames.append({"notes": notes, **location})

    tonic_pc = _key_tonic_pc(key)
    for previous, current in zip(frames, frames[1:]):
        prev_notes = previous["notes"]
        curr_notes = current["notes"]
        location = {"measure": current["measure"], "beat": current["beat"]}
        for upper, lower in _VOICE_PAIRS:
            upper_delta = curr_notes[upper][0] - prev_notes[upper][0]
            lower_delta = curr_notes[lower][0] - prev_notes[lower][0]
            if not upper_delta or not lower_delta or (upper_delta > 0) != (lower_delta > 0):
                continue
            before = (prev_notes[upper][0] - prev_notes[lower][0]) % 12
            after = (curr_notes[upper][0] - curr_notes[lower][0]) % 12
            if before == after == 7:
                errors.append(_issue(
                    "PARALLEL_FIFTH", f"Parallel fifth between {upper} and {lower}.", "error",
                    voices=[upper, lower], **location,
                ))
            elif before == after == 0:
                errors.append(_issue(
                    "PARALLEL_OCTAVE", f"Parallel octave/unison between {upper} and {lower}.", "error",
                    voices=[upper, lower], **location,
                ))

        soprano_delta = curr_notes["soprano"][0] - prev_notes["soprano"][0]
        bass_delta = curr_notes["bass"][0] - prev_notes["bass"][0]
        outer_interval = (curr_notes["soprano"][0] - curr_notes["bass"][0]) % 12
        if (
            abs(soprano_delta) > 2 and bass_delta
            and (soprano_delta > 0) == (bass_delta > 0)
            and outer_interval in {0, 7}
        ):
            warnings.append(_issue(
                "DIRECT_OUTER_PERFECT", "Outer voices approach a perfect interval by similar motion.",
                "warning", voices=["soprano", "bass"], **location,
            ))

        if tonic_pc is not None:
            leading_pc = (tonic_pc - 1) % 12
            for voice in VOICE_ORDER:
                if voice == anchored_voice:
                    continue
                previous_midi, previous_pc = prev_notes[voice]
                current_midi, current_pc = curr_notes[voice]
                if previous_pc == leading_pc and current_midi != previous_midi:
                    if current_pc != tonic_pc or current_midi - previous_midi != 1:
                        errors.append(_issue(
                            "LEADING_TONE_RESOLUTION",
                            f"Leading tone in {voice} does not resolve upward by semitone.",
                            "error", voice=voice, **location,
                        ))

    return {
        "valid": not errors,
        "ruleSet": "independent-satb-v1",
        "checkedFrames": len(frames),
        "errorCount": len(errors),
        "warningCount": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
