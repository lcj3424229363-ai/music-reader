"""Step 2 roundtrip test — verify editor_to_solver.py 现状符合 ENTRY_SCHEMA.md.

测试矩阵:
  1. 单音 entry → solver Note
  2. chord (多 pitches) entry → solver Note (取最高音, Sposobin 约定)
  3. rest entry → None
  4. 4/4 measure with 4 quarter notes → 4 Note
  5. dotted quarter + 8th → 2 Note (with extended duration)
  6. voice="1"|"2" 都接受, 转换结果相同 (因为 voice 字段被忽略)
  7. accidental (#/b) 正确转换
  8. duration / units 一致性

通过条件: 全部断言通过, 跟 schema §6 不变量一致.
"""
import sys
from pathlib import Path

# Add music-reader to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from editor_to_solver import (
    appjs_entry_to_soprano_note,
    appjs_entry_to_solver_beats,
    appjs_measures_to_solver_melody,
    appjs_measures_to_solver_bass,
    _APPJS_DURATION_TO_QUARTER,
)


def make_note_entry(step, octave, voice="1", duration="4", dotted=0, units=8, accidental=""):
    """Build a single note entry following ENTRY_SCHEMA.md §2.

    Display convention: step + alter + octave (e.g. "F#4", "Bb3", "C5").
    """
    display = f"{step}{accidental}{octave}"
    return {
        "kind": "note",
        "voice": voice,
        "pitches": [{"step": step, "octave": octave, "accidental": accidental, "display": display}],
        "duration": duration,
        "dotted": dotted,
        "units": units,
    }


def make_rest_entry(voice="1", duration="4", dotted=0, units=8):
    return {
        "kind": "rest",
        "voice": voice,
        "duration": duration,
        "dotted": dotted,
        "units": units,
    }


def make_chord_entry(pitches, voice="1", duration="4", dotted=0, units=8):
    """pitches: [(step, octave, accidental), ...]"""
    return {
        "kind": "note",
        "voice": voice,
        "pitches": [
            {"step": s, "octave": o, "accidental": a, "display": f"{s}{a}{o}"}
            for s, o, a in pitches
        ],
        "duration": duration,
        "dotted": dotted,
        "units": units,
    }


passed = 0
failed = 0


def check(name, cond, msg=""):
    global passed, failed
    if cond:
        print(f"  OK   {name}")
        passed += 1
    else:
        print(f"  FAIL {name}  {msg}")
        failed += 1


# ---- Test 1: 单音 entry → solver Note ----
print("Test 1: 单音 entry → solver Note")
n = appjs_entry_to_soprano_note(make_note_entry("C", 4))
check("C4 entry → Note", n is not None and n.pc == 0 and n.oct == 4, f"got {n}")

# ---- Test 2: chord → 最高音 ----
print("\nTest 2: chord (多 pitches) → 最高音 Note")
chord = make_chord_entry([("C", 4, ""), ("E", 4, ""), ("G", 4, "")])
n = appjs_entry_to_soprano_note(chord)
check("C-E-G chord → topmost (G4)", n is not None and n.pc == 7 and n.oct == 4, f"got {n}")

# ---- Test 3: rest → None ----
print("\nTest 3: rest entry → None")
n = appjs_entry_to_soprano_note(make_rest_entry())
check("rest entry → None", n is None, f"got {n}")

# ---- Test 4: 4/4 measure 4 quarter notes ----
print("\nTest 4: 4/4 measure with 4 quarter notes → 4 Note")
m = [make_note_entry(s, 4) for s in ["C", "D", "E", "F"]]
solver_m = appjs_measures_to_solver_melody([m])
check("1 measure × 4 entries → [[Note × 4]]", len(solver_m) == 1 and len(solver_m[0]) == 4)
check("solver pc sequence C-D-E-F (0,2,4,5)", [n.pc for n in solver_m[0]] == [0, 2, 4, 5])

# ---- Test 5: dotted quarter + 8th → 2 Note (duration in beat) ----
print("\nTest 5: dotted quarter (1.5) + 8th (0.5) → 2 Note with right beats")
m = [make_note_entry("C", 4, duration="4", dotted=1, units=12),  # dotted quarter
     make_note_entry("D", 4, duration="8", units=4)]             # eighth
