"""editor_to_solver.py — 公共转换层

P22 第一刀: 把 app.js 编辑器内部 entry 数据结构
转换为 solver.solve_melody 所需的 melody_pitches /
bass_pitches 格式.

数据契约: 跟 docs/ENTRY_SCHEMA.md 严格一致. 任何修改请同步更新 schema 文档.

格式约定 (entry 形状, 完整定义见 ENTRY_SCHEMA.md §2):
    app.js editor entry (UI 内部, voice="1"|"2" legacy):
        { kind: "note", voice: "1"|"2", pitches: [{step, octave, accidental, display}],
          duration: "1|2|4|8|16|32|64|0", dotted: 0|1|2, units,
          tieStart, tieStop, ... }
        { kind: "rest", voice: "1"|"2", duration, dotted, units, ... }

    solver input:
        list[measure][beat] -> solver.Note | None
        1 beat = 1 quarter note (1.0)

    server 端两个 list 接口:
        melodyMeasures: 1 voice (soprano), treble.voice="1" 收集
        bassMeasures:   1 voice (bass),   bass.voice="2"   收集
        alto.voice="2" 和 tenor.voice="1" 不送 solver (UI 内部声部).

Voice 字段处理:
    当前实现 (P2.7+ 集成) **忽略 entry.voice 字段** — server 端按
    "哪个 list 在哪" 判断声部 (melodyMeasures 全部当 soprano,
    bassMeasures 全部当 bass). 这是因为:
      1. 用户实际操作只输 1 voice (melody 或 bass), 其他由 solver 填
      2. treble.voice="2" (alto) 和 bass.voice="1" (tenor) 是 UI 内部用,
         solver 不知道也不需要
    后续如果需要支持 4-voice 完整输入, 加一个 appjs_split_4voice 函数
    按 voice 字段拆 4 个 list (schema §3 映射), 见 ENTRY_SCHEMA.md §7.

Roundtrip 不变量 (跟 ENTRY_SCHEMA.md §6 对齐):
    1. 小节数 = N (N ≥ 1)
    2. 每小节总 units = 32 (4/4)
    3. pitches[].display == f"{step}{octave}{accidental}"
    4. duration ↔ units 一致 (4↔8, 2↔16, 1↔32, 8↔4, 16↔2)

迁移记录:
    原 server.py 4 个函数 (_appjs_entry_to_soprano_note /
    _appjs_entry_to_solver_beats / _appjs_measures_to_solver_melody /
    _appjs_measures_to_solver_bass) 一字不改照搬到此模块.

后续 (P22.1+):
    修 Bug #1 eighth-overcount: 4/4 8 个八分音符同 pitch
    应合并成 4 beats 而非 8 beats. 当前未做 (留给第二刀).
"""

from __future__ import annotations

import solver as sposobin_solver


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Accidental in app.js is 'b' for flat (or '#' for sharp).  Map to solver Note.
_APPJS_ACCIDENTAL_TO_SOLVER = {
    "":  "",   # natural
    "#": "#",
    "b": "b",  # music21 uses 'b' for flat
    "♯": "#",
    "♭": "b",
}


# app.js duration code (vexflow "w" / "h" / "q" / "8" / "16" / ...) -> quarter
# fractions used by the solver.  Solver's beat unit is 1 quarter = 1.0;
# a whole note is 4.0, a half is 2.0, a quarter is 1.0, an eighth is 0.5.
# app.js also has a separate "units" field where 1 quarter = 8 units
# (1/16 of a whole = 1 unit, see app.js durationUnits).  We compute the
# beat count from the duration code (the source of truth) and fall back
# to units/8 if duration is missing.
_APPJS_DURATION_TO_QUARTER = {
    "1": 4.0,    # whole
    "2": 2.0,    # half
    "4": 1.0,    # quarter
    "8": 0.5,    # eighth
    "16": 0.25,  # sixteenth
    "32": 0.125, # thirty-second
    "64": 0.0625,
    "0": 8.0,    # double-whole
}


# ---------------------------------------------------------------------------
# Single-entry converters
# ---------------------------------------------------------------------------


def appjs_entry_to_soprano_note(entry: dict) -> "sposobin_solver.Note | None":
    """Convert a single app.js note entry to a solver.Note.  Returns None
    for rests, missing pitches, or parser failures (so the caller can
    skip that beat)."""
    if entry.get("kind") != "note":
        return None
    pitches = entry.get("pitches") or []
    if not pitches:
        return None
    # Multi-pitch entry (chord) — take the topmost pitch (soprano) for
    # the solver melody input.  This matches the Sposobin convention of
    # treating the topmost voice as the soprano line.
    top = max(pitches, key=lambda p: (p.get("octave", 0),
                                      p.get("step", "")))
    step = (top.get("step") or "C").upper()
    octave = int(top.get("octave", 4))
    acc = _APPJS_ACCIDENTAL_TO_SOLVER.get(top.get("accidental", ""), "")
    name = f"{step}{acc}{octave}"
    try:
        return sposobin_solver.Note.from_name(name)
    except Exception:
        return None


