"""
Sposobin (И. Способин) 《和声学教程》aligned 4-part harmony solver — P0.

P0 scope (per phased plan, strictly following the textbook):
  * 5 triads in major (I, IV, V, ii, vi), 4 triads in minor (i, iv, V, VI)
  * Voice ranges (SATB)
  * Hard constraints: parallel 5th / 8ve, voice crossing, leading-tone resolution
  * Soft scoring: common-tone retention, smooth voice leading, doubling rules
  * Cadence detection: PAC / IAC / HC / plagal
  * Greedy forward selection with top-K beam (K=3)
  * Any major / harmonic-minor key

Output schema (stable contract for downstream UI):
  {
    "solver": "spohr-v0",
    "summary": { "key", "timeSignature", "measureCount",
                 "qualify", "violations": [...] },
    "measures": [
      {
        "number": 1,
        "beats": [
          { "beat": 1, "offset": 0.0, "duration": 1.0,
            "soprano": "C5", "alto": "E4", "tenor": "G4", "bass": "C3",
            "roman": "I", "figure": "I", "inversion": "root",
            "doubled": "root", "function": "T",
            "explanation": "..." }
        ],
        "cadence": "PAC" | "IAC" | "HC" | "plagal" | null
      }
    ],
    "warnings": [...],
    "alternatives": [...]
  }

No magic.  Every rule cites Sposobin.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Iterable

# P21.4: phrase-plan hint layer.  Optional — solver works
# without it exactly as before.
try:
    from phrase_planner_interface import (
        PhrasePlanSet, compute_phrase_bonus, get_phrase_at_beat,
    )
    _PHRASE_PLANNER_AVAILABLE = True
except ImportError:  # pragma: no cover — defensive
    _PHRASE_PLANNER_AVAILABLE = False

# ---------------------------------------------------------------------------
# 1. Pitch primitives
# ---------------------------------------------------------------------------

# Pitch-class map.  We use sharp spelling internally; display in text below.
PC_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Flat-first spelling for nicer display (Bb instead of A#).  Both
# pc 10 (A#/Bb) and pc 11 (B) coexist; the display layer picks Bb.
PC_NAMES_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

# Chromatic scale degree offset (semitones above tonic) for the 7 diatonic
# degrees of a major scale.  This is the reference for every key.
MAJOR_DEGREE_OFFSET = (0, 2, 4, 5, 7, 9, 11)  # 1,2,3,4,5,6,7
# Natural minor: 1 2 b3 4 5 b6 b7.  b7 is at offset 10 (G in A minor,
# not G#).  Harmonic minor raises the 7th via `Key.degree_offset`.
MINOR_DEGREE_OFFSET = (0, 2, 3, 5, 7, 8, 10)


@dataclass(frozen=True, order=True)
class Note:
    """A concrete pitch.  `pc` is 0..11 (C=0), `oct` is scientific octave."""

    pc: int
    oct: int

    @classmethod
    def from_name(cls, name: str) -> "Note":
        # Accept forms like "C4", "C#4", "Db4", "Bb3".
        letter = name[0].upper()
        idx = 1
        if idx < len(name) and name[idx] in ("#", "b"):
            idx += 1
        oct_str = name[idx:]
        oct_v = int(oct_str)
        # Base pc by letter
        base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[letter]
        # Apply accidental (only one)
        if idx == 2:
            acc = name[1]
            if acc == "#":
                base = (base + 1) % 12
            elif acc == "b":
                base = (base - 1) % 12
        return cls(pc=base % 12, oct=oct_v)

    @property
    def midi(self) -> int:
        return (self.oct + 1) * 12 + self.pc

    @property
    def name(self) -> str:
        # Display uses flat-first spelling so Bb shows as Bb (not A#3).
        return f"{PC_NAMES_FLAT[self.pc]}{self.oct}"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


# ---------------------------------------------------------------------------
# 2. Key
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Key:
    """A tonal key.  `tonic_pc` is 0..11, `mode` is 'major' or 'minor'.
    `variant` is 'natural' (default), 'harmonic' (raised 7th, for V/V7/
    vii° in minor), or 'melodic' (raised 6th + 7th ascending, for
    I/II/III+/IV/V/vi°/vii° in minor).  Only meaningful when mode='minor'.
    """

    tonic_pc: int
    mode: str  # 'major' or 'minor'
    variant: str = "natural"  # 'natural' | 'harmonic' | 'melodic'

    def __post_init__(self):
        # P7.5: accept string tonic names (e.g. Key("C", "major")) for
        # friendlier call sites; convert to int pc 0..11 here.  P7.5
        # helper regression found that Key("C","major") silently stored
        # the string "C" in `tonic_pc`, which then crashed tonic_name
        # and relative().  Prefer Key.from_name(...) when parsing user
        # input — this fallback is for positional-arg call sites.
        if isinstance(self.tonic_pc, str):
            letter = self.tonic_pc[0].upper()
            base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[letter]
            if len(self.tonic_pc) == 2 and self.tonic_pc[1] == "#":
                base = (base + 1) % 12
            elif len(self.tonic_pc) == 2 and self.tonic_pc[1] == "b":
                base = (base - 1) % 12
            # frozen dataclass: must use object.__setattr__
            object.__setattr__(self, "tonic_pc", base)
        if not isinstance(self.tonic_pc, int):
            raise TypeError(
                f"Key.tonic_pc must be int 0..11, got {type(self.tonic_pc).__name__}: "
                f"{self.tonic_pc!r}.  Use Key.from_name('C') for name parsing."
            )
        if self.tonic_pc < 0 or self.tonic_pc > 11:
            raise ValueError(f"Key.tonic_pc out of range: {self.tonic_pc}")
        if self.mode not in ("major", "minor"):
            raise ValueError(f"Key.mode must be 'major' or 'minor', got {self.mode!r}")
        if self.variant not in ("natural", "harmonic", "melodic"):
            raise ValueError(f"Key.variant must be natural/harmonic/melodic, got {self.variant!r}")

    @classmethod
    def from_name(cls, name: str) -> "Key":
        # Accept:
        #   "C" / "c"  (Helmholtz: uppercase=uppercase major; lowercase=minor)
        #   "Am" / "am" / "a"  → A minor
        #   "A minor" / "a minor" / "A major" / "a major" / etc.
        #   "A harmonic" / "a h" → A harmonic minor (raised 7th)
        #   "A melodic"  / "a m" (after "A m" stripped) → ambiguous
        #   so we use "harm"/"mel" to disambiguate
        raw = name.strip()
        lower = raw.lower()
        # Detect variant BEFORE the stripping
        variant = "natural"
        if "harmonic" in lower:
            variant = "harmonic"
        elif "melodic" in lower:
            variant = "melodic"
        # Strip the variant word so the rest is parsed normally
        s = lower.replace("harmonic", "").replace("melodic", "").replace("natural", "").strip()
        # The original "minor"/"major" stripping still applies
        s = s.replace("minor", "m").replace("major", "").strip()
        # "Cm" / "C#m" / "Cbm" / "am" etc. all end with "m"
        explicit_minor = s.endswith("m")
        if explicit_minor:
            s = s[:-1]
        # Helmholtz convention: a single lowercase letter with no explicit
        # "M" suffix (e.g. "a", "f#") means minor.
        helmholtz_minor = (
            not explicit_minor
            and len(s) <= 2
            and raw[0].islower()
        )
        is_minor = explicit_minor or helmholtz_minor
        if not s:
            raise ValueError(f"empty key name: {name!r}")
        letter = s[0].upper()
        base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[letter]
        if len(s) == 2 and s[1] == "#":
            base = (base + 1) % 12
        elif len(s) == 2 and s[1] == "b":
            base = (base - 1) % 12
        return cls(tonic_pc=base % 12,
                   mode="minor" if is_minor else "major",
                   variant=variant if is_minor else "natural")

    @property
    def tonic_name(self) -> str:
        return f"{PC_NAMES_SHARP[self.tonic_pc]}"

    @property
    def degree_offsets(self) -> tuple[int, ...]:
        """Natural scale offsets.  For harmonic / melodic variants, use
        `degree_offset(degree)` instead — that one applies the raised
        6th / 7th adjustments."""
        return MINOR_DEGREE_OFFSET if self.mode == "minor" else MAJOR_DEGREE_OFFSET

    def degree_offset(self, degree: int) -> int:
        """Variant-aware semitone offset of `degree` from the tonic.

        For natural (or major): same as degree_offsets[degree - 1].
        For harmonic minor: degree 7 is raised by 1 semitone.
        For melodic minor (ascending): degrees 6 and 7 are raised.
        """
        base = self.degree_offsets[degree - 1]
        if self.mode != "minor":
            return base
        if self.variant == "harmonic" and degree == 7:
            return (base + 1) % 12
        if self.variant == "melodic" and degree in (6, 7):
            return (base + 1) % 12
        return base

    def scale_pitch_classes(self) -> list[int]:
        """All 7 scale degrees' pitch classes (variant-aware)."""
        return [(self.tonic_pc + self.degree_offset(d)) % 12
                for d in range(1, 8)]

    def degree_name(self, degree: int) -> str:
        """Roman degree name (uppercase major, lowercase minor)."""
        if self.mode == "major":
            return ["I", "II", "III", "IV", "V", "VI", "VII"][degree - 1]
        return ["i", "ii", "iii", "iv", "v", "vi", "vii"][degree - 1]

    # -- P7.5 helper: 调性关系 (Sposobin ch31 / ch35) --

    def parallel(self) -> "Key":
        """P7.5: 平行调 (同主音大小调, Sposobin ch31) — same tonic,
        opposite mode.  C major → c minor;  a minor → A major.
        Paving for P7.5 (ch35 uses 平行 as a close-relation target).
        """
        if self.mode == "major":
            return Key(tonic_pc=self.tonic_pc, mode="minor", variant="natural")
        return Key(tonic_pc=self.tonic_pc, mode="major", variant="natural")

    def relative(self) -> "Key":
        """P7.5: 关系调 (同中音大小调, Sposobin ch31) — tonic 3 semitones
        down (for major) or up (for minor), opposite mode.
        C major → a minor;  a minor → C major.
        """
        if self.mode == "major":
            # relative minor is 3 semitones below
            return Key(tonic_pc=(self.tonic_pc + 9) % 12, mode="minor",
                       variant="natural")
        # relative major is 3 semitones above
        return Key(tonic_pc=(self.tonic_pc + 3) % 12, mode="major",
                   variant="natural")

    def close_related_keys(self) -> list["Key"]:
        """P7.5: 一级关系调 (Sposobin ch31 / ch35) — 6 closely-related keys
        used for the most common modulations:

        For major key (e.g. C major):
          - 上五度 (P5 up):    G major
          - 下五度 (P5 down):  F major
          - 大二度上 (M2 up):  D major
          - 大二度下 (M2 down): B♭ major
          - 关系小调 (relative minor):  a minor
          - 平行小调 (parallel minor):  c minor

        For minor key (e.g. a minor):
          - 上五度 / 下五度:  e minor / d minor
          - 大二度上 / 大二度下:  b minor / g minor
          - 关系大调:  C major
          - 平行大调:  A major

        Sposobin calls these "一级关系调" (first-level related keys).
        Paving for P7.5 (ch35: 到一级关系调的转调).
        """
        keys: list[Key] = []
        # 上五度 (P5 up)
        keys.append(Key(tonic_pc=(self.tonic_pc + 7) % 12, mode=self.mode))
        # 下五度 (P5 down)
        keys.append(Key(tonic_pc=(self.tonic_pc + 5) % 12, mode=self.mode))
        # 大二度上 (M2 up)
        keys.append(Key(tonic_pc=(self.tonic_pc + 2) % 12, mode=self.mode))
        # 大二度下 (M2 down) — e.g. C major → B♭ major
        keys.append(Key(tonic_pc=(self.tonic_pc + 10) % 12, mode=self.mode))
        # 关系 / 平行 (relative / parallel)
        keys.append(self.relative())
        keys.append(self.parallel())
        return keys

    def is_close_related_to(self, other: "Key") -> bool:
        """P7.5: True iff `other` is in `self.close_related_keys()`.
        Used to decide which modulations are "easy" (likely involve
        a common pivot chord) vs "hard" (need extended techniques).
        """
        if (self.tonic_pc, self.mode) == (other.tonic_pc, other.mode):
            return True   # same key
        return any((k.tonic_pc, k.mode) == (other.tonic_pc, other.mode)
                   for k in self.close_related_keys())

    def relationship_to(self, other: "Key") -> str:
        """P7.5: return a string describing the tonal relationship
        between `self` and `other`.  Used for tonal layout analysis
        (Sposobin ch31).  Returns one of:
          - 'same'            (same tonic + same mode)
          - 'parallel'        (same tonic, opposite mode = 平行)
          - 'relative'        (同中音大小调, opposite mode)
          - 'P5_up' / 'P5_down' / 'M2_up' / 'M2_down'
          - 'close'           (one of the above 5 types)
          - 'distant'         (any other relationship)
        """
        if (self.tonic_pc, self.mode) == (other.tonic_pc, other.mode):
            return "same"
        if (self.tonic_pc == other.tonic_pc
                and self.mode != other.mode):
            return "parallel"
        if self.relative() == other:
            return "relative"
        diff = (other.tonic_pc - self.tonic_pc) % 12
        if diff == 7:
            return "P5_up"
        if diff == 5:
            return "P5_down"
        if diff == 2:
            return "M2_up"
        if diff == 10:
            return "M2_down"
        if self.is_close_related_to(other):
            return "close"
        return "distant"


@dataclass(frozen=True)
class KeyChange:
    """P7.5: a modulation point in a melody.  Starting at measure
    `measure` (0-indexed), the local key becomes `key_name`.

    Used in `solve_melody(..., key_changes=[KeyChange(2, "G"), ...])`.
    Measures before the change still use the home key; measures at
    and after use the new key.  Sposobin ch34-35 says modulation
    usually has a pivot chord near the change point, but the basic
    change-of-key machinery is independent of pivot choice.
    """
    measure: int
    key_name: str

    def __post_init__(self):
        if not isinstance(self.measure, int) or self.measure < 0:
            raise ValueError(
                f"KeyChange.measure must be a non-negative int, got {self.measure!r}"
            )
        if not isinstance(self.key_name, str) or not self.key_name:
            raise ValueError(
                f"KeyChange.key_name must be a non-empty str, got {self.key_name!r}"
            )


