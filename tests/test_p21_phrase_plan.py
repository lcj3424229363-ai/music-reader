"""
P21.3 — tests for phrase_planner_interface.

These tests are deliberately self-contained: they construct
mock chord / key objects so we don't have to spin up the full
solver just to test the planner.  The mocks follow the
duck-typed contract that ``compute_phrase_bonus`` and friends
rely on:

    chord.degree      : str   (e.g. 'C', 'F#', 'a')
    chord.quality     : str   ('major'/'minor'/'diminished'/'augmented')
    chord.kind        : str   ('triad'/'seventh'/'d7'/'d9')
    chord.inversion   : str   ('I'/'I6'/'V7'/...)
    chord.root_pc()   : int   (0..11, method)
    chord.figure()    : str   (optional, method)
    chord.target      : str|None   (secondary-dominant target)

    key.tonic_name    : str
    key.tonic_pc      : int
    key.mode          : str   ('major'/'minor')
"""
from __future__ import annotations

import sys, os
import pytest

# Make ``phrase_planner_interface`` importable from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import phrase_planner_interface as pi
from phrase_planner_interface import (
    PhrasePlan,
    PhrasePlanSet,
    make_phrase,
    make_plan_set,
    get_phrase_at_beat,
    compute_phrase_bonus,
    validate_phrase_plan,
    auto_plan_phrases,
    PHRASE_BONUS_MAX,
    PHRASE_BONUS_MIN,
    PHRASE_ROLES,
    CADENCE_TARGETS,
    FUNCTION_TARGETS,
    _chord_symbol_safe,
    _is_tonic_chord,
    _is_dominant_chord,
)


# ---------------------------------------------------------------------------
# Mock objects — keep this file independent of ``solver.py`` so the
# tests verify the *interface* and not the full solver.
# ---------------------------------------------------------------------------

class MockChord:
    """Minimal chord duck-type: degree, quality, kind, inversion,
    root_pc(), optional figure()."""

    def __init__(
        self,
        degree: str,
        quality: str,
        kind: str = "triad",
        inversion: str = "I",
        figure: str | None = None,
        target: str | None = None,
    ):
        self.degree = degree
        self.quality = quality
        self.kind = kind
        self.inversion = inversion
        self.target = target
        self._figure = figure
        self._pc = self._pc_of(degree)

    @staticmethod
    def _pc_of(degree: str) -> int:
        """Map a note name (C, C#, Db, ...) to a pitch class 0..11."""
        NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        NAMES_FLAT  = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
        d = degree.strip()
        if d in NAMES_SHARP:
            return NAMES_SHARP.index(d)
        if d in NAMES_FLAT:
            return NAMES_FLAT.index(d)
        raise ValueError(f"unknown note name: {degree!r}")

    def root_pc(self) -> int:
        return self._pc

    def figure(self) -> str:
        if self._figure is not None:
            return self._figure
        # default: degree + short quality + inversion
        short = {"major": "", "minor": "m", "diminished": "dim", "augmented": "aug"}.get(
            self.quality, self.quality
        )
        inv = "" if self.inversion == "I" else self.inversion
        return f"{self.degree}{short}{inv}"


class MockKey:
    def __init__(self, tonic_name: str, mode: str = "major"):
        self.tonic_name = tonic_name
        self.mode = mode
        self.tonic_pc = MockChord._pc_of(tonic_name)


# ---------------------------------------------------------------------------
# get_phrase_at_beat
# ---------------------------------------------------------------------------