def appjs_entry_to_solver_beats(entry: dict) -> int:
    """How many quarter-note beats does this app.js entry cover?

    P18.7 fix: app.js durationUnits uses 1 quarter = 8 units (1 unit = a
    sixteenth), but the previous server logic used "1 quarter = 2 units"
    so a 4-quarter note became 16 beats and overflowed the measure,
    causing solver IndexError.  Now we read the duration code (the
    authoritative source) and round to the nearest integer beat count.
    A dotted quarter (duration '4', dotted 1) yields 1.5 → 2 beats in
    practice (we round up to preserve the entry's actual span).
    """
    dur = str(entry.get("duration") or "4")
    quarter = _APPJS_DURATION_TO_QUARTER.get(dur)
    if quarter is None:
        # Fall back to units/8 (1 quarter = 8 units per app.js)
        units = float(entry.get("units", 8) or 8)
        quarter = units / 8.0
    dotted = int(entry.get("dotted") or 0)
    if dotted >= 2:
        quarter *= 1.75
    elif dotted == 1:
        quarter *= 1.5
    # Round to the nearest 0.25 beat (eighth-note resolution).  The
    # solver stores one Note per beat, so an entry that lasts 0.5 beat
    # fills 1 beat (held for the second half) — but we mark the note
    # as repeating, see caller.  Beat counts of 0 round up to 1.
    n_beats = max(1, int(round(quarter * 4) / 4))
    # Actually round to nearest 0.5 beat
    n_beats_quarter = max(0.25, quarter)
    # Convert quarter-fraction to integer beat count: we want each
    # quarter fraction to map to whole beats when possible.  An entry
    # that lasts 1 quarter = 1 beat; 0.5 quarter = 0.5 beat (we round
    # to 1 in the array; sub-beat entries are out of solver's scope).
    n_beats = max(1, int(round(quarter)))
    return n_beats


# ---------------------------------------------------------------------------
# Per-measure converters
# ---------------------------------------------------------------------------


def appjs_measures_to_solver_melody(measures: list[list[dict]]) -> list[list["sposobin_solver.Note | None"]]:
    """Convert app.js per-measure entries to solver's melody_pitches
    format: list[measure][beat] -> Note | None.

    P18 bug fix: the previous version treated each entry as one beat.
    That's wrong — a 4/4 measure with 1 whole-note entry (units=8) was
    sent as 1 beat, and 8 eighth-notes (each units=1) as 8 beats, both
    claiming to fill a 4/4 measure.  Solver ended up with whatever
    length the user typed in entry count, not in rhythmic units.

    P18.7 fix: app.js units field is 1/16 of a whole note (so 1 quarter
    = 8 units), but the prior code used "1 quarter = 2 units" which
    over-expanded every entry by 4× and overflowed measure capacity,
    causing IndexError inside the solver.

    Now: each entry is expanded to (entry duration in quarter fraction,
    rounded) beats.  duration code '4' (quarter) = 1 beat, '2' (half)
    = 2 beats, '1' (whole) = 4 beats, '8' (eighth) = 1 beat (rounded).
    """
    out: list[list[sposobin_solver.Note | None]] = []
    for measure in measures:
        line: list[sposobin_solver.Note | None] = []
        for entry in measure:
            if entry is None:
                line.append(None)
                continue
            note = appjs_entry_to_soprano_note(entry)
            n_beats = appjs_entry_to_solver_beats(entry)
            if note is None:
                # Rest or failed parse.  Spend the entry's beat count as
                # None beats so the measure still sums to the right
                # length.  If duration missing, default to 1 quarter
                # (1 beat).
                line.extend([None] * n_beats)
            else:
                # Duplicate the note across its beat span — solver
                # stores one Note per beat, so a held whole-note shows
                # up as 4 quarter beats at the same pitch.
                line.extend([note] * n_beats)
        out.append(line)
    return out


def appjs_measures_to_solver_bass(measures: list[list[dict]]) -> list[list["sposobin_solver.Note | None"]]:
    """P8: convert app.js per-measure entries to solver's bass_pitches
    format.  Identical to the melody converter — the difference is only
    in what the solver does with the result (anchors bass instead of
    soprano).  Kept as a separate function for clarity at call sites.
    """
    return appjs_measures_to_solver_melody(measures)


# ---------------------------------------------------------------------------
# Public alias (re-exported under non-underscore name for editor_to_solver)
# ---------------------------------------------------------------------------

# 保持原 server.py 的下划线命名以最小化 diff. 外部 import 推荐用 public 名.
public_appjs_entry_to_soprano_note = appjs_entry_to_soprano_note
public_appjs_entry_to_solver_beats = appjs_entry_to_solver_beats
public_appjs_measures_to_solver_melody = appjs_measures_to_solver_melody
public_appjs_measures_to_solver_bass = appjs_measures_to_solver_bass