# ---------------------------------------------------------------------------
# 3. Chord
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Chord:
    """A chord (triad or seventh).

    Parameters
    ----------
    degree : 1..7
    quality : for triads: 'maj' | 'min' | 'dim'
              for sevenths: 'dom7' (P1) | 'maj7' | 'min7' | 'half_dim7' | 'dim7' (P2+)
    inversion :
        triads:    'root' (5/3)  |  '6' (6/3)  |  '6/4'
        sevenths:  '7'   (7/5/3) | '6/5'      | '4/3'   | '2' (4/2)
    kind : 'triad' (default) or 'seventh'
    target : for secondary dominants (P2), the degree of the chord this
             chord tonicizes.  None for diatonic chords.  E.g., a
             V7/V chord has target=5 (resolves to V).
    """

    degree: int
    quality: str
    inversion: str
    kind: str = "triad"  # 'triad' | 'seventh' | 'ninth'
    target: int | None = None
    # P7.3: for "ninth" chords, the 9th is stored here (pitch class 0-11).
    # The 9th is computed by `ninth_pc(key)` based on degree, quality, key
    # variant, and target.  4-part writing omits one of the 5 chord tones
    # (typically the 5th, sometimes the root).  Sposobin ch23 (PDF p143).
    # Defaults to None (no 9th) for triad / seventh chords.
    ninth_pc_override: int | None = None

    # ---- chord-tone pitch classes in ROOT position (regardless of inversion) ---

    def root_pc(self, key: Key) -> int:
        return (key.tonic_pc + key.degree_offset(self.degree)) % 12

    def third_pc(self, key: Key) -> int:
        base = self.root_pc(key)
        if self.quality in ("maj", "dom7", "maj7", "dom9"):
            return (base + 4) % 12
        # P9.1: dom7+5 has major 3rd (the +5 is on the 5th, not the 3rd)
        if self.quality == "dom7+5":
            return (base + 4) % 12
        # P5: augmented triad (melodic minor III+) — major 3rd but
        # augmented 5th.
        if self.quality == "aug":
            return (base + 4) % 12
        # min, dim, min7, half_dim7, dim7 → minor third
        return (base + 3) % 12

    def fifth_pc(self, key: Key) -> int:
        base = self.root_pc(key)
        # P5: augmented triad → augmented 5th (8 semitones)
        if self.quality == "aug":
            return (base + 8) % 12
        # P9.1: dom7+5 (V7 with raised 5th — 副属和弦变音) → aug 5th
        if self.quality == "dom7+5":
            return (base + 8) % 12
        # dim triad / dim7 / half_dim7 → dim 5th (6 semitones)
        if self.quality in ("dim", "dim7", "half_dim7"):
            return (base + 6) % 12
        return (base + 7) % 12

    def seventh_pc(self, key: Key) -> int:
        """Seventh chord-tone (M/m/dim 7).  Only valid for kind='seventh' or kind='ninth'."""
        base = self.root_pc(key)
        if self.quality in ("dom7", "dom9", "dom7+5"):
            return (base + 10) % 12   # m7 (raised 5th doesn't change the 7th)
        if self.quality == "maj7":
            return (base + 11) % 12   # M7
        if self.quality == "min7":
            return (base + 10) % 12   # m7
        if self.quality == "half_dim7":
            return (base + 10) % 12   # m7
        if self.quality == "dim7":
            return (base + 9) % 12    # dim7
        return base                   # fallback

    def pitch_classes(self, key: Key) -> list[int]:
        """Pitch classes in root position, before inversion."""
        # P3 / P7.4: chromatic chords (augmented 6th, Neapolitan, DD aug6)
        # have pitch-class sets that don't fit the diatonic degree system.
        if self.quality in ("aug6_ger", "aug6_fr", "aug6_it"):
            return self._aug6_pcs(key)
        # P7.4: aug6_dd is the same chord as standard aug6 (Ger+6 form),
        # but used in the DD (pre-V) function.  Use the Ger+6 pcs.
        if self.quality == "aug6_dd":
            return self._aug6_pcs(key)
        if self.quality == "neapolitan":
            return self._neapolitan_pcs(key)
        if self.quality in ("modal_b6", "modal_b3", "modal_b7", "modal_iv"):
            return self._modal_pcs(key)
        if self.kind == "seventh":
            return [self.root_pc(key), self.third_pc(key),
                    self.fifth_pc(key), self.seventh_pc(key)]
        if self.kind == "ninth":
            # P7.3: 5-tone chord (root, 3, 5, 7, 9).  In 4-part writing
            # one tone is omitted.
            return [self.root_pc(key), self.third_pc(key),
                    self.fifth_pc(key), self.seventh_pc(key),
                    self.ninth_pc(key)]
        return [self.root_pc(key), self.third_pc(key), self.fifth_pc(key)]

    def ninth_pc(self, key: Key) -> int:
        """P7.3: pitch class of the 9th (relative to key's tonic).
        Sposobin ch23 (PDF p143, 例 23-318):
          - Natural major: 大 9 度 (M2 above root, +2 st).
          - 小调 (minor) 与 和声大调: 小 9 度 (m2 above root, +1 st).
        We follow the textbook strictly: minor mode always returns
        小 9 (= 1 st), regardless of variant.  Major always returns 大 9.
        Override via `ninth_pc_override` if set.
        """
        if self.ninth_pc_override is not None:
            return self.ninth_pc_override
        base = self.root_pc(key)
        if key.mode == "major":
            return (base + 2) % 12   # 大 9
        # Minor (any variant): 小 9
        return (base + 1) % 12

    def _aug6_dd_pcs(self, key: Key) -> list[int]:
        """P7.4 extension: DD 增六和弦 (含增六度的重属和弦, Sposobin ch30
        PDF p208 / 课本 p200).  After re-reading the chapter carefully,
        DD 增六 is the STANDARD augmented-6th chord (Ger+6, Fr+6, It+6)
        used in the DD (pre-V) function.  The bass is ♭6 of the home
        key (same as standard aug6).  The "DD" label indicates the
        function (pre-V), not a different chord.

        So this method is kept as an alias for the standard aug6 in
        the home key domain.  We preserve it as a separate quality
        for output labeling, but the pitch classes are identical to
        the home-key aug6 (the bass must be ♭6 of the home key per
        textbook example 30-450, 30-451).

        Reference: Sposobin ch30 "重属和弦中的变音" — lists 5 voicings
        of the same chord (增 6, 增 4/3, 倍增 4/3, 增 6/5, 倍增 6/5),
        all with the aug-6 interval between ♭VI and the raised tone
        (F# in c minor, F# in C major harmonic).
        """
        # Same as standard aug6 (Ger+6) — 4-tone: ♭6, 1, ♭3, #4 of home key
        tonic = key.tonic_pc
        b6 = (tonic + 8) % 12
        one = tonic
        b3 = (tonic + 3) % 12
        sh4 = (tonic + 6) % 12
        return [b6, one, b3, sh4]

    # -- P3: chromatic chord-tone sets --

    def _aug6_pcs(self, key: Key) -> list[int]:
        """Pitch classes of the augmented-6th chord in C major:

        ♭6, 1, [♭3 or 2], #4    (Sposobin §50)

        - Ger+6:  Ab, C, Eb, F#  (♭6 + 1 + ♭3 + #4)
        - Fr+6:   Ab, C, D,  F#  (♭6 + 1 + 2  + #4)
        - It+6:   Ab, C,    F#  (♭6 + 1      + #4)  — incomplete, 3 tones

        The bass MUST be ♭6 of I/i, and the chord resolves to V (or
        directly to I).  The ♭6 moves up by step to 5; the #4 moves
        down by step to 5 — outward expansion (Sposobin §51).
        """
        tonic = key.tonic_pc
        b6 = (tonic + 8) % 12   # ♭6 of I
        one = tonic
        sh4 = (tonic + 6) % 12  # #4 of I
        if self.quality == "aug6_ger":
            b3 = (tonic + 3) % 12   # ♭3 of I (minor 3rd above tonic)
            return [b6, one, b3, sh4]
        if self.quality == "aug6_fr":
            two = (tonic + 2) % 12   # 2 of I (major 2nd above tonic)
            return [b6, one, two, sh4]
        if self.quality == "aug6_it":
            return [b6, one, sh4]
        # P7.4: DD 增六 uses the Ger+6 form (♭6 + 1 + ♭3 + #4).
        if self.quality == "aug6_dd":
            b3 = (tonic + 3) % 12
            return [b6, one, b3, sh4]
        raise ValueError(f"unknown aug6 quality: {self.quality}")

    def _neapolitan_pcs(self, key: Key) -> list[int]:
        """N6 (Neapolitan sixth) = ♭II6 in C major: Db, F, Ab.

        Bass is the 3rd of ♭II (F in C major), giving ♭II6 in first
        inversion.  Always in 6/3 inversion; resolves to V (Sposobin
        §52).
        """
        tonic = key.tonic_pc
        b2 = (tonic + 1) % 12   # ♭2 of I
        fourth = (tonic + 5) % 12  # 4 of I (= 3rd of ♭II)
        b6 = (tonic + 8) % 12   # ♭6 of I (= 5th of ♭II)
        return [b2, fourth, b6]

    def _modal_pcs(self, key: Key) -> list[int]:
        """Modal-mixture triads (Sposobin §53): chords borrowed from
        the parallel minor (or, in the case of iv, the parallel
        minor's iv against a major tonic).

        In C major:
          ♭VI  = Ab major   = {Ab, C,  Eb}    = {(t+8) % 12, t, (t+3) % 12}
          ♭III = Eb major   = {Eb, G,  Bb}    = {(t+3) % 12, (t+7) % 12, (t+10) % 12}
          ♭VII = Bb major   = {Bb, D,  F}     = {(t+10) % 12, (t+2) % 12, (t+5) % 12}
          iv   = F minor    = {F,  Ab, C}     = {(t+5) % 12, (t+8) % 12, t}

        All are major or minor triads in the parallel-minor key, so
        they share the parallel-minor pcs (not the diatonic pcs).
        """
        tonic = key.tonic_pc
        if self.quality == "modal_b6":   # ♭VI major
            return [(tonic + 8) % 12, tonic, (tonic + 3) % 12]
        if self.quality == "modal_b3":   # ♭III major
            return [(tonic + 3) % 12, (tonic + 7) % 12, (tonic + 10) % 12]
        if self.quality == "modal_b7":   # ♭VII major
            return [(tonic + 10) % 12, (tonic + 2) % 12, (tonic + 5) % 12]
        if self.quality == "modal_iv":   # iv minor (borrowed)
            return [(tonic + 5) % 12, (tonic + 8) % 12, tonic]
        raise ValueError(f"unknown modal quality: {self.quality}")

    def bass_pitch_class(self, key: Key) -> int:
        """Pitch class of the bass after inversion."""
        # P3: chromatic chords — aug6 always has ♭6 in bass (no
        # inversion — it's already an inverted sonority built on ♭6).
        # N6 always has the 3rd of ♭II in bass (6/3 inversion).
        if self.quality in ("aug6_ger", "aug6_fr", "aug6_it"):
            return (key.tonic_pc + 8) % 12
        # P7.4: DD 增六 has ♭6 of home key in bass (same as standard aug6).
        if self.quality == "aug6_dd":
            return (key.tonic_pc + 8) % 12
        if self.quality == "neapolitan":
            return (key.tonic_pc + 5) % 12  # 3rd of ♭II = 4 of I
        if self.quality in ("modal_b6", "modal_b3", "modal_b7", "modal_iv"):
            # Modal-mixture bass uses the modal chord's pcs directly.
            pcs = self.pitch_classes(key)
            if self.inversion == "root":
                return pcs[0]
            if self.inversion == "6":
                return pcs[1]
            return pcs[2]
        if self.kind == "ninth":
            # P7.3: Sposobin ch23 says D9 几乎只用原位 (D9 is almost
            # only in root position).  We enforce root-position bass.
            return self.root_pc(key)
        if self.kind == "seventh":
            if self.inversion == "7":       # root in bass
                return self.root_pc(key)
            if self.inversion == "6/5":     # 3rd in bass
                return self.third_pc(key)
            if self.inversion == "4/3":     # 5th in bass
                return self.fifth_pc(key)
            if self.inversion == "2":       # 7th in bass
                return self.seventh_pc(key)
            return self.root_pc(key)
        # triad
        if self.inversion == "root":
            return self.root_pc(key)
        if self.inversion == "6":
            return self.third_pc(key)
        return self.fifth_pc(key)   # 6/4

    def roman_label(self, key: Key) -> str:
        # Case determined by quality (Sposobin convention).
        if self.quality == "maj":
            base = ["I", "II", "III", "IV", "V", "VI", "VII"][self.degree - 1]
        elif self.quality == "min":
            base = ["i", "ii", "iii", "iv", "v", "vi", "vii"][self.degree - 1]
        elif self.quality == "dim":
            base = ["i°", "ii°", "iii°", "iv°", "v°", "vi°", "vii°"][self.degree - 1]
        elif self.quality == "aug":
            # P5: augmented triad (melodic minor III+)
            base = ["I+", "II+", "III+", "IV+", "V+", "VI+", "VII+"][self.degree - 1]
        elif self.quality == "dom7":
            base = ["I7", "II7", "III7", "IV7", "V7", "VI7", "VII7"][self.degree - 1]
        elif self.quality == "maj7":
            base = ["Imaj7", "IImaj7", "IIImaj7", "IVmaj7",
                    "Vmaj7", "VImaj7", "VIImaj7"][self.degree - 1]
        elif self.quality == "min7":
            base = ["i7", "ii7", "iii7", "iv7", "v7", "vi7", "vii7"][self.degree - 1]
        elif self.quality == "half_dim7":
            base = ["iø7", "iiø7", "iiiø7", "ivø7", "vø7", "viø7", "viiø7"][self.degree - 1]
        elif self.quality == "dim7":
            base = ["i°7", "ii°7", "iii°7", "iv°7", "v°7", "vi°7", "vii°7"][self.degree - 1]
        elif self.quality == "dom9":
            # P7.3: D9 (属九) — applied to dominant function
            base = ["I9", "II9", "III9", "IV9", "V9", "VI9", "VII9"][self.degree - 1]
        elif self.quality == "aug6_ger":
            base = "Ger+6"
        elif self.quality == "aug6_fr":
            base = "Fr+6"
        elif self.quality == "aug6_it":
            base = "It+6"
        elif self.quality == "aug6_dd":
            # P7.4: DD 增六 — Sposobin ch30.  We mark it as "DDaug6" to
            # distinguish from regular aug6 (Ger+6, Fr+6, It+6).
            base = "DDaug6"
        elif self.quality == "neapolitan":
            base = "N6"
        elif self.quality == "modal_b6":
            base = "bVI"
        elif self.quality == "modal_b3":
            base = "bIII"
        elif self.quality == "modal_b7":
            base = "bVII"
        elif self.quality == "modal_iv":
            base = "iv"
        else:
            base = "?"
        # Suffix for inversion
        suffix = ""
        if self.kind == "seventh":
            if self.inversion == "6/5":
                suffix = "6/5"
            elif self.inversion == "4/3":
                suffix = "4/3"
            elif self.inversion == "2":
                suffix = "4/2" if "7" in base else "2"
        elif self.kind == "ninth":
            # P7.3: D9 is almost always in root position (Sposobin
            # ch23), so no inversion suffix.
            suffix = ""
        else:
            if self.inversion == "6":
                suffix = "6"
            elif self.inversion == "6/4":
                suffix = "6/4"
        # Secondary dominant notation: V7/x → "V7/x" or "V7/ii" (target letter)
        if self.target is not None and self.target != 1:
            # Use the TARGET chord's roman letter, uppercased
            target_letter = ["I", "II", "III", "IV", "V", "VI", "VII"][self.target - 1]
            if self.quality == "dom9":
                return f"V9/{target_letter}{suffix}"
            return f"V7/{target_letter}{suffix}"
        if self.target is not None and self.target == 1 and self.quality in ("dom7", "dom9"):
            # V7/I is just V7; V9/I is just V9.
            return base + suffix
        return base + suffix

    def figure(self, key: Key) -> str:
        """Numeric figured bass."""
        if self.kind == "ninth":
            # P7.3: D9 in root position = "9" figured bass.
            return "9"
        if self.kind == "seventh":
            if self.inversion == "7":
                return "7"
            if self.inversion == "6/5":
                return "6/5"
            if self.inversion == "4/3":
                return "4/3"
            if self.inversion == "2":
                return "4/2"
            return "7"
        # triad
        if self.inversion == "root":
            return "5/3"
        if self.inversion == "6":
            return "6/3"
        return "6/4"


# ---------------------------------------------------------------------------
# 4. Voice ranges (SATB) — Sposobin textbook, p.~28 of 高等教育出版社中译本
# ---------------------------------------------------------------------------

VOICE_RANGES = {
    # P18.5: Soprano high extended to D6 to accommodate user's C6/D6
    # accidentals in the staff editor.  Sposobin's textbook high is
    # C6, but D6 appears in some exercises (high lyric soprano) and we
    # don't want the solver to 422 the user when they hit D6.
    # Soprano low kept at A3 (B3 occasionally appears below the staff).
    "soprano": (Note.from_name("A3"), Note.from_name("D6")),
    "alto":    (Note.from_name("G3"), Note.from_name("E5")),
    "tenor":   (Note.from_name("C3"), Note.from_name("A4")),
    "bass":    (Note.from_name("E2"), Note.from_name("D4")),
}
VOICE_ORDER = ("soprano", "alto", "tenor", "bass")


def in_range(voice: str, note: Note) -> bool:
    lo, hi = VOICE_RANGES[voice]
    return lo.midi <= note.midi <= hi.midi


# ---------------------------------------------------------------------------
# 5. Voicing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Voicing:
    """SATB at one beat: four notes."""
    soprano: Note
    alto: Note
    tenor: Note
    bass: Note

    def notes(self) -> list[Note]:
        return [self.soprano, self.alto, self.tenor, self.bass]

    def by_voice(self) -> dict[str, Note]:
        return {"soprano": self.soprano, "alto": self.alto,
                "tenor": self.tenor, "bass": self.bass}


# ---------------------------------------------------------------------------
# 6. Pitch-class helpers
# ---------------------------------------------------------------------------


def pc_distance(a: int, b: int) -> int:
    """Smallest semitone distance between two pitch classes (0..6)."""
    d = abs(a - b) % 12
    return min(d, 12 - d)


def interval_semitones(lo: Note, hi: Note) -> int:
    """Signed semitones hi - lo (hi - lo in pitch space, signed by octave)."""
    return hi.midi - lo.midi


def interval_quality(semitones: int) -> str:
    """Classify 12-tone interval into Sposobin categories."""
    s = semitones % 12
    if s == 0:
        return "P1"   # perfect unison
    if s == 7:
        return "P5"
    if s == 12 or s == 0:
        return "P8"   # perfect octave (when fully counted)
    if s == 4 or s == 9:
        return "M3"   # major 3rd or minor 6th — consonant
    if s == 3 or s == 8:
        return "m3"   # minor 3rd or major 6th — consonant
    return "other"    # 2nds / 7ths / tritones


# ---------------------------------------------------------------------------
# 7. Hard constraints
# ---------------------------------------------------------------------------


def has_parallel(va: Voicing, vb: Voicing) -> list[str]:
    """Return list of violated parallels between two consecutive voicings.

    Sposobin §28: parallel perfect 5ths and 8ves are forbidden.  Parallel
    motion means BOTH voices move in the SAME direction by the same
    perfect interval.  Contrary motion (one up, one down) to a P5 or P8
    is permitted; oblique motion (one voice holds) to a P5 or P8 is
    permitted (no parallel because only one voice moved).

    A voicing held over (all four voices at the same pitch) is also not
    a parallel — there is no motion.
    """
    # If all four voices are at exactly the same midi value, no motion.
    if (va.soprano.midi == vb.soprano.midi
            and va.alto.midi == vb.alto.midi
            and va.tenor.midi == vb.tenor.midi
            and va.bass.midi == vb.bass.midi):
        return []
    issues: list[str] = []
    pairs = (("soprano", "alto"), ("soprano", "tenor"),
             ("soprano", "bass"), ("alto", "tenor"),
             ("alto", "bass"), ("tenor", "bass"))
    for upper, lower in pairs:
        u_a = va.by_voice()[upper].midi
        l_a = va.by_voice()[lower].midi
        u_b = vb.by_voice()[upper].midi
        l_b = vb.by_voice()[lower].midi

        # Voice motion direction (per voice).  Zero = held.
        u_delta = u_b - u_a
        l_delta = l_b - l_a
        # 0 means oblique; if both are non-zero and same sign, parallel motion.
        if u_delta == 0 or l_delta == 0:
            continue
        if (u_delta > 0) != (l_delta > 0):
            # contrary motion — not a parallel
            continue

        # Compute intervals (semitones from lower to upper).
        a_full = u_a - l_a
        b_full = u_b - l_b
        a_mod = a_full % 12
        b_mod = b_full % 12
        a_p = a_mod
        b_p = b_mod
        a_perf = a_mod == 0 or a_mod == 7
        b_perf = b_mod == 0 or b_mod == 7
        # Disambiguate unison (P1) from octave (P8): if mod 0 and full != 0,
        # it's a P8.
        if a_mod == 0 and a_full != 0:
            a_p = 12
        if b_mod == 0 and b_full != 0:
            b_p = 12
        if a_perf and b_perf and a_p == b_p:
            if a_p == 7:
                issues.append(f"parallel 5 between {upper}/{lower}")
            elif a_p == 12:
                issues.append(f"parallel 8 between {upper}/{lower}")
            elif a_p == 0:
                issues.append(f"unison doubling {upper}/{lower}")
    return issues


def has_voice_crossing(va: Voicing) -> list[str]:
    issues: list[str] = []
    ns = va.notes()
    # descending in MIDI must be S > A > T > B (strict: S > A and A > T and T > B)
    if not (va.soprano.midi > va.alto.midi > va.tenor.midi > va.bass.midi):
        # Be lenient about adjacent equal (doubled), but flag genuine crossing
        if va.soprano.midi < va.alto.midi:
            issues.append("soprano crosses alto")
        if va.alto.midi < va.tenor.midi:
            issues.append("alto crosses tenor")
        if va.tenor.midi < va.bass.midi:
            issues.append("tenor crosses bass")
    return issues


def has_leading_tone_violation(prev: Voicing, curr: Voicing, key: Key) -> list[str]:
    """Leading tone must resolve up by step to tonic in the same voice.

    The 7th scale degree (a half-step below tonic) is the leading tone in
    both major and harmonic-minor keys.

    No violation if the voice is held (no motion) — the leading tone is
    still there, but no resolution was required because the voice did not
    move (Sposobin §39 only requires the leading tone to resolve WHEN it
    moves).
    """
    # Held voicing: all four voices at the same pitch — no motion, no LT
    # resolution required.
    if (prev.soprano.midi == curr.soprano.midi
            and prev.alto.midi == curr.alto.midi
            and prev.tenor.midi == curr.tenor.midi
            and prev.bass.midi == curr.bass.midi):
        return []
    lt_pc = (key.tonic_pc + 11) % 12  # 7th degree
    ton_pc = key.tonic_pc
    issues: list[str] = []
    for voice in VOICE_ORDER:
        p = prev.by_voice()[voice]
        c = curr.by_voice()[voice]
        if p.midi == c.midi:
            # Voice held → no resolution required.
            continue
        if p.pc == lt_pc and c.pc != ton_pc:
            # The voice must move up by step.  Going down or sideways is
            # forbidden (Sposobin §39).
            issues.append(
                f"leading tone in {voice} does not resolve up to tonic "
                f"({p.name} → {c.name})"
            )
    return issues


