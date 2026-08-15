"""
P21 — Phrase Planner Interface (final)

The phrase-planner module exposes:

* Two dataclasses — :class:`PhrasePlan` and :class:`PhrasePlanSet` —
  for describing phrase-level decisions (role, target cadence,
  target function, strategy hints).
* Four helpers — :func:`get_phrase_at_beat`,
  :func:`compute_phrase_bonus`, :func:`validate_phrase_plan`,
  :func:`auto_plan_phrases` — for the solver to query, score, and
  validate a plan.
* Two builders — :func:`make_phrase`, :func:`make_plan_set` — for
  ergonomic construction of plans from primitive arguments.
* Five public constants — :data:`PHRASE_BONUS_MAX`,
  :data:`PHRASE_BONUS_MIN`, :data:`PHRASE_ROLES`,
  :data:`CADENCE_TARGETS`, :data:`FUNCTION_TARGETS`.

The solver reads plans via this module (P21.4 integration) but
does NOT import any heavy data structure into the planning
module — the dependency direction is one-way.

Goals
-----
Give the per-beat beam search solver (solver.py) a *phrase-level*
hint layer so it can make decisions that span a whole musical
phrase, not just one beat at a time.

Design principles
-----------------
1.  A phrase plan is a HINT, never a hard constraint. The solver
    is free to ignore any part of the plan if it conflicts with
    voice-leading rules or phrase-level style profile.

2.  Default behaviour is identical to P0–P7.7 when
    ``phrase_plan=None``.  This is a strict compatibility
    requirement: all 160 existing tests must continue to pass
    without modification.

3.  No reference to Sposobin pedagogy.  Field names and roles are
    chosen to be self-explanatory, and ``strategy_hint`` is an
    open dict so future logic (P22+) can extend without schema
    changes.

4.  This file does not import ``solver`` — the dependency goes the
    other way. ``solver.py`` imports from here (P21.4 integration
    is complete).

5.  All helpers are defensive: if the plan is malformed, out of
    range, or missing fields, they return a safe default and
    never raise.

P21 status
----------
* P21.1 (audit solver gaps)              — done
* P21.2 (skeleton interface)             — done
* P21.3 (helper bodies + 56 unit tests)  — done
* P21.4 (solver integration + 0 regression) — done
* P21.5 (acceptance: 216/216 pass)       — done
* P21.6 (frontend phrase panel)          — deferred (UI work, not blocker)
* P21.7 (auto-plan quality assessment)   — deferred (no P22+ usage yet)

P22+ (曲式结构层) will sit ABOVE this module — it will own
multiple :class:`PhrasePlanSet` objects, the macro structure of
a piece, and key-modulation planning.  See P22 plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Public constants — exposed so P21.3+ solvers, tests, and UI can refer
# to them without magic numbers.  These are *hints*; the solver may use
# different values internally but the documented ranges must be honoured
# by ``compute_phrase_bonus``.
# ---------------------------------------------------------------------------

#: Maximum positive bonus ``compute_phrase_bonus`` may add to a voicing
#: score.  Kept below the K6/4 cadence bonus (+8.0 in solver.py) so a
#: phrase plan can never override a hard structural reward.
PHRASE_BONUS_MAX: float = 1.0

#: Maximum negative penalty (absolute value).  Kept small so a bad plan
#: never destroys a good voicings.
PHRASE_BONUS_MIN: float = -0.5

#: Recognised phrase-role labels.  These are solver-agnostic: they
#: describe *what kind of phrase this is*.  Future (P22+) may
#: extend this list with form-level roles.
PHRASE_ROLES: tuple[str, ...] = (
    "opening",       # phrase start — pool favours T / vi / ii
    "continuation",  # middle of a phrase — pool favours unstable chords
    "cadential",     # penultimate beat cluster — pool favours V / V7 / K6/4
    "concluding",    # final beat of a phrase — must end on target cadence
)

#: Recognised cadence targets.  Mirrors the labels already produced
#: by ``solver.detect_cadence``; new labels added to that function
#: should be appended here as well.
CADENCE_TARGETS: tuple[str, ...] = (
    "PAC",        # Perfect Authentic
    "IAC",        # Imperfect Authentic
    "HC",         # Half Cadence (ends on V)
    "Deceptive",  # V → vi
    "Plagal",     # IV → I
    "Phrygian",   # iv6 → V (in minor)
    "Lydian",     # II → I  (in major)
    "None",       # explicit "no cadence target" — distinct from None
)

#: Recognised functional targets.  These mirror the labels produced
#: by ``solver.function_of`` and the role-of-degree conventions
#: in Sposobin chapter organisation, but the *meaning* here is just
#: "what functional region is this phrase pointing at".
FUNCTION_TARGETS: tuple[str, ...] = (
    "T",   # tonic / subdominant area (i, vi, ii, IV)
    "S",   # subdominant (ii, IV)
    "D",   # dominant (V, V7, vii°)
    "TS",  # tonic-of-subdominant pivot
    "None",
)


# ---------------------------------------------------------------------------
# PhrasePlan — a single phrase's plan.
# ---------------------------------------------------------------------------

@dataclass
class PhrasePlan:
    """A single musical phrase, described in solver-agnostic terms.

    A phrase is a contiguous run of beats (one-indexed? no —
    zero-indexed throughout this project) with a single functional
    goal.  Plans must NOT overlap, and together they should cover
    the whole piece (see :class:`PhrasePlanSet`).

    All fields beyond ``phrase_id`` / ``start_beat`` / ``end_beat``
    are *hints* — solvers and planners may leave them ``None``.

    Attributes
    ----------
    phrase_id
        Stable identifier of the phrase within a plan set.
        0-indexed, unique, never reused.  Mostly a debugging /
        tracing aid; the solver keys off ``start_beat``.
    start_beat, end_beat
        Inclusive range of beats covered by this phrase, in
        *global beat index* of the whole piece (0-based).
        ``end_beat`` is inclusive — a 4-beat phrase occupying
        beats 0..3 has ``start_beat=0, end_beat=3, length_beats=4``.
    length_beats
        ``end_beat - start_beat + 1``.  Cached to make
        front-end display and validation cheap.
    phrase_role
        One of :data:`PHRASE_ROLES`.  Drives which chord pool is
        preferred in this region.  ``None`` means "no role hint".
    target_cadence
        One of :data:`CADENCE_TARGETS` or ``None``.  Tells the
        solver what cadence the planner expects to end this
        phrase with.  ``None`` means "no cadence target".
    target_function
        One of :data:`FUNCTION_TARGETS` or ``None``.  Higher-level
        than ``target_cadence``: "this phrase should end on a
        dominant-function chord" without specifying the exact
        cadence type.
    strategy_hint
        Open extension point.  Reserved keys (documented here so
        the solver and any future planner stay consistent):

        * ``"chord_preference"`` — list[str], chord symbols to
          weight positively in the pool
        * ``"avoid_chord"`` — list[str], chord symbols to
          remove from the pool
        * ``"cadence_strength"`` — float 0..1, how strictly
          the plan expects the target_cadence to be honoured
        * ``"max_jump_interval"`` — int (semitones), soft
          limit on melodic jumps
        * ``"voice_role_hint"`` — dict[str, str], per-voice
          roles (e.g. ``{"soprano": "cantabile"}``)
        * ``"rhythm_density"`` — str, reserved (P22+)

        Unknown keys are allowed and ignored by the solver.
    """

    phrase_id: int
    start_beat: int
    end_beat: int
    length_beats: int
    phrase_role: Optional[str] = None
    target_cadence: Optional[str] = None
    target_function: Optional[str] = None
    strategy_hint: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# PhrasePlanSet — the full phrase decomposition of a piece.
# ---------------------------------------------------------------------------

@dataclass
class PhrasePlanSet:
    """A complete phrase decomposition of a piece.

    Invariants (enforced by :func:`validate_phrase_plan`, NOT here
    so this dataclass stays a thin data holder):

    * ``plans`` is sorted by ``start_beat`` ascending.
    * Plans do not overlap.
    * ``plans[0].start_beat == 0``.
    * ``plans[-1].end_beat == total_beats - 1``.
    * Every beat in ``[0, total_beats)`` is covered by exactly one
      plan — i.e. the plans tile the piece.

    Attributes
    ----------
    plans
        Phrases in ``start_beat`` ascending order.
    total_beats
        Total number of beats in the piece.  Sanity-check anchor.
    source
        Where this plan came from.  Free-form, but expected values:

        * ``"user"``   — supplied by the user (UI form)
        * ``"auto"``   — produced by an auto-planner
        * ``"default"``— synthesised by the solver (single phrase)
    """

    plans: list[PhrasePlan]
    total_beats: int
    source: str = "default"


# ---------------------------------------------------------------------------
# Helpers — implemented in P21.3, consumed by the solver in P21.4.
# ---------------------------------------------------------------------------

def get_phrase_at_beat(
    plan_set: PhrasePlanSet,
    beat: int,
) -> Optional[PhrasePlan]:
    """Return the phrase covering ``beat``, or ``None``.

    Robust to out-of-range ``beat`` (returns ``None``, never
    raises).  The caller is expected to handle the ``None`` case
    the same as if ``plan_set`` were ``None`` — i.e. the solver
    gracefully degrades.

    Parameters
    ----------
    plan_set
        Plan set to query.  If ``None``, return ``None``.
    beat
        Global beat index (0-based).

    Returns
    -------
    PhrasePlan or None
        The phrase whose ``[start_beat, end_beat]`` contains
        ``beat``, or ``None`` if no phrase covers it.
    """
    # Linear scan with early termination: plans are sorted by
    # start_beat ascending, so once we see a plan that starts
    # after ``beat`` we can stop.  The number of plans per
    # piece is small (typically 2-8), so a linear scan is the
    # right complexity.
    if plan_set is None:
        return None
    if not isinstance(beat, int):
        return None
    for plan in plan_set.plans:
        if plan.start_beat <= beat <= plan.end_beat:
            return plan
        if plan.start_beat > beat:
            return None
    return None


def compute_phrase_bonus(
    plan_set: PhrasePlanSet,
    beat: int,
    chord: Any,           # solver.Chord — avoid hard import
    key: Any,              # solver.Key   — avoid hard import
) -> float:
    """Return a bonus in ``[PHRASE_BONUS_MIN, PHRASE_BONUS_MAX]``.

    The bonus is *additive* to the per-voicing score in
    ``solver.score_voicing``.  It expresses "how well does this
    chord fit the plan for this beat?".

    Contract
    --------
    * Range is **clipped** to ``[PHRASE_BONUS_MIN, PHRASE_BONUS_MAX]``.
    * ``plan_set is None`` → return ``0.0`` (no plan, no bonus).
    * ``beat`` out of range → return ``0.0``.
    * Any unexpected error → return ``0.0`` (the solver must
      not crash because the planner misbehaved).

    Hint rules (current P21.3 implementation, contract):

    1. ``target_cadence == "PAC"`` and ``chord`` is tonic in
       ``key`` and ``beat == plan.end_beat`` → **+0.5**
    2. ``target_function == "D"`` and ``chord`` is dominant in
       ``key`` → **+0.3**
    3. ``chord`` is in ``strategy_hint["chord_preference"]`` →
       **+0.2 per match**
    4. ``chord`` is in ``strategy_hint["avoid_chord"]`` →
       **-0.5**
    5. ``phrase_role == "opening"`` and ``chord`` is tonic
       → **+0.2**
    6. ``phrase_role == "concluding"`` and ``chord`` is V/V7/V9
       and ``beat != plan.end_beat`` → **+0.3**
    7. Otherwise → 0.0
    """
    # The whole body is wrapped in try/except so a malformed
    # plan or a chord object missing the expected attributes
    # can never break the solver.  This is non-negotiable:
    # ``compute_phrase_bonus`` is called per-beat, per-beam
    # during beam search, so a single failure would derail
    # the whole search.
    try:
        if plan_set is None:
            return 0.0
        if not isinstance(beat, int):
            return 0.0
        if chord is None or key is None:
            return 0.0

        plan = get_phrase_at_beat(plan_set, beat)
        if plan is None:
            return 0.0

        bonus = 0.0

        # ---- hint inspection (defensive) ----
        hint = plan.strategy_hint if isinstance(plan.strategy_hint, dict) else {}
        pref = hint.get("chord_preference") or []
        avoid = hint.get("avoid_chord") or []
        chord_sym = _chord_symbol_safe(chord)

        # ---- chord-preference / avoid-chord ----
        # These two are independent of cadence/role; apply them
        # first so role-based rules don't shadow a hard avoid.
        if chord_sym is not None and avoid:
            if any(chord_sym == a or chord_sym.startswith(a) for a in avoid):
                bonus -= 0.5
        if chord_sym is not None and pref:
            for p in pref:
                if chord_sym == p or chord_sym.startswith(p):
                    bonus += 0.2

        # ---- Rule 1: target_cadence == PAC, chord is tonic, last beat ----
        if (
            plan.target_cadence == "PAC"
            and beat == plan.end_beat
            and _is_tonic_chord(chord, key)
        ):
            bonus += 0.5

        # ---- Rule 2: target_function == D, chord is dominant ----
        if (
            plan.target_function == "D"
            and _is_dominant_chord(chord, key)
        ):
            bonus += 0.3

        # ---- Rule 5: role == opening, chord is tonic ----
        if (
            plan.phrase_role == "opening"
            and _is_tonic_chord(chord, key)
        ):
            bonus += 0.2

        # ---- Rule 6: role == concluding, chord is V/V7/V9, NOT last beat ----
        if (
            plan.phrase_role == "concluding"
            and beat != plan.end_beat
            and _is_dominant_chord(chord, key)
        ):
            bonus += 0.3

        # ---- clip to documented range ----
        if bonus > PHRASE_BONUS_MAX:
            bonus = PHRASE_BONUS_MAX
        if bonus < PHRASE_BONUS_MIN:
            bonus = PHRASE_BONUS_MIN
        return bonus

    except Exception:
        # Honour the "never crash" contract.
        return 0.0


def validate_phrase_plan(
    plan_set: PhrasePlanSet,
    total_beats: int,
) -> list[str]:
    """Return a list of human-readable issues; empty = OK.

    Designed for diagnostic use (printed in the server log, or
    surfaced in the UI as a warning ribbon).  This function is
    intentionally **non-throwing** — even a completely broken
    plan should produce a list of strings, not an exception.

    Checks (current P21.3 implementation):

    * Plan list non-empty
    * Plans sorted by ``start_beat``
    * No overlap between adjacent plans
    * First plan starts at 0
    * Last plan ends at ``total_beats - 1``
    * Every beat in ``[0, total_beats)`` is covered
    * All enum-valued fields are in their allowed set
    * ``length_beats == end_beat - start_beat + 1`` for every plan
    * ``strategy_hint`` keys are within the documented set
      (warning, not error)

    Parameters
    ----------
    plan_set
        The plan set to validate.
    total_beats
        Total number of beats in the piece the plan is supposed
        to cover.

    Returns
    -------
    list[str]
        Empty if the plan is valid; otherwise a list of
        human-readable issue descriptions.
    """
    # Non-throwing: every check appends a string to the result
    # list and continues.  Even a totally broken plan must yield
    # *some* list, not raise.
    issues: list[str] = []
    try:
        if plan_set is None:
            issues.append("plan_set is None")
            return issues

        plans = plan_set.plans
        total = int(total_beats) if isinstance(total_beats, (int,)) else 0

        if not plans:
            issues.append("plan list is empty")
            return issues

        if total <= 0:
            issues.append(f"total_beats must be > 0, got {total}")
            return issues

        # ---- per-plan checks ----
        for i, p in enumerate(plans):
            # length_beats consistency
            expected_len = p.end_beat - p.start_beat + 1
            if p.length_beats != expected_len:
                issues.append(
                    f"plan[{i}] length_beats ({p.length_beats}) != "
                    f"end-start+1 ({expected_len})"
                )
            if p.start_beat < 0 or p.end_beat >= total:
                issues.append(
                    f"plan[{i}] out of range: "
                    f"[{p.start_beat},{p.end_beat}] not in [0,{total-1}]"
                )
            if p.end_beat < p.start_beat:
                issues.append(
                    f"plan[{i}] end_beat ({p.end_beat}) < start_beat ({p.start_beat})"
                )
            # enum-valued fields
            if p.phrase_role is not None and p.phrase_role not in PHRASE_ROLES:
                issues.append(
                    f"plan[{i}] phrase_role {p.phrase_role!r} not in {PHRASE_ROLES}"
                )
            if p.target_cadence is not None and p.target_cadence not in CADENCE_TARGETS:
                issues.append(
                    f"plan[{i}] target_cadence {p.target_cadence!r} not in {CADENCE_TARGETS}"
                )
            if p.target_function is not None and p.target_function not in FUNCTION_TARGETS:
                issues.append(
                    f"plan[{i}] target_function {p.target_function!r} not in {FUNCTION_TARGETS}"
                )
            # strategy_hint key set (warning, not error)
            if isinstance(p.strategy_hint, dict):
                _KNOWN_HINT_KEYS = {
                    "chord_preference", "avoid_chord", "cadence_strength",
                    "max_jump_interval", "voice_role_hint", "rhythm_density",
                }
                unknown = set(p.strategy_hint.keys()) - _KNOWN_HINT_KEYS
                if unknown:
                    issues.append(
                        f"plan[{i}] strategy_hint has unknown keys: {sorted(unknown)}"
                    )

        # ---- ordering / coverage checks ----
        # plans must be sorted by start_beat ascending
        for i in range(1, len(plans)):
            if plans[i].start_beat < plans[i - 1].start_beat:
                issues.append(
                    f"plans not sorted by start_beat: plan[{i}].start_beat "
                    f"({plans[i].start_beat}) < plan[{i-1}].start_beat "
                    f"({plans[i-1].start_beat})"
                )
                break

        # first plan must start at 0
        if plans[0].start_beat != 0:
            issues.append(
                f"first plan starts at {plans[0].start_beat}, expected 0"
            )

        # last plan must end at total-1
        if plans[-1].end_beat != total - 1:
            issues.append(
                f"last plan ends at {plans[-1].end_beat}, expected {total - 1}"
            )

        # adjacency: plan[i].start_beat == plan[i-1].end_beat + 1
        # (no overlap, no gap, sequential)
        for i in range(1, len(plans)):
            expected_start = plans[i - 1].end_beat + 1
            if plans[i].start_beat != expected_start:
                gap = plans[i].start_beat - expected_start
                if gap > 0:
                    issues.append(
                        f"gap between plan[{i-1}] (ends {plans[i-1].end_beat}) "
                        f"and plan[{i}] (starts {plans[i].start_beat}): "
                        f"{gap} uncovered beat(s)"
                    )
                else:
                    issues.append(
                        f"overlap between plan[{i-1}] (ends {plans[i-1].end_beat}) "
                        f"and plan[{i}] (starts {plans[i].start_beat}): "
                        f"{-gap} beat(s)"
                    )

    except Exception as e:
        # Last-resort safety net: a bug in the validator must not
        # crash the caller.  Report the exception as an issue.
        issues.append(f"validator crashed: {type(e).__name__}: {e}")

    return issues


def auto_plan_phrases(
    melody: Any,                # list[list[Note | None]] — avoid hard import
    key: Any,                   # solver.Key — avoid hard import
    measure_count: int,
    beats_per_measure: int,
) -> PhrasePlanSet:
    """Synthesise a default plan from raw melody + key.

    Current implementation is a simple rule-based segmenter
    (cut at every 2- or 4-measure boundary, mark middle
    phrases as "continuation", last as "concluding", first
    as "opening").  Future (P22+) may replace this with a
    more sophisticated approach (LBDM, GTTM-style grouping,
    LLM-suggested segmentation), but the *contract* of this
    function is fixed.

    Contract
    --------
    * Always returns a *valid* :class:`PhrasePlanSet` (no need
      to call :func:`validate_phrase_plan` on the result before
      passing it to the solver).
    * ``source="auto"``.
    * If the melody is empty or otherwise degenerate, returns
      a single "concluding" phrase covering all beats (degraded
      but valid plan).

    Parameters
    ----------
    melody
        2-D list shaped ``[measure][beat]`` of ``Note | None``,
        matching the convention used by ``solver.solve_melody``.
    key
        The home :class:`solver.Key` (or anything with a
        ``.tonic`` attribute) for the piece.
    measure_count, beats_per_measure
        Dimensions of the melody grid.  Must satisfy
        ``measure_count * beats_per_measure == total_beats``.

    Returns
    -------
    PhrasePlanSet
    """
    # Rule-based default segmenter.  P21.3 keeps it dead simple:
    # cut at fixed-measure boundaries, label roles by position.
    # P21.7 may replace this with a learned segmenter; the
    # *contract* (always returns a valid PhrasePlanSet with
    # source="auto") stays the same.
    try:
        mc = int(measure_count) if isinstance(measure_count, (int,)) else 0
        bpm = int(beats_per_measure) if isinstance(beats_per_measure, (int,)) else 0
        if mc < 0 or bpm <= 0:
            mc, bpm = 0, 0

        # Try to recover dimensions from melody if needed.
        if (mc == 0 or bpm == 0) and melody is not None:
            try:
                if mc == 0:
                    mc = len(melody)
                if bpm == 0 and mc > 0 and melody[0] is not None:
                    bpm = len(melody[0])
            except Exception:
                pass

        total = mc * bpm
        if total <= 0:
            # Truly degenerate: emit a single zero-length
            # placeholder so the caller still has *something*.
            zero = make_phrase(0, 0, 0, phrase_role="concluding",
                               target_cadence="None")
            return make_plan_set([zero], total_beats=0, source="auto")

        # Choose segment size: prefer 4-measure phrases (the
        # most common in tonal music), fall back to 2 if the
        # piece is very short.
        if mc >= 4 and mc % 4 == 0:
            seg_measures = 4
        elif mc >= 2 and mc % 2 == 0:
            seg_measures = 2
        else:
            seg_measures = mc  # one phrase for the whole thing

        plans: list[PhrasePlan] = []
        pid = 0
        m = 0
        while m < mc:
            m_end = min(m + seg_measures, mc)
            start_beat = m * bpm
            end_beat = m_end * bpm - 1
            is_first = (m == 0)
            is_last = (m_end == mc)
            if is_first and is_last:
                # Whole piece is one phrase
                role = "concluding"
                cadence = "PAC"
            elif is_first:
                role = "opening"
                cadence = None
            elif is_last:
                role = "concluding"
                cadence = "PAC"
            else:
                role = "continuation"
                cadence = None
            plans.append(
                make_phrase(
                    pid, start_beat, end_beat,
                    phrase_role=role,
                    target_cadence=cadence,
                )
            )
            pid += 1
            m = m_end

        return make_plan_set(plans, total_beats=total, source="auto")

    except Exception:
        # On any unexpected failure, return a single "concluding"
        # phrase covering the whole grid (degraded but valid).
        try:
            total = int(measure_count) * int(beats_per_measure)
        except Exception:
            total = 0
        if total <= 0:
            total = 1
        fallback = make_phrase(0, 0, total - 1, phrase_role="concluding",
                               target_cadence="PAC")
        return make_plan_set([fallback], total_beats=total, source="auto")


# ---------------------------------------------------------------------------
# Internal helpers — duck-typed chord/key inspection.  These
# never import ``solver`` so the interface module stays
# solver-agnostic.  They use ``getattr`` defensively so any
# object exposing ``.degree`` / ``.quality`` / ``.root_pc()``
# / ``.tonic_name`` / ``.tonic_pc`` / ``.mode`` will work,
# including test doubles in ``tests/test_p21_phrase_plan.py``.
# ---------------------------------------------------------------------------

def _normalize_quality(q: Any) -> Optional[str]:
    """Normalise a chord-quality string to a canonical short form.

    Accepts the long names ('major'/'minor'/'diminished'/'augmented')
    used in some textbooks and our test mocks, AND the short
    names used by the real ``solver.Chord`` ('maj'/'min'/'dim'/
    'aug'/'dom7'/'maj7'/'min7'/'half_dim7'/'dim7'/'dom9').

    Returns one of: 'maj', 'min', 'dim', 'aug', 'dom7', 'maj7',
    'min7', 'half_dim7', 'dim7', 'dom9', or the input string
    itself if unrecognised.  Returns ``None`` if input is
    not a string at all.
    """
    if not isinstance(q, str):
        return None
    ql = q.strip().lower()
    table = {
        "major": "maj", "maj": "maj",
        "minor": "min", "min": "min",
        "diminished": "dim", "dim": "dim",
        "augmented": "aug", "aug": "aug",
        "dominant7": "dom7", "dom7": "dom7", "dom7+5": "dom7",
        "major7": "maj7", "maj7": "maj7",
        "minor7": "min7", "min7": "min7",
        "half_dim7": "half_dim7", "half_diminished7": "half_dim7",
        "diminished7": "dim7", "dim7": "dim7",
        "dominant9": "dom9", "dom9": "dom9",
    }
    return table.get(ql, ql)


def _normalize_kind(k: Any) -> Optional[str]:
    """Normalise a chord-kind string.

    Accepts solver-style ('triad'/'seventh'/'ninth') and
    mock-style ('d7'/'d9').  Returns one of 'triad',
    'seventh', 'ninth', or the input if unrecognised.
    """
    if not isinstance(k, str):
        return None
    kl = k.strip().lower()
    if kl in ("triad", "d3", ""):
        return "triad"
    if kl in ("seventh", "d7", "7"):
        return "seventh"
    if kl in ("ninth", "d9", "9"):
        return "ninth"
    return kl


def _is_root_inversion(inv: Any) -> bool:
    """True iff the inversion is the root position.

    Accepts solver-style ('root') and mock-style ('I').
    """
    if not isinstance(inv, str):
        return False
    return inv.strip().lower() in ("root", "i", "")


def _get_root_pc(chord: Any, key: Any) -> Optional[int]:
    """Return chord's root pitch class, or None.

    Two calling conventions are accepted:
      - Real ``solver.Chord``: ``chord.root_pc(key)`` (mandatory key)
      - Test mocks: ``chord.root_pc()`` (no arg) or ``chord._pc`` attr
    """
    if chord is None:
        return None
    # Real interface: root_pc(key)
    try:
        rpc_attr = getattr(chord, "root_pc", None)
        if callable(rpc_attr):
            try:
                # Try with key first (real interface)
                rpc = rpc_attr(key)
                if rpc is not None:
                    return int(rpc)
            except TypeError:
                # Mock interface: no-arg
                try:
                    rpc = rpc_attr()
                    if rpc is not None:
                        return int(rpc)
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        pass
    # Fallback: direct _pc attribute (used in test mocks)
    direct = getattr(chord, "_pc", None)
    if direct is not None:
        try:
            return int(direct)
        except Exception:
            return None
    return None


def _chord_symbol_safe(chord: Any) -> Optional[str]:
    """Best-effort string label for a chord.

    Returns ``chord.figure()`` if available, else falls back to
    ``<degree><quality_short>[<inversion>]``.  Returns ``None``
    for anything unrecognisable.  Used to match against
    ``strategy_hint["chord_preference"]`` / ``"avoid_chord"``.

    Note: ``chord.degree`` may be either an int (solver's
    relative degree 1..7) or a string (mock's absolute note
    name).  Both shapes produce a sensible label.
    """
    try:
        fig = chord.figure
        if callable(fig):
            try:
                return str(fig())
            except Exception:
                pass
        deg = getattr(chord, "degree", None)
        qual_raw = getattr(chord, "quality", None)
        inv = getattr(chord, "inversion", None)
        kind_raw = getattr(chord, "kind", None)
        if deg is None or qual_raw is None:
            return None
        s = f"{deg}{_quality_short(qual_raw)}"
        kind = _normalize_kind(kind_raw)
        if kind and kind != "triad":
            s += f"({kind})"
        if inv is not None and not _is_root_inversion(inv):
            s += str(inv)
        return s
    except Exception:
        return None


def _quality_short(q: Any) -> str:
    """Compress quality name to a short symbol for chord labels.

    Returns the canonical short form via ``_normalize_quality``,
    then maps to the symbol used in the chord label.

    >>> _quality_short("major")
    ''
    >>> _quality_short("maj")
    ''
    >>> _quality_short("minor")
    'm'
    >>> _quality_short("diminished")
    'dim'
    """
    n = _normalize_quality(q)
    if n is None:
        return ""
    if n == "maj":
        return ""
    if n == "min":
        return "m"
    if n == "dim":
        return "dim"
    if n == "aug":
        return "aug"
    if n == "dom7":
        return "7"
    if n == "dom9":
        return "9"
    if n == "maj7":
        return "maj7"
    if n == "min7":
        return "m7"
    if n == "half_dim7":
        return "ø7"
    if n == "dim7":
        return "°7"
    return str(n)


def _is_tonic_chord(chord: Any, key: Any) -> bool:
    """True iff ``chord`` is the tonic of ``key`` (any inversion).

    Two compatibility strategies are used and combined with OR:

    1. **Relative-degree check** (real solver): if
       ``chord.degree == 1`` and quality matches ``key.mode``
       ('maj' for major, 'min' for minor).

    2. **Pitch-class check** (robust): ``chord.root_pc(key)``
       equals ``key.tonic_pc``, and the quality is the
       tonic-flavoured one ('maj' or 'min').

    Inversions of the tonic (6, 6/4, 7, etc.) still count
    as tonic — the goal is harmonic function, not chord
    kind.  The seventh chord on the tonic is also tonic.
    """
    try:
        qual = _normalize_quality(getattr(chord, "quality", None))
        if qual is None:
            return False
        mode = getattr(key, "mode", None)
        if mode not in ("major", "minor"):
            return False
        expected_qual = "maj" if mode == "major" else "min"
        # In major, both 'maj' and 'maj7' are tonic; in minor,
        # both 'min' and 'min7' are tonic.  Diminished tonic
        # (e.g. in harmonic minor) is NOT tonic by this rule.
        if qual not in (expected_qual, expected_qual + "7"):
            return False
        rpc = _get_root_pc(chord, key)
        tonic_pc = getattr(key, "tonic_pc", None)
        if rpc is None or tonic_pc is None:
            return False
        if int(rpc) != int(tonic_pc):
            return False
        # --- Path 1: relative degree (sanity check, not independent) ---
        try:
            deg = getattr(chord, "degree", None)
            if isinstance(deg, int) and deg == 1:
                return True
        except Exception:
            pass
        # --- Path 2: pitch class (already verified above) ---
        return True
    except Exception:
        return False


def _is_dominant_chord(chord: Any, key: Any) -> bool:
    """True iff ``chord`` is V / V7 / V9 in ``key`` (any inversion).

    Two compatibility strategies, OR'd:

    1. **Relative-degree check**: ``chord.degree == 5`` AND
       quality ∈ {'maj', 'dom7', 'dom9'}.

    2. **Pitch-class check**: ``chord.root_pc(key)`` equals
       ``(tonic_pc + 7) % 12`` AND quality is dominant-flavoured
       ('maj' / 'dom7' / 'dom9') AND kind is triad/seventh/ninth.

    Secondary dominants (``chord.target is not None``) are
    *included* — for the planner's purposes, V/V is also a
    dominant-function chord.
    """
    try:
        qual = _normalize_quality(getattr(chord, "quality", None))
        if qual is None:
            return False
        if qual not in ("maj", "dom7", "dom9"):
            return False
        rpc = _get_root_pc(chord, key)
        tonic_pc = getattr(key, "tonic_pc", None)
        if rpc is None or tonic_pc is None:
            return False
        dominant_pc = (int(tonic_pc) + 7) % 12
        if int(rpc) != dominant_pc:
            return False
        # --- Path 1: relative degree (sanity check, not independent) ---
        try:
            deg = getattr(chord, "degree", None)
            if isinstance(deg, int) and deg == 5:
                return True
        except Exception:
            pass
        # --- Path 2: pitch class + kind (already verified rpc above) ---
        kind = _normalize_kind(getattr(chord, "kind", None))
        if kind not in ("triad", "seventh", "ninth"):
            return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Convenience builders — used by tests and by the future UI to
# construct plans from primitive arguments without manually
# computing length_beats.  These are pure helpers, no logic.
# ---------------------------------------------------------------------------

def make_phrase(
    phrase_id: int,
    start_beat: int,
    end_beat: int,
    *,
    phrase_role: Optional[str] = None,
    target_cadence: Optional[str] = None,
    target_function: Optional[str] = None,
    strategy_hint: Optional[dict[str, Any]] = None,
) -> PhrasePlan:
    """Construct a :class:`PhrasePlan` and auto-fill ``length_beats``.

    This is the canonical way to build a phrase — direct
    construction of ``PhrasePlan`` is also allowed, but you must
    supply ``length_beats`` yourself in that case.
    """
    if end_beat < start_beat:
        raise ValueError(
            f"end_beat ({end_beat}) < start_beat ({start_beat})"
        )
    if phrase_role is not None and phrase_role not in PHRASE_ROLES:
        raise ValueError(
            f"phrase_role {phrase_role!r} not in {PHRASE_ROLES}"
        )
    if target_cadence is not None and target_cadence not in CADENCE_TARGETS:
        raise ValueError(
            f"target_cadence {target_cadence!r} not in {CADENCE_TARGETS}"
        )
    if target_function is not None and target_function not in FUNCTION_TARGETS:
        raise ValueError(
            f"target_function {target_function!r} not in {FUNCTION_TARGETS}"
        )
    return PhrasePlan(
        phrase_id=phrase_id,
        start_beat=start_beat,
        end_beat=end_beat,
        length_beats=end_beat - start_beat + 1,
        phrase_role=phrase_role,
        target_cadence=target_cadence,
        target_function=target_function,
        strategy_hint=dict(strategy_hint) if strategy_hint else {},
    )


def make_plan_set(
    plans: list[PhrasePlan],
    total_beats: int,
    source: str = "user",
) -> PhrasePlanSet:
    """Build a :class:`PhrasePlanSet` and assign sequential
    ``phrase_id`` if any are missing (set to ``-1``).

    No validation here — call :func:`validate_phrase_plan` to
    check invariants.
    """
    fixed: list[PhrasePlan] = []
    next_id = 0
    for p in plans:
        if p.phrase_id < 0:
            object.__setattr__(p, "phrase_id", next_id)
        next_id = max(next_id, p.phrase_id + 1)
        fixed.append(p)
    return PhrasePlanSet(plans=fixed, total_beats=total_beats, source=source)


__all__ = [
    "PHRASE_BONUS_MAX",
    "PHRASE_BONUS_MIN",
    "PHRASE_ROLES",
    "CADENCE_TARGETS",
    "FUNCTION_TARGETS",
    "PhrasePlan",
    "PhrasePlanSet",
    "make_phrase",
    "make_plan_set",
    "get_phrase_at_beat",
    "compute_phrase_bonus",
    "validate_phrase_plan",
    "auto_plan_phrases",
]
