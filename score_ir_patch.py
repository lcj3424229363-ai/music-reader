"""Transactional, human-confirmed patches for ScoreIR events."""
from __future__ import annotations

import copy
from fractions import Fraction
from typing import Any

from score_ir import fraction_text, parse_fraction, validate_score_ir


VOICE_ROLES = {"soprano", "alto", "tenor", "bass"}


class ScoreIrPatchError(ValueError):
    pass


def apply_confirmed_corrections(
    score_ir: dict[str, Any],
    corrections: list[dict[str, Any]],
    *,
    confirmed: bool,
    source: str = "vlm",
    review_id: str | None = None,
) -> dict[str, Any]:
    """Apply bounded event replacements atomically.

    VLM correction timing uses whole-note units while ScoreIR uses quarter-note
    units, so values are multiplied by four before matching and storage.
    """
    if not confirmed:
        raise ScoreIrPatchError("Human confirmation is required before applying corrections.")
    validation = validate_score_ir(score_ir)
    if not validation["valid"]:
        raise ScoreIrPatchError("The source ScoreIR is invalid.")
    if not isinstance(corrections, list) or not 1 <= len(corrections) <= 128:
        raise ScoreIrPatchError("Corrections must contain between 1 and 128 items.")
    if source not in {"vlm", "human"}:
        raise ScoreIrPatchError("Correction source must be vlm or human.")

    patched = copy.deepcopy(score_ir)
    targets = _role_targets(patched)
    changed_ids: set[str] = set()
    applied = []
    for index, correction in enumerate(corrections):
        normalized = _normalize_correction(correction, index)
        key = (normalized["measure"], normalized["voice"], normalized["onset"])
        candidates = targets.get(key, [])
        if len(candidates) != 1:
            raise ScoreIrPatchError(
                f"Correction {index} matched {len(candidates)} events; exactly one is required."
            )
        event = candidates[0]
        event_id = str(event.get("id") or "")
        if event_id in changed_ids:
            raise ScoreIrPatchError(f"Correction {index} targets an event more than once.")
        changed_ids.add(event_id)
        previous = {
            "kind": event.get("kind"),
            "duration": event.get("duration"),
            "pitches": copy.deepcopy(event.get("pitches", [])),
        }
        event["kind"] = (
            "rest" if normalized["kind"] == "rest"
            else "chord" if len(normalized["pitches"]) > 1
            else "note"
        )
        event["duration"] = fraction_text(normalized["duration"])
        event["pitches"] = normalized["pitches"]
        history = event.setdefault("provenance", {}).setdefault("corrections", [])
        if len(history) >= 20:
            raise ScoreIrPatchError(f"Event {event_id} correction history is full.")
        history.append({
            "source": source,
            "reviewId": review_id,
            "inputUnit": "whole-note",
            "previous": previous,
        })
        applied.append({"eventId": event_id, "measure": normalized["measure"], "voice": normalized["voice"]})

    patched_validation = validate_score_ir(patched)
    if not patched_validation["valid"]:
        codes = ", ".join(item["code"] for item in patched_validation["errors"][:5])
        raise ScoreIrPatchError(f"Corrections would make ScoreIR invalid: {codes}")
    return {"scoreIr": patched, "validation": patched_validation, "applied": applied}


