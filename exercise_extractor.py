"""Extract explicit four-part exercise constraints from an editor projection."""
from __future__ import annotations

from typing import Any


VOICE_FIELDS = {
    "soprano": "sopranoMeasures",
    "alto": "altoMeasures",
    "tenor": "tenorMeasures",
    "bass": "bassMeasures",
}


def _has_pitched_content(measures: Any) -> bool:
    return any(
        isinstance(entry, dict)
        and entry.get("kind") in {"note", "chord"}
        and bool(entry.get("pitches"))
        for measure in (measures or [])
        if isinstance(measure, list)
        for entry in measure
    )


def extract_exercise_constraints(editor_payload: dict[str, Any]) -> dict[str, Any]:
    """Classify known voices without guessing that a complete score is a question."""
    assignment = editor_payload.get("voiceAssignment", {}) or {}
    assignment_confidence = assignment.get("confidence")
    assignment_ambiguous = (
        assignment.get("method") not in {None, "none"}
        and assignment_confidence == "low"
    )
    key_assessment = editor_payload.get("keyAssessment", {}) or {}
    key_ambiguous = key_assessment.get("confidence") == "low"
    known_voices = [
        voice for voice, field in VOICE_FIELDS.items()
        if _has_pitched_content(editor_payload.get(field))
    ]
    known = set(known_voices)
    if known == {"soprano"}:
        kind = "melody-given"
        recommended = "melody"
    elif known == {"alto"}:
        kind = "alto-given"
        recommended = "alto"
    elif known == {"tenor"}:
        kind = "tenor-given"
        recommended = "tenor"
    elif known == {"bass"}:
        kind = "bass-given"
        recommended = "bass"
    elif known == {"soprano", "bass"}:
        kind = "dual-anchor"
        recommended = None
    elif known == set(VOICE_FIELDS):
        kind = "complete-score"
        recommended = None
    elif not known:
        kind = "empty"
        recommended = None
    else:
        kind = "partial-score"
        recommended = None

    if assignment_ambiguous and (recommended is not None or editor_payload.get("unassignedVoices")):
        kind = "ambiguous-voice-assignment"
        recommended = None
    elif key_ambiguous and recommended is not None:
        kind = "ambiguous-key"
        recommended = None

    candidates = []
    eligibility = editor_payload.get("solverEligibility", {}) or {}
    for mode, voice in (
        ("melody", "soprano"), ("alto", "alto"),
        ("tenor", "tenor"), ("bass", "bass"),
    ):
        if voice in known:
            candidate = {
                "questionType": mode,
                "anchorVoice": voice,
                "measureField": VOICE_FIELDS[voice],
            }
            if mode in eligibility:
                candidate["eligibility"] = eligibility[mode]
            candidates.append(candidate)

    return {
        "version": "exercise-extractor-v1",
        "kind": kind,
        "knownVoices": known_voices,
        "recommendedQuestionType": recommended,
        "requiresUserConfirmation": recommended is None,
        "voiceAssignment": assignment,
        "voiceAssignmentConfidence": assignment_confidence,
        "keyAssessment": key_assessment,
        "keyConfidence": key_assessment.get("confidence"),
        "candidates": candidates,
    }
