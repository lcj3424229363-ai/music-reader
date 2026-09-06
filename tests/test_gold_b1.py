"""B1 gold 对拍: 用斯波索宾教材例题验证细分网格 (八分/附点节奏) 往返正确。

数据集: eval-data/extracted/hamony dataset/
  - four/<file>.xml     = 旋律 (题, 单声部 soprano)
  - original/<file>.xml = 完整 SATB 答案 (人工标准答案)

本测试验证: 旋律 fed into solver (细分因子自动检测) → 答案 soprano 声部
的节奏 (duration + dotted) 与原旋律完全一致, 音高 (pitch class) 一致.
和弦选择不强制等于课本 (多解并存), 只锁节奏往返这一 B1 核心不变量.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from reader import read_score
from reader_to_editor import reader_payload_to_editor
from editor_to_solver import (
    appjs_measures_subdivision,
    appjs_measures_to_solver_melody,
)
import solver as S
from server import _solver_to_four_part_response, FourPartRequest

SHTE = Path(r"C:\Users\Administrator\Documents\try\eval-data\extracted\hamony dataset")


def _pc(step, accidental):
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[step]
    if accidental == "#":
        base += 1
    elif accidental == "b":
        base -= 1
    return base % 12


def _rhythm_sig(measures):
    """输入旋律的 (kind, duration, dotted) 扁平节奏签名 (不含音高)."""
    out = []
    for m in measures:
        for e in m:
            out.append((e["kind"], e["duration"], int(e.get("dotted", 0) or 0)))
    return out


def _pitch_sig(measures):
    """输入旋律的扁平音高 (pc) 签名."""
    out = []
    for m in measures:
        for e in m:
            if e["kind"] == "rest":
                out.append(None)
            else:
                p = e["pitches"][0]
                out.append(_pc(p["step"], p.get("accidental", "")))
    return out


def _answer_rhythm_sig(entries):
    out = []
    for e in entries:
        out.append((e["kind"], e["duration"], int(e.get("dotted", 0) or 0)))
    return out


def _answer_pitch_sig(entries):
    out = []
    for e in entries:
        if e["kind"] == "rest":
            out.append(None)
        else:
            p = e["pitches"][0]
            out.append(_pc(p["step"], p.get("accidental", "")))
    return out


def _solve(chapter, fname, key, time_sig, profile="ch1-4_triad_only"):
    mel = reader_payload_to_editor(read_score(str(SHTE / chapter / "four" / fname)))
    measures = mel["sopranoMeasures"]
    subdiv = appjs_measures_subdivision(measures, time_sig)
    melody = appjs_measures_to_solver_melody(measures, time_sig)
    res = S.solve_melody(key, time_sig, melody, subdivision=subdiv,
                         chord_pool_profile=profile)
    req = FourPartRequest(key=key, timeSignature=time_sig, melodyMeasures=measures,
                          questionType="melody", chordPoolProfile=profile)
    out = _solver_to_four_part_response(res.to_dict(), req, melody_rhythm=measures)
    soprano = next(v for v in out["fourPart"]["voices"] if v["id"] == "soprano")
    flat = [e for m in soprano["measures"] for e in m["entries"]]
    return (subdiv, melody, _rhythm_sig(measures), _answer_rhythm_sig(flat),
            _pitch_sig(measures), _answer_pitch_sig(flat))


def test_ch4_04_e_major_dotted_eighth_roundtrip():
    """ch4-04 E major (2/4, 附点四分+八分): S=2, 节奏+音高往返一致."""
    subdiv, melody, in_r, out_r, in_p, out_p = _solve("ch4", "ch4-04_E major.xml", "E major", "2/4")
    assert subdiv == 2
    assert [len(m) for m in melody] == [4, 4, 4, 4]
    assert out_r == in_r, f"rhythm mismatch:\nin : {in_r}\nout: {out_r}"
    assert out_p == in_p, f"pitch mismatch:\nin : {in_p}\nout: {out_p}"


def test_ch4_09_g_major_eighth_roundtrip():
    """ch4-09 G major (含八分): S=2, 节奏+音高往返一致.

    此前最后终止处 solver 会把 V 延入末小节 (导音被重复 → 平行八度 → 束
    搜索断档 → 强制回退). 已加"导音不得重复"硬约束修复, 现在 V→I 正常.
    """
    subdiv, melody, in_r, out_r, in_p, out_p = _solve("ch4", "ch4-09_G major.xml", "G major", "4/4")
    assert subdiv == 2
    assert out_r == in_r, f"rhythm mismatch:\nin : {in_r}\nout: {out_r}"
    assert out_p == in_p, f"pitch mismatch:\nin : {in_p}\nout: {out_p}"


# ---- 多时值例题: 验证后端真的读到并往返保留"不同时值" ----

# (chapter, filename, key, expected_subdivision, chord_pool_profile)
_MULTI_DURATION_CASES = [
    # 3/8 拍, 旋律含 5 种时值: 十六分/八分/附点八分/四分/附点四分
    ("ch16", "ch16-08_c minor.xml", "C minor", 2, "ch8-20_v7"),
    # 3/4 拍, 十六分+四分+二分 (S=4 十六分网格)
    ("ch18", "ch18-04_B- major.xml", "B- major", 4, "full_p0-p7"),
    # 3/8 拍, 同 ch16-08 的 5 种时值
    ("ch20", "ch20-02_F major.xml", "F major", 2, "full_p0-p7"),
]


def _distinct_kinds(measures):
    out = set()
    for m in measures:
        for e in m:
            out.add((e["kind"], e["duration"], int(e.get("dotted", 0) or 0),
                     e.get("units")))
    return out


def test_multi_duration_examples_roundtrip():
    """多时值例题: 后端读到的不同时值 (duration/dotted/units) 往返后必须
    完全一致 —— 证明 reader→converter→solver→response 全链路真的区分了
    十六分/八分/附点八分/四分/附点四分/二分等不同时值, 没有混成一种."""
    for chapter, fname, key, exp_sub, profile in _MULTI_DURATION_CASES:
        mel = reader_payload_to_editor(
            read_score(str(SHTE / chapter / "four" / fname)))
        measures = mel["sopranoMeasures"]
        ts = mel["timeSignature"]
        subdiv = appjs_measures_subdivision(measures, ts)
        melody = appjs_measures_to_solver_melody(measures, ts)
        res = S.solve_melody(key, ts, melody, subdivision=subdiv,
                             chord_pool_profile=profile)
        req = FourPartRequest(key=key, timeSignature=ts, melodyMeasures=measures,
                              questionType="melody", chordPoolProfile=profile)
        out = _solver_to_four_part_response(res.to_dict(), req, melody_rhythm=measures)
        soprano = next(v for v in out["fourPart"]["voices"] if v["id"] == "soprano")
        out_measures = [m["entries"] for m in soprano["measures"]]

        assert subdiv == exp_sub, f"{fname}: S={subdiv}, expected {exp_sub}"
        in_kinds = _distinct_kinds(measures)
        out_kinds = _distinct_kinds(out_measures)
        assert out_kinds == in_kinds, (
            f"{fname}: 时值往返不一致\nin : {sorted(in_kinds)}\nout: {sorted(out_kinds)}"
        )