def has_seventh_resolution_violation(
    prev: Voicing, prev_chord: Chord | None, curr: Voicing, curr_chord: Chord, key: Key,
) -> list[str]:
    """V7 / V7-derived chord's 7th must resolve down to a chord tone of the target.

    Sposobin §45: the chordal 7th (m7 for dom7 / min7; dim7 for dim7) is a
    dissonance that must resolve downward in the same voice.  The
    classical destination is the 3rd of the following chord.  In the
    simplest case V7 → I, the 7th (m7) goes down by step to the 3rd (M3)
    of I.  For secondary dominants V7/x → x, the 7th goes down to the
    3rd of x — which may be a 3rd or 2nd interval (not always a half
    step), but the rule is "down to a chord tone of the target".

    P2 fix: the "voice held = no motion needed" exception only applies
    when the chord is the SAME V7 (sustained).  When the chord changes,
    the 7th must move to a chord tone of the new chord — even if the
    same voice stays at the same pitch.  Otherwise a V7 can be
    sustained indefinitely without ever resolving, which is
    Sposobin-forbidden.
    """
    issues: list[str] = []
    if prev_chord is None or prev_chord.kind != "seventh":
        return issues
    if curr_chord is None or curr_chord.degree == 0:
        return issues
    # If both voicing and chord are identical, the chord is sustained
    # and no resolution is required (the 7th is still a chord tone of
    # the same V7).
    same_chord = _chord_eq(prev_chord, curr_chord)
    if (same_chord
            and prev.soprano.midi == curr.soprano.midi
            and prev.alto.midi == curr.alto.midi
            and prev.tenor.midi == curr.tenor.midi
            and prev.bass.midi == curr.bass.midi):
        return []

    prev_7th_pc = prev_chord.seventh_pc(key)
    curr_pcs = set(curr_chord.pitch_classes(key))

    for voice in VOICE_ORDER:
        pv = prev.by_voice()[voice]
        cv = curr.by_voice()[voice]
        if pv.pc != prev_7th_pc:
            continue
        # Voice had the 7th in prev.  Now:
        #   - if same chord, voice may be held (the 7th is still a chord
        #     tone of the same V7).
        #   - if different chord, the 7th must move to a chord tone of
        #     the new chord, going down (or at most staying — but
        #     staying is unusual unless the new chord shares the pitch).
        if pv.midi == cv.midi and same_chord:
            continue
        if cv.midi > pv.midi:
            issues.append(
                f"chord 7th in {voice} moved up instead of down "
                f"({pv.name} → {cv.name})"
            )
            continue
        # If chord changed and pitch is held, that's NOT a resolution —
        # the 7th must move.  We require it to be a chord tone of the
        # new chord.
        if cv.pc not in curr_pcs:
            issues.append(
                f"chord 7th in {voice} did not resolve to a chord tone "
                f"of the target ({pv.name} → {cv.name})"
            )
    return issues


# ---------------------------------------------------------------------------
# 8. Doubling & chord-membership check
# ---------------------------------------------------------------------------


def is_chord_tone(note: Note, chord: Chord, key: Key) -> bool:
    pcs = set(chord.pitch_classes(key))
    return note.pc in pcs


# ---------------------------------------------------------------------------
# 5b. Non-chord tone (NCT) classification  (Sposobin §17-22)
# ---------------------------------------------------------------------------


def stepwise(a: Note, b: Note) -> bool:
    """True iff the two notes are a step (1 or 2 semitones) apart."""
    d = abs(a.pc - b.pc) % 12
    return d in (1, 2, 10, 11)   # half / whole step in either direction


def classify_soprano_nct(
    curr_mel: Note,
    chord: Chord,
    key: Key,
    *,
    prev_mel: Note | None,
    next_mel: Note | None,
    prev_chord: Chord | None,
    is_strong: bool,
) -> str | None:
    """If `curr_mel` is a chord tone of `chord`, return None (no NCT).
    Otherwise, attempt to classify it as a non-chord tone per Sposobin
    §17-22:

      - "passing"   (Sposobin §17): curr_mel is stepwise between two
                    chord tones of the same chord (prev and next melody
                    are both chord tones; curr is between them).  Only
                    on weak beats.
      - "neighbor"  (Sposobin §18): curr_mel is stepwise away from a
                    chord tone and back.  prev == next melody, both
                    chord tones.  Only on weak beats.
      - "suspension" (Sposobin §19-20): curr_mel is a chord tone of
                    `prev_chord` but NOT of `chord`.  It resolves down
                    by step to `next_mel`, which IS a chord tone of
                    `chord`.  Only on strong beats (the suspension
                    itself is the dissonance, on the accented beat).

    Returns None if no valid classification.
    """
    if is_chord_tone(curr_mel, chord, key):
        return None

    # 1. Suspension (strong beat, depends on prev_chord)
    if (is_strong and prev_chord is not None
            and next_mel is not None
            and is_chord_tone(curr_mel, prev_chord, key)
            and stepwise(curr_mel, next_mel)
            and is_chord_tone(next_mel, chord, key)):
        # Resolution should be down by step (curr_mel - next_mel)
        # in the natural direction.  Modulo wrap prevents the
        # classification when the wrap suggests a 7th up.
        diff = (curr_mel.pc - next_mel.pc) % 12
        if diff in (1, 11):   # 1 semitone up (or 11 = 1 down mod 12)
            return "suspension"

    # 2. Neighbor (weak beat, prev == next, both chord tones).
    # Checked BEFORE passing because the pattern prev == curr_step ==
    # next is the neighbor signature (Sposobin §18).  When prev and
    # next are the same, a stepwise decoration is by definition a
    # neighbor, not a "passing through" the same note.
    if (not is_strong and prev_mel is not None and next_mel is not None
            and prev_mel.pc == next_mel.pc
            and stepwise(prev_mel, curr_mel)
            and is_chord_tone(prev_mel, chord, key)):
        return "neighbor"

    # 3. Passing (weak beat, prev and next are both chord tones of chord)
    if (not is_strong and prev_mel is not None and next_mel is not None
            and stepwise(prev_mel, curr_mel)
            and stepwise(curr_mel, next_mel)
            and is_chord_tone(prev_mel, chord, key)
            and is_chord_tone(next_mel, chord, key)):
        return "passing"

    return None


def is_anticipation(curr_mel: Note, next_chord: Chord, key: Key) -> bool:
    """Sposobin §21 anticipation: melody at the current beat is a chord
    tone of the NEXT chord (a note 'anticipated' from the next chord
    appearing early).  Returns True iff curr_mel is a chord tone of
    next_chord.

    The caller decides whether to apply this (typically: weak beat +
    not already classified as passing/neighbor + chord tone of next).
    """
    return is_chord_tone(curr_mel, next_chord, key)


def is_escape_tone(
    prev_prev_mel: Note | None,
    prev_mel: Note,
    curr_mel: Note,
    key: Key,
    chord: Chord,
) -> bool:
    """Sposobin §22 escape tone (and ch43 跳进的辅助音 / 短倚音):
    a 3-step pattern where the middle note is a non-chord-tone and
    the surrounding notes are chord tones.  Two variants:

      A) "no preparation" (Sposobin §22 跳进进入):
         prev_prev (chord tone) → prev (NCT, LEAP) → curr (chord
         tone, step).  The leap + step go to a *different* chord tone.

      B) "no resolution"   (Sposobin ch43 跳进离去):
         prev_prev (chord tone) → prev (NCT, step) → curr (chord
         tone, LEAP).  Symmetric to (A): step + leap.

    In both variants:
      - prev is a non-chord-tone of `chord`.
      - curr is a chord tone of `chord`.
      - the leap is any interval > 2 semitones (a "跳进").
      - prev_prev != curr (so it's a leap-tone, not a repeated tone).

    Returns True iff either pattern matches.  The label is uniformly
    reported as "escape" in solve_melody.
    """
    if prev_prev_mel is None:
        return False
    d_AB = abs(prev_mel.pc - prev_prev_mel.pc) % 12
    d_AB = min(d_AB, 12 - d_AB)
    d_BC = abs(curr_mel.pc - prev_mel.pc) % 12
    d_BC = min(d_BC, 12 - d_BC)
    d_AC = abs(curr_mel.pc - prev_prev_mel.pc) % 12
    d_AC = min(d_AC, 12 - d_AC)
    # curr must be a chord tone, prev must be the escape (non-chord-tone).
    if not is_chord_tone(curr_mel, chord, key):
        return False
    if is_chord_tone(prev_mel, chord, key):
        return False
    # The two endpoints must be different (else we'd be saying the leap
    # is to the same chord tone, which is just a neighbor).
    if d_AC == 0:
        return False
    # Variant A: A→B is a leap (>2 st), B→C is a step (1-2 st).
    if d_AB > 2 and d_BC in (1, 2):
        return True
    # Variant B: A→B is a step (1-2 st), B→C is a leap (>2 st).
    if d_AB in (1, 2) and d_BC > 2:
        return True
    return False


# ---------------------------------------------------------------------------
# 5c. Multi-voice suspension  (Sposobin ch36-37 + ch44)
# ---------------------------------------------------------------------------
#
# Sposobin ch36-37 + ch44 covers suspensions in any voice, not just soprano:
#
#   ch36  "在一个声部中的有准备的延留音"  — single-voice suspension rules
#   ch37  "两个和三个声部中有准备的延留音" — double / triple suspension
#   ch44  "延留音的各种形式"               — variations on preparation /
#                                           resolution / no-prep
#
# A "suspension" requires:
#   1. The current note is NOT a chord tone of the current chord
#      (it is a dissonance on the accented beat).
#   2. The current note IS a chord tone of the previous chord
#      (preparation).
#   3. The NEXT note in the same voice IS a chord tone of the current chord
#      and is reached by step (typically down by step — Sposobin §20).
#
# Multiple voices can satisfy this simultaneously: a "double suspension"
# (二重延留音) suspends in two voices (e.g. alto + tenor, or soprano +
# alto), a "triple suspension" (三重延留音) in three.  Per Sposobin ch37
# the suspended voices typically move in parallel 3rds or 6ths, and they
# often resolve by contrary motion to a unison / octave in the bass.


def is_suspension_in_voice(
    voice_note: Note | None,
    prev_voice_note: Note | None,
    next_voice_note: Note | None,
    prev_chord: Chord | None,
    curr_chord: Chord,
    key: Key,
    is_strong: bool,
) -> bool:
    """P7.7: detect a suspension in any single voice.

    Returns True iff the current beat's note in this voice is a
    *dissonance on the accented beat* that was prepared as a chord tone
    of the previous chord and resolves stepwise (typically down) to a
    chord tone of the current chord.  See Sposobin §19-20 (suspension),
    applied to any of the 4 voices (Sposobin ch36-37, ch44).

    This is the voice-generalized version of the suspension test inside
    `classify_soprano_nct`.  It deliberately returns just the boolean;
    the wrapper `classify_voicing_ncts` aggregates across all 4 voices
    and reports how many suspensions happen simultaneously.
    """
    if voice_note is None or prev_voice_note is None or next_voice_note is None:
        return False
    if prev_chord is None:
        return False
    if not is_strong:
        return False
    if is_chord_tone(voice_note, curr_chord, key):
        return False
    if not is_chord_tone(voice_note, prev_chord, key):
        return False
    if not is_chord_tone(next_voice_note, curr_chord, key):
        return False
    if not stepwise(voice_note, next_voice_note):
        return False
    # Resolution should be DOWN by step.  (curr - next) mod 12 == 1 means
    # the next pitch is one semitone below the current; mod 12 == 11
    # means one semitone above (i.e. resolving up — Sposobin §19 still
    # allows this in some cases, but rare; we accept it as "stepwise
    # resolution" without filtering direction here — `classify_soprano_nct`
    # has the stricter down-only check, but for the multi-voice detector
    # we accept either direction because a stepwise resolution in either
    # direction is still a resolution).
    diff = (voice_note.pc - next_voice_note.pc) % 12
    return diff in (1, 11, 2, 10)   # accept half / whole in either direction


def count_suspension_layers(
    voicing: "Voicing",
    prev_voicing: "Voicing | None",
    next_voicing: "Voicing | None",
    prev_chord: Chord | None,
    curr_chord: Chord,
    key: Key,
    is_strong: bool,
) -> int:
    """P7.7: count how many voices are simultaneously suspending on the
    current beat.  Returns 0 (none), 1 (single), 2 (double — 二重延留音),
    or 3 (triple — 三重延留音).  Per Sposobin ch37 the four-voice
    suspension is rare and treated as "more about texture than harmony".
    """
    if prev_voicing is None or next_voicing is None or prev_chord is None:
        return 0
    n = 0
    for vname in ("soprano", "alto", "tenor", "bass"):
        v_curr = getattr(voicing, vname)
        v_prev = getattr(prev_voicing, vname)
        v_next = getattr(next_voicing, vname)
        if is_suspension_in_voice(
            v_curr, v_prev, v_next, prev_chord, curr_chord, key, is_strong
        ):
            n += 1
    return n


def classify_voicing_ncts(
    voicing: "Voicing",
    prev_voicing: "Voicing | None",
    next_voicing: "Voicing | None",
    prev_chord: Chord | None,
    curr_chord: Chord,
    next_chord: Chord | None,
    key: Key,
    is_strong: bool,
) -> dict:
    """P7.7: classify NCT type per voice + aggregate multi-voice
    suspension count for the current beat.

    Returns a dict:
      {
        "per_voice": {soprano, alto, tenor, bass}  — each is the NCT
                                                   label or "none"
        "multi_voice_suspension": "none" | "single" | "double" | "triple"
      }

    For now only SUSPENSION is reported per-voice (passing / neighbor
    in inner voices are common but not textbook-emphasized at the beat
    level; soprano is still classified by `classify_soprano_nct` which
    already handles the full NCT taxonomy).
    """
    per_voice = {"soprano": "none", "alto": "none", "tenor": "none", "bass": "none"}
    if not is_strong or prev_voicing is None or next_voicing is None or prev_chord is None:
        return {"per_voice": per_voice, "multi_voice_suspension": "none"}

    for vname in ("soprano", "alto", "tenor", "bass"):
        v_curr = getattr(voicing, vname)
        v_prev = getattr(prev_voicing, vname)
        v_next = getattr(next_voicing, vname)
        if is_suspension_in_voice(
            v_curr, v_prev, v_next, prev_chord, curr_chord, key, is_strong
        ):
            per_voice[vname] = "suspension"

    n_susp = sum(1 for v in per_voice.values() if v == "suspension")
    if n_susp >= 3:
        label = "triple"
    elif n_susp == 2:
        label = "double"
    elif n_susp == 1:
        label = "single"
    else:
        label = "none"
    return {"per_voice": per_voice, "multi_voice_suspension": label}


# ---------------------------------------------------------------------------
# 5d. Pivot chord  (Sposobin ch34 §5-6)
# ---------------------------------------------------------------------------
#
# Sposobin ch34 §5: 自然关系的转调 (diatonic modulation) is achieved via
# a "共同和弦" (common chord = "pivot chord" = 中介和弦).  This chord has
# ONE function in the home key (e.g. IV) and ANOTHER function in the
# target key (e.g. I), giving the "function shift" (功能的转移) that
# marks the modulation point.
#
# Sposobin ch34 §6 — how many common chords exist per relationship:
#
#   - 平行调 (parallel / relative):  e.g. C major ↔ a minor.  All 7
#     diatonic triads of one are also valid in the other (just with
#     different function labels).  C-E-G is I in C and i in a.
#
#   - 1 accidental apart:  e.g. C major ↔ F major or C ↔ G.  4 common
#     triads:  each tonic + each tonic's parallel.  C-E-G + A-C-E +
#     F-A-C + D-F-A.  (Each pair shares 2 pitches.)
#
#   - 4 accidentals apart:  e.g. C major ↔ F minor (or C ↔ c).  Only
#     2 common triads:  each tonic.  (C-E-G is in C major; F-Ab-C is
#     in F minor; only the parallel of one matches: c minor's tonic
#     is C-Eb-G which is not the same as C major's I.  So just the
#     parallel-c and C major's I are the only common ones.)
#
# Implementation: enumerate the candidate_chords pool of each key,
# then pair chords whose pitch-class sets are equal.  A "pivot" is
# any such pair; the two members are the home-key reading and the
# target-key reading of the SAME chord.


def _modulation_relationships(
    home_key: "Key",
    parsed_changes: "list[tuple[int, Key]]",
) -> list[dict]:
    """P11: per-key-change tonal relationship.

    Returns a list of {measure (0-indexed), fromKey, toKey, relationship}
    dicts.  relationship ∈ 'close' | 'distant' | 'parallel' | 'relative'
    | 'chromatic'.  'chromatic' = 6+ accidentals apart, requires
    enharmonic pivot (Sposobin ch35).
    """
    out: list[dict] = []
    prev_key = home_key
    for m_idx, kc_key in sorted(parsed_changes, key=lambda x: x[0]):
        # Accidentals distance: count sharps/flats in key sigs
        from_acc = _key_accidentals(prev_key)
        to_acc = _key_accidentals(kc_key)
        acc_diff = abs(to_acc - from_acc)
        if acc_diff >= 6:
            relationship = "chromatic"
        else:
            relationship = prev_key.relationship_to(kc_key)
        out.append({
            "measure": m_idx,
            "fromKey": f"{prev_key.tonic_name} {prev_key.mode}",
            "toKey": f"{kc_key.tonic_name} {kc_key.mode}",
            "relationship": relationship,
            "accidentalsDiff": acc_diff,
        })
        prev_key = kc_key
    return out


def _key_accidentals(key: "Key") -> int:
    """Return the number of accidentals in this key's signature.

    Positive for sharps, negative for flats.  Used by P11 to detect
    chromatic modulations (≥6 accidentals difference).
    """
    if key.mode == "major":
        # Standard circle of 5ths
        return MAJOR_TO_SHARPS.get(key.tonic_pc, 0)
    # minor: relative major sharps
    rel = key.tonic_pc + 3   # relative major is 3 semitones up
    return MAJOR_TO_SHARPS.get(rel % 12, 0)


MAJOR_TO_SHARPS = {
    0: 0,    # C
    7: 1,    # G
    2: 2,    # D
    9: 3,    # A
    4: 4,    # E
    11: 5,   # B
    6: 6,    # F#
    1: 7,    # C#
    5: -7,   # Db (5 flats)
    10: -6,  # Ab
    3: -5,   # Eb
    8: -4,   # Ab (4 flats)  -- same as 10? actually 8 = Ab too
}


