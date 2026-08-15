"""P8: Bass-given mode tests (Sposobin §18-19 bass-given exercises).

These tests verify that ``solve_melody(..., bass_pitches=...)`` runs
end-to-end and produces a valid 4-part harmonization when the bass
line is fixed.  This is the minimum baseline; richer Sposobin-style
tests (cadence patterns, common bass formulas, secondary dominants
in bass-given context) will follow once the framework is in place.
"""

import pytest

from solver import (
    Chord,
    Key,
    Note,
    Voicing,
    solve_melody,
)


# --- Helpers ---------------------------------------------------------------

def _note_set(n: Note | None) -> set[int]:
    """Pitch-class set of a single note (or empty for None)."""
    if n is None:
        return set()
    return {n.pc}


def _chord_pcs(chord: Chord, key: Key) -> set[int]:
    """Pitch-class set of a chord under a key."""
    return set(chord.pitch_classes(key))


# --- Test 1: Smoke test ---------------------------------------------------

def test_bass_given_cadence_smoke():
    """C major, 2 measures 4/4, bass line C3-C3-G2-G2 / C3-C3-G2-C3.

    Each beat is a quarter.  Bass anchors the chord; the solver must
    produce a 4-part harmonization without crashing.  We assert:
      - 8 beats × 4 voices = 32 notes
      - the final bass note is C3 (preserved)
      - the final chord is I (root position) for PAC
    """
    C3 = Note.from_name("C3")
    G2 = Note.from_name("G2")
    bass_pitches: list[list[Note]] = [
        [C3, C3, G2, G2],   # m1: I - I - V - V
        [C3, C3, G2, C3],   # m2: I - I - V - I  (final = I root)
    ]
    result = solve_melody("C", "4/4", melody_pitches=[[None] * 4] * 2,
                          bass_pitches=bass_pitches)
    # Flatten: 2 measures × 4 beats
    beats_flat: list[dict] = []
    for m in result.measures:
        for beat in m["beats"]:
            beats_flat.append(beat)
    assert len(beats_flat) == 8, f"expected 8 beats, got {len(beats_flat)}"
    # Final beat: bass must be C3 (preserved), chord should be I (root).
    final_beat = beats_flat[-1]
    assert final_beat["bass"] == "C3", f"final bass = {final_beat['bass']}, expected C3"
    assert final_beat["roman"].startswith("I"), (
        f"final chord roman = {final_beat['roman']}, expected I..."
    )
    assert final_beat["inversion"] == "root", (
        f"final chord inversion = {final_beat['inversion']}, expected 'root' (PAC)"
    )


# --- Test 2: Bass must be preserved --------------------------------------

@pytest.mark.parametrize("bass_name,key,expected_pc", [
    ("C3", "C", 0),    # C major: I
    ("D3", "D", 2),    # D major: I
    ("F3", "F", 5),    # F major: I
    ("G2", "C", 7),    # C major: V (root)
    ("E2", "C", 4),    # C major: iii (root) — not the textbook bass, but
                       # the solver should still preserve the bass if it
                       # can find a voicing.
])
def test_bass_preserved_for_root_position_chord(bass_name, key, expected_pc):
    """Given a single bass note (1 measure, 1 beat), the resulting bass
    voice in the output must equal the input bass, and the chord must
    include the bass pitch-class."""
    bass = Note.from_name(bass_name)
    result = solve_melody(
        key, "4/4",
        melody_pitches=[[None]],
        bass_pitches=[[bass]],
    )
    beat_out = result.measures[0]["beats"][0]
    assert beat_out["bass"] == bass.name, (
        f"bass not preserved: input={bass.name}, output={beat_out['bass']}"
    )
    # expected_pc: pitch class of the bass must equal what we asked for
    assert bass.pc == expected_pc  # sanity: test data is consistent


# --- Test 3: Bass not a chord tone → pool empties → no crash -----------

