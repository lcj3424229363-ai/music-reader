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
    Bug #1 eighth-overcount 已在第二刀修复: `appjs_entry_to_solver_beats`
    现在按拍号把时值精确换算成整拍, 非整拍时值(八分/附点四分等)直接抛
    明确的 ValueError, 不再用 `round()` 银行家舍入把 0.5 拍抬成 1 拍.
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


def _beat_units(time_signature: str) -> int:
    """一个"拍"的 32 分单位数: 32/den (4/4→8, 6/8→4, 2/2→16)."""
    try:
        den = int(str(time_signature).split("/")[1])
    except (ValueError, IndexError):
        den = 4
    if den <= 0:
        den = 4
    return max(1, 32 // den)


def _entry_units(entry: dict) -> float:
    """Entry 时值, 单位 = 32 分音符 (1 四分 = 8 单位, 与前端 units 一致).

    前端 `units` 字段为准 (已含附点/三连音); 缺失时退回 duration 码 + dotted.
    """
    units = entry.get("units")
    if isinstance(units, (int, float)) and units > 0:
        return float(units)
    dur = str(entry.get("duration") or "4")
    quarter = _APPJS_DURATION_TO_QUARTER.get(dur)
    if quarter is None:
        quarter = 1.0
    base = quarter * 8.0
    dotted = int(entry.get("dotted") or 0)
    if dotted >= 2:
        base *= 1.75
    elif dotted == 1:
        base *= 1.5
    return base


def _gcd_int(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


def appjs_measures_subdivision(measures: list[list[dict]], time_signature: str = "4/4") -> int:
    """网格细分因子 S (1/2/4...): 由全曲最细音符时值决定.

    例 (4/4): 全四分 → 1 (向后兼容); 含八分 → 2; 含十六分 → 4.
    6/8 含十六分 → 2.  用所有音符时值的 GCD 对齐到拍 (1 拍 = 32/den 单位).
    """
    beat_units = _beat_units(time_signature)
    unit_list: list[int] = []
    for measure in (measures or []):
        for entry in (measure or []):
            if entry is None:
                continue
            # 休止符也要参与 GCD (如 2/2 拍里四分休止符比二分音符更细,
            # 网格必须细到能表示休止符, 否则四分休止符无法落格).
            u = _entry_units(entry)
            if u > 0:
                unit_list.append(int(round(u)))
    if not unit_list:
        return 1
    cell = unit_list[0]
    for u in unit_list[1:]:
        cell = _gcd_int(cell, u)
        if cell == 1:
            break
    cell = max(1, cell)
    if cell >= beat_units:
        return 1
    return beat_units // cell


def appjs_entry_to_solver_cells(entry: dict, cell_units: int) -> int:
    """Entry → 网格格数 (entry_units / cell_units). 必须整除, 否则 ValueError."""
    units = _entry_units(entry)
    n_cells = units / cell_units
    nearest = int(round(n_cells))
    if abs(n_cells - nearest) > 1e-6:
        raise ValueError(
            f"音符时值 {units:g} 单位无法落到 {cell_units} 单位的网格上："
            f"当前求解器只支持四分/八分/十六分及其附点、整拍组合。"
        )
    if nearest < 1:
        raise ValueError(f"音符时值 {units:g} 单位小于一个网格格，无法表示。")
    return nearest


# ---------------------------------------------------------------------------
# Per-measure converters
# ---------------------------------------------------------------------------


def appjs_measures_to_solver_melody(
    measures: list[list[dict]],
    time_signature: str = "4/4",
) -> list[list["sposobin_solver.Note | None"]]:
    """Convert app.js per-measure entries to solver's melody_pitches
    format: list[measure][cell] -> Note | None (B1 细分网格).

    网格格长 = 拍 / S, S 由全曲最细时值决定 (``appjs_measures_subdivision``).
    例 4/4 S=2: 全音符→8 格, 二分→4, 四分→2, 八分→1.  6/8 四分→4 格 (S=2).
    """
    subdiv = appjs_measures_subdivision(measures, time_signature)
    cell_units = _beat_units(time_signature) // subdiv
    out: list[list[sposobin_solver.Note | None]] = []
    for measure in measures:
        line: list[sposobin_solver.Note | None] = []
        for entry in measure:
            if entry is None:
                line.append(None)
                continue
            note = appjs_entry_to_soprano_note(entry)
            n_cells = appjs_entry_to_solver_cells(entry, cell_units)
            if note is None:
                # Rest: 占 n_cells 个空拍, 保持小节长度对齐.
                line.extend([None] * n_cells)
            else:
                # 一个音跨多格时复制到每一格 (solver 每格一个音),
                # 输出侧按 rhythm_template 再合并回原时值.
                line.extend([note] * n_cells)
        out.append(line)
    return out


def appjs_measures_to_solver_bass(
    measures: list[list[dict]],
    time_signature: str = "4/4",
) -> list[list["sposobin_solver.Note | None"]]:
    """P8: bass 转换 = melody 转换 (同一细分网格)."""
    return appjs_measures_to_solver_melody(measures, time_signature)


def appjs_measures_rhythm_template(
    measures: list[list[dict]],
    time_signature: str = "4/4",
) -> list[list[tuple[dict, int]]]:
    """Per-measure list of ``(entry, cell_count)`` in solver grid order.

    Used by the server to rebuild the original rhythm on the output side:
    the solver works at one note per cell, so this template lets the response
    re-merge a whole/half/eighth note back into a single long note instead of
    a run of repeated cells.
    """
    subdiv = appjs_measures_subdivision(measures, time_signature)
    cell_units = _beat_units(time_signature) // subdiv
    out: list[list[tuple[dict, int]]] = []
    for measure in measures:
        row: list[tuple[dict, int]] = []
        for entry in measure:
            if entry is None:
                continue
            row.append((entry, appjs_entry_to_solver_cells(entry, cell_units)))
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Public alias (re-exported under non-underscore name for editor_to_solver)
# ---------------------------------------------------------------------------

# 保持原 server.py 的下划线命名以最小化 diff. 外部 import 推荐用 public 名.
public_appjs_entry_to_soprano_note = appjs_entry_to_soprano_note
public_appjs_measures_subdivision = appjs_measures_subdivision
public_appjs_entry_to_solver_cells = appjs_entry_to_solver_cells
public_appjs_measures_to_solver_melody = appjs_measures_to_solver_melody
public_appjs_measures_to_solver_bass = appjs_measures_to_solver_bass
public_appjs_measures_rhythm_template = appjs_measures_rhythm_template