def find_sequence_spans(measures: list[dict]) -> list[dict]:
    """P10 (Sposobin ch33 模进): post-detect sequence in voicing path.

    A sequence is 2+ consecutive beats whose chord-pattern (by Roman
    label, e.g. 'V6' or 'I') is identical AND whose bass is a parallel
    transposition by a fixed interval (the "step").  Returns a list of
    {startBeat, length, step, pattern} dicts.

    Sequence detector is post-hoc — beam search doesn't enforce
    sequences, but Sposobin exercises often contain sequences and the
    user wants them marked.
    """
    flat = []
    for m in measures:
        for b in m['beats']:
            flat.append((b['soprano'], b['bass'], b['roman']))
    n = len(flat)
    spans = []
    for k in range(2, n // 2 + 1):
        for i in range(n - 2 * k + 1):
            ref_pattern = [flat[i + j][2] for j in range(k)]
            next_pattern = [flat[i + k + j][2] for j in range(k)]
            if ref_pattern != next_pattern:
                continue
            try:
                ref_b_midi = Note.from_name(flat[i][1]).midi
                next_b_midi = Note.from_name(flat[i + k][1]).midi
                step = next_b_midi - ref_b_midi
            except Exception:
                continue
            if step == 0:
                continue
            spans.append({
                'startBeat': i,
                'length': k,
                'step': step,
                'pattern': ref_pattern,
            })
    return spans


def find_pivot_chords(
    home_key: Key,
    target_key: Key,
) -> list[tuple[Chord, Chord]]:
    """P7.5.2 (Sposobin ch34 §5-6): find common chords between two keys.

    Returns a list of (home_chord, target_chord) pairs where the two
    chords share the same pitch-class set.  The same physical chord
    has one function in the home key (e.g. "IV") and another in the
    target key (e.g. "I"), allowing it to bridge the two tonalities.

    For Sposobin's typical modulation relationships:
      - parallel (C ↔ c): 7 common triads
      - 1 accidental apart (C ↔ F or C ↔ G): 4 common triads
      - relative (C ↔ a): 7 common triads (same as parallel — same
        key signature, just different tonic)
      - 4 accidentals apart (C ↔ f or C ↔ c in some readings):
        2 common triads

    The pool is built from `candidate_chords(home_key)` and
    `candidate_chords(target_key)`, so secondary dominants, V7, and
    chromatic chords (aug6 / neapolitan) are also considered.  These
    rarely serve as pivots in Sposobin but the algorithm doesn't
    exclude them.
    """
    if home_key == target_key:
        return []   # no modulation needed
    home_chords = candidate_chords(home_key)
    target_chords = candidate_chords(target_key)
    # Cache target pcsets to avoid re-computing
    target_index: dict[frozenset[int], list[Chord]] = {}
    for tc in target_chords:
        key = frozenset(tc.pitch_classes(target_key))
        target_index.setdefault(key, []).append(tc)
    pivots: list[tuple[Chord, Chord]] = []
    for hc in home_chords:
        hc_pcs = frozenset(hc.pitch_classes(home_key))
        for tc in target_index.get(hc_pcs, []):
            pivots.append((hc, tc))
    return pivots


def get_target_key_pivots(
    home_key: Key,
    target_key: Key,
) -> list[Chord]:
    """P7.5.2: same as `find_pivot_chords` but returns just the
    target-key readings.  Used at the modulation boundary to restrict
    the chord pool of the boundary measure to chords that are valid
    in both keys.

    Returns: list of target_key Chord objects (in target-key spelling).
    """
    return [tc for (_hc, tc) in find_pivot_chords(home_key, target_key)]


def doubled_degree(voicing: Voicing, chord: Chord, key: Key) -> str:
    """Which chord-tone role (root/third/fifth/seventh) is doubled.

    Counts pitch-class occurrences across all 4 voices and returns the role
    that appears most often (only meaningful when count >= 2).  Seventh
    chords can naturally double the root (5 voices, 4 chord tones → one
    must be doubled).

    For chromatic chords (aug6, neapolitan) we use the chord's actual
    pitch classes, not the diatonic-degree pcs (which would be wrong
    for N6 etc.).
    """
    if chord.quality in ("aug6_ger", "aug6_fr", "aug6_it",
                        "neapolitan"):
        # Chromatic: use the chord's actual pcs and label them by
        # interval position from the bass.
        chord_pcs = chord.pitch_classes(key)
        # For aug6, the first pc is ♭6 (bass), second is 1, third is
        # the variable one (♭3 / 2 / omitted), fourth is #4.  We
        # assign role by index: 0=root(=♭6), 1=third(=1), 2=fifth,
        # 3=seventh(=#4).
        # For N6 (3 pcs): 0=root(=♭2), 1=third(=4 of I=3rd of ♭II),
        # 2=fifth(=♭6 of I=5th of ♭II).  Index 2 = fifth.
        if len(chord_pcs) == 4:
            roles = ["root", "third", "fifth", "seventh"]
        elif len(chord_pcs) == 3:
            roles = ["root", "third", "fifth"]
        else:
            roles = [f"pc{i}" for i in range(len(chord_pcs))]
        role_of_pc = {pc: roles[i] for i, pc in enumerate(chord_pcs)}
        counts: dict[str, int] = {r: 0 for r in roles}
        for n in voicing.notes():
            role = role_of_pc.get(n.pc)
            if role is not None:
                counts[role] += 1
        if max(counts.values()) < 2:
            return ""
        order = ("root", "fifth", "third", "seventh")
        for role in order:
            if role in counts and counts[role] >= 2:
                return role
        return ""
    # Diatonic path
    root_pc = chord.root_pc(key)
    third_pc = chord.third_pc(key)
    fifth_pc = chord.fifth_pc(key)
    role_of_pc: dict[int, str] = {
        root_pc: "root", third_pc: "third", fifth_pc: "fifth"}
    if chord.kind == "seventh":
        role_of_pc[chord.seventh_pc(key)] = "seventh"
    counts = {"root": 0, "third": 0, "fifth": 0, "seventh": 0}
    for n in voicing.notes():
        role = role_of_pc.get(n.pc)
        if role is not None:
            counts[role] += 1
    # No doubling if all roles appear at most once
    if max(counts.values()) < 2:
        return ""
    # Pick the role with the highest count; tiebreak: root > fifth > third > seventh
    order = ("root", "fifth", "third", "seventh")
    for role in order:
        if counts[role] >= 2:
            return role
    return ""


# ---------------------------------------------------------------------------
# 9. Soft scoring
# ---------------------------------------------------------------------------


# Doubling table per chord function — Sposobin §33
# T (tonic)        → root doubled
# S (subdominant)  → root or 5th doubled (NOT 3rd; doubling 3rd = "feminine"
#                    ending forbidden)
# D (dominant)     → root or 5th doubled (NOT 3rd; 3rd is the leading tone in
#                    minor and must be in an outer voice resolving up)
DOUBLING_PREFERENCE = {
    "T":  {"root": 1.0, "fifth": 0.6, "third": -1.0},
    "S":  {"root": 0.7, "fifth": 1.0, "third": -2.0},
    "D":  {"root": 0.7, "fifth": 1.0, "third": -1.5},
}


def function_of(degree: int, mode: str) -> str:
    if degree in (1, 3, 6):
        return "T"
    if degree in (2, 4):
        return "S"
    if degree in (5, 7):
        return "D"
    return "T"  # default


def score_voicing(
    prev: Voicing | None,
    prev_chord: Chord | None,
    voicing: Voicing,
    chord: Chord,
    key: Key,
    *,
    melody_note: Note | None,
    is_strong_beat: bool,
    is_cadence_beat: bool,
    is_c64_beat: bool = False,
    nct_type: str | None = None,
    preferred_doubling: str | None = None,
    # P21.4: phrase-plan hint layer.  Both default to "no plan",
    # so callers that don't care about phrases (P0-P8) see no
    # change at all.
    phrase_plan: "PhrasePlanSet | None" = None,
    beat_idx: int = 0,
) -> tuple[float, list[str]]:
    """Soft score (higher is better).  Hard constraints are checked
    separately in `check_voicing`.
    """
    notes = [("soprano", voicing.soprano), ("alto", voicing.alto),
             ("tenor", voicing.tenor), ("bass", voicing.bass)]
    score = 0.0
    parts: list[str] = []

    # 8.1 chord-membership (every voice must be a chord tone on a strong beat)
    for voice, n in notes:
        if is_chord_tone(n, chord, key):
            score += 1.0
        else:
            # P4: if the SOPRANO is a non-chord tone, the caller has
            # already classified it as a valid NCT (passing / neighbor /
            # suspension).  Skip the -5.0 penalty for the soprano and
            # let the NCT bonus below kick in instead.  Inner-voice
            # non-chord tones are still penalized on STRONG beats.
            if voice == "soprano" and nct_type is not None:
                continue
            # P4.5: allow inner-voice non-chord tones on WEAK beats
            # (alto / tenor passing, etc.) with a milder penalty.  Sposobin
            # §24 is strict on strong beats, lenient on weak.
            if voice in ("alto", "tenor") and not is_strong_beat:
                score -= 1.5   # mild penalty, not -5.0
                continue
            score -= 5.0
            parts.append(f"non-chord tone in {voice}: {n.name}")
    # P4: bonus for a valid NCT in the soprano.  Sposobin allows
    # these as melodic decoration on weak beats (passing, neighbor)
    # and as suspension on strong beats.  Reward so the solver
    # prefers them over skipping the beat.
    if nct_type == "passing":
        score += 1.5
    elif nct_type == "neighbor":
        score += 1.5
    elif nct_type == "suspension":
        score += 1.0

    # 8.2 voice range
    for voice, n in notes:
        if in_range(voice, n):
            score += 0.5
        else:
            score -= 100.0
            parts.append(f"{voice} out of range: {n.name}")

    # 8.3 soprano must be chord tone on cadence
    if is_cadence_beat and not is_chord_tone(voicing.soprano, chord, key):
        score -= 3.0
        parts.append("soprano not chord tone on cadence beat")

    # 8.4 doubling rule
    doubled = doubled_degree(voicing, chord, key)
    func = function_of(chord.degree, key.mode)
    pref = DOUBLING_PREFERENCE.get(func, {})
    if doubled:
        score += pref.get(doubled, 0.0) * 1.5
        if doubled == "third" and func in ("S", "D"):
            # Strong penalty — "feminine" / leading tone doubling
            score -= 3.0
            parts.append(f"doubled {doubled} of {func} chord (forbidden)")

    # 8.5 voice leading from previous
    if prev is not None:
        for voice, n in notes:
            p = prev.by_voice()[voice]
            d = abs(n.midi - p.midi)
            if d == 0:
                score += 0.4   # common tone — small reward
            elif d <= 2:
                score += 1.0   # step — best
            elif d <= 4:
                score += 0.0   # third
            elif d <= 7:
                score -= 0.3   # fifth
            else:
                score -= 1.5   # leap
        # Reward common-tone retention overall
        prev_pcs = [p.pc for p in prev.notes()]
        curr_pcs = [n.pc for n in voicing.notes()]
        common = len(set(prev_pcs) & set(curr_pcs))
        score += common * 0.3

        # Avoid leap-then-reverse (Sposobin §34)
        # If a voice leapt up, next motion should not immediately leap down.
        for voice, n in notes:
            p = prev.by_voice()[voice]
            d = n.midi - p.midi
            # We don't have next state here; that's checked at solve level.

    # 8.6 melody adherence
    if melody_note is not None:
        if voicing.soprano.midi == melody_note.midi:
            score += 5.0
        else:
            score -= 100.0   # mandatory: soprano is given melody
            parts.append(
                f"soprano {voicing.soprano.name} != melody {melody_note.name}"
            )

    # 8.6b melody-tone preference (Sposobin §30: melody notes should align
    # with chord roots / chord tones by priority).  If melody is a chord root,
    # the chord whose root matches is strongly favored.
    if melody_note is not None:
        # Modal-mixture chords get a small baseline nudge ONLY when
        # the melody is the modal root (so they can win against
        # the diatonic equivalent in the right context — P3.5
        # Sposobin §53).  When the melody is just a chord tone, the
        # diatonic IV / iii / vii / iv wins by default; this avoids
        # modal_iv stealing F5 from IV in textbook C-major contexts.
        if chord.quality in ("modal_b6", "modal_b3", "modal_b7", "modal_iv"):
            modal_root_pc = chord.pitch_classes(key)[0]
            if melody_note.pc == modal_root_pc:
                score += 0.4
        # For chromatic chords (modal, aug6, neapolitan), the "root"
        # is the first pc in the chord's pitch class set — NOT the
        # diatonic-degree root_pc.
        if chord.quality in ("modal_b6", "modal_b3", "modal_b7", "modal_iv",
                            "aug6_ger", "aug6_fr", "aug6_it",
                            "neapolitan"):
            chord_pcs = chord.pitch_classes(key)
            modal_root = chord_pcs[0]
            modal_third = chord_pcs[1] if len(chord_pcs) > 1 else None
            modal_fifth = chord_pcs[2] if len(chord_pcs) > 2 else None
            if melody_note.pc == modal_root:
                if chord.target is not None:
                    score += 2.5
                else:
                    score += 3.5
            elif modal_fifth is not None and melody_note.pc == modal_fifth:
                score += 0.8
            elif modal_third is not None and melody_note.pc == modal_third:
                score += 0.4
        else:
            if melody_note.pc == chord.root_pc(key):
                if chord.target is not None:
                    score += 2.5
                else:
                    score += 3.5
            elif melody_note.pc == chord.fifth_pc(key):
                score += 0.8
            elif melody_note.pc == chord.third_pc(key):
                score += 0.4

    # 8.7 cadence-friendly bass (V→I strong beat I, root position)
    if is_cadence_beat and chord.degree == 1 and chord.inversion == "root":
        score += 1.0

    # 8.7b cadential 6/4 bonus — I6/4 in the c64 slot is preferred
    # (Sposobin §46).  We don't have access to the slot here directly,
    # so we approximate: if the previous chord was I (the most common
    # cadential 6/4 prep), and this is I6/4 with a 5th-degree melody,
    # give a small bonus.
    # P7.3: D9 (ninth chord) prefers 9 in soprano per Sposobin ch23
    # ("D9 正确的排列应该使其根音与九音分处在不同的八度音区中").
    # When the melody is the 9th pc, give a strong bonus to encourage
    # the beam to pick the ninth chord (vs. V7).
    if (chord.kind == "ninth" and melody_note is not None
            and melody_note.pc == chord.ninth_pc(key)):
        score += 2.0
    if prev_chord is not None and _chord_eq(
            Chord(degree=prev_chord.degree, quality=prev_chord.quality,
                  inversion=prev_chord.inversion, kind=prev_chord.kind),
            prev_chord) and False:
        # This branch never executes; placeholder for future hook
        pass
    # 8.7c Cadential 6/4 bonus — applies only at the c64_beat slot
    # (Sposobin §46).  I6/4 with a melody tone that is also a chord tone
    # of V gets a strong bonus.  Outside the c64_beat this is irrelevant.
    if is_c64_beat and chord.degree == 1 and chord.inversion == "6/4":
        if melody_note is not None:
            v_chord = Chord(degree=5, quality="maj", inversion="root",
                            kind="triad")
            if is_chord_tone(melody_note, v_chord, key):
                score += 8.0
            else:
                score += 3.0
        else:
            score += 1.5

    # 8.8 Bass-stability preference (Sposobin §38: 稳定低音优先于频繁跳进)
    # Always reward keeping the bass on the same pitch as the previous beat.
    if prev is not None and voicing.bass.midi == prev.bass.midi:
        score += 1.0
        # If the chord is the same too, the reward is doubled
        if prev_chord is not None and _chord_eq(chord, prev_chord):
            score += 2.0

    # 8.9 chord-repetition bonus (Sposobin §38: harmonic rhythm should not
    # change every beat for stable melodies)
    if prev_chord is not None and _chord_eq(chord, prev_chord):
        # Same chord: also reward keeping inner voices close to where they were
        if prev is not None:
            for voice, n in notes:
                p = prev.by_voice()[voice]
                d = abs(n.midi - p.midi)
                if d == 0:
                    score += 0.6
                elif d <= 2:
                    score += 0.3
        # Same chord, same bass: best
        if prev is not None and voicing.bass.midi == prev.bass.midi:
            score += 0.5
        else:
            score += 0.2

    # 8.10 distinct-but-related chord: small reward for common tones between
    # the new chord and the previous one (helps Sposobin's "和声连接法").
    elif prev_chord is not None and prev is not None:
        prev_pcs = {n.pc for n in prev.notes()}
        curr_pcs = {n.pc for n in voicing.notes()}
        common = len(prev_pcs & curr_pcs)
        score += common * 0.4

    # P21.4 — phrase-plan hint bonus.
    # ``compute_phrase_bonus`` is already clipped to
    # [PHRASE_BONUS_MIN=-0.5, PHRASE_BONUS_MAX=+1.0] internally and
    # never raises (all exceptions are swallowed).  The bonus is
    # strictly smaller in magnitude than the K6/4 cadence bonus
    # (+8.0) so it cannot override hard structural rewards.
    if phrase_plan is not None and _PHRASE_PLANNER_AVAILABLE:
        try:
            score += compute_phrase_bonus(phrase_plan, beat_idx, chord, key)
        except Exception:
            # Defensive — bonus must never break the score pipeline.
            pass

    return score, parts


def _chord_eq(a: Chord, b: Chord) -> bool:
    return a.degree == b.degree and a.quality == b.quality and a.inversion == b.inversion


def check_voicing(
    prev: Voicing | None,
    prev_chord: Chord | None,
    voicing: Voicing,
    chord: Chord,
    key: Key,
) -> list[str]:
    """Return all hard-constraint violations (empty list == valid)."""
    errs: list[str] = []
    errs.extend(has_voice_crossing(voicing))
    if prev is not None:
        errs.extend(has_parallel(prev, voicing))
        errs.extend(has_leading_tone_violation(prev, voicing, key))
        errs.extend(has_seventh_resolution_violation(
            prev, prev_chord, voicing, chord, key))
    # P2: in a seventh chord, all 4 chord tones must be present
    # (Sposobin §45).  With 4 voices and 4 chord tones, one tone may
    # be doubled — but no chord tone may be entirely absent.
    # Catches voicings like (C5, E4, C4, G2) for C7 which omit Bb
    # (the 7th), and (Bb4, C4, E3, C3) for C7 which omits G.
    if chord.kind == "seventh":
        chord_pcs = set(chord.pitch_classes(key))
        voicing_pcs = {n.pc for n in voicing.notes()}
        missing = chord_pcs - voicing_pcs
        if missing:
            errs.append(
                f"7th chord {chord.roman_label(key)} is missing chord tone(s) "
                f"{sorted(missing)} — Sposobin §45 requires all 4 tones"
            )
    # P7.3: in a ninth chord, all 5 chord tones cannot fit in 4
    # voices — one tone (typically the 5th, sometimes the root)
    # is omitted.  Sposobin ch23 (PDF p143).  Allow exactly 1
    # missing chord tone; require the 9th to be present (textbook
    # standard: the 9 is the "color tone" that defines D9).
    if chord.kind == "ninth":
        chord_pcs = set(chord.pitch_classes(key))
        voicing_pcs = {n.pc for n in voicing.notes()}
        missing = chord_pcs - voicing_pcs
        ninth = chord.ninth_pc(key)
        if ninth in missing:
            errs.append(
                f"9th chord {chord.roman_label(key)} is missing the 9th tone "
                f"(pc {ninth}) — Sposobin ch23 requires the 9 in the voicing"
            )
        # Allow exactly 1 missing tone (the omitted 5th or root).
        if len(missing) > 1:
            errs.append(
                f"9th chord {chord.roman_label(key)} is missing "
                f"{len(missing)} chord tones {sorted(missing)} — "
                f"4-part writing can omit at most 1"
            )
    # P3: Ger+6 and Fr+6 also require all 4 chord tones in 4-part
    # writing (Sposobin §50).  It+6 is by definition 3 tones but in
    # 4-voice writing all 3 must still be present (one is doubled, none
    # may be omitted).  N6 (3 tones) has the same requirement.
    # P7.4: DD 增六 (aug6_dd) is 4-tone (Fr+6 form in V/V domain) and
    # follows the same rule as Fr+6.
    if chord.quality in ("aug6_ger", "aug6_fr", "aug6_it", "aug6_dd",
                        "neapolitan"):
        chord_pcs = set(chord.pitch_classes(key))
        voicing_pcs = {n.pc for n in voicing.notes()}
        missing = chord_pcs - voicing_pcs
        if missing:
            errs.append(
                f"{chord.roman_label(key)} is missing chord tone(s) "
                f"{sorted(missing)} — Sposobin §50/§52 requires all chord tones"
            )
    return errs


# ---------------------------------------------------------------------------
# 10. Voicing enumeration
# ---------------------------------------------------------------------------


def enumerate_voicings(
    chord: Chord,
    key: Key,
    *,
    melody: Note | None = None,
    fixed_bass: Note | None = None,
    prev: Voicing | None = None,
    prev_chord: Chord | None = None,
    prev_melody: Note | None = None,
    next_melody: Note | None = None,
    is_strong_beat: bool = True,
    is_cadence_beat: bool = False,
    is_c64_beat: bool = False,
    require_chord_tones: bool = False,
    max_results: int = 80,
    # P21.4: phrase-plan hint layer.  Default None = "no plan",
    # which makes score_voicing compute the same value as P0-P8.
    phrase_plan: "PhrasePlanSet | None" = None,
    beat_idx: int = 0,
) -> list[tuple[Voicing, float, list[str]]]:
    """Enumerate feasible SATB voicings for `chord`.

    Two anchor modes (mutually exclusive in practice):

    * **Soprano-anchored** (default): ``melody`` is given, bass is auto-derived
      from the chord's inversion.  This is the P0+ behaviour.
    * **Bass-anchored** (P8 / bass-given): ``fixed_bass`` is given, soprano
      is free.  Used for Sposobin bass-given exercises where the bass line
      is the input.

    The rest of the function is shared: for each (soprano, bass) pair, fill
    alto and tenor with all valid combinations of the remaining chord tones
    within their ranges, with at most one doubling.
    """
    if melody is not None and fixed_bass is not None:
        raise ValueError(
            "enumerate_voicings: melody and fixed_bass are mutually exclusive; "
            "pass exactly one anchor."
        )
    chord_pcs = chord.pitch_classes(key)
    results: list[tuple[Voicing, float, list[str]]] = []
    bass_pc = chord.bass_pitch_class(key)

    # Soprano candidates
    if melody is not None:
        sops = [melody]
    else:
        sops = []
        for pc in chord_pcs:
            for oct_ in range(VOICE_RANGES["soprano"][0].oct,
                               VOICE_RANGES["soprano"][1].oct + 1):
                cand = Note(pc=pc, oct=oct_)
                if in_range("soprano", cand):
                    sops.append(cand)
    # If melody is given but not in any chord tone, we must include it
    # (we'll tolerate a non-chord tone marker via score_voicing penalty).

    # Bass candidates — every pitch of bass_pc in bass range,
    # OR a single fixed_bass if explicitly given (P8 / bass-given).
    if fixed_bass is not None:
        # Sanity: the fixed bass must be a chord tone of this chord, and
        # its pitch class must equal the chord's bass_pitch_class (since
        # the chord's inversion already determines the bass pc).
        if fixed_bass.pc != bass_pc:
            return results
        if not in_range("bass", fixed_bass):
            return results
        basses = [fixed_bass]
    else:
        basses = []
        for oct_ in range(VOICE_RANGES["bass"][0].oct,
                          VOICE_RANGES["bass"][1].oct + 1):
            cand = Note(pc=bass_pc, oct=oct_)
            if in_range("bass", cand):
                basses.append(cand)

    # For inner voices: list all (pc, oct) candidates per voice
    def inner_candidates(voice: str) -> list[Note]:
        lo, hi = VOICE_RANGES[voice]
        out: list[Note] = []
        for pc in chord_pcs:
            for oct_ in range(lo.oct, hi.oct + 1):
                cand = Note(pc=pc, oct=oct_)
                if in_range(voice, cand):
                    out.append(cand)
        return out

    altos = inner_candidates("alto")
    tenors = inner_candidates("tenor")

    # P4: classify the melody as chord-tone / non-chord-tone
    # (passing / neighbor / suspension) so we can allow non-chord-tone
    # melodies on weak beats (Sposobin §17-22).
    nct_type: str | None = None
    if melody is not None and not is_chord_tone(melody, chord, key):
        nct_type = classify_soprano_nct(
            melody, chord, key,
            prev_mel=prev_melody,
            next_mel=next_melody,
            prev_chord=prev_chord,
            is_strong=is_strong_beat,
        )
        if nct_type is None:
            # Melody is incompatible with this chord and not a valid NCT.
            # The caller (solve_melody) will get an empty list and may
            # try a different chord.  We don't try harder here.
            return results

    for s in sops:
        for b in basses:
            # Bass must be below tenor
            if b.midi >= s.midi:
                continue
            for a in altos:
                if a.midi >= s.midi:
                    continue
                if a.midi <= b.midi:
                    continue
                for t in tenors:
                    if t.midi >= a.midi:
                        continue
                    if t.midi <= b.midi:
                        continue
                    v = Voicing(soprano=s, alto=a, tenor=t, bass=b)
                    # Hard constraint: on strong beats / cadences / V-beat
                    # all 4 voices must be chord tones (Sposobin §24).
                    # On weak / non-cadence beats we leave room for passing
                    # tones etc. — but P0/P1 don't model those, so the soft
                    # score still penalizes non-chord tones.
                    if require_chord_tones:
                        # The melody is allowed to be a non-chord tone
                        # ONLY if it's a suspension (strong-beat only).
                        # Passing and neighbor are weak-beat NCTs and
                        # are NOT allowed on a chord-tone-required beat.
                        for n in v.notes():
                            if n is v.soprano and nct_type == "suspension":
                                continue
                            if not is_chord_tone(n, chord, key):
                                v = None
                                break
                        if v is None:
                            continue
                    errs = check_voicing(prev, prev_chord, v, chord, key)
                    if errs:
                        continue
                    sc, _parts = score_voicing(
                        prev, prev_chord, v, chord, key,
                        melody_note=melody,
                        is_strong_beat=is_strong_beat,
                        is_cadence_beat=is_cadence_beat,
                        is_c64_beat=is_c64_beat,
                        nct_type=nct_type,
                        phrase_plan=phrase_plan,
                        beat_idx=beat_idx,
                    )
                    results.append((v, sc, errs))
                    if len(results) >= max_results:
                        results.sort(key=lambda r: r[1], reverse=True)
                        return results

    results.sort(key=lambda r: r[1], reverse=True)
    return results[:max_results]


# ---------------------------------------------------------------------------
# 11. Cadence detection
# ---------------------------------------------------------------------------


def detect_cadence(prev_chord: Chord | None, last_chord: Chord, last_voicing: Voicing,
                   key: Key) -> str | None:
    """Return 'PAC', 'IAC', 'HC', 'plagal', 'phrygian', 'deceptive', 'lydian',
    or None.

    P5: Phrygian half cadence (Sposobin §57-58) — iv6 → V in minor,
    characterized by the b2 melodic descent.

    P6 polish:
      - Deceptive cadence (V → vi in major; V → VI in minor) — Sposobin §46
      - Lydian cadence (II → I in major) — Sposobin §58 (Lydian mode)
    """
    if prev_chord is None:
        return None
    # HC: ends on V
    if last_chord.degree == 5:
        # Phrygian half cadence: prev is iv6 (degree 4, min, "6") and the
        # melody at the V beat is b2 (key tonic + 1 semitone).
        if (prev_chord.degree == 4
                and prev_chord.quality == "min"
                and prev_chord.inversion == "6"):
            b2_pc = (key.tonic_pc + 1) % 12
            if last_voicing.soprano.pc == b2_pc:
                return "phrygian"
        return "HC"
    # Deceptive cadence: V → vi (major) or V → VI (minor)
    if prev_chord.degree == 5 and last_chord.degree == 6:
        return "deceptive"
    # PAC: V → I with I in root, soprano on tonic
    if (prev_chord.degree == 5 and last_chord.degree == 1
            and last_chord.inversion == "root"
            and last_voicing.soprano.pc == key.tonic_pc):
        return "PAC"
    # Lydian cadence: II → I in major (Lydian mode flavor; Sposobin §58)
    if (key.mode == "major" and prev_chord.degree == 2
            and last_chord.degree == 1
            and last_chord.inversion == "root"
            and last_voicing.soprano.pc == key.tonic_pc):
        return "lydian"
    # IAC: V → I but I inverted or soprano not tonic
    if prev_chord.degree == 5 and last_chord.degree == 1:
        return "IAC"
    # Plagal: IV → I (P5: include modal_b6 borrowed iv, since it's
    # the chromatic-equivalent of diatonic iv in Sposobin modal mixture).
    if prev_chord.degree == 4 and last_chord.degree == 1:
        if prev_chord.quality in ("min", "maj", "modal_b6", "modal_iv"):
            return "plagal"
    # Sposobin §32 secondary-dominant-to-I: ii7 (V7/V) → I in major is
    # an "incomplete authentic" — V is missing, but the supertonic
    # chord functions as a stand-in.  In Sposobin's late 上册 chapter
    # this is acceptable; mark it as "half_authentic" so the user
    # sees the solver noticed the resolution.
    if prev_chord.degree == 2 and last_chord.degree == 1:
        return "half_authentic"
    return None


# ---------------------------------------------------------------------------
# 12. Candidate chords per beat
# ---------------------------------------------------------------------------


def _secondary_v7_degree(key: Key, target: int) -> int:
    """Given a target degree t in key, return the degree of V7/t.

    V7/t is built on the dominant of t (a 5th above t's root).  We
    search which degree in the key has the same pitch class.
    """
    t_root_pc = (key.tonic_pc + key.degree_offsets[target - 1]) % 12
    sec_root_pc = (t_root_pc + 7) % 12
    for i, off in enumerate(key.degree_offsets):
        if (key.tonic_pc + off) % 12 == sec_root_pc:
            return i + 1
    raise ValueError(f"can't find V7/t degree for target={target} in key={key}")


def _secondary_vii_deg7_degree(key: Key, target: int) -> int:
    """P9.1: return the degree of vii°7/t (副导七和弦).

    vii°7/t is built a half-step BELOW t's root (the leading tone of
    t's scale).  In C major, vii°7/V = F#°7 (F# is a half-step below
    G).  We search which degree in the key has the same pitch class
    as the leading tone of t.  If no diatonic degree matches (e.g.
    natural minor lacks the raised 7th of V), raise ValueError to
    skip the entry — vii°7/t is only meaningful when the target's
    leading tone exists in the local key.
    """
    t_root_pc = (key.tonic_pc + key.degree_offsets[target - 1]) % 12
    lt_pc = (t_root_pc - 1) % 12
    for i, off in enumerate(key.degree_offsets):
        if (key.tonic_pc + off) % 12 == lt_pc:
            return i + 1
    raise ValueError(f"no leading tone for target={target} in key={key}")


def _candidates_tonal_triads(key: Key) -> list[Chord]:
    """P0 base: only I, ii, IV, V, vi (and their inversions) in major;
    i, ii°, iv, V, VI in harmonic minor.  No V7, no secondary, no
    augmented 6th, no modal mixture, no 7ths, no 9ths.  This is the
    chord pool Sposobin covers by end of ch4 (三和弦 + 转位).
    """
    out: list[Chord] = []
    if key.mode == "major":
        triples = [(1, "maj"), (2, "min"), (4, "maj"),
                   (5, "maj"), (6, "min")]
    else:
        if key.variant == "harmonic":
            triples = [
                (1, "min"), (2, "dim"), (3, "maj"), (4, "min"),
                (5, "maj"), (6, "maj"), (7, "dim"),
            ]
        elif key.variant == "melodic":
            triples = [
                (1, "min"), (2, "maj"), (3, "aug"), (4, "maj"),
                (5, "maj"), (6, "dim"), (7, "dim"),
            ]
        else:
            triples = [
                (1, "min"), (2, "dim"), (3, "maj"), (4, "min"),
                (5, "min"), (6, "maj"), (7, "maj"),
            ]
    for deg, qual in triples:
        for inv in ("root", "6", "6/4"):
            out.append(Chord(degree=deg, quality=qual, inversion=inv,
                             kind="triad"))
    return out


def _candidates_tonal_plus_d7(key: Key) -> list[Chord]:
    """P0 + V7 in 4 inversions.  Sposobin ch8 introduces V7.  No
    secondary dominants, no augmented 6th, no 7ths of other degrees.
    """
    out = _candidates_tonal_triads(key)
    for inv in ("7", "6/5", "4/3", "2"):
        out.append(Chord(degree=5, quality="dom7", inversion=inv,
                         kind="seventh"))
    return out


def _candidates_tonal_plus_d7_ii7_vii7(key: Key) -> list[Chord]:
    """P0 + V7 + ii7 (SII7) + vii°7 (DVII7).  Sposobin ch21-22.

    No secondary dominants, no augmented 6th, no D9, no modal mixture.
    """
    out = _candidates_tonal_plus_d7(key)
    # ii7 / iiø7
    sii7_quality = "min7" if key.mode == "major" else "half_dim7"
    for inv in ("7", "6/5", "4/3", "2"):
        out.append(Chord(degree=2, quality=sii7_quality, inversion=inv,
                         kind="seventh"))
    # vii°7 / viiø7
    if key.mode == "major":
        d7_quality = "half_dim7"
        d7_enabled = True
    elif key.variant in ("harmonic", "melodic"):
        d7_quality = "dim7"
        d7_enabled = True
    else:
        d7_enabled = False
    if d7_enabled:
        for inv in ("7", "6/5", "4/3", "2"):
            out.append(Chord(degree=7, quality=d7_quality, inversion=inv,
                             kind="seventh"))
    return out


def _candidates_tonal_plus_d9(key: Key) -> list[Chord]:
    """P0 + V7 + ii7 + vii°7 + V9 (root only).  Sposobin ch23.

    No secondary dominants, no augmented 6th, no modal mixture.
    """
    out = _candidates_tonal_plus_d7_ii7_vii7(key)
    out.append(Chord(degree=5, quality="dom9", inversion="root",
                     kind="ninth"))
    return out


def _candidates_full_p7(key: Key) -> list[Chord]:
    """P7.5: full pool — same as `candidate_chords(key)` minus the
    modulation-only extras.  Used as the 'everything before P7.5' default.
    """
    # Just delegate to the big candidate_chords but without P7.5 modulation
    # bits (modulation helpers are not pool restrictions).
    return _candidates_tonal_plus_d9(key)  # current P0-P7 baseline
    # NOTE: this intentionally does NOT add secondary dominants /
    # aug6 / modal mixture / DD-aug6 — those are P2 / P3 / P5 / P7.4
    # features that the user can opt into explicitly via
    # `profile="full_with_secondary"` etc.


# ---------------------------------------------------------------------------
# Pool profile registry.  Maps a profile name to a candidate-pool
# builder.  The default is the full P0-P7.7 pool (i.e. current
# behaviour).  P8.1 adds `chord_pool_profile` to `solve_melody` so
# callers can restrict the pool to a Sposobin chapter.
# ---------------------------------------------------------------------------

CANDIDATE_POOL_PROFILES = {
    # Sposobin ch1-ch4: triads only, no V7.  Used for the earliest
    # "为旋律配和声" exercises in §3, §4 (e.g.题 3 from §3 review).
    "ch1-4_triad_only":          _candidates_tonal_triads,
    # Sposobin ch5-ch7: triads + V6/4 在终止.  Cadential 6/4 is built
    # dynamically by the cadence_beat path, so the pool doesn't need
    # to change here.
    "ch5-7_triad_plus_v64":      _candidates_tonal_triads,
    # Sposobin ch8-ch20: triads + V7.  The bulk of 上册 exercises.
    "ch8-20_v7":                 _candidates_tonal_plus_d7,
    # Sposobin ch21-ch22: + SII7 + DVII7.
    "ch21-22_d7_ii7_vii7":       _candidates_tonal_plus_d7_ii7_vii7,
    # Sposobin ch23: + V9.
    "ch23_v9":                   _candidates_tonal_plus_d9,
    # Sposobin ch25+ (P9.1 done): triads + V7 + ii7 + vii°7 + V9 +
    # V7/x secondary dominants (including V7+5/x alterations) +
    # vii°7/x leading-tone seventh.  Same as P0-P9 (excluding aug6
    # and modal mixture for now).
    "ch24-26_dd":                None,  # sentinel → use candidate_chords
    # Sposobin ch25+: + secondary dominants V7/x, V9/x.
    # The full P0-P7.7 pool (default; same as calling without
    # chord_pool_profile).
    "full_p0-p7":                None,  # sentinel → use candidate_chords
    # P9 full pool: P0-P7.7 + V7+5/x + vii°7/x.  Same as
    # candidate_chords since P9.1 added those directly inside
    # candidate_chords.
    "full_p0-p9":                None,  # sentinel → use candidate_chords
}


# ---------------------------------------------------------------------------
# P1.1: declarative Profile system
# ---------------------------------------------------------------------------
# Each Profile is an explicit whitelist per Sposobin chapter.  The
# candidate generator (below) intersects the diatonic inversion/extension
# set with this whitelist.  Cadential 6/4 (K6/4) and DD7 are still
# injected dynamically in the cadence_beat path, not here.
#
# Tuple format: (degree, quality)
#   degree: 1..7
#   quality: 'maj' | 'min' | 'dim' | 'aug'  (triads)
#            'dom7' | 'maj7' | 'min7' | 'half_dim7' | 'dim7'  (sevenths)
#            'dom9'  (ninths)


@dataclass(frozen=True)
class Profile:
    name: str
    triads: dict[str, tuple[tuple[int, str], ...]]
    sevenths: dict[str, tuple[tuple[int, str], ...]] = field(default_factory=dict)
    ninths: dict[str, tuple[tuple[int, str], ...]] = field(default_factory=dict)


# Sposobin ch1-4: only I, ii, IV, V, vi (major) / i, ii°, iv, v, VI (minor).
# In minor, v is the natural-minor v (minor triad).  ch1-4 explicitly
# excludes III (modal mixture, ch25+) and VII (natural-minor triad).
CH1_4 = Profile(
    name="ch1-4_triad_only",
    triads={
        "major": ((1, "maj"), (2, "min"), (4, "maj"), (5, "maj"), (6, "min")),
        "minor": ((1, "min"), (2, "dim"), (4, "min"), (5, "min"), (6, "maj")),
    },
)

# Sposobin ch5-7: same 5 triads but V is raised to maj in minor
# (harmonic minor V).  The 5/4 cadence is added dynamically in the
# cadence_beat path, not here.
CH5_7 = Profile(
    name="ch5-7_triad_plus_v64",
    triads={
        "major": ((1, "maj"), (2, "min"), (4, "maj"), (5, "maj"), (6, "min")),
        "minor": ((1, "min"), (2, "dim"), (4, "min"), (5, "maj"), (6, "maj")),
    },
)

# Sposobin ch8-20: 5 triads (ch5-7 set) + V7 in 4 inversions.
CH8_20 = Profile(
    name="ch8-20_v7",
    triads=CH5_7.triads,
    sevenths={
        "major": ((5, "dom7"),),
        "minor": ((5, "dom7"),),
    },
)

# Sposobin ch21-22: 5 triads + V7 + ii7 + viiø7.  In major, ii7 is min7
# and vii7 is half-dim7.  In minor, ii7 is half-dim7 and vii7 is dim7
# (raised leading tone in harmonic minor).
CH21_22 = Profile(
    name="ch21-22_d7_ii7_vii7",
    triads=CH8_20.triads,
    sevenths={
        "major": ((2, "min7"), (5, "dom7"), (7, "half_dim7")),
        "minor": ((2, "half_dim7"), (5, "dom7"), (7, "dim7")),
    },
)

# Sposobin ch23: same as ch21-22 + V9 in root position only.
CH23 = Profile(
    name="ch23_v9",
    triads=CH21_22.triads,
    sevenths=CH21_22.sevenths,
    ninths={
        "major": ((5, "dom9"),),
        "minor": ((5, "dom9"),),
    },
)

PROFILES = {
    "ch1-4_triad_only":    CH1_4,
    "ch5-7_triad_plus_v64": CH5_7,
    "ch8-20_v7":            CH8_20,
    "ch21-22_d7_ii7_vii7":  CH21_22,
    "ch23_v9":              CH23,
}


def generate_candidates(key: Key, profile: Profile) -> list[Chord]:
    """P1.1: produce the chord pool for ``key`` under a chapter profile.

    Intersects the profile's explicit whitelist with the standard
    inversion/extension set.  Cadential 6/4 (K6/4) and DD7 are still
    injected dynamically in the cadence_beat path, not here.
    """
    mode = "minor" if key.mode == "minor" else "major"
    out: list[Chord] = []
    # Triads: 3 inversions (root, 6, 6/4)
    for deg, qual in profile.triads.get(mode, ()):
        for inv in ("root", "6", "6/4"):
            out.append(Chord(degree=deg, quality=qual, inversion=inv, kind="triad"))
    # Sevenths: 4 inversions (7, 6/5, 4/3, 2)
    for deg, qual in profile.sevenths.get(mode, ()):
        for inv in ("7", "6/5", "4/3", "2"):
            out.append(Chord(degree=deg, quality=qual, inversion=inv, kind="seventh"))
    # Ninths: root only (Sposobin ch23)
    for deg, qual in profile.ninths.get(mode, ()):
        for inv in ("root",):
            out.append(Chord(degree=deg, quality=qual, inversion=inv, kind="ninth"))
    return out


def _resolve_pool_profile(name: str | None):
    """Return (pool_or_profile, name) tuple, or (None, None) for default.

    P1.1: chapter profiles return a Profile object (declarative);
    full-pool profiles return None (use candidate_chords).
    """
    if name is None:
        return None, None
    if name in PROFILES:
        return PROFILES[name], name
    if name in CANDIDATE_POOL_PROFILES:
        return CANDIDATE_POOL_PROFILES[name], name
    raise ValueError(
        f"unknown chord_pool_profile {name!r}; valid: "
        f"{sorted(PROFILES.keys())}"
    )


def candidate_chords(key: Key) -> list[Chord]:
    """P0/P1/P2/P5 chord pool: diatonic triads + V7 + secondary dominants.

    Triads:
      major: I, ii, IV, V, vi  (skipping iii for now)
      minor (default = harmonic V):
        - natural:    i, ii°, III, iv, v, VI, VII
        - harmonic:   i, ii°, III, iv, V, VI, vii°  (raised 7)
        - melodic ↑:  i, II, III+, IV, V, vi°, vii° (raised 6+7)
    Inversions allowed: root, 6, 6/4 for any of them.

    P1: V7 in all four inversions (root / 6/5 / 4/3 / 2).

    P2: Secondary dominants V7/x for x in {ii, iii, IV, V, vi} in all
    four inversions.  We do NOT add V7/I (it's the same as V7) or
    V7/vii (vii° doesn't get tonicized in Sposobin).
    """
    out: list[Chord] = []
    if key.mode == "major":
        triples = [(1, "maj"), (2, "min"), (4, "maj"),
                   (5, "maj"), (6, "min")]
    else:
        # P5: minor variant-aware triads
        if key.variant == "melodic":
            triples = [
                (1, "min"),   # i
                (2, "maj"),   # II (raised 6)
                (3, "aug"),   # III+ (raised 7)
                (4, "maj"),   # IV (raised 6)
                (5, "maj"),   # V (raised 7)
                (6, "dim"),   # vi° (raised 6)
                (7, "dim"),   # vii° (raised 7)
            ]
        elif key.variant == "harmonic":
            triples = [
                (1, "min"),   # i
                (2, "dim"),   # ii°
                (3, "maj"),   # III (natural — major triad on b3 of natural minor)
                (4, "min"),   # iv
                (5, "maj"),   # V (raised 7)
                (6, "maj"),   # VI
                (7, "dim"),   # vii° (raised 7)
            ]
        else:
            # natural minor
            triples = [
                (1, "min"),   # i
                (2, "dim"),   # ii°
                (3, "maj"),   # III
                (4, "min"),   # iv
                (5, "min"),   # v (natural — minor triad)
                (6, "maj"),   # VI
                (7, "maj"),   # VII (natural — major triad on b7)
            ]
    for deg, qual in triples:
        for inv in ("root", "6", "6/4"):
            out.append(Chord(degree=deg, quality=qual, inversion=inv,
                             kind="triad"))
    # P1: V7 in all 4 inversions (placed first in pool for c64_beat
    # convenience; diatonic triads come earlier so they win when
    # appropriate).
    for inv in ("7", "6/5", "4/3", "2"):
        out.append(Chord(degree=5, quality="dom7", inversion=inv,
                         kind="seventh"))
    # P2: secondary dominants V7/x for x in {2, 3, 4, 5, 6} — placed
    # AFTER diatonic chords so they only get picked when their root is
    # in the melody and no diatonic chord wins.  Beam-K=3 will still
    # keep them in the running.
    for target in (2, 3, 4, 5, 6):
        try:
            sec_deg = _secondary_v7_degree(key, target)
        except ValueError:
            continue
        for inv in ("7", "6/5", "4/3", "2"):
            out.append(Chord(degree=sec_deg, quality="dom7", inversion=inv,
                             kind="seventh", target=target))
        # P9.1 (Sposobin ch24 副属和弦中的变音): V7/x with raised 5th
        # (V7+5/x).  The augmented 5th strengthens the leading-tone pull
        # to the target.  Used in chromatic / late-Romantic style;
        # 4 inversions like V7/x.  We add root + 6/5 only (raised 5th in
        # bass is unusual and the 4/3 and 2 inversions are rare enough
        # to skip in beam search).
        for inv in ("7", "6/5"):
            out.append(Chord(degree=sec_deg, quality="dom7+5", inversion=inv,
                             kind="seventh", target=target))
    # P9.1 (Sposobin ch24 副属和弦中的变音): vii°7/x (副导七和弦,
    # fully-diminished 7th chord built on the leading tone of each
    # secondary target).  Example: in C major, vii°7/V = F#-A-C-Eb,
    # resolves to V (G major).  4 inversions.  We add to the pool the
    # same way V7/x is added, and the dim7 quality / leading-tone
    # resolution is already handled by has_leading_tone_violation
    # (line 869) and the dom7/dim7 family in has_seventh_resolution.
    for target in (2, 3, 4, 5, 6):
        try:
            sec_deg = _secondary_vii_deg7_degree(key, target)
        except ValueError:
            continue
        for inv in ("7", "6/5", "4/3", "2"):
            out.append(Chord(degree=sec_deg, quality="dim7", inversion=inv,
                             kind="seventh", target=target))
    # P3: augmented 6th chords (Ger+6, Fr+6, It+6) and Neapolitan sixth
    # (N6 = ♭II6).  All four have fixed voicings (the bass is determined
    # by the chord type, not an inversion label).  Inversion is set to
    # "root" for these (their actual bass position is encoded in
    # bass_pitch_class).
    out.append(Chord(degree=1, quality="aug6_ger", inversion="root",
                     kind="triad"))
    out.append(Chord(degree=1, quality="aug6_fr", inversion="root",
                     kind="triad"))
    out.append(Chord(degree=1, quality="aug6_it", inversion="root",
                     kind="triad"))
    out.append(Chord(degree=2, quality="neapolitan", inversion="6",
                     kind="triad"))
    # P7.4: DD 增六和弦 (含增六度的重属和弦, Sposobin ch30 PDF p208 /
    # 课本 p200).  4-tone chord (Fr+6 form in V/V domain).
    # Bass fixed at ♭3 of V/V.  Only available when V/V is well-defined
    # (i.e. when the V/V's leading tone exists in the key).  For major,
    # this is always.  For minor harmonic/melodic, V/V is the V of V
    # (which uses the raised 7), so V/V is also well-defined.  For minor
    # natural (no raised 7), V/V exists but the V/V's leading tone is
    # the borrowed minor 7 → natural V/V.  DD 增六 only meaningfully
    # appears with the leading tone of V/V (i.e. harmonic or melodic
    # minor), so we skip natural minor.
    if key.mode == "major" or key.variant in ("harmonic", "melodic"):
        out.append(Chord(degree=2, quality="aug6_dd", inversion="root",
                         kind="triad"))
    # P3.5: modal mixture (Sposobin §53) — chords borrowed from the
    # parallel minor.  Only meaningful in major mode (minor already
    # has these diatonically).  Includes ♭VI, ♭III, ♭VII, and the
    # borrowed minor iv.
    if key.mode == "major":
        for mod_q, mod_deg in [("modal_b6", 6), ("modal_b3", 3),
                               ("modal_b7", 7), ("modal_iv", 4)]:
            for inv in ("root", "6", "6/4"):
                out.append(Chord(degree=mod_deg, quality=mod_q,
                                 inversion=inv, kind="triad"))
    # P7.1: SII7 (下属七和弦) — Sposobin ch21 (PDF p127 / book p119).
    # In major: ii7 = m3 + P5 + m7  →  "min7" quality.
    # In minor (natural/harmonic/melodic): iiø7 = m3 + d5 + m7  →
    #   "half_dim7" quality.
    # Sposobin notation: SII7 in major, sII7 in minor.  The 5/6
    # inversion (SII6/5) is the most common, but we offer all four
    # inversions in the pool; the beam + scoring will pick the best.
    sii7_quality = "min7" if key.mode == "major" else "half_dim7"
    for inv in ("7", "6/5", "4/3", "2"):
        out.append(Chord(degree=2, quality=sii7_quality, inversion=inv,
                         kind="seventh"))
    # P7.2: DVII7 (导七和弦) — Sposobin ch22 (PDF p135 / book p127).
    # In major (natural): viiø7 = m3 + d5 + m7  →  "half_dim7".
    # In minor harmonic/melodic: vii°7 = m3 + d5 + d7  →  "dim7".
    # In minor natural: vii is a major triad (no leading tone), so
    # DVII7 is not applicable — we skip it.  Major "harmonic/melodic"
    # variants do not exist in our Key class, so major is always natural.
    if key.mode == "major":
        d7_quality = "half_dim7"
        d7_enabled = True
    elif key.variant in ("harmonic", "melodic"):
        d7_quality = "dim7"
        d7_enabled = True
    else:
        d7_enabled = False
    if d7_enabled:
        for inv in ("7", "6/5", "4/3", "2"):
            out.append(Chord(degree=7, quality=d7_quality, inversion=inv,
                             kind="seventh"))
    # P7.3: D9 (属九和弦) — Sposobin ch23 (PDF p143 / book p135).
    # V9 has 5 chord tones (root, 3, 5, 7, 9); 4-part writing omits
    # one (typically the 5th).  Sposobin says D9 is "almost only in
    # root position" (几乎只用原位), so we only add it in root.
    # In natural major / natural minor: 大 9 度 (= M2 above root).
    # In harmonic/melodic minor: 小 9 度 (= m2 above root).
    # The 9th is computed by Chord.ninth_pc() based on key variant.
    out.append(Chord(degree=5, quality="dom9", inversion="root",
                     kind="ninth"))
    # P7.3 secondary: V9/V (target=5).  Built on V/V's root (D in C
    # major).  Also add V9/ii (target=2), V9/vi (target=6) for
    # completeness, matching the V7 secondary pool coverage.
    for sec_target in (2, 5, 6):
        try:
            sec_deg = _secondary_v7_degree(key, sec_target)
        except ValueError:
            continue
        out.append(Chord(degree=sec_deg, quality="dom9", inversion="root",
                         kind="ninth", target=sec_target))
    return out


# ---------------------------------------------------------------------------
# 13. Top-level solver
# ---------------------------------------------------------------------------


@dataclass
class Beat:
    """One beat in the input melody.

    Either ``soprano`` (soprano-anchored mode, the original P0+ design) or
    ``bass`` (bass-given mode, P8) is set.  A beat may have both, neither,
    or just one — but ``solve_melody`` treats exactly one of them as the
    fixed anchor; the other voices are filled in by the search.
    """
    offset: float
    duration: float
    soprano: Note | None = None  # None for rests
    bass: Note | None = None     # None unless bass-given mode (P8)


@dataclass
class SolveResult:
    summary: dict
    measures: list[dict]
    warnings: list[str]
    alternatives: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "solver": "spohr-v0",
            "summary": self.summary,
            "measures": self.measures,
            "warnings": self.warnings,
            "alternatives": self.alternatives,
        }