class TestGetPhraseAtBeat:
    def test_none_plan_set_returns_none(self):
        assert get_phrase_at_beat(None, 0) is None

    def test_empty_plans_returns_none(self):
        ps = PhrasePlanSet(plans=[], total_beats=8, source="user")
        assert get_phrase_at_beat(ps, 0) is None

    def test_beat_within_first_phrase(self):
        p1 = make_phrase(0, 0, 7, phrase_role="opening")
        p2 = make_phrase(1, 8, 15, phrase_role="concluding", target_cadence="PAC")
        ps = make_plan_set([p1, p2], total_beats=16, source="user")
        assert get_phrase_at_beat(ps, 0).phrase_id == 0
        assert get_phrase_at_beat(ps, 4).phrase_id == 0
        assert get_phrase_at_beat(ps, 7).phrase_id == 0

    def test_beat_in_second_phrase(self):
        p1 = make_phrase(0, 0, 7)
        p2 = make_phrase(1, 8, 15)
        ps = make_plan_set([p1, p2], total_beats=16, source="user")
        assert get_phrase_at_beat(ps, 8).phrase_id == 1
        assert get_phrase_at_beat(ps, 15).phrase_id == 1

    def test_beat_before_first_phrase(self):
        """If a plan starts after 0, beat=0 has no phrase."""
        p1 = make_phrase(0, 4, 11)  # gap from 0..3
        ps = make_plan_set([p1], total_beats=12, source="user")
        assert get_phrase_at_beat(ps, 0) is None
        assert get_phrase_at_beat(ps, 3) is None

    def test_beat_after_last_phrase(self):
        p1 = make_phrase(0, 0, 7)
        ps = make_plan_set([p1], total_beats=8, source="user")
        assert get_phrase_at_beat(ps, 8) is None
        assert get_phrase_at_beat(ps, 999) is None

    def test_non_int_beat_returns_none(self):
        p1 = make_phrase(0, 0, 7)
        ps = make_plan_set([p1], total_beats=8, source="user")
        assert get_phrase_at_beat(ps, "0") is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_phrase_plan
# ---------------------------------------------------------------------------

