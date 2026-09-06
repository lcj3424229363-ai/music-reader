"""test_editor_to_solver.py — 转换层验收测试 (含 B1 细分网格).

覆盖:
  1. P0 课本例题: 4 measures × 4 beats, 音高序列正确 (S=1 向后兼容)
  2. 全音符 / 二分音符 / 四分音符各自在 4/4 的格数
  3. 8 个八分音符 -> S=2, 8 cells (B1 支持八分)
  4. 4 个不同 pitch 四分音符 -> 4 cells 顺序正确
  5. rest entry -> None cell
  6. bass 转换 = melody 转换
  7. 和弦 -> 选 topmost pitch (soprano)
  8. 升降号 (# / b / natural) - solver flat-first 约定
  9. rest entry -> None note
 10. 附点四分 + 八分 -> S=2, 4 cells (附点节奏支持)
"""
import pytest

import solver as sposobin_solver
from editor_to_solver import (
    appjs_entry_to_soprano_note,
    appjs_measures_subdivision,
    appjs_measures_to_solver_bass,
    appjs_measures_to_solver_melody,
)


# ---------------------------------------------------------------------------
# Helper: build app.js entry dict
# ---------------------------------------------------------------------------

_DURATION_TO_UNITS = {
    "1": 32, "2": 16, "4": 8, "8": 4, "16": 2, "32": 1, "64": 0.5, "0": 32,
}


def make_note_entry(step, octave, duration, accidental=""):
    return {
        "kind": "note",
        "voice": "1",
        "pitches": [{
            "step": step, "octave": octave,
            "accidental": accidental,
            "display": f"{step}{octave}",
        }],
        "duration": duration,
        "dotted": False,
        "units": _DURATION_TO_UNITS.get(duration, 8),
        "tieStart": False, "tieStop": False, "slurStart": False, "slurStop": False,
        "fermata": False, "tupletType": "", "tupletGroup": "", "tupletPosition": "",
        "dynamic": "",
    }


def make_rest_entry(duration):
    return {
        "kind": "rest", "voice": "1", "duration": duration, "dotted": False,
        "units": _DURATION_TO_UNITS.get(duration, 8),
        "fermata": False, "tupletType": "", "tupletGroup": "", "tupletPosition": "",
        "dynamic": "",
    }