def _normalize_correction(value: Any, index: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ScoreIrPatchError(f"Correction {index} must be an object.")
    measure = value.get("measure")
    voice = value.get("voice")
    kind = value.get("kind")
    if isinstance(measure, bool) or not isinstance(measure, int) or measure < 1:
        raise ScoreIrPatchError(f"Correction {index} has an invalid measure.")
    if voice not in VOICE_ROLES:
        raise ScoreIrPatchError(f"Correction {index} requires a known SATB voice.")
    if kind not in {"note", "rest"}:
        raise ScoreIrPatchError(f"Correction {index} has an invalid kind.")
    try:
        onset = parse_fraction(value.get("onset")) * 4
        duration = parse_fraction(value.get("duration")) * 4
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise ScoreIrPatchError(f"Correction {index} has invalid timing.") from exc
    if onset < 0 or duration <= 0:
        raise ScoreIrPatchError(f"Correction {index} has invalid timing.")
    raw_pitches = value.get("pitches", [])
    if not isinstance(raw_pitches, list) or len(raw_pitches) > 8:
        raise ScoreIrPatchError(f"Correction {index} has invalid pitches.")
    pitches = [_normalize_pitch(pitch, index) for pitch in raw_pitches]
    if (kind == "note") != bool(pitches):
        raise ScoreIrPatchError(f"Correction {index} pitch/rest content is inconsistent.")
    return {
        "measure": measure,
        "voice": voice,
        "kind": kind,
        "onset": fraction_text(onset),
        "duration": duration,
        "pitches": pitches,
    }


def _normalize_pitch(value: Any, correction_index: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ScoreIrPatchError(f"Correction {correction_index} has an invalid pitch.")
    step, alter, octave = value.get("step"), value.get("alter", 0), value.get("octave")
    if (
        step not in set("ABCDEFG")
        or isinstance(alter, bool) or not isinstance(alter, int) or not -2 <= alter <= 2
        or isinstance(octave, bool) or not isinstance(octave, int) or not 0 <= octave <= 9
    ):
        raise ScoreIrPatchError(f"Correction {correction_index} has an invalid pitch.")
    accidental = "#" * alter if alter > 0 else "-" * (-alter)
    pitch_class = ({"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[step] + alter) % 12
    return {
        "step": step,
        "alter": alter,
        "octave": octave,
        "display": f"{step}{accidental}{octave}",
        "pitchClass": pitch_class,
    }


def _voice_sort_key(value: str) -> tuple[int, int | str]:
    try:
        return (0, int(value))
    except (TypeError, ValueError):
        return (1, str(value))


def _role_targets(score_ir: dict[str, Any]) -> dict[tuple[int, str, str], list[dict[str, Any]]]:
    parts = score_ir.get("parts", []) or []
    result: dict[tuple[int, str, str], list[dict[str, Any]]] = {}
    measure_count = max((len(part.get("measures", []) or []) for part in parts), default=0)
    for measure_position in range(1, measure_count + 1):
        role_events = _measure_role_events(parts, measure_position - 1)
        for role, events in role_events.items():
            for event in events:
                key = (measure_position, role, str(event.get("onset")))
                result.setdefault(key, []).append(event)
    return result


def _measure_role_events(parts: list[dict[str, Any]], measure_index: int) -> dict[str, list[dict[str, Any]]]:
    if not parts:
        return {}
    if len(parts) == 1:
        events = _events_by_voice(parts[0], measure_index)
        voices = sorted(events, key=_voice_sort_key)
        if len(voices) >= 4:
            roles = ["soprano", "alto", "tenor", "bass"]
        elif len(voices) == 2:
            roles = ["soprano", "bass"]
        else:
            roles = ["soprano"]
        return {role: events[voice] for role, voice in zip(roles, voices)}

    upper = _events_by_voice(parts[0], measure_index)
    lower = _events_by_voice(parts[-1], measure_index)
    upper_voices = sorted(upper, key=_voice_sort_key)
    lower_voices = sorted(lower, key=_voice_sort_key)
    result = {}
    if upper_voices:
        result["soprano"] = upper[upper_voices[0]]
    if len(upper_voices) > 1:
        result["alto"] = upper[upper_voices[1]]
    if len(lower_voices) == 1:
        result["bass"] = lower[lower_voices[0]]
    elif lower_voices:
        result["tenor"] = lower[lower_voices[0]]
        result["bass"] = lower[lower_voices[1]]
    return result


def _events_by_voice(part: dict[str, Any], measure_index: int) -> dict[str, list[dict[str, Any]]]:
    measures = part.get("measures", []) or []
    if measure_index >= len(measures):
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for event in measures[measure_index].get("events", []) or []:
        if event.get("grace"):
            continue
        result.setdefault(str(event.get("voice") or "1"), []).append(event)
    return result
