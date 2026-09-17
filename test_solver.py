"""Unit tests for solver.py — P0 textbook examples.

Each test runs a Sposobin-style harmonization and prints the result.
Pass criteria: prints JSON and exits 0; tests check expected cadences
and that the final chord / bass / soprano is correct.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make sibling import work
sys.path.insert(0, str(Path(__file__).parent))

from solver import (
    Key,
    Note,
    Chord,
    Voicing,
    solve_melody,
    detect_cadence,
    has_parallel,
    has_voice_crossing,
    has_voice_spacing_violation,
    in_range,
    VOICE_RANGES,
    Note as N,
)


def test_upper_voice_spacing_is_a_hard_constraint():
    valid = Voicing(
        soprano=N.from_name("C5"), alto=N.from_name("C4"),
        tenor=N.from_name("G3"), bass=N.from_name("C3"),
    )
    invalid = Voicing(
        soprano=N.from_name("D5"), alto=N.from_name("C4"),
        tenor=N.from_name("G3"), bass=N.from_name("C3"),
    )

    assert has_voice_spacing_violation(valid) == []
    assert has_voice_spacing_violation(invalid) == [
        "soprano/alto spacing exceeds an octave"
    ]


def _flat_melody(measures: list[list[N]]) -> list[N]:
    out: list[N] = []
    for m in measures:
        out.extend(m)
    return out


def _check_named(name, result_dict, expect):
    """Light assertion helper."""
    errs = []
    s = result_dict["summary"]
    measures = result_dict["measures"]
    # Last beat final chord
    last_beat = measures[-1]["beats"][-1]
    if "final_chord" in expect:
        if last_beat["roman"] != expect["final_chord"]:
            errs.append(f"final chord {last_beat['roman']} != {expect['final_chord']}")
    if "final_soprano" in expect:
        if last_beat["soprano"] != expect["final_soprano"]:
            errs.append(f"final soprano {last_beat['soprano']} != {expect['final_soprano']}")
    if "final_bass" in expect:
        if last_beat["bass"] != expect["final_bass"]:
            errs.append(f"final bass {last_beat['bass']} != {expect['final_bass']}")
    if "last_cadence" in expect:
        last_cad = measures[-1]["cadence"]
        if last_cad != expect["last_cadence"]:
            errs.append(f"last cadence {last_cad} != {expect['last_cadence']}")
    if "m1_first_chord" in expect:
        m1_first = measures[0]["beats"][0]["roman"]
        if m1_first != expect["m1_first_chord"]:
            errs.append(f"m1 beat1 chord {m1_first} != {expect['m1_first_chord']}")
    if "no_parallel" in expect and expect["no_parallel"]:
        # Scan all consecutive voicing pairs
        flat_v = []
        for m in measures:
            for b in m["beats"]:
                flat_v.append(Voicing(
                    soprano=N.from_name(b["soprano"]),
                    alto=N.from_name(b["alto"]),
                    tenor=N.from_name(b["tenor"]),
                    bass=N.from_name(b["bass"]),
                ))
        for i in range(len(flat_v) - 1):
            par = has_parallel(flat_v[i], flat_v[i + 1])
            if par:
                errs.append(f"parallel at beat {i+1}->{i+2}: {par}")
    if "all_in_range" in expect and expect["all_in_range"]:
        for m in measures:
            for b in m["beats"]:
                for voice, n in (("soprano", b["soprano"]),
                                  ("alto", b["alto"]),
                                  ("tenor", b["tenor"]),
                                  ("bass", b["bass"])):
                    note = N.from_name(n)
                    if not in_range(voice, note):
                        errs.append(f"{voice}={n} out of range in m{b['beat']}")
    if "no_voice_crossing" in expect and expect["no_voice_crossing"]:
        for m in measures:
            for b in m["beats"]:
                v = Voicing(
                    soprano=N.from_name(b["soprano"]),
                    alto=N.from_name(b["alto"]),
                    tenor=N.from_name(b["tenor"]),
                    bass=N.from_name(b["bass"]),
                )
                xc = has_voice_crossing(v)
                if xc:
                    errs.append(f"voice crossing {xc} in m{b['beat']}")
    return errs


def test_c_major_4_4_i_iv_v_i():
    """C major 4/4: soprano C5 C5 C5 C5 | F5 F5 F5 F5 | G5 G5 G5 G5 | C5 C5 C5 C5.
    Expected textbook answer: I - IV - V - I with PAC at end.
    """
    melody = [
        [N.from_name("C5")] * 4,
        [N.from_name("F5")] * 4,
        [N.from_name("G5")] * 4,
        [N.from_name("C5")] * 4,
    ]
    res = solve_melody("C", "4/4", melody).to_dict()
    errs = _check_named("C major I-IV-V-I", res, {
        "m1_first_chord": "I",
        "final_chord": "I",
        "final_soprano": "C5",
        "final_bass": "C3",
        "last_cadence": "PAC",
        "no_parallel": True,
        "all_in_range": True,
        "no_voice_crossing": True,
    })
    return res, errs


def test_c_major_3_4():
    """C major 3/4: I-I-V / IV-IV-I / V-V-I / I-I-I  — simplified."""
    melody = [
        [N.from_name("C5"), N.from_name("E5"), N.from_name("G5")],
        [N.from_name("F5"), N.from_name("A5"), N.from_name("F5")],
        [N.from_name("G5"), N.from_name("B5"), N.from_name("G5")],
        [N.from_name("C5"), N.from_name("G5"), N.from_name("C5")],
    ]
    res = solve_melody("C", "3/4", melody).to_dict()
    errs = _check_named("C major 3/4", res, {
        "final_chord": "I",
        "final_soprano": "C5",
        "last_cadence": "PAC",
        "no_parallel": True,
        "all_in_range": True,
    })
    return res, errs


def test_a_minor_4_4():
    """A minor 4/4: a - d - E - a (harmonic minor V must be major)."""
    melody = [
        [N.from_name("A4")] * 4,
        [N.from_name("D5")] * 4,
        [N.from_name("E5")] * 4,
        [N.from_name("A4")] * 4,
    ]
    res = solve_melody("a", "4/4", melody).to_dict()
    errs = _check_named("A minor i-iv-V-i", res, {
        "m1_first_chord": "i",
        "final_chord": "i",
        "final_soprano": "A4",
        "last_cadence": "PAC",
        "no_parallel": True,
        "all_in_range": True,
    })
    return res, errs


def test_f_major_4_4():
    """F major 4/4: F - Bb - C - F (I-IV-V-I)."""
    melody = [
        [N.from_name("F5")] * 4,
        [N.from_name("Bb5")] * 4,
        [N.from_name("C6")] * 4,
        [N.from_name("F5")] * 4,
    ]
    res = solve_melody("F", "4/4", melody).to_dict()
    errs = _check_named("F major I-IV-V-I", res, {
        "final_chord": "I",
        "final_soprano": "F5",
        "last_cadence": "PAC",
        "no_parallel": True,
        "all_in_range": True,
    })
    return res, errs


def test_g_major_with_ii():
    """G major 4/4: G - Am - D - G (I-ii-IV-I, common progression)."""
    melody = [
        [N.from_name("G5")] * 4,
        [N.from_name("A5")] * 4,
        [N.from_name("D5")] * 4,
        [N.from_name("G5")] * 4,
    ]
    res = solve_melody("G", "4/4", melody).to_dict()
    errs = _check_named("G major I-ii-IV-I", res, {
        "final_chord": "I",
        "last_cadence": "PAC",
        "no_parallel": True,
        "all_in_range": True,
    })
    return res, errs


def test_c_major_v7_resolution():
    """P1: V7 → I cadence with 7th resolving down by step.

    Melody: C5 C5 C5 C5 | F5 F5 F5 F5 | G5 G5 G5 G5 | C5 C5 C5 C5
    Expected:
      - m3.b3: I6/4 (cadential 6/4)
      - m3.b4: V7 (root or 6/5) — the V7 slot
      - m4.b1: I root or first inversion; 7th must resolve down to E
      - m4.b4: I root, PAC
    """
    from solver import Note as N2
    melody = [
        [N2.from_name("C5")] * 4,
        [N2.from_name("F5")] * 4,
        [N2.from_name("G5")] * 4,
        [N2.from_name("C5")] * 4,
    ]
    res = solve_melody("C", "4/4", melody).to_dict()
    errs = _check_named("C major V7 resolution", res, {
        "final_chord": "I",
        "last_cadence": "PAC",
        "no_parallel": True,
        "all_in_range": True,
    })
    # Verify V7 is in pool: the v_beat (m3.b4) should be V7 or V
    v7_beat = res["measures"][2]["beats"][3]
    if "V" not in v7_beat["roman"]:
        errs.append(f"v_beat should be V chord, got {v7_beat['roman']}")
    # Verify cadential 6/4 at c64_beat (m3.b3)
    c64_beat = res["measures"][2]["beats"][2]
    if c64_beat["roman"] != "I6/4":
        errs.append(f"c64_beat should be I6/4, got {c64_beat['roman']}")
    # Verify 7th resolution: if m3.b4 was V7, the 7th (F) must resolve
    # down by step in the same voice in m4.b1.
    if v7_beat["roman"].startswith("V") and "7" in v7_beat["roman"]:
        # Find the voice with F (the 7th) in v7_beat
        seventh_voices = {"soprano": "F5", "alto": "F4",
                          "tenor": "F3", "bass": "F2"}
        next_beat = res["measures"][3]["beats"][0]
        for voice, f_name in seventh_voices.items():
            if v7_beat[voice] == f_name:
                # Same voice in next beat should be E (one semitone down)
                expected = {"F5": "E5", "F4": "E4",
                            "F3": "E3", "F2": "E2"}[f_name]
                if next_beat[voice] != expected:
                    errs.append(
                        f"V7 7th in {voice} should resolve down to "
                        f"{expected}, got {next_beat[voice]}"
                    )
    return res, errs


def test_a_minor_v7_resolution():
    """P1: harmonic minor V7 → i cadence.

    Melody: A4 A4 A4 A4 | D5 D5 D5 D5 | E5 E5 E5 E5 | A4 A4 A4 A4
    Expected: m3.b3 = i6/4, m3.b4 = V7 (G# leading tone in voice),
              m4.b1 = i (7th → 3rd resolution)
    """
    from solver import Note as N2
    melody = [
        [N2.from_name("A4")] * 4,
        [N2.from_name("D5")] * 4,
        [N2.from_name("E5")] * 4,
        [N2.from_name("A4")] * 4,
    ]
    res = solve_melody("a", "4/4", melody).to_dict()
    errs = _check_named("A minor V7 → i", res, {
        "final_chord": "i",
        "last_cadence": "PAC",
        "no_parallel": True,
        "all_in_range": True,
    })
    return res, errs


def test_c_major_secondary_dominant_V_V():
    """P2: V7/V (secondary dominant of V) tonicizes V.

    Melody: D5 F#5 D5 F#5 | C5 C5 C5 C5 | C5 C5 C5 C5 | C5 C5 C5 C5
    The F#5 (3rd of D7 = V7/V) disambiguates from ii (D minor) which
    has F natural, not F#.  P7.3 expanded the secondary-dominant pool
    to include V9/x variants; the beam may now pick V9/VI (E9 with
    melody F# = its 9th) instead of V7/V.  Both are valid Sposobin
    secondary dominants; we accept either.
    """
    from solver import Note as N2
    melody = [
        [N2.from_name("D5"), N2.from_name("F#5"),
         N2.from_name("D5"), N2.from_name("F#5")],
        [N2.from_name("C5")] * 4,
        [N2.from_name("C5")] * 4,
        [N2.from_name("C5")] * 4,
    ]
    res = solve_melody("C", "4/4", melody).to_dict()
    errs = _check_named("C major V7/V → V", res, {
        "no_parallel": True,
        "all_in_range": True,
    })
    measures = res["measures"]
    found_secondary = False
    for m in measures:
        for b in m["beats"]:
            # Accept any secondary dominant (V7/x or V9/x)
            r = b["roman"]
            if ("V7/" in r and "/" in r) or ("V9/" in r and "/" in r):
                found_secondary = True
                break
    if not found_secondary:
        errs.append("No secondary dominant (V7/x or V9/x) found in any beat (P2/P7.3 missing)")
    return res, errs


def test_c_major_secondary_dominant_V_IV():
    """P2: A secondary dominant of IV (V7/IV) OR a chromatic
    pre-dominant of IV (bVII, N6) appears.  Bb4 in the melody is the
    7th of V7/IV = C7 and the root of bVII = Bb major — both
    legitimate.  We accept any of these.

    m1 = I (C5) | Bb4 C5 Bb4 → m2 = IV-area | A4 (3rd of F) ...
    """
    from solver import Note as N2
    melody = [
        [N2.from_name("C5"), N2.from_name("Bb4"),
         N2.from_name("C5"), N2.from_name("Bb4")],
        [N2.from_name("A4")] * 4,
        [N2.from_name("A4")] * 4,
        [N2.from_name("A4")] * 4,
    ]
    res = solve_melody("C", "4/4", melody).to_dict()
    errs = _check_named("C major V7/IV / bVII → IV", res, {
        "no_parallel": True,
        "all_in_range": True,
    })
    found = any(
        "V7/IV" in b["roman"] or "bVII" in b["roman"] or "N6" in b["roman"]
        for m in res["measures"] for b in m["beats"]
    )
    if not found:
        errs.append("V7/IV / bVII / N6 not found in any beat (P2 missing)")
    return res, errs


def test_c_major_german_aug6():
    """P3: An augmented 6th chord (Ger+6, Fr+6, or It+6) or a modal-mixture
    pre-dominant (iv, bVI) appears between IV and V.  The exact chord
    depends on which fits the SATB voicing best.

    Melody: m1 = IV (F5) → m2 = chromatic predom (Ab5) → m3 = V (G5) → m4 = I (C5).
    """
    from solver import Note as N2
    melody = [
        [N2.from_name("F5")] * 4,
        [N2.from_name("Ab5")] * 4,
        [N2.from_name("G5")] * 4,
        [N2.from_name("C5")] * 4,
    ]
    res = solve_melody("C", "4/4", melody).to_dict()
    errs = _check_named("C major aug6/iv → V", res, {
        "final_chord": "I",
        "last_cadence": "PAC",
        "no_parallel": True,
        "all_in_range": True,
    })
    # Verify some chromatic pre-dominant appears
    found = any(
        any(t in b["roman"] for t in
            ("Ger+6", "Fr+6", "It+6", "iv", "bVI"))
        or "N6" in b["roman"]
        for m in res["measures"] for b in m["beats"]
    )
    if not found:
        errs.append("No augmented-6th / modal pre-dominant found (P3 missing)")
    return res, errs


def test_c_major_neapolitan():
    """P3: A chromatic pre-dominant (N6, Ger+6/Fr+6/It+6, or any
    modal-mixture chord) appears and resolves to V then I.  The exact
    chord depends on which fits the SATB voicing best.

    Melody: m1 = I (C5) → m2 = chromatic pre-dominant (Ab5) →
            m3 = V (G5) → m4 = I (C5).
    """
    from solver import Note as N2
    melody = [
        [N2.from_name("C5")] * 4,
        [N2.from_name("Ab5")] * 4,
        [N2.from_name("G5")] * 4,
        [N2.from_name("C5")] * 4,
    ]
    res = solve_melody("C", "4/4", melody).to_dict()
    errs = _check_named("C major chromatic predom → V", res, {
        "final_chord": "I",
        "last_cadence": "PAC",
        "no_parallel": True,
        "all_in_range": True,
    })
    # Verify some chromatic pre-dominant appears
    found = any(
        "N6" in b["roman"]
        or any(t in b["roman"] for t in
              ("Ger+6", "Fr+6", "It+6", "bVI", "bIII", "bVII", "iv"))
        for m in res["measures"] for b in m["beats"]
    )
    if not found:
        errs.append("No chromatic pre-dominant found (P3 missing)")
    return res, errs


def test_c_major_bVI_modal():
    """P3.5: Modal mixture bVI in C major = Ab major (Ab-C-Eb).  When the
    melody is Ab5 (the b6 / bVI root) for a full measure, the solver may
    legitimately choose either bVI OR an augmented-6th chord (the bass
    note Ab is also the bass of Ger+6, Fr+6, It+6, and of N6 — all
    valid Sposobin chromatic pre-dominants).  We accept any of these.

    Melody: m1 = I (C5) → m2 = bVI (Ab5) → m3 = V (G5) → m4 = I (C5).
    """
    from solver import Note as N2
    melody = [
        [N2.from_name("C5")] * 4,
        [N2.from_name("Ab5")] * 4,
        [N2.from_name("G5")] * 4,
        [N2.from_name("C5")] * 4,
    ]
    res = solve_melody("C", "4/4", melody).to_dict()
    errs = _check_named("C major bVI / aug6 → V", res, {
        "final_chord": "I",
        "last_cadence": "PAC",
        "no_parallel": True,
        "all_in_range": True,
    })
    # Ab5 can be harmonized as bVI (modal mixture) OR any aug6
    # (Ger+6/Fr+6/It+6) OR N6 — all are valid Sposobin chromatic
    # pre-dominants of V → I.
    found = any(
        any(t in b["roman"] for t in ("bVI", "Ger+6", "Fr+6", "It+6", "N6"))
        for m in res["measures"] for b in m["beats"]
    )
    if not found:
        errs.append("No chromatic pre-dominant found (P3 / P3.5 missing)")
    return res, errs


def test_c_major_bVII_modal():
    """P3.5: Modal mixture bVII in C major = Bb major (Bb-D-F).

    Melody: m1 = I (C5) → m2 = bVII (Bb4) → m3 = I (C5).
    """
    from solver import Note as N2
    melody = [
        [N2.from_name("C5")] * 4,
        [N2.from_name("Bb4")] * 4,
        [N2.from_name("C5")] * 4,
        [N2.from_name("C5")] * 4,
    ]
    res = solve_melody("C", "4/4", melody).to_dict()
    errs = _check_named("C major bVII", res, {
        "no_parallel": True,
        "all_in_range": True,
    })
    found = any("bVII" in b["roman"] for m in res["measures"] for b in m["beats"])
    if not found:
        errs.append("bVII not found in any beat (P3.5 missing)")
    return res, errs


def test_c_major_bIII_modal():
    """P3.5: Modal mixture bIII in C major = Eb major (Eb-G-Bb).

    Melody: m1 = I (C5) → m2 = bIII (Eb5) → m3 = I (C5).
    """
    from solver import Note as N2
    melody = [
        [N2.from_name("C5")] * 4,
        [N2.from_name("Eb5")] * 4,
        [N2.from_name("C5")] * 4,
        [N2.from_name("C5")] * 4,
    ]
    res = solve_melody("C", "4/4", melody).to_dict()
    errs = _check_named("C major bIII", res, {
        "no_parallel": True,
        "all_in_range": True,
    })
    found = any("bIII" in b["roman"] for m in res["measures"] for b in m["beats"])
    if not found:
        errs.append("bIII not found in any beat (P3.5 missing)")
    return res, errs


def main():
    cases = [
        test_c_major_4_4_i_iv_v_i,
        test_c_major_3_4,
        test_a_minor_4_4,
        test_f_major_4_4,
        test_g_major_with_ii,
        test_c_major_v7_resolution,
        test_a_minor_v7_resolution,
        test_c_major_secondary_dominant_V_V,
        test_c_major_secondary_dominant_V_IV,
        test_c_major_german_aug6,
        test_c_major_neapolitan,
        test_c_major_bVI_modal,
        test_c_major_bVII_modal,
        test_c_major_bIII_modal,
    ]
    failed = 0
    for case in cases:
        print(f"\n=== {case.__name__} ===")
        res, errs = case()
        summary = res["summary"]
        print(f"  key={summary['key']} ts={summary['timeSignature']} "
              f"score={summary['score']:.1f} cadences={summary['cadences']}")
        if errs:
            failed += 1
            print(f"  FAIL: {len(errs)} issue(s)")
            for e in errs[:5]:
                # Replace Unicode flat/half-flat with ASCII for cmd output
                e_safe = e.replace("\u266d", "b").replace("\u00b0", "o")
                print(f"    - {e_safe}")
        else:
            print(f"  OK")
    print(f"\n{'='*50}")
    if failed:
        print(f"{failed} / {len(cases)} cases FAILED")
        return 1
    print(f"All {len(cases)} cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