def _default_beat_durations(time_sig: str, measure_count: int) -> list[list[float]]:
    """Return per-measure per-beat durations.

    The number of beats per measure equals the numerator of the time
    signature (one beat per "click" the musician counts: 4/4 → 4, 3/8 → 3,
    6/8 → 6).  Each beat is (4/den) quarter notes long:
        4/4 → 4 beats × 1.0 quarter
        3/4 → 3 beats × 1.0 quarter
        3/8 → 3 beats × 0.5 quarter   (eight-note triplets)
        6/8 → 6 beats × 0.5 quarter   (compound duple, 6 eighth notes)
    """
    num, den = time_sig.split("/")
    num = int(num)
    den = int(den)
    beat_dur = 4.0 / den
    return [[beat_dur] * num for _ in range(measure_count)]


def solve_melody(
    key_name: str,
    time_signature: str,
    melody_pitches: list[list[Note | None]],
    *,
    measure_count: int | None = None,
    beam_k: int = 3,
    top_n: int = 1,
    key_changes: "list[KeyChange | tuple[int, str]] | None" = None,
    bass_pitches: "list[list[Note | None]] | None" = None,
    chord_pool_profile: str | None = None,
    # P21.4: phrase-plan hint layer.  Optional; default None
    # reproduces P0-P7.7 behaviour exactly.
    phrase_plan: "PhrasePlanSet | None" = None,
) -> SolveResult:
    """Solve a 4-part harmonization for a given melody (or bass line).

    Parameters
    ----------
    key_name : "C", "a", "Am", "F#m", etc.
    time_signature : "4/4", "3/4", etc.
    melody_pitches : list per measure of per-beat melody notes (or None for rest).
    measure_count : optional, defaults to len(melody_pitches).
    chord_pool_profile : optional chapter-restricted chord pool name
        (P8.1).  When set, ``candidate_chords`` returns only the
        diatonic / Sposobin-allowed chords for that chapter range.
        Valid profiles:
            "ch1-4_triad_only"      — only I, ii, IV, V, vi (and inversions)
            "ch5-7_triad_plus_v64"  — same (cadential 6/4 added dynamically)
            "ch8-20_v7"             — + V7 in 4 inversions
            "ch21-22_d7_ii7_vii7"   — + ii7, vii°7
            "ch23_v9"               — + V9
            "full_p0-p7"            — full P0-P7.7 pool (default)
        Default ``None`` keeps the historical P0-P7.7 behaviour
        (secondary dominants, aug6, modal mixture, DD-aug6 all in pool).
    beam_k : top-K to keep at each beat (K=3 in P0 spec).
    top_n : how many distinct full-path solutions to return (P8.1).  The
        beam is widened to max(beam_k, top_n) so that the top-N
        full-path solutions are all available at the end.  The first
        one becomes the primary `measures` / `summary`; the rest are
        returned under `alternatives` as `{score, measures, summary}`
        dicts.  Default 1 preserves P0-P8 behaviour exactly.
    key_changes : optional list of (measure_idx, key_name) or KeyChange entries
        for Sposobin ch34-35 modulation.  When a key change occurs at
        measure M, the local key from M onwards is the new one.  The
        home key (key_name) still applies in [0, M).  Default None
        means no modulation (single home key throughout — backwards
        compatible with P0-P7).
    bass_pitches : optional list per measure of per-beat bass notes.
        When provided, the solver runs in **bass-given** mode (P8):
        for each beat, the chord pool is restricted to chords whose
        bass pitch-class matches the given bass, and ``enumerate_voicings``
        is called with ``fixed_bass=...`` so soprano / alto / tenor are
        filled in by the search.  ``melody_pitches`` may still be used
        for the optional ``prev_melody`` / ``next_melody`` context
        passed to ``classify_soprano_nct`` (weak-beat NCTs) but is
        NOT enforced as the soprano voice.

        If both ``melody_pitches`` and ``bass_pitches`` contain notes
        at the same beat, the bass is the binding constraint (it
        determines the chord) and the soprano is a free variable.

        A bass beat of ``None`` means "rest" and falls back to the
        default chord pool (same as no bass given for that beat).
    """
    key = Key.from_name(key_name)
    if measure_count is None:
        measure_count = len(melody_pitches)

    # P8.1: resolve chord pool profile.  When set, the chapter's allowed
    # chord pool replaces the full P0-P7.7 pool everywhere the solver
    # asks for "candidate chords".  Bass-given mode (P8) still works
    # because the bass filter is applied AFTER the pool is built.
    #
    # P1.1: _resolve_pool_profile now returns either a Profile object
    # (declarative whitelist) or a legacy builder function, or None
    # (use full candidate_chords).  generate_candidates() is the new
    # declarative path.
    pool_or_profile, _ = _resolve_pool_profile(chord_pool_profile)
    if pool_or_profile is None:
        def _pool(local_key):
            return candidate_chords(local_key)
    elif isinstance(pool_or_profile, Profile):
        profile_obj = pool_or_profile
        def _pool(local_key):
            return generate_candidates(local_key, profile_obj)
    else:
        # Legacy builder function (e.g. _candidates_tonal_triads)
        pool_builder = pool_or_profile
        def _pool(local_key):
            return pool_builder(local_key)

    # P7.5: parse and sort key_changes; build a per-measure lookup.
    # Each entry: (measure_idx_0_based, Key).  When multiple changes
    # apply to the same measure, the LATER one wins (last-write-wins).
    # When no change is given, every measure uses `key` (home key).
    parsed_changes: list[tuple[int, Key]] = []
    if key_changes:
        for kc in key_changes:
            if isinstance(kc, KeyChange):
                kc_measure = kc.measure
                kc_name = kc.key_name
            else:
                kc_measure, kc_name = kc[0], kc[1]
            parsed_changes.append((kc_measure, Key.from_name(kc_name)))
        # Sort by measure, then dedupe (later entries win via overwrite).
        parsed_changes.sort(key=lambda x: x[0])

    def local_key_for_measure(m_idx: int) -> Key:
        """Active key at the start of measure `m_idx` (0-indexed)."""
        lk = key  # home key
        for change_m, change_key in parsed_changes:
            if change_m <= m_idx:
                lk = change_key
            else:
                break
        return lk

    # Guard: validate the melody is non-empty and in-range.
    # P8: when bass_pitches is given, the melody may be all-None (it's
    # not the binding input) and the bass acts as the anchor.  We only
    # require a non-empty *input* (melody OR bass) and the in-range
    # check applies to whichever is non-None.
    if measure_count == 0:
        raise ValueError("melody is empty (no measures)")
    flat: list[Note | None] = [n for m in melody_pitches for n in m]
    flat = [n for n in flat if n is not None]
    flat_bass_check: list[Note | None] = (
        [n for m in bass_pitches for n in m] if bass_pitches is not None else []
    )
    flat_bass_check = [n for n in flat_bass_check if n is not None]
    if not flat and not flat_bass_check:
        raise ValueError("melody is empty (no notes and no bass)")
    sop_lo, sop_hi = VOICE_RANGES["soprano"]
    for n in flat:
        if n.midi < sop_lo.midi or n.midi > sop_hi.midi:
            raise ValueError(
                f"melody note {n.name} is out of soprano range "
                f"[{sop_lo.name}..{sop_hi.name}].  "
                f"Pass melody in soprano range or set VOICE_RANGES wider."
            )
    if bass_pitches is not None:
        bass_lo, bass_hi = VOICE_RANGES["bass"]
        for n in flat_bass_check:
            if n.midi < bass_lo.midi or n.midi > bass_hi.midi:
                raise ValueError(
                    f"bass note {n.name} is out of bass range "
                    f"[{bass_lo.name}..{bass_hi.name}].  "
                    f"Pass bass in bass range or set VOICE_RANGES wider."
                )

    # Build beat list
    beats: list[Beat] = []
    beats_per_measure: list[int] = []
    flat_melody: list[Note | None] = []   # for prev/next lookups (P4)
    flat_bass: list[Note | None] = []     # for P8 (bass-given mode)
    for m_idx, measure in enumerate(melody_pitches):
        durs = _default_beat_durations(time_signature, 1)[0]
        beats_per_measure.append(len(measure))
        for b_idx, mel in enumerate(measure):
            offset = sum(durs[:b_idx])
            b_note: Note | None = None
            if bass_pitches is not None and m_idx < len(bass_pitches):
                m_bass = bass_pitches[m_idx]
                if b_idx < len(m_bass):
                    b_note = m_bass[b_idx]
            beats.append(
                Beat(offset=offset, duration=durs[b_idx], soprano=mel, bass=b_note)
            )
            flat_melody.append(mel)
            flat_bass.append(b_note)

    # P4: build prev_melody / next_melody arrays for NCT classification.
    prev_mels: list[Note | None] = [None] + flat_melody[:-1]
    next_mels: list[Note | None] = flat_melody[1:] + [None]
    # P4.5: prev_prev_melody array for escape tone (3-step context).
    prev_prev_mels: list[Note | None] = [None, None] + flat_melody[:-2]
    # P4 fix: which beat number (1-indexed) within the measure each
    # global b_idx falls on, so we can identify the secondary metric
    # accent (beat 3 in 4/4).  beats_per_measure_in_beat[b_idx] = N
    # means b_idx is the Nth beat of its measure (1-indexed).
    beats_per_measure_in_beat: list[int] = []
    for n in beats_per_measure:
        for k in range(n):
            beats_per_measure_in_beat.append(k + 1)

    # Where should V land for a proper "V → I" cadence?
    # The standard pattern: last beat of the penultimate measure = V,
    # final measure = I.  So the "V beat" is at the last beat of measure M-1
    # (or M if M==1 — but we always have at least 2 measures here).
    if measure_count >= 2:
        v_beat_idx = sum(beats_per_measure[:-1]) - 1
    else:
        v_beat_idx = -1
    # Cadential 6/4 (Sposobin §46): the beat just before V should hold I6/4
    # as preparation.  This is a soft preference, not a hard requirement.
    if measure_count >= 2:
        c64_beat_idx = v_beat_idx - 1
    else:
        c64_beat_idx = -1

    # P7.5: per-beat measure index and per-beat local key.
    # Used so that every chord-pool / voicing / cadence lookup
    # uses the local key for that measure (Sposobin ch34-35).
    beat_to_measure_idx: list[int] = []
    for mi, nb in enumerate(beats_per_measure):
        beat_to_measure_idx.extend([mi] * nb)
    beat_to_local_key: list[Key] = [
        local_key_for_measure(beat_to_measure_idx[bi])
        for bi in range(len(beats))
    ]

    # Beam state: each entry is (prev_voicing, prev_chord, score, path)
    initial: list[tuple[Voicing | None, Chord | None, float, list[Voicing], list[Chord]]] = [
        (None, None, 0.0, [], [])
    ]
    beam = initial
    # P8.1: when top_n > beam_k, widen the beam so the top-N full
    # paths survive.  Effective beam width = max(beam_k, top_n).
    effective_k = max(beam_k, top_n)

    warnings: list[str] = []
    chosen: list[tuple[Voicing, Chord, float]] = []

    for b_idx, beat in enumerate(beats):
        is_cadence_beat = (b_idx == len(beats) - 1)
        is_v_beat = (b_idx == v_beat_idx)
        is_c64_beat = (b_idx == c64_beat_idx)
        is_strong = (beat.offset == 0.0)
        # P7.5: local key for this beat (may differ from home key if a
        # modulation was declared via key_changes).
        local_key = beat_to_local_key[b_idx]

        # P7.5.2 (Sposobin ch34 §5-6): at the modulation boundary, the
        # first beat of the new-key measure MUST be a pivot chord (中介
        # 和弦) — a chord that's valid in BOTH the home and the target
        # key.  This is the chord where the function shifts (功能转移),
        # and it's the textbook signal that a modulation is occurring.
        # We restrict the boundary beat's pool to the target-key reading
        # of the pivot chords.  Subsequent beats in the new key get the
        # full pool.
        is_pivot_beat = False
        prev_local_key = beat_to_local_key[b_idx - 1] if b_idx > 0 else key
        if (b_idx > 0
                and local_key != prev_local_key
                and beat.offset == 0.0):
            pivots_tc = get_target_key_pivots(prev_local_key, local_key)
            if pivots_tc:
                # Restrict the pool to chords that match a pivot's
                # pitch-class set.  We do this by keeping only chords
                # whose pc-set is in the pivot's pc-set.
                pivot_pcs = [
                    frozenset(tc.pitch_classes(local_key))
                    for tc in pivots_tc
                ]
                # Build a set of allowed (degree, quality, inversion)
                # for direct membership check on the chord pool.
                # We match by pc-set, not by degree/quality, because
                # pivots can have different degree/quality in home vs
                # target (e.g. "I" in C is "iv" in G).
                # Use pc-set on the original chord object.
                is_pivot_beat = True

        # On the final beat, force tonic (I / i) in root position for PAC.
        if is_cadence_beat:
            i_root = Chord(degree=1, quality=("maj" if local_key.mode == "major" else "min"),
                           inversion="root", kind="triad")
            # P23: profile 硬约束 - cadence 强制 I_root 必须先在 profile pool 内
            if (i_root.degree, i_root.quality, i_root.inversion, i_root.kind) in {
                (c.degree, c.quality, c.inversion, c.kind) for c in _pool(local_key)
            }:
                pool = [i_root]
            else:
                pool = _pool(local_key)  # 极端情况：profile 没有 I，回退
            # P8: in bass-given mode, the final-bass is fixed by the
            # user.  If it doesn't match the cadence I-root bass (e.g.
            # the user gave a final bass that is NOT the tonic), we
            # honour the bass — the user knows better than the
            # textbook default.  Fall back to the full candidate pool
            # so the bass-given filter can produce a valid chord.
            if beat.bass is not None and len(pool) == 1:
                i_root_bass_pc = pool[0].bass_pitch_class(local_key)
                if beat.bass.pc != i_root_bass_pc:
                    pool = _pool(local_key)
        else:
            pool = _pool(local_key)

        # P21.4 — phrase-plan role hint: reorder (do NOT drop) the
        # pool so the preferred-chord list reflects the current
        # phrase's role.  This is a HINT, not a hard constraint:
        #   * concluding role → V / V7 / V9 first
        #   * opening role    → I / vi / ii first
        #   * other roles     → no change
        # Reordering only — every chord in the original pool is still
        # reachable, so this can never reduce the set of valid
        # solutions; it just changes the order beam search sees them.
        if phrase_plan is not None and _PHRASE_PLANNER_AVAILABLE and pool:
            try:
                cur_phrase = get_phrase_at_beat(phrase_plan, b_idx)
            except Exception:
                cur_phrase = None
            if cur_phrase is not None:
                role = cur_phrase.phrase_role
                if role == "concluding":
                    preferred = {"V", "V7", "V9", "D7"}
                elif role == "opening":
                    preferred = {"I", "vi", "ii", "I6", "I64"}
                else:
                    preferred = None
                if preferred:
                    pri, rest = [], []
                    for c in pool:
                        key_lbl = c.figure(local_key) if hasattr(c, "figure") else str(c.degree)
                        # crude key match: any of the tokens appears
                        if any(p in str(key_lbl) for p in preferred):
                            pri.append(c)
                        else:
                            rest.append(c)
                    pool = pri + rest

        # P8: in bass-given mode, restrict the chord pool to chords whose
        # bass pitch-class matches the given bass.  This is the binding
        # constraint: bass-given exercises (Sposobin §18-19 etc.) anchor
        # the chord via the bass, so the pool must reflect that.
        if beat.bass is not None:
            target_bass_pc = beat.bass.pc
            pool = [c for c in pool
                    if c.bass_pitch_class(local_key) == target_bass_pc]

        # P7.5.2: at the modulation boundary, restrict the pool to
        # pivot chords only.  The function-shift (Sposobin ch34 §5)
        # happens AT the pivot, so this is the only valid choice.
        if is_pivot_beat and not is_cadence_beat and not is_v_beat and not is_c64_beat:
            pivots_tc = get_target_key_pivots(prev_local_key, local_key)
            if pivots_tc:
                pivot_pcs = [
                    frozenset(tc.pitch_classes(local_key))
                    for tc in pivots_tc
                ]
                pool = [c for c in pool
                        if frozenset(c.pitch_classes(local_key)) in pivot_pcs]

        # On the cadential 6/4 beat (just before V), the textbook default
        # is I6/4 (Sposobin §46 终止 6/4).  Prepend I6/4 to the pool so
        # the bonus in score_voicing (8.7c) prefers it, but DON'T hard-
        # restrict — if the melody is incompatible with I6/4 (e.g. a
        # plagal cadence where c64_beat melody doesn't fit I6/4), the
        # solver must still be able to pick a sensible chord.  Hard
        # restricting caused a "no valid voicing" fallback in题 3
        # (plagal cadence on Db5 melody).  See P8.1 review.
        if is_c64_beat and not is_cadence_beat and not is_v_beat:
            i64 = Chord(degree=1, quality=("maj" if local_key.mode == "major" else "min"),
                        inversion="6/4", kind="triad")
            # P14 (Sposobin ch46 终止中的重属和弦): also prepend DD7
            # (V7/V) so the cadential 6/4 can be prepared by a DD7→V6/4
            # → I PAC instead of the simpler I6/4→V→I.  In major keys
            # the DD7 root is the supertonic (degree 2).  We add all 4
            # inversions so the solver can pick the most natural.
            dd7_pool: list[Chord] = []
            try:
                dd7_deg = _secondary_v7_degree(local_key, 5)  # V/V root
                for inv in ("7", "6/5", "4/3", "2"):
                    dd7_pool.append(Chord(degree=dd7_deg, quality="dom7",
                                          inversion=inv, kind="seventh",
                                          target=5))
            except ValueError:
                pass
            # P23: profile 硬约束 - 强制 prepend 的 chord 必须先经过 profile pool 过滤
            #   (否则会在 ch1-4_triad_only profile 下塞进 DD7 / V7，破坏章节边界)
            allowed_keys = {(c.degree, c.quality, c.inversion, c.kind) for c in pool}
            i64_ok = (i64.degree, i64.quality, i64.inversion, i64.kind) in allowed_keys
            dd7_pool = [c for c in dd7_pool
                        if (c.degree, c.quality, c.inversion, c.kind) in allowed_keys]
            prepend = ([i64] if i64_ok else []) + dd7_pool
            pool = prepend + [c for c in pool
                              if not (c.degree == 1 and c.inversion == "6/4")]
        else:
            # Outside the c64_beat slot, the textbook default is I in
            # root position (or another I inversion only if bass is already
            # there).  We filter out I6/4 to prevent the solver from
            # picking cadential 6/4 decoration in places where it doesn't
            # belong.
            pool = [c for c in pool
                    if not (c.degree == 1 and c.inversion == "6/4")]

        # On the V beat (last beat of the second-to-last measure), restrict
        # the pool to V in root position.  This is the textbook cadence slot
        # where the bass should land on the dominant in preparation for the
        # final tonic.  V6/4 is not used here because the bass would need
        # to leap from the 5th of V to the root of I in one step, which is
        # considered stylistically rough in Sposobin.
        if is_v_beat and not is_cadence_beat:
            # P1/P5: V can be either V root or V7 in any inversion.  Bass
            # must land on the dominant in preparation for the final tonic.
            # For natural minor, use the natural v (minor triad); for
            # harmonic / melodic (and major), use V (major triad).
            # P7.5: the v_beat lives in the penultimate measure; its
            # local key is whatever was active for that measure.
            if local_key.mode == "minor" and local_key.variant == "natural":
                v_qual = "min"   # v (natural minor dominant)
            else:
                v_qual = "maj"   # V (harmonic minor / major dominant)
            v_root = Chord(degree=5, quality=v_qual, inversion="root", kind="triad")
            v7_root = Chord(degree=5, quality="dom7", inversion="7", kind="seventh")
            v76 = Chord(degree=5, quality="dom7", inversion="6/5", kind="seventh")
            v743 = Chord(degree=5, quality="dom7", inversion="4/3", kind="seventh")
            v2 = Chord(degree=5, quality="dom7", inversion="2", kind="seventh")
            # P7.3: include V9 (root position only, Sposobin ch23).
            v9_root = Chord(degree=5, quality="dom9", inversion="root",
                            kind="ninth")
            # P7.4: include DD 增六 (Sposobin ch30).  The DD 增六 is the
            # standard aug6 chord (Ger+6 form) used in the DD (pre-V)
            # function.  Resolves outward to V (♭6 → 5, #4 → 5).
            dd_aug6 = Chord(degree=2, quality="aug6_dd", inversion="root",
                            kind="triad")
            v_beat_candidates = [v_root, v7_root, v76, v743, v2, v9_root, dd_aug6]
            # P23: profile 硬约束 - V_beat 强制候选必须先经过 profile pool 过滤
            #   否则 ch1-4_triad_only profile 下会塞进 V7/V9/DDaug6，破坏章节边界
            allowed_keys = {(c.degree, c.quality, c.inversion, c.kind) for c in pool}
            v_beat_pool = [c for c in v_beat_candidates
                           if (c.degree, c.quality, c.inversion, c.kind) in allowed_keys]
            pool = v_beat_pool if v_beat_pool else pool  # 极端 fallback: 用原 pool

        # Chord-tone requirement (Sposobin §24, §45):
        #   - on metric accents (beat 1; and beat 3 in 4/4 which is the
        #     secondary accent),
        #   - on cadential slots (cadence / V_beat / c64_beat),
        # all 4 voices must be chord tones.  WEAK beats (beat 2, beat 4
        # in 4/4; beats 2, 3 in 3/4) allow non-chord tones in the
        # soprano via the NCT classifier (P4: passing / neighbor /
        # suspension).
        beat_in_m = beats_per_measure_in_beat[b_idx]
        is_secondary_strong = (beat_in_m == 3 and beat.duration == 1.0)
        require_ct = (is_strong or is_secondary_strong or is_cadence_beat
                      or is_v_beat or is_c64_beat)

        expansions: list[tuple[Voicing, Chord, float, list[Voicing], list[Chord], list[str]]] = []
        for (prev_v, prev_c, prev_sc, prev_v_list, prev_c_list) in beam:
            for chord in pool:
                # Penultimate cadence: if prev is already V and current would
                # be I, OK; if current is V and prev was non-V, accept.
                voicings = enumerate_voicings(
                    chord, local_key,
                    melody=beat.soprano,
                    fixed_bass=beat.bass,
                    prev=prev_v,
                    prev_chord=prev_c,
                    prev_melody=prev_mels[b_idx],
                    next_melody=next_mels[b_idx],
                    is_strong_beat=is_strong,
                    is_cadence_beat=is_cadence_beat,
                    is_c64_beat=is_c64_beat,
                    require_chord_tones=require_ct,
                    max_results=40,
                    phrase_plan=phrase_plan,
                    beat_idx=b_idx,
                )
                # Note: we deliberately do NOT fall back to prev=None
                # when no valid voicing is found.  P1 review showed that
                # prev=None bypasses parallel-5/8 detection and produces
                # forbidden voicings.  Better to let the beam die and
                # report "no valid voicing" downstream.
                # See P1 stress test review for details.
                for v, sc, errs in voicings:
                    total = prev_sc + sc
                    expansions.append((
                        v, chord, total,
                        prev_v_list + [v],
                        prev_c_list + [chord],
                        errs,
                    ))
        if not expansions:
            # P18.5: if the melody-wins forced-fallback below succeeds,
            # we DON'T want a hard "no valid voicing" warning (the
            # user gets a working voicing, just not textbook-preferred).
            # The forced-fallback path appends directly to new_beam,
            # so we detect the rescue by checking new_beam after the
            # loop.  Here we only emit a hard warning if the rescue
            # fails.
            pass  # warning emitted only if the melody-wins fallback can't rescue
            # P8 (bass-given): if the pool was filtered down to nothing
            # by the bass constraint, fall back to the unfiltered pool
            # for this beat ONLY.  This is a graceful degradation —
            # the warning above tells the user the bass-given constraint
            # couldn't be satisfied (e.g. chromatic bass with no
            # matching diatonic chord).
            if beat.bass is not None and not is_cadence_beat:
                fallback_pool = _pool(local_key)
                fallback_voicings: list[tuple[Voicing, float, list[str]]] = []
                for chord in fallback_pool:
                    fallback_voicings.extend(
                        enumerate_voicings(
                            chord, local_key,
                            melody=beat.soprano,
                            prev=beam[0][0] if beam else None,
                            prev_chord=beam[0][1] if beam else None,
                            prev_melody=prev_mels[b_idx],
                            next_melody=next_mels[b_idx],
                            is_strong_beat=is_strong,
                            is_cadence_beat=is_cadence_beat,
                            is_c64_beat=is_c64_beat,
                            require_chord_tones=require_ct,
                            max_results=40,
                            phrase_plan=phrase_plan,
                            beat_idx=b_idx,
                        )
                    )
                if fallback_voicings:
                    fallback_voicings.sort(key=lambda r: r[1], reverse=True)
                    best_v_f, best_sc_f, _ = fallback_voicings[0]
                    best_c_f = fallback_pool[0]  # paired by index not guaranteed
                    # Use the chord that produced the best voicing
                    # (fallback_voicings and fallback_pool are in same
                    # order from enumerate_voicings, but we'll re-derive)
                    # Simpler: take the first valid (v, c) pair by
                    # re-running enumerate for the first chord that
                    # produced a valid voicing.
                    for chord in fallback_pool:
                        vs = enumerate_voicings(
                            chord, local_key,
                            melody=beat.soprano,
                            prev=beam[0][0] if beam else None,
                            prev_chord=beam[0][1] if beam else None,
                            prev_melody=prev_mels[b_idx],
                            next_melody=next_mels[b_idx],
                            is_strong_beat=is_strong,
                            is_cadence_beat=is_cadence_beat,
                            is_c64_beat=is_c64_beat,
                            require_chord_tones=require_ct,
                            max_results=1,
                            phrase_plan=phrase_plan,
                            beat_idx=b_idx,
                        )
                        if vs:
                            best_v_f, best_sc_f, _ = vs[0]
                            best_c_f = chord
                            break
                    # P8 review fix: PRESERVE the v_list / c_list from
                    # the current beam — rebuilding from [best_v_f] would
                    # discard the path accumulated so far, and the
                    # post-processing loop (`v_path[cum_beats + k]`)
                    # would then IndexError on later measures because
                    # v_path is shorter than the expected beat count.
                    cur_v_list = beam[0][3] if beam else []
                    cur_c_list = beam[0][4] if beam else []
                    new_beam_fb: list[tuple] = [(
                        best_v_f, best_c_f, best_sc_f,
                        cur_v_list + [best_v_f],
                        cur_c_list + [best_c_f],
                    )]
                    beam = new_beam_fb
                    chosen.append((best_v_f, best_c_f, best_sc_f))
                    continue
            # Standard fallback: carry forward the best state and grow
            # the path by one (re-using the last voicing).  We do NOT
            # fall back to prev=None here — that bypasses parallel-5/8
            # and produces forbidden voicings (see P1 review).
            new_beam = []
            for (pv, pc, ps, pvl, pcl) in beam:
                # P8: if pc is None (first beat, prev_c was None) and we
                # have no valid candidate, fall back to a tonic I chord
                # in the local key so the rest of the pipeline (which
                # accesses c.quality / c.degree / c.inversion) doesn't
                # crash.  This is a graceful degradation, not a correct
                # harmonization — the warning above is the user signal.
                if pc is None:
                    pc = Chord(
                        degree=1,
                        quality=("maj" if local_key.mode == "major" else "min"),
                        inversion="root",
                        kind="triad",
                    )
                # Also: if pv is None (first beat) and the pool was
                # empty even for the fallback, synthesize a default
                # voicing so the rest of the pipeline doesn't crash on
                # `voicing.notes()`.
                if pv is None:
                    sop_note = beat.soprano or Note.from_name("C4")
                    if local_key.mode == "major":
                        alt_note = Note.from_name("E4")
                        ten_note = Note.from_name("G3")
                    else:
                        alt_note = Note.from_name("Eb4")
                        ten_note = Note.from_name("G3")
                    if beat.bass is not None:
                        bas_note = beat.bass
                    else:
                        bas_note = Note.from_name("C3")
                    pv = Voicing(soprano=sop_note, alto=alt_note,
                                 tenor=ten_note, bass=bas_note)
                # P18.5 fix: if the user's melody is NOT a chord tone of
                # the carried-forward chord, the carry-forward will
                # silently drop the melody (soprano stays at prev_v's
                # pitch).  Force the soprano to beat.soprano by
                # synthesizing a new voicing in a chord that has the
                # melody as a chord tone.  Prefer I (tonic) for
                # melody-given carry-forward — Sposobin §46 ending
                # cadence: ii7/V → I is the textbook resolution, so
                # when forced, the melody should land on I.
                if beat.soprano is not None and pv.soprano.midi != beat.soprano.midi:
                    # Try every chord whose pitch-class set contains
                    # beat.soprano.pc.  Score each candidate by inner-
                    # voice delta from pv, with I (tonic) preferred by
                    # a 5-semitone tiebreaker.
                    mel_pc = beat.soprano.pc
                    best_pick: tuple[Chord, Voicing] | None = None
                    best_dist = 1_000_000
                    for c2 in _pool(local_key):
                        if c2.degree == 0:
                            continue
                        if mel_pc not in c2.pitch_classes(local_key):
                            continue
                        # Just try to find any inner voicing for
                        # this chord that minimizes distance to pv.
                        from_inner = enumerate_voicings(
                            c2, local_key,
                            melody=beat.soprano,
                            prev=pv, prev_chord=pc,
                            prev_melody=prev_mels[b_idx],
                            next_melody=next_mels[b_idx],
                            is_strong_beat=is_strong,
                            is_cadence_beat=is_cadence_beat,
                            is_c64_beat=is_c64_beat,
                            require_chord_tones=require_ct,
                            max_results=4,
                            phrase_plan=phrase_plan,
                            beat_idx=b_idx,
                        )
                        for v2, sc2, _ in from_inner:
                            # total inner-voice distance from pv
                            d = (abs(v2.alto.midi - pv.alto.midi)
                                 + abs(v2.tenor.midi - pv.tenor.midi)
                                 + abs(v2.bass.midi - pv.bass.midi))
                            # Sposobin preference: when melody is the
                            # 3rd or 5th of I (tonic), prefer I over
                            # vi/IV — the textbook resolution.
                            if c2.degree == 1 and c2.quality == ("maj" if local_key.mode == "major" else "min"):
                                d -= 5
                            if d < best_dist:
                                best_dist = d
                                best_pick = (c2, v2)
                    if best_pick is not None:
                        c2, v2 = best_pick
                        new_beam.append((
                            v2, c2, ps - 5.0,  # small penalty for forced fallback
                            pvl + [v2], pcl + [c2],
                        ))
                        continue
                new_beam.append((pv, pc, ps, pvl + [pv], pcl + [pc]))
            beam = new_beam
            chosen.append((beam[0][0], beam[0][1], beam[0][2]))
            continue
        # Top-K
        expansions.sort(key=lambda r: r[2], reverse=True)
        new_beam: list[tuple] = []
        for v, chord, total, v_list, c_list, errs in expansions[:effective_k]:
            new_beam.append((v, chord, total, v_list, c_list))
        beam = new_beam
        # Take best so far
        best_v, best_c, best_sc, _, _ = beam[0]
        chosen.append((best_v, best_c, best_sc))

    # Build output for top-N full paths.  First one becomes the
    # primary result; the rest go under `alternatives`.
    # P8.1: top_n distinct full-path solutions returned.
    def _build_path_output(v_path, c_path, score) -> dict:
        """Build {summary, measures} for one full path."""
        measures_out: list[dict] = []
        cadence_per_measure: list[str | None] = [None] * measure_count
        cum_beats = 0
        prev_last_c: Chord | None = None
        prev_last_v: Voicing | None = None
        for m_idx in range(measure_count):
            n_beats = len(melody_pitches[m_idx])
            m_beats_out = []
            for k in range(n_beats):
                v = v_path[cum_beats + k]
                c = c_path[cum_beats + k]
                b_abs = cum_beats + k
                lk = beat_to_local_key[b_abs]
                dbl = doubled_degree(v, c, lk)
                func = function_of(c.degree, lk.mode)
                nct_type: str | None = None
                if v.soprano is not None and not is_chord_tone(v.soprano, c, lk):
                    prev_c = c_path[b_abs - 1] if b_abs > 0 else None
                    nct_type = classify_soprano_nct(
                        v.soprano, c, lk,
                        prev_mel=prev_mels[b_abs],
                        next_mel=next_mels[b_abs],
                        prev_chord=prev_c,
                        is_strong=(k == 0),
                    )
                    if nct_type is None and k != 0:
                        next_c = c_path[b_abs + 1] if b_abs + 1 < len(c_path) else None
                        if next_c is not None and is_anticipation(v.soprano, next_c, lk):
                            nct_type = "anticipation"
                    if (nct_type is None
                            and prev_mels[b_abs] is not None
                            and prev_prev_mels[b_abs] is not None):
                        if is_escape_tone(
                                prev_prev_mels[b_abs], prev_mels[b_abs],
                                v.soprano, lk, c):
                            nct_type = "escape"
                v_prev = v_path[b_abs - 1] if b_abs > 0 else None
                v_next = v_path[b_abs + 1] if b_abs + 1 < len(v_path) else None
                c_prev = c_path[b_abs - 1] if b_abs > 0 else None
                c_next = c_path[b_abs + 1] if b_abs + 1 < len(c_path) else None
                nct_agg = classify_voicing_ncts(
                    v, v_prev, v_next, c_prev, c, c_next, lk,
                    is_strong=(k == 0),
                )
                voice_ncts = dict(nct_agg["per_voice"])
                if nct_type == "suspension":
                    voice_ncts["soprano"] = "suspension"
                multi_susp = nct_agg["multi_voice_suspension"]
                n_susp = sum(1 for v_label in voice_ncts.values() if v_label == "suspension")
                if n_susp >= 3:
                    multi_susp = "triple"
                elif n_susp == 2:
                    multi_susp = "double"
                elif n_susp == 1:
                    multi_susp = "single"
                else:
                    multi_susp = "none"
                expl = (
                    f"rom={c.roman_label(lk)} fig={c.figure(lk)} "
                    f"inv={c.inversion} func={func} doubled={dbl or 'none'}"
                    + (f" nct={nct_type}" if nct_type else "")
                    + (f" multiSusp={multi_susp}" if multi_susp != "none" else "")
                )
                beat_dict = {
                    "beat": k + 1,
                    "offset": float(k),
                    "duration": 1.0,
                    "soprano": v.soprano.name,
                    "alto": v.alto.name,
                    "tenor": v.tenor.name,
                    "bass": v.bass.name,
                    "roman": c.roman_label(key),
                    "figure": c.figure(key),
                    "inversion": c.inversion,
                    "doubled": dbl or "none",
                    "function": func,
                    "non_chord_tone": nct_type or "none",
                    "voice_ncts": voice_ncts,
                    "multi_voice_suspension": multi_susp,
                    "is_pivot": bool(k == 0 and lk != beat_to_local_key[b_abs - 1] if b_abs > 0 else False),
                    "explanation": expl,
                }
                m_beats_out.append(beat_dict)
            # Cadence detection per measure
            cadence = None
            if m_idx > 0 and prev_last_c is not None:
                curr_c = c_path[cum_beats + n_beats - 1]
                curr_v = v_path[cum_beats + n_beats - 1]
                lk_for_cadence = beat_to_local_key[cum_beats + n_beats - 1]
                cadence = detect_cadence(prev_last_c, curr_c, curr_v, lk_for_cadence)
                prev_lk = beat_to_local_key[cum_beats - 1] if cum_beats > 0 else key
                curr_lk = lk_for_cadence
                if prev_lk != curr_lk and cadence is not None and not cadence.startswith("modulation_"):
                    cadence = f"modulation_{cadence}"
            prev_last_c = c_path[cum_beats + n_beats - 1]
            prev_last_v = v_path[cum_beats + n_beats - 1]
            cum_beats += n_beats
            m_dict = {
                "number": m_idx + 1,
                "beats": m_beats_out,
                "cadence": cadence,
            }
            measures_out.append(m_dict)
            cadence_per_measure[m_idx] = cadence

        key_per_measure: list[str] = [
            f"{local_key_for_measure(mi).tonic_name} {local_key_for_measure(mi).mode}"
            for mi in range(measure_count)
        ]
        summary = {
            "key": f"{key.tonic_name} {key.mode}",
            "timeSignature": time_signature,
            "measureCount": measure_count,
            "qualify": True,
            "violations": [],
            "score": float(score),
            "cadences": cadence_per_measure,
            "keyPerMeasure": key_per_measure,
            "sequenceSpans": find_sequence_spans(measures_out),
            # P11 (Sposobin ch35 远关系调/半音转调): per-key-change
            # tonal relationship.  Each entry: {measure, fromKey, toKey,
            # relationship} where relationship is one of 'close' /
            # 'distant' / 'parallel' / 'relative' / 'chromatic'
            # (6+ accidentals apart, requires enharmonic pivot).
            "modulationRelationships": _modulation_relationships(
                key, parsed_changes),
            # P18.5: confidence score 0-100 with evidence list, so the
            # frontend can show "置信度 87% — 3 个依据" instead of just
            # raw float score.  Computed per-path; not yet attached here
            # (this is in the warning-free primary path).  See below.
        }
        summary["confidence"], summary["confidenceEvidence"] = _compute_confidence(
            score, cadence_per_measure, warnings
        )

        # P21.4 — phrase-plan attached to output for the frontend.
        # Two fields:
        #   "phrasePlan"    : the input plan (or null if no plan given)
        #   "phraseMatch"   : per-phrase summary of the actual solution —
        #                     chord sequence + role match + cadence match.
        # The match field is computed only when phrase_plan is given;
        # otherwise it's null so P0-P8 outputs are byte-identical to
        # before P21.4.
        if phrase_plan is not None and _PHRASE_PLANNER_AVAILABLE:
            try:
                summary["phrasePlan"] = {
                    "source": phrase_plan.source,
                    "totalBeats": phrase_plan.total_beats,
                    "plans": [
                        {
                            "phraseId": p.phrase_id,
                            "startBeat": p.start_beat,
                            "endBeat": p.end_beat,
                            "lengthBeats": p.length_beats,
                            "phraseRole": p.phrase_role,
                            "targetCadence": p.target_cadence,
                            "targetFunction": p.target_function,
                            "strategyHint": dict(p.strategy_hint),
                        }
                        for p in phrase_plan.plans
                    ],
                }
                summary["phraseMatch"] = _summarise_phrase_match(
                    phrase_plan, c_path, beat_to_local_key, measure_count,
                )
            except Exception:
                # Phrase output is purely diagnostic — never break
                # the primary output over a planner bug.
                summary["phrasePlan"] = None
                summary["phraseMatch"] = None
        else:
            summary["phrasePlan"] = None
            summary["phraseMatch"] = None

        return {"summary": summary, "measures": measures_out}

    # Build top-N (or however many survived in the beam)
    n_results = min(top_n, len(beam))
    primary = beam[0]
    primary_out = _build_path_output(primary[3], primary[4], primary[2])
    alternatives: list[dict] = []
    for i in range(1, n_results):
        pv, pc, psc, pvl, pcl = beam[i]
        alt_out = _build_path_output(pvl, pcl, psc)
        alt_out["rank"] = i + 1
        alt_out["deltaScore"] = round(primary[2] - psc, 2)
        alternatives.append(alt_out)

    return SolveResult(
        summary=primary_out["summary"],
        measures=primary_out["measures"],
        warnings=warnings,
        alternatives=alternatives,
    )