class TestValidatePhrasePlan:
    def test_valid_plan_returns_empty(self):
        p1 = make_phrase(0, 0, 7, phrase_role="opening")
        p2 = make_phrase(1, 8, 15, phrase_role="concluding", target_cadence="PAC")
        ps = make_plan_set([p1, p2], total_beats=16, source="user")
        issues = validate_phrase_plan(ps, total_beats=16)
        assert issues == [], f"unexpected issues: {issues}"

    def test_empty_plan_list_is_an_issue(self):
        ps = PhrasePlanSet(plans=[], total_beats=8, source="user")
        issues = validate_phrase_plan(ps, total_beats=8)
        assert any("empty" in s for s in issues)

    def test_none_plan_set_is_an_issue(self):
        issues = validate_phrase_plan(None, total_beats=8)  # type: ignore[arg-type]
        assert issues and "None" in issues[0]

    def test_zero_total_beats_is_an_issue(self):
        p1 = make_phrase(0, 0, 0)
        ps = make_plan_set([p1], total_beats=0, source="user")
        issues = validate_phrase_plan(ps, total_beats=0)
        assert any("total_beats" in s for s in issues)

    def test_non_monotonic_start_beat_is_an_issue(self):
        p1 = make_phrase(0, 8, 15)  # out of order
        p2 = make_phrase(1, 0, 7)
        ps = PhrasePlanSet(plans=[p1, p2], total_beats=16, source="user")
        issues = validate_phrase_plan(ps, total_beats=16)
        assert any("sorted" in s for s in issues)

    def test_overlap_is_an_issue(self):
        p1 = make_phrase(0, 0, 8)  # overlaps with p2
        p2 = make_phrase(1, 5, 15)
        ps = PhrasePlanSet(plans=[p1, p2], total_beats=16, source="user")
        issues = validate_phrase_plan(ps, total_beats=16)
        assert any("overlap" in s for s in issues)

    def test_gap_is_an_issue(self):
        p1 = make_phrase(0, 0, 3)
        p2 = make_phrase(1, 6, 15)  # gap at 4, 5
        ps = PhrasePlanSet(plans=[p1, p2], total_beats=16, source="user")
        issues = validate_phrase_plan(ps, total_beats=16)
        assert any("gap" in s for s in issues)

    def test_first_plan_must_start_at_zero(self):
        p1 = make_phrase(0, 2, 7)  # starts at 2, not 0
        ps = make_plan_set([p1], total_beats=8, source="user")
        issues = validate_phrase_plan(ps, total_beats=8)
        assert any("first plan starts" in s for s in issues)

    def test_last_plan_must_end_at_total_minus_one(self):
        p1 = make_phrase(0, 0, 5)  # ends at 5, total_beats=8 -> expected 7
        ps = make_plan_set([p1], total_beats=8, source="user")
        issues = validate_phrase_plan(ps, total_beats=8)
        assert any("last plan ends" in s for s in issues)

    def test_length_beats_mismatch_is_an_issue(self):
        p1 = PhrasePlan(
            phrase_id=0, start_beat=0, end_beat=7,
            length_beats=99,  # wrong
            phrase_role=None, target_cadence=None, target_function=None,
            strategy_hint={},
        )
        ps = make_plan_set([p1], total_beats=8, source="user")
        issues = validate_phrase_plan(ps, total_beats=8)
        assert any("length_beats" in s for s in issues)

    def test_bad_phrase_role_is_an_issue(self):
        # bypass make_phrase to inject a bad value
        p1 = PhrasePlan(
            phrase_id=0, start_beat=0, end_beat=7, length_beats=8,
            phrase_role="bogus", target_cadence=None, target_function=None,
            strategy_hint={},
        )
        ps = make_plan_set([p1], total_beats=8, source="user")
        issues = validate_phrase_plan(ps, total_beats=8)
        assert any("phrase_role" in s for s in issues)

    def test_unknown_hint_key_warns(self):
        p1 = make_phrase(0, 0, 7, strategy_hint={"chord_preference": ["I"],
                                                 "this_is_not_documented": True})
        ps = make_plan_set([p1], total_beats=8, source="user")
        issues = validate_phrase_plan(ps, total_beats=8)
        assert any("strategy_hint" in s and "unknown" in s for s in issues)

    def test_end_before_start_is_an_issue(self):
        p1 = PhrasePlan(
            phrase_id=0, start_beat=5, end_beat=3, length_beats=-1,
            phrase_role=None, target_cadence=None, target_function=None,
            strategy_hint={},
        )
        ps = make_plan_set([p1], total_beats=8, source="user")
        issues = validate_phrase_plan(ps, total_beats=8)
        assert any("end_beat" in s and "start_beat" in s for s in issues)

    def test_validator_does_not_throw_on_garbage(self):
        """Even a totally broken plan_set should yield a list, not raise."""
        # Use object() so the validator's hasattr/getattr fall through.
        class Weird:
            pass
        w = Weird()
        w.plans = [object()]  # plans[i] lacks every attribute
        w.total_beats = 8
        w.source = "weird"
        issues = validate_phrase_plan(w, total_beats=8)  # type: ignore[arg-type]
        # We don't care *what* it returns, only that it returns a list.
        assert isinstance(issues, list)


# ---------------------------------------------------------------------------
# compute_phrase_bonus
# ---------------------------------------------------------------------------

