"""P8 / Level 2 integration end-to-end check.

Verifies that all four-part paths go through the Sposobin solver
(no more fallback to legacy four_part.py):
  - /solve-melody  questionType=melody  -> engine='sposobin-solver'
  - /solve-melody  questionType=bass    -> engine='sposobin-solver', bass preserved
  - /four-part-answer  questionType=melody -> engine='sposobin-solver' (Level 2)
  - /four-part-answer  questionType=bass   -> engine='sposobin-solver' (Level 2 + P8)

Runs against the FastAPI TestClient (no live server needed).
"""

import pytest
from fastapi.testclient import TestClient

import server

client = TestClient(server.app)


def _note_entry(step, octave, duration="4", voice="1"):
    """Build an app.js-style note entry (matches what the frontend sends)."""
    return {
        "kind": "note",
        "voice": voice,
        "duration": duration,
        "dotted": False,
        "units": 1,
        "pitches": [{"step": step, "octave": octave, "accidental": ""}],
    }


def _bass_line_from_response(data):
    """Pull the bass voice's per-beat pitch display names."""
    voices = data.get("fourPart", {}).get("voices", [])
    bass = next((v for v in voices if v.get("id") == "bass"), None)
    if not bass:
        return None
    out = []
    for entry in bass.get("entries", []):
        if entry.get("kind") == "note" and entry.get("pitches"):
            top = entry["pitches"][0]
            out.append(f"{top['step']}{top['octave']}")
        else:
            out.append("R")
    return out


def test_solve_melody_melody_mode():
    """P0-P7: melody-given mode still works through the Sposobin solver."""
    r = client.post("/solve-melody", json={
        "key": "C", "timeSignature": "4/4", "questionType": "melody",
        "melodyMeasures": [[
            _note_entry("C", 5), _note_entry("D", 5),
            _note_entry("E", 5), _note_entry("C", 5),
        ]],
    })
    assert r.status_code == 200, f"body={r.text[:300]}"
    data = r.json()
    assert data.get("source", {}).get("engine") == "sposobin-solver"


def test_solve_melody_bass_mode():
    """P8: bass-given mode routes to the Sposobin solver and preserves the
    bass line exactly."""
    r = client.post("/solve-melody", json={
        "key": "C", "timeSignature": "4/4", "questionType": "bass",
        "melodyMeasures": [],
        "bassMeasures": [[
            _note_entry("C", 3, voice="2"),
            _note_entry("F", 3, voice="2"),
            _note_entry("G", 2, voice="2"),
            _note_entry("C", 3, voice="2"),
        ]],
    })
    assert r.status_code == 200, f"body={r.text[:300]}"
    data = r.json()
    assert data.get("source", {}).get("engine") == "sposobin-solver"
    bass_line = _bass_line_from_response(data)
    assert bass_line == ["C3", "F3", "G2", "C3"], (
        f"bass not preserved: {bass_line}"
    )


def test_four_part_answer_melody_mode():
    """Level 2: /four-part-answer now forwards to the Sposobin solver
    (legacy four_part.py removed)."""
    r = client.post("/four-part-answer", json={
        "key": "C", "timeSignature": "4/4", "questionType": "melody",
        "melodyMeasures": [[
            _note_entry("C", 5), _note_entry("E", 5),
            _note_entry("G", 5), _note_entry("C", 5),
        ]],
    })
    assert r.status_code == 200
    data = r.json()
    assert data.get("source", {}).get("engine") == "sposobin-solver"


def test_four_part_answer_bass_mode():
    """Level 2 + P8: /four-part-answer with questionType=bass also goes
    through the Sposobin solver and preserves the bass line."""
    r = client.post("/four-part-answer", json={
        "key": "C", "timeSignature": "4/4", "questionType": "bass",
        "melodyMeasures": [],
        "bassMeasures": [[
            _note_entry("C", 3, voice="2"),
            _note_entry("F", 3, voice="2"),
            _note_entry("G", 2, voice="2"),
            _note_entry("C", 3, voice="2"),
        ]],
    })
    assert r.status_code == 200
    data = r.json()
    assert data.get("source", {}).get("engine") == "sposobin-solver"
    bass_line = _bass_line_from_response(data)
    assert bass_line == ["C3", "F3", "G2", "C3"]


# --- P8 review edge cases -----------------------------------------------