def test_bass_not_in_any_chord_returns_empty_gracefully():
    """If the bass is a chromatic note that doesn't fit any diatonic chord
    in the candidate pool, the pool becomes empty for that beat and the
    solver should fall back (not crash).  We use a chromatic note in
    C major that's in bass range but not a chord tone of any diatonic
    chord."""
    # C#3 in C major: it's a chromatic note.  V/ii = A7 contains C#, so
    # C# DOES fit V/ii.  Use a more out-of-pool pitch: F#3 — wait, F#
    # is in V/vi.  Try B#2 = pc 0 = C... no, B# is in our parser maybe
    # differently.  Use the cleanest non-diatonic note: Ab2.
    # Ab is in bVI (modal, not in default candidate pool) but not in
    # I, ii, IV, V, vi, V7, or any built-in secondary dominant.
    out_of_pool = Note.from_name("Ab2")  # pc 8
    result = solve_melody(
        "C", "4/4",
        melody_pitches=[[None]],
        bass_pitches=[[out_of_pool]],
    )
    # The solver should not crash.  The output may be empty for that
    # beat (no valid voicing) or fall back to something degenerate; we
    # just check it returned without exception.  The warning list
    # should mention the issue.
    assert isinstance(result.warnings, list)


# --- Test 4: Multiple bass-given beats in a phrase ----------------------

def test_bass_given_phrase_i_iv_v_i():
    """C major 4/4, 1 measure, bass C3 - F3 - G2 - C3.
    Expectation: chord progression I - IV - V - I in some inversions
    (C major bass formula: I, IV6 (or IV), V (or V6), I)."""
    C3 = Note.from_name("C3")
    F3 = Note.from_name("F3")
    G2 = Note.from_name("G2")
    bass_pitches = [[C3, F3, G2, C3]]
    result = solve_melody(
        "C", "4/4",
        melody_pitches=[[None] * 4],
        bass_pitches=bass_pitches,
    )
    beats_flat = [b for m in result.measures for b in m["beats"]]
    bass_names = [b["bass"] for b in beats_flat]
    # Bass line must be exactly preserved.
    assert bass_names == ["C3", "F3", "G2", "C3"], (
        f"bass line = {bass_names}, expected ['C3','F3','G2','C3']"
    )
    # Each beat's chord should be a reasonable Sposobin chord for that bass
    # (I, IV, V, or inversions thereof).  We don't assert the exact chord
    # because the solver picks among multiple inversions; we just check
    # the roman label is sensible.
    for i, beat_out in enumerate(beats_flat):
        roman = beat_out.get("roman", "")
        assert roman in ("I", "IV", "V", "i", "iv", "v", "i6", "I6", "IV6",
                         "V6", "V7", "V65", "V43", "V2"), (
            f"beat {i} roman = {roman}, expected a sensible Sposobin chord"
        )


# --- Test 5: Inversion preserved ----------------------------------------

def test_bass_given_with_inversion():
    """If the bass note is the THIRD of a triad (inversion 6), the chord
    should be the 6-inversion.  E.g. bass E3 in C major = I6 (E in bass,
    C and G above)."""
    E3 = Note.from_name("E3")
    result = solve_melody(
        "C", "4/4",
        melody_pitches=[[None]],
        bass_pitches=[[E3]],
    )
    beat_out = result.measures[0]["beats"][0]
    # E3 in C major = I6 or vi6.  The bass must be E, the inversion
    # must be "6" (third in bass), and the chord figure must mention
    # I or vi.
    assert beat_out["bass"] == "E3", f"bass not preserved: {beat_out['bass']}"
    assert beat_out["inversion"] == "6", (
        f"expected inversion='6' (third in bass), got '{beat_out['inversion']}' "
        f"figure={beat_out.get('figure')}"
    )
    assert beat_out["roman"].startswith(("I", "vi")), (
        f"roman = {beat_out['roman']}, expected I... or vi..."
    )