def _summarise_phrase_match(
    phrase_plan,
    c_path: list,
    beat_to_local_key: list,
    measure_count: int,
) -> list[dict]:
    """P21.4 — per-phrase summary of the actual chord sequence.

    For each PhrasePlan in the plan, gather the chord sequence that
    actually landed on its beat range and compare it to the
    planner's intent.  The output is a list of dicts suitable for
    direct JSON serialisation, intended for the frontend's
    phrase-detail panel.

    Each match entry has:
      phraseId, startBeat, endBeat, phraseRole,
      targetCadence, targetFunction,
      actualCadence (string or None — the cadence that
        ``detect_cadence`` would report for the last chord of the
        phrase),
      roleMatch (bool — whether actualCadence matches targetCadence
        when both are non-None),
      chordSequence (list[str] — the chord figure() for each beat).
    """
    match: list[dict] = []
    for p in phrase_plan.plans:
        seq: list[str] = []
        for b in range(p.start_beat, p.end_beat + 1):
            if b < len(c_path) and b < len(beat_to_local_key):
                ch = c_path[b]
                lk = beat_to_local_key[b]
                try:
                    seq.append(str(ch.figure(lk)) if ch is not None else "—")
                except Exception:
                    seq.append("?")
            else:
                seq.append("—")
        # Cadence at the end of the phrase (if any)
        actual_cadence: str | None = None
        try:
            end_b = p.end_beat
            if end_b > 0 and end_b < len(c_path) and end_b < len(beat_to_local_key):
                prev_c = c_path[end_b - 1]
                curr_c = c_path[end_b]
                if prev_c is not None and curr_c is not None:
                    actual_cadence = detect_cadence(
                        prev_c, curr_c,
                        # voicing is not available here; we pass a
                        # minimal stand-in so detect_cadence can
                        # still check root motion and bass.  Bass is
                        # all that detect_cadence actually needs.
                        # See solver.detect_cadence for the full
                        # signature; we only care about root+inversion
                        # which doesn't need the voicing.
                        # We pass a dummy voicing — detect_cadence
                        # will use prev_c.bass and curr_c.bass via
                        # pitch_classes() which doesn't need the
                        # voicing either.
                        _dummy_voicing_for_cadence(),
                        beat_to_local_key[end_b],
                    )
        except Exception:
            actual_cadence = None
        # role match: simple check — if both target and actual are
        # set, do they agree?
        role_match: bool | None = None
        if p.target_cadence and actual_cadence:
            # Normalise: target "PAC" matches actual "PAC"
            # (detect_cadence returns lower-case "pac" in some
            # versions; upper-case in others — be defensive).
            t = p.target_cadence.strip().lower()
            a = actual_cadence.strip().lower()
            role_match = (t == a)
        elif p.target_cadence is None and actual_cadence is None:
            role_match = None  # nothing to compare
        elif p.target_cadence is None and actual_cadence is not None:
            role_match = None  # user didn't specify; we don't claim match
        else:
            role_match = False  # user wanted a cadence, didn't get one
        match.append({
            "phraseId": p.phrase_id,
            "startBeat": p.start_beat,
            "endBeat": p.end_beat,
            "phraseRole": p.phrase_role,
            "targetCadence": p.target_cadence,
            "targetFunction": p.target_function,
            "actualCadence": actual_cadence,
            "roleMatch": role_match,
            "chordSequence": seq,
        })
    return match