def test_bass_mode_with_melody_in_payload_does_not_crash():
    """Edge case (caught by P8 review): if a user accidentally sends both
    melodyMeasures AND bassMeasures in questionType='bass', the server
    should treat the bass as the binding constraint and ignore the
    melody (rather than triggering the enumerate_voicings mutex
    error: 'melody and fixed_bass are mutually exclusive')."""
    r = client.post("/solve-melody", json={
        "key": "C", "timeSignature": "4/4", "questionType": "bass",
        "melodyMeasures": [[
            _note_entry("C", 5, voice="1"),
            _note_entry("D", 5, voice="1"),
            _note_entry("E", 5, voice="1"),
            _note_entry("C", 5, voice="1"),
        ]],
        "bassMeasures": [[
            _note_entry("C", 3, voice="2"),
            _note_entry("F", 3, voice="2"),
            _note_entry("G", 2, voice="2"),
            _note_entry("C", 3, voice="2"),
        ]],
    })
    assert r.status_code == 200, f"body={r.text[:300]}"
    data = r.json()
    assert data.get("source", {}).get("engine") == "sposobin-solver"
    bass_line = _bass_line_from_response(data)
    assert bass_line == ["C3", "F3", "G2", "C3"], (
        f"bass not preserved when both melody and bass sent: {bass_line}"
    )


def test_bass_mode_with_key_changes_multi_measure():
    """Edge case (caught by P8 review): bass-given + modulation
    (keyChanges).  This triggered an IndexError in the bass-given
    fallback path because the fallback rebuilt v_list from
    [best_v_f] (length 1) instead of preserving the path so far.
    The fix: preserve cur_v_list / cur_c_list in the fallback beam."""
    r = client.post("/solve-melody", json={
        "key": "C", "timeSignature": "4/4", "questionType": "bass",
        "melodyMeasures": [],
        "bassMeasures": [
            [_note_entry("C", 3, voice="2")] * 4,
            [_note_entry("G", 2, voice="2")] * 4,
        ],
        "keyChanges": [[2, "G"]],
    })
    assert r.status_code == 200, f"body={r.text[:300]}"
    data = r.json()
    assert data.get("source", {}).get("engine") == "sposobin-solver"


def test_bass_mode_with_short_bass_measures():
    """Edge case: bassMeasures shorter than full — solver should still
    produce something graceful (placeholder melody synthesized)."""
    r = client.post("/solve-melody", json={
        "key": "C", "timeSignature": "4/4", "questionType": "bass",
        "melodyMeasures": [],
        "bassMeasures": [[_note_entry("C", 3, voice="2")]],
    })
    assert r.status_code == 200
    data = r.json()
    assert data.get("source", {}).get("engine") == "sposobin-solver"


def test_bass_mode_with_no_bass_data_returns_400():
    """Edge case: questionType='bass' with no bassMeasures should
    return a clear 400 error, not crash with IndexError or 500."""
    r = client.post("/solve-melody", json={
        "key": "C", "timeSignature": "4/4", "questionType": "bass",
        "melodyMeasures": [[_note_entry("C", 5, voice="1")]] * 4,
        # no bassMeasures
    })
    # P18.6: server returns 200 + safe error response (no 4xx/5xx with
    # raw Python internals).  The frontend reads warnings[] and shows
    # the message in the answer panel.
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["status"] == "error"
    assert "低音" in (body["warnings"][0] if body["warnings"] else "")


def test_bass_note_out_of_range_returns_422():
    """Edge case: bassMeasures with a note above the bass range
    (E2..D4) used to return 422.  P18.6: the server now returns 200 +
    a safe error response so the frontend never shows raw Python
    internals like "list index out of range"."""
    r = client.post("/solve-melody", json={
        "key": "C", "timeSignature": "4/4", "questionType": "bass",
        "melodyMeasures": [],
        "bassMeasures": [[_note_entry("C", 5, voice="2")]] * 4,  # C5 is above bass range
    })
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["status"] == "error"
    msg = (body["warnings"][0] if body["warnings"] else "").lower()
    # P18.6: server returns a friendly message in either English or Chinese
    # — never the raw Python exception.  Just confirm it mentions bass/range.
    assert "bass" in msg or "低音" in (body["warnings"][0] if body["warnings"] else "")
    assert "range" in msg or "范围" in (body["warnings"][0] if body["warnings"] else "")
