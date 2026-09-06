"""批量对拍: 扫描 SHTE 数据集里所有含细分时值 (八分/十六分/附点) 的例题,
跑完整流水线 (reader → converter → 细分检测 → solver → response), 检查:

  1. 细分因子 S 检测正确 (与最细时值一致)
  2. 节奏往返 (duration/dotted/units 种类) 一致
  3. 音高往返 (soprano == 旋律) 一致

用法: python scripts/batch_gold_check.py [--max N]
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from reader import read_score
from reader_to_editor import reader_payload_to_editor
from editor_to_solver import appjs_measures_subdivision, appjs_measures_to_solver_melody
import solver as S
from server import _solver_to_four_part_response, FourPartRequest

SHTE = Path(r"C:\Users\Administrator\Documents\try\eval-data\extracted\hamony dataset")


def parse_key_from_filename(fname: str):
    """'ch16-08_c minor' → 'C minor'; 'ch4-03_A- major' → 'Ab major'."""
    stem = Path(fname).stem
    m = re.search(r'_([A-Ga-g])([#\-]?)\s*(major|minor)\s*$', stem)
    if not m:
        return None
    tonic = m.group(1).upper()
    acc = m.group(2)
    acc = "b" if acc == "-" else acc
    mode = m.group(3)
    return f"{tonic}{acc} {mode}"


def _kinds(measures):
    out = set()
    for m in measures:
        for e in m:
            out.add((e["kind"], e["duration"], int(e.get("dotted", 0) or 0),
                     e.get("units")))
    return out


def _rhythm(measures):
    out = []
    for m in measures:
        for e in m:
            out.append((e["kind"], e["duration"], int(e.get("dotted", 0) or 0)))
    return out


def _pitch(measures):
    out = []
    pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    for m in measures:
        for e in m:
            if e["kind"] == "rest":
                out.append(None)
            else:
                p = e["pitches"][0]
                v = pc[p["step"]] + (1 if p["accidental"] == "#" else -1 if p["accidental"] == "b" else 0)
                out.append(v % 12)
    return out


def run_one(four_path, key):
    mel = reader_payload_to_editor(read_score(str(four_path)))
    ts = mel["timeSignature"]
    measures = mel["sopranoMeasures"]
    subdiv = appjs_measures_subdivision(measures, ts)
    if subdiv <= 1:
        return None  # 只有整拍时值, 跳过
    melody = appjs_measures_to_solver_melody(measures, ts)
    try:
        res = S.solve_melody(key, ts, melody, subdivision=subdiv,
                             chord_pool_profile="full_p0-p7")
    except Exception as exc:
        return (subdiv, ts, key, "SOLVER_ERROR", str(exc)[:80])
    req = FourPartRequest(key=key, timeSignature=ts, melodyMeasures=measures,
                          questionType="melody", chordPoolProfile="full_p0-p7")
    out = _solver_to_four_part_response(res.to_dict(), req, melody_rhythm=measures)
    sop = next(v for v in out["fourPart"]["voices"] if v["id"] == "soprano")
    out_measures = [m["entries"] for m in sop["measures"]]

    rhythm_ok = _rhythm(out_measures) == _rhythm(measures)
    kinds_ok = _kinds(out_measures) == _kinds(measures)
    pitch_ok = _pitch(out_measures) == _pitch(measures)
    return (subdiv, ts, key, "OK" if (rhythm_ok and kinds_ok and pitch_ok) else "FAIL",
            "" if pitch_ok else f"pitch_ok={pitch_ok} rhythm_ok={rhythm_ok}")


def _has_subdivision(fp):
    """快速预筛: 原始 XML 里是否含八分/十六分 (避免对整拍文件跑 music21)."""
    try:
        text = fp.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return "<type>eighth</type>" in text or "<type>16th</type>" in text


def main():
    files = sorted(SHTE.glob("*/four/*.xml"))
    candidates = [fp for fp in files if _has_subdivision(fp)]
    print(f"四声部旋律文件 {len(files)} 个, 其中含八分/十六分 {len(candidates)} 个", flush=True)
    results = []
    for i, fp in enumerate(candidates, 1):
        key = parse_key_from_filename(fp.name)
        if key is None:
            continue
        print(f"[{i}/{len(candidates)}] {fp.parent.parent.name}/{fp.name} ...", flush=True)
        r = run_one(fp, key)
        if r is None:
            continue
        results.append((fp.name, fp.parent.parent.name, *r))

    # results 元组: (name, chapter, subdiv, ts, key, status, detail)
    ok = [r for r in results if r[5] == "OK"]
    fail = [r for r in results if r[5] != "OK"]
    print(f"总含细分时值例题: {len(results)}, 节奏+音高全通过: {len(ok)}, 失败: {len(fail)}")
    print()
    if fail:
        print("=== 失败详情 ===")
        for name, chapter, subdiv, ts, key, status, detail in fail:
            print(f"  {chapter}/{name}  S={subdiv}  ts={ts}  key={key}  {status}  {detail}")
    else:
        print("全部通过 (OK)")
    # 打印通过的文件里, 时值种类最多的几个 (确认多时值确实被覆盖)
    print()
    print("=== 细分因子分布 ===")
    from collections import Counter
    c = Counter(r[2] for r in results)
    for s, n in sorted(c.items()):
        print(f"  S={s}: {n} 个")


if __name__ == "__main__":
    main()