class TestComputePhraseBonus:
    def _plan(self, **kw):
        defaults = dict(
            phrase_id=0, start_beat=0, end_beat=7,
            phrase_role="opening",
            target_cadence=None, target_function=None,
            strategy_hint={},
        )
        defaults.update(kw)
        return make_phrase(**defaults)

    def test_plan_set_none_returns_zero(self):
        assert compute_phrase_bonus(None, 0, MockChord("C", "major"), MockKey("C", "major")) == 0.0

    def test_beat_out_of_range_returns_zero(self):
        p = self._plan()
        ps = make_plan_set([p], total_beats=8, source="user")
        # beat=99 not in plan's range
        assert compute_phrase_bonus(ps, 99, MockChord("C", "major"), MockKey("C", "major")) == 0.0

    def test_chord_none_returns_zero(self):
        p = self._plan()
        ps = make_plan_set([p], total_beats=8, source="user")
        assert compute_phrase_bonus(ps, 0, None, MockKey("C", "major")) == 0.0  # type: ignore[arg-type]

    def test_key_none_returns_zero(self):
        p = self._plan()
        ps = make_plan_set([p], total_beats=8, source="user")
        assert compute_phrase_bonus(ps, 0, MockChord("C", "major"), None) == 0.0  # type: ignore[arg-type]

    def test_pac_target_tonic_at_last_beat_gives_positive(self):
        p = self._plan(phrase_role="concluding", target_cadence="PAC")
        ps = make_plan_set([p], total_beats=8, source="user")
        # Rule 1: +0.5
        # Rule 5: would not fire (role is concluding, not opening)
        # Rule 6: would not fire (beat == end_beat)
        bonus = compute_phrase_bonus(
            ps, beat=7, chord=MockChord("C", "major"), key=MockKey("C", "major"),
        )
        assert bonus == pytest.approx(0.5)

    def test_target_function_d_with_dominant_gives_positive(self):
        p = self._plan(phrase_role="continuation", target_function="D")
        ps = make_plan_set([p], total_beats=8, source="user")
        bonus = compute_phrase_bonus(
            ps, beat=2, chord=MockChord("G", "major", kind="triad"), key=MockKey("C", "major"),
        )
        assert bonus == pytest.approx(0.3)

    def test_chord_in_chord_preference_gives_positive(self):
        p = self._plan(phrase_role="continuation",
                       strategy_hint={"chord_preference": ["Dm"]})
        ps = make_plan_set([p], total_beats=8, source="user")
        bonus = compute_phrase_bonus(
            ps, beat=3, chord=MockChord("D", "minor"), key=MockKey("C", "major"),
        )
        assert bonus == pytest.approx(0.2)

    def test_chord_in_avoid_gives_negative(self):
        p = self._plan(phrase_role="continuation",
                       strategy_hint={"avoid_chord": ["viidim"]})
        ps = make_plan_set([p], total_beats=8, source="user")
        # Force the chord's figure() to a string that starts with the
        # avoid-list entry.  The bonus rule uses ``chord_sym.startswith(a)``
        # so this is the cleanest match.
        bonus = compute_phrase_bonus(
            ps, beat=3,
            chord=MockChord("B", "diminished", figure="viidim"),
            key=MockKey("C", "major"),
        )
        # Rule 4 fires: -0.5
        # No other rule fires (chord is B dim, not tonic; not dominant in
        # C major — root_pc=11, tonic_pc=0, dominant_pc=7).
        assert bonus == pytest.approx(-0.5)

    def test_opening_role_with_tonic_chord_gives_positive(self):
        p = self._plan(phrase_role="opening")
        ps = make_plan_set([p], total_beats=8, source="user")
        bonus = compute_phrase_bonus(
            ps, beat=0, chord=MockChord("C", "major"), key=MockKey("C", "major"),
        )
        # Rule 5: +0.2 (opening + tonic)
        assert bonus == pytest.approx(0.2)

    def test_concluding_role_with_dominant_not_at_last_beat(self):
        p = self._plan(phrase_role="concluding", target_cadence="PAC")
        ps = make_plan_set([p], total_beats=8, source="user")
        # beat=6, last beat is 7 -> Rule 6 fires
        bonus = compute_phrase_bonus(
            ps, beat=6, chord=MockChord("G", "major", kind="seventh"),
            key=MockKey("C", "major"),
        )
        # Rule 6: +0.3
        assert bonus == pytest.approx(0.3)

    def test_combined_rules_clip_to_max(self):
        """When multiple positive rules fire, total is clipped to PHRASE_BONUS_MAX."""
        # PAC + opening (well, concluding role here) -> can't be both.
        # Build a plan that fires: target_function=D + chord_preference match
        # + opening role tonic.
        p = self._plan(
            phrase_role="opening",
            target_function="D",
            strategy_hint={"chord_preference": ["G"]},
        )
        ps = make_plan_set([p], total_beats=8, source="user")
        # G is dominant (V) of C, also in preference, also tonic? No, G != C
        # So expected: rule 2 (+0.3) + rule 3 (+0.2) + NOT rule 5 (chord not tonic) = 0.5
        bonus = compute_phrase_bonus(
            ps, beat=2, chord=MockChord("G", "major"), key=MockKey("C", "major"),
        )
        assert bonus == pytest.approx(0.5)
        assert bonus <= PHRASE_BONUS_MAX

    def test_avoid_and_preference_cancel_below(self):
        """A chord in both avoid and preference: avoid wins (more negative)."""
        p = self._plan(
            strategy_hint={"chord_preference": ["G"], "avoid_chord": ["G"]},
        )
        ps = make_plan_set([p], total_beats=8, source="user")
        bonus = compute_phrase_bonus(
            ps, beat=2, chord=MockChord("G", "major"), key=MockKey("C", "major"),
        )
        # Rule 4 first: -0.5; Rule 3 later: +0.2. Net -0.3.
        assert bonus == pytest.approx(-0.3)

    def test_clipped_to_bonus_max(self):
        """Even with all rules firing, total is clipped to PHRASE_BONUS_MAX."""
        # Build a plan that fires: rule 1 (PAC + tonic at last beat = +0.5)
        # PLUS rule 3 (chord matches multiple preference entries, each +0.2).
        # Use nested strings so startswith() matches multiple times.
        p = self._plan(
            phrase_role="concluding", target_cadence="PAC",
            strategy_hint={"chord_preference": ["Cmaj", "Cma", "Cm"]},
        )
        ps = make_plan_set([p], total_beats=8, source="user")
        bonus = compute_phrase_bonus(
            ps, beat=7,
            # "Cmaj7" starts with "Cmaj", "Cma", and "Cm" -> 3 matches.
            chord=MockChord("C", "major", figure="Cmaj7"),
            key=MockKey("C", "major"),
        )
        # rule 1 = +0.5; rule 3 = +0.2 * 3 = +0.6; total = 1.1 -> clip to 1.0
        assert bonus == pytest.approx(PHRASE_BONUS_MAX)
        assert bonus == 1.0

    def test_never_crashes_on_garbage_chord(self):
        p = self._plan()
        ps = make_plan_set([p], total_beats=8, source="user")
        class BrokenChord:
            degree = 42  # wrong type
        # Must not raise.
        bonus = compute_phrase_bonus(ps, 0, BrokenChord(), MockKey("C", "major"))  # type: ignore[arg-type]
        assert isinstance(bonus, float)

    def test_never_crashes_on_garbage_key(self):
        p = self._plan()
        ps = make_plan_set([p], total_beats=8, source="user")
        class BrokenKey:
            pass
        bonus = compute_phrase_bonus(ps, 0, MockChord("C", "major"), BrokenKey())  # type: ignore[arg-type]
        assert isinstance(bonus, float)