def make_chord_entry(pitches, duration):
    """pitches: list of (step, octave)"""
    return {
        "kind": "note", "voice": "1",
        "pitches": [
            {"step": s, "octave": o, "accidental": "", "display": f"{s}{o}"}
            for s, o in pitches
        ],
        "duration": duration, "dotted": False,
        "units": _DURATION_TO_UNITS.get(duration, 8),
        "tieStart": False, "tieStop": False, "slurStart": False, "slurStop": False,
        "fermata": False, "tupletType": "", "tupletGroup": "", "tupletPosition": "",
        "dynamic": "",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_p0_textbook_cadence_4_measures_4_beats_each():
    """P0 课本例题 p0_cadence: C-D-E-C | F-F-F-F | G-G-G-G | C-C-C-C in 4/4.

    验证抽出后行为与原 server.py 一致.
    """
    p0_measures = [
        [make_note_entry("C", 5, "4"), make_note_entry("D", 5, "4"),
         make_note_entry("E", 5, "4"), make_note_entry("C", 5, "4")],
        [make_note_entry("F", 5, "4")] * 4,
        [make_note_entry("G", 5, "4")] * 4,
        [make_note_entry("C", 5, "4")] * 4,
    ]
    melody = appjs_measures_to_solver_melody(p0_measures)

    assert len(melody) == 4
    assert all(len(m) == 4 for m in melody), \
        f"each 4/4 measure must have 4 beats, got {[len(m) for m in melody]}"

    # Verify pitch sequence per measure
    assert [n.name for n in melody[0]] == ["C5", "D5", "E5", "C5"]
    assert [n.name for n in melody[1]] == ["F5"] * 4
    assert [n.name for n in melody[2]] == ["G5"] * 4
    assert [n.name for n in melody[3]] == ["C5"] * 4


def test_whole_note_4_beats():
    """1 whole note in 4/4 -> 4 beats."""
    m = appjs_measures_to_solver_melody([[make_note_entry("C", 4, "1")]])
    assert len(m[0]) == 4
    assert m[0][0].name == "C4"


def test_two_half_notes_4_beats():
    """2 half notes in 4/4 -> 4 beats (2 + 2)."""
    m = appjs_measures_to_solver_melody([
        [make_note_entry("D", 4, "2"), make_note_entry("E", 4, "2")]
    ])
    assert len(m[0]) == 4
    assert [n.name for n in m[0]] == ["D4", "D4", "E4", "E4"]


def test_four_quarters_different_pitch_4_beats_in_order():
    """4 different quarter notes in 4/4 -> 4 beats, in pitch order."""
    m = appjs_measures_to_solver_melody([[
        make_note_entry("C", 4, "4"), make_note_entry("D", 4, "4"),
        make_note_entry("E", 4, "4"), make_note_entry("F", 4, "4"),
    ]])
    assert len(m[0]) == 4
    assert [n.name for n in m[0]] == ["C4", "D4", "E4", "F4"]


def test_eight_eighths_expand_to_eight_cells():
    """B1: 8 eighth notes (4/4) → S=2, 8 cells (八分现已支持)."""
    m = appjs_measures_to_solver_melody([
        [make_note_entry("C", 4, "8")] * 8
    ])
    assert appjs_measures_subdivision([[make_note_entry("C", 4, "8")] * 8], "4/4") == 2
    assert len(m[0]) == 8
    assert all(n.name == "C4" for n in m[0])


def test_rest_entry_is_none_beat():
    """Rest entry 转换为 None beat, 仍占一拍."""
    m = appjs_measures_to_solver_melody([[
        make_note_entry("C", 4, "4"), make_rest_entry("4"),
        make_note_entry("E", 4, "4"), make_note_entry("F", 4, "4"),
    ]])
    assert len(m[0]) == 4
    assert m[0][0].name == "C4"
    assert m[0][1] is None
    assert m[0][2].name == "E4"
    assert m[0][3].name == "F4"


def test_bass_converter_equals_melody_converter():
    """P8: bass 转换函数实现就是调 melody 转换函数 (行为一致)."""
    p0 = [[
        make_note_entry("C", 4, "4"), make_note_entry("D", 4, "4"),
        make_note_entry("E", 4, "4"), make_note_entry("F", 4, "4"),
    ]]
    melody = appjs_measures_to_solver_melody(p0)
    bass = appjs_measures_to_solver_bass(p0)
    assert melody == bass
    assert [n.name for n in bass[0]] == ["C4", "D4", "E4", "F4"]


def test_chord_picks_topmost_pitch_soprano():
    """多音和弦: 选 topmost pitch (soprano).

    P0 Sposobin 约定: topmost = soprano line.
    """
    entry = make_chord_entry([("C", 4), ("E", 4), ("G", 4)], "4")
    note = appjs_entry_to_soprano_note(entry)
    assert note.name == "G4", f"chord C+E+G should pick top G4, got {note.name}"


def test_chord_with_octave_diff_picks_topmost_octave():
    """和弦跨八度: topmost by (octave, step)."""
    entry = make_chord_entry([("C", 4), ("G", 5)], "4")
    note = appjs_entry_to_soprano_note(entry)
    assert note.name == "G5", f"chord C4+G5 should pick top G5, got {note.name}"


def test_accidentals_flat_first_spelling():
    """升降号转换: solver 用 flat-first spelling (F# 存为 Gb).

    已知约束: 这是 solver 内部约定, editor 端显示可保持 # / b 但
    进 solver 后会按 pc 重新拼写. 验证转化正确.
    """
    sharp = make_note_entry("F", 4, "4", "#")
    flat = make_note_entry("B", 4, "4", "b")
    natural = make_note_entry("C", 4, "4", "")

    # F#4 -> Gb4 (flat-first in solver)
    assert appjs_entry_to_soprano_note(sharp).name == "Gb4"
    # Bb4 -> Bb4
    assert appjs_entry_to_soprano_note(flat).name == "Bb4"
    # C4 -> C4
    assert appjs_entry_to_soprano_note(natural).name == "C4"


def test_rest_entry_returns_none_note():
    """Rest entry -> appjs_entry_to_soprano_note 返回 None."""
    rest = make_rest_entry("4")
    assert appjs_entry_to_soprano_note(rest) is None


def test_dotted_quarter_plus_eighth_supported():
    """附点四分 (12 单位) + 八分 (4 单位) → S=2, 4 cells (3+1), B1 支持附点."""
    dotted_q = make_note_entry("C", 4, "4")
    dotted_q["dotted"] = 1
    dotted_q["units"] = 12  # 前端 unitsForDuration 会正确填 12
    eighth = make_note_entry("D", 4, "8")
    m = appjs_measures_to_solver_melody([[dotted_q, eighth]])
    assert appjs_measures_subdivision([[dotted_q, eighth]], "4/4") == 2
    assert len(m[0]) == 4
    assert [n.name for n in m[0]] == ["C4", "C4", "C4", "D4"]


def test_double_dotted_quarter_alone_off_grid():
    """双附点四分 (14 单位) 单独无法对齐拍点 -> ValueError (仍明确拒绝)."""
    entry = make_note_entry("C", 4, "4")
    entry["dotted"] = 2
    entry["units"] = 14
    with pytest.raises(ValueError):
        appjs_measures_to_solver_melody([[entry]])