def _dummy_voicing_for_cadence():
    """P21.4 — minimal stand-in Voicing for ``detect_cadence``.

    ``detect_cadence`` only uses the voicing to extract the bass
    position (root-position check, etc.).  Since the bass pitch
    class is fully determined by the chord itself, the voicing
    object is mostly a placeholder.  We import Voicing here to
    avoid a hard import at module load (in case Voicing is later
    moved or refactored).
    """
    try:
        return Voicing(soprano=Note.from_name("C4"),
                       alto=Note.from_name("E4"),
                       tenor=Note.from_name("G3"),
                       bass=Note.from_name("C3"))
    except Exception:
        return None


def _compute_confidence(score: float, cadence_per_measure: list, warnings: list) -> tuple[int, list[str]]:
    """P18.5: compute a 0-100 confidence percentage + evidence list.

    Heuristic (transparent and Sposobin-rule-based — no LLM):
      - Internal score 90..130 normalises to 0..30 baseline.
      - Cadence bonus: PAC=+30, plagal=+20, IAC=+18, HC=+8, deceptive=+5, None=0.
        Each measure's cadence is counted once.
      - Fallback warning penalty: -4 per warning (the solver couldn't
        satisfy hard constraints at that beat — major issue).
      - Clamp to [0, 100].

    Returns (percent, evidence) where evidence is a list of human-readable
    reasons so the user knows why confidence is what it is.
    """
    baseline = max(0.0, min(30.0, (score - 90.0) * 0.75))  # 90→0, 130→30
    bonus = 0.0
    evidence: list[str] = []
    if cadence_per_measure:
        pac = sum(1 for c in cadence_per_measure if c == "PAC")
        plagal = sum(1 for c in cadence_per_measure if c == "plagal")
        iac = sum(1 for c in cadence_per_measure if c == "IAC")
        hc = sum(1 for c in cadence_per_measure if c == "HC")
        deceptive = sum(1 for c in cadence_per_measure if c == "deceptive")
        half_auth = sum(1 for c in cadence_per_measure if c == "half_authentic")
        if pac:
            bonus += 30.0 * pac
            evidence.append(f"{pac} 个 PAC 完全终止（+{30*pac:.0f}）")
        if plagal:
            bonus += 20.0 * plagal
            evidence.append(f"{plagal} 个变格终止（+{20*plagal:.0f}）")
        if iac:
            bonus += 18.0 * iac
            evidence.append(f"{iac} 个 IAC 不完全终止（+{18*iac:.0f}）")
        if hc:
            bonus += 8.0 * hc
            evidence.append(f"{hc} 个 HC 半终止（+{8*hc:.0f}）")
        if deceptive:
            bonus += 5.0 * deceptive
            evidence.append(f"{deceptive} 个阻碍终止（+{5*deceptive:.0f}）")
        if half_auth:
            evidence.append(f"{half_auth} 个半成终止（无加分）")
    penalty = 4.0 * len(warnings)
    if warnings:
        evidence.append(f"{len(warnings)} 个 fallback 警告（-{penalty:.0f}）")
    if not evidence:
        evidence.append("无可用依据 — 答案可能不可靠")
    confidence = max(0, min(100, int(round(baseline + bonus - penalty))))
    return confidence, evidence