# ---------------------------------------------------------------------------
# auto_plan_phrases
# ---------------------------------------------------------------------------

class TestAutoPlanPhrases:
    def test_eight_measures_yields_two_4_measure_phrases(self):
        melody = [[None] * 4 for _ in range(8)]
        ps = auto_plan_phrases(melody, MockKey("C", "major"),
                               measure_count=8, beats_per_measure=4)
        assert ps.source == "auto"
        assert ps.total_beats == 32
        assert len(ps.plans) == 2
        # First is opening, last is concluding
        assert ps.plans[0].phrase_role == "opening"
        assert ps.plans[1].phrase_role == "concluding"
        assert ps.plans[1].target_cadence == "PAC"
        # Phrases cover the whole piece without overlap
        issues = validate_phrase_plan(ps, ps.total_beats)
        assert issues == [], issues

    def test_four_measures_yields_one_phrase(self):
        melody = [[None] * 4 for _ in range(4)]
        ps = auto_plan_phrases(melody, MockKey("C", "major"),
                               measure_count=4, beats_per_measure=4)
        assert len(ps.plans) == 1
        assert ps.plans[0].phrase_role == "concluding"
        assert ps.plans[0].target_cadence == "PAC"

    def test_six_measures_yields_three_2_measure_phrases(self):
        # 6 is divisible by 2 but not by 4 -> seg_measures=2
        melody = [[None] * 4 for _ in range(6)]
        ps = auto_plan_phrases(melody, MockKey("C", "major"),
                               measure_count=6, beats_per_measure=4)
        assert len(ps.plans) == 3
        assert ps.plans[0].phrase_role == "opening"
        assert ps.plans[1].phrase_role == "continuation"
        assert ps.plans[2].phrase_role == "concluding"

    def test_zero_dimensions_falls_back_to_placeholder(self):
        ps = auto_plan_phrases(None, MockKey("C", "major"),
                               measure_count=0, beats_per_measure=0)
        # Should still return *something* valid-shaped.
        assert ps.source == "auto"
        assert len(ps.plans) >= 1

    def test_phrase_ids_are_sequential(self):
        melody = [[None] * 4 for _ in range(8)]
        ps = auto_plan_phrases(melody, MockKey("C", "major"),
                               measure_count=8, beats_per_measure=4)
        ids = [p.phrase_id for p in ps.plans]
        assert ids == list(range(len(ps.plans)))

    def test_output_always_passes_validation(self):
        for mc in (1, 2, 3, 4, 5, 6, 7, 8, 12, 16):
            melody = [[None] * 4 for _ in range(mc)]
            ps = auto_plan_phrases(melody, MockKey("C", "major"),
                                   measure_count=mc, beats_per_measure=4)
            issues = validate_phrase_plan(ps, ps.total_beats)
            assert issues == [], f"mc={mc} produced issues: {issues}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class TestChordSymbolSafe:
    def test_returns_figure_if_provided(self):
        c = MockChord("C", "major", figure="I")
        assert _chord_symbol_safe(c) == "I"

    def test_falls_back_to_degree_quality(self):
        c = MockChord("C", "major")
        c._figure = None  # remove the figure override
        assert _chord_symbol_safe(c) == "C"

    def test_minor_chord(self):
        c = MockChord("A", "minor")
        c._figure = None
        assert _chord_symbol_safe(c) == "Am"

    def test_returns_none_on_broken(self):
        class B:
            pass
        assert _chord_symbol_safe(B()) is None