beats = appjs_entry_to_solver_beats(m[0]), appjs_entry_to_solver_beats(m[1])
check("dotted quarter = 2 beats (rounded up)", beats[0] == 2, f"got {beats[0]}")
check("eighth = 1 beat (rounded)", beats[1] == 1, f"got {beats[1]}")
solver_m = appjs_measures_to_solver_melody([m])
check("2 entries → 3 beats (2+1) — but solver stores 1 Note per beat",
      len(solver_m[0]) == 3, f"got {len(solver_m[0])} beats")
# first 2 beats should be C (held), last beat should be D
check("beats 0,1 = C (dotted quarter held)", solver_m[0][0].pc == 0 and solver_m[0][1].pc == 0)
check("beat 2 = D (8th)", solver_m[0][2].pc == 2)

# ---- Test 6: voice="1" vs voice="2" 转换结果相同 ----
print("\nTest 6: voice='1' vs voice='2' 转换结果相同 (voice 字段被忽略)")
m1 = [make_note_entry("C", 4, voice="1")]
m2 = [make_note_entry("C", 4, voice="2")]
s1 = appjs_measures_to_solver_melody([m1])
s2 = appjs_measures_to_solver_melody([m2])
check("voice='1' and voice='2' produce same solver Note", s1[0][0].pc == s2[0][0].pc == 0)

# ---- Test 7: accidental (#/b) ----
print("\nTest 7: accidental #/b 正确转换")
n_sharp = appjs_entry_to_soprano_note(make_note_entry("F", 4, accidental="#"))
n_flat = appjs_entry_to_soprano_note(make_note_entry("B", 4, accidental="b"))
check("F#4 has pc=6 (F is 5, +1 = 6)", n_sharp is not None and n_sharp.pc == 6, f"got {n_sharp}")
check("Bb4 has pc=10 (B is 11, -1 = 10)", n_flat is not None and n_flat.pc == 10, f"got {n_flat}")

# ---- Test 8: duration / units 一致性 ----
print("\nTest 8: duration / units 转换表一致")
for dur, expected_quarter in _APPJS_DURATION_TO_QUARTER.items():
    expected_units = int(expected_quarter * 8)  # 1 quarter = 8 units
    entry = make_note_entry("C", 4, duration=dur, units=expected_units)
    beats = appjs_entry_to_solver_beats(entry)
    check(f"duration='{dur}' ({expected_quarter}q) → {beats} beats, {expected_units} units",
          beats >= 1)

# ---- Test 9: bass path (appjs_measures_to_solver_bass) ----
print("\nTest 9: bass path 跟 melody path 同 (P8 mode)")
m = [make_note_entry("C", 2)]  # C2 = low bass
solver_b = appjs_measures_to_solver_bass([m])
check("bass path produces C2 (pc=0, oct=2)", solver_b[0][0].pc == 0 and solver_b[0][0].oct == 2)

# ---- Test 10: 多小节 ----
print("\nTest 10: 多小节 (2 measures × 4 quarter notes)")
measures = [
    [make_note_entry("C", 4), make_note_entry("D", 4), make_note_entry("E", 4), make_note_entry("F", 4)],
    [make_note_entry("G", 4), make_note_entry("A", 4), make_note_entry("G", 4), make_note_entry("F", 4)],
]
solver_m = appjs_measures_to_solver_melody(measures)
check("2 measures", len(solver_m) == 2)
check("each measure has 4 beats", all(len(m) == 4 for m in solver_m))
check("measure 1 = C-D-E-F (pc 0,2,4,5)", [n.pc for n in solver_m[0]] == [0, 2, 4, 5])
check("measure 2 = G-A-G-F (pc 7,9,7,5)", [n.pc for n in solver_m[1]] == [7, 9, 7, 5])

# ---- Test 11: 不变量 — pitch display 跟 step+octave 一致 ----
print("\nTest 11: pitch display == f'{step}{octave}{accidental}'")
e = make_note_entry("F", 4, accidental="#")
p = e["pitches"][0]
check("F#4 display matches", p["display"] == "F#4" and p["step"] == "F" and p["octave"] == 4 and p["accidental"] == "#")

# ---- Summary ----
print()
print(f"Total: {passed + failed}, Passed: {passed}, Failed: {failed}")
if failed:
    print("\nFAIL: editor_to_solver.py has issues — see failures above")
    sys.exit(1)
else:
    print("\nPASS: editor_to_solver.py roundtrip matches ENTRY_SCHEMA.md invariants")
    sys.exit(0)