def _degree_from_roman(roman: str) -> int:
    """Parse 'I', 'ii', 'vi6', 'V6/4' etc. into degree 1..7."""
    base = roman[0].lower()
    mapping = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7}
    return mapping.get(base, 1)


# ---------------------------------------------------------------------------
# 14. CLI / test entry
# ---------------------------------------------------------------------------


def _self_test() -> dict:
    """Smoke test: 4-measure C major I-IV-V-I in 4/4 with textbook bass.

    Soprano: C5 D5 E5 C5
    Bass textbook answer: C3 F2 G2 C3
    """
    key = "C"
    ts = "4/4"
    melody = [
        [Note.from_name("C5"), Note.from_name("C5"),
         Note.from_name("C5"), Note.from_name("C5")],
        [Note.from_name("F5"), Note.from_name("F5"),
         Note.from_name("F5"), Note.from_name("F5")],
        [Note.from_name("G5"), Note.from_name("G5"),
         Note.from_name("G5"), Note.from_name("G5")],
        [Note.from_name("C5"), Note.from_name("C5"),
         Note.from_name("C5"), Note.from_name("C5")],
    ]
    result = solve_melody(key, ts, melody)
    return result.to_dict()


if __name__ == "__main__":
    import json
    out = _self_test()
    print(json.dumps(out, indent=2, ensure_ascii=False))