class TestIsTonicChord:
    def test_c_major_in_c_major(self):
        assert _is_tonic_chord(MockChord("C", "major"), MockKey("C", "major")) is True

    def test_a_minor_in_a_minor(self):
        assert _is_tonic_chord(MockChord("A", "minor"), MockKey("A", "minor")) is True

    def test_a_minor_in_c_major_is_not_tonic(self):
        # wrong root
        assert _is_tonic_chord(MockChord("A", "minor"), MockKey("C", "major")) is False

    def test_c_major_in_a_minor_is_not_tonic(self):
        # wrong quality (should be minor in a minor key)
        assert _is_tonic_chord(MockChord("C", "major"), MockKey("A", "minor")) is False

    def test_seventh_tonic_still_counted(self):
        # Cmaj7 is still tonic in C major
        assert _is_tonic_chord(MockChord("C", "major", kind="seventh"),
                               MockKey("C", "major")) is True


class TestIsDominantChord:
    def test_g_major_in_c_major(self):
        assert _is_dominant_chord(MockChord("G", "major"), MockKey("C", "major")) is True

    def test_g7_in_c_major(self):
        assert _is_dominant_chord(MockChord("G", "major", kind="seventh"),
                                  MockKey("C", "major")) is True

    def test_g_in_g_major_is_not_dominant_of_g(self):
        # G is the tonic of G major, not the dominant
        assert _is_dominant_chord(MockChord("G", "major"), MockKey("G", "major")) is False

    def test_g_minor_is_not_dominant(self):
        # V must be major quality
        assert _is_dominant_chord(MockChord("G", "minor"), MockKey("C", "major")) is False

    def test_d_major_in_g_major(self):
        # D is dominant of G
        assert _is_dominant_chord(MockChord("D", "major"), MockKey("G", "major")) is True
