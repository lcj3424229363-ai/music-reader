from __future__ import annotations

import re
from typing import Any

from music21 import pitch


NOTE_RE = re.compile(r"^([A-Ga-g])([#b-]?)(-?\d+)$")
STEP_INDEX = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}
CLEF_REFS = {
    "treble": {"bottomLine": "E4", "label": "高音谱号"},
    "bass": {"bottomLine": "G2", "label": "低音谱号"},
}


def locate_manual_notes(clef: str, notes: str, measure_number: int = 1) -> dict[str, Any]:
    clef_name = clef.strip().lower() or "treble"
    if clef_name not in CLEF_REFS:
        raise ValueError("Clef must be treble or bass.")

    tokens = parse_note_tokens(notes)
    if not tokens:
        raise ValueError("No notes found. Use note names like C4 E4 G4.")

    positions = [locate_note(token, clef_name, index, len(tokens)) for index, token in enumerate(tokens)]

    return {
        "source": {
            "fileName": "manual-notes",
            "extension": ".manual-notes",
            "path": "",
        },
        "summary": {
            "status": "manual_notes",
            "measureCount": 1,
            "partCount": 1,
            "clef": clef_name,
            "clefLabel": CLEF_REFS[clef_name]["label"],
        },
        "manualNotes": {
            "measureNumber": measure_number,
            "inputNotes": notes,
            "clef": clef_name,
            "notes": positions,
        },
        "warnings": [],
    }


def parse_note_tokens(notes: str) -> list[str]:
    raw_tokens = [token for token in re.split(r"[\s,;|]+", notes.strip()) if token]
    return [normalize_note_token(token) for token in raw_tokens]


def normalize_note_token(token: str) -> str:
    cleaned = token.strip().replace("♭", "b").replace("♯", "#")
    match = NOTE_RE.match(cleaned)
    if not match:
        raise ValueError(f"Invalid note token: {token}. Use forms like C4, F#4, Bb3.")
    step, accidental, octave = match.groups()
    if accidental == "b":
        accidental = "-"
    return f"{step.upper()}{accidental}{octave}"


def locate_note(token: str, clef_name: str, index: int, total: int) -> dict[str, Any]:
    note_pitch = pitch.Pitch(token)
    bottom_pitch = pitch.Pitch(CLEF_REFS[clef_name]["bottomLine"])
    note_index = diatonic_index(note_pitch)
    bottom_index = diatonic_index(bottom_pitch)

    staff_top_y = 20
    staff_gap = 12
    bottom_line_y = staff_top_y + staff_gap * 4
    step_y = staff_gap / 2
    y = bottom_line_y - ((note_index - bottom_index) * step_y)
    x = 58 + index * (360 / max(total, 1))

    return {
        "token": token,
        "display": token.replace("-", "b"),
        "step": note_pitch.step,
        "octave": note_pitch.octave,
        "accidental": note_pitch.accidental.name if note_pitch.accidental else None,
        "midi": note_pitch.midi,
        "x": round(x, 2),
        "y": round(y, 2),
        "ledgerLines": ledger_lines_for_y(y, staff_top_y, staff_gap),
    }


def diatonic_index(value: pitch.Pitch) -> int:
    return int(value.octave) * 7 + STEP_INDEX[value.step]


def ledger_lines_for_y(y: float, staff_top_y: int, staff_gap: int) -> list[float]:
    top = staff_top_y
    bottom = staff_top_y + staff_gap * 4
    lines = []

    if y < top:
        line = top - staff_gap
        while line >= y - 0.01:
            lines.append(round(line, 2))
            line -= staff_gap
    elif y > bottom:
        line = bottom + staff_gap
        while line <= y + 0.01:
            lines.append(round(line, 2))
            line += staff_gap

    return lines

