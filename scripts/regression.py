"""P4: 全量回归门.

对每个例题 (SHTE 数据集 */four/*.xml = 旋律题, */original/*.xml = 人工答案):
  1. 节奏保真 (硬门): 答案 soprano 的 duration/dotted/units 与旋律完全一致
  2. 音高保真 (硬门): 答案 soprano 的 pitch class 与旋律完全一致
  3. 和弦一致率 (软信号, 无硬门): 根音度相等 (忽略转位/七音/性质)

门槛:
  - 节奏/音高保真 必须 100% (任何一处不一致 → FAIL, 退出码非 0)
  - 和弦一致率只打印, 不参与 pass/fail

用法:
  python scripts/regression.py [--chapter ch4] [--max N]
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from music21 import converter, roman, chord as m21chord, stream as m21stream, key as m21key

from reader import read_score
from reader_to_editor import reader_payload_to_editor
from editor_to_solver import appjs_measures_subdivision, appjs_measures_to_solver_melody
import solver as S
from server import _solver_to_four_part_response, FourPartRequest

SHTE = Path(r"C:\Users\Administrator\Documents\try\eval-data\extracted\hamony dataset")

_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def parse_key_from_filename(fname: str):
    stem = Path(fname).stem
    m = re.search(r'_([A-Ga-g])([#\-]?)\s*(major|minor)\s*$', stem)
    if not m:
        return None
    tonic = m.group(1).upper()
    acc = "b" if m.group(2) == "-" else m.group(2)
    return f"{tonic}{acc} {m.group(3)}"


def _m21_key(key_name: str):
    tonic, mode = key_name.split(" ", 1)
    letter = tonic[0].upper() if mode == "major" else tonic[0].lower()
    acc = tonic[1:] if len(tonic) > 1 else ""
    if acc == "b":
        acc = "-"
    return m21key.Key(letter + acc)


def _degree_from_roman(r: str):
    if not r:
        return None
    s = str(r).split("/")[0].lstrip("#b").strip()
    m = re.match(r'(?i)(vii|vi|iv|v|iii|ii|i)', s)
    if not m:
        return None
    return {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7}[m.group(1).lower()]


def gold_degrees(orig_path: str, key_name: str) -> list[int]:
    score = converter.parse(orig_path)
    k = _m21_key(key_name)
    chordified = score.chordify()
    out: list[int] = []
    for m in chordified.getElementsByClass(m21stream.Measure):
        for el in m.recurse().notes:
            if isinstance(el, m21chord.Chord) and len(el.pitches) >= 2:
                try:
                    rn = roman.romanNumeralFromChord(el, k)
                    d = getattr(rn, "scaleDegree", None)
                    if d is not None:
                        out.append(int(d))
                except Exception:
                    pass
    return out


def _rhythm(measures):
    out = []
    for m in measures:
        for e in m:
            out.append((e["kind"], e["duration"], int(e.get("dotted", 0) or 0)))
    return out


def _pitch(measures):
    out = []
    for m in measures:
        for e in m:
            if e["kind"] == "rest":
                out.append(None)
            else:
                p = e["pitches"][0]
                v = _PC[p["step"]] + (1 if p.get("accidental") == "#" else -1 if p.get("accidental") == "b" else 0)
                out.append(v % 12)
    return out


def _consistency(gold: list[int], solver: list[int]) -> tuple[int, int]:
    n = min(len(gold), len(solver))
    if n == 0:
        return 0, 0
    return sum(1 for g, s in zip(gold[:n], solver[:n]) if g == s), n


# ---------------------------------------------------------------------------
# per-file
# ---------------------------------------------------------------------------

def process_file(four_path: Path, orig_path: Path, key: str):
    mel = reader_payload_to_editor(read_score(str(four_path)))
    ts = mel["timeSignature"]
    measures = mel["sopranoMeasures"]
    subdiv = appjs_measures_subdivision(measures, ts)
    melody = appjs_measures_to_solver_melody(measures, ts)
    res = S.solve_melody(key, ts, melody, subdivision=subdiv,
                         chord_pool_profile="full_p0-p7")
    req = FourPartRequest(key=key, timeSignature=ts, melodyMeasures=measures,
                          questionType="melody", chordPoolProfile="full_p0-p7")
    out = _solver_to_four_part_response(res.to_dict(), req, melody_rhythm=measures)
    soprano = next(v for v in out["fourPart"]["voices"] if v["id"] == "soprano")
    out_measures = [m["entries"] for m in soprano["measures"]]

    rhythm_ok = _rhythm(out_measures) == _rhythm(measures)
    pitch_ok = _pitch(out_measures) == _pitch(measures)

    solver_deg = [_degree_from_roman(b.get("roman")) for m in res.measures for b in m["beats"]]
    solver_deg = [d for d in solver_deg if d is not None]
    if orig_path is not None:
        gold_deg = gold_degrees(str(orig_path), key)
        hits, n = _consistency(gold_deg, solver_deg)
    else:
        hits, n = 0, 0

    n_notes = len([e for m in measures for e in m if e["kind"] == "note"])
    return rhythm_ok, pitch_ok, hits, n, n_notes


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    max_n = None
    chapter = None
    for i, a in enumerate(args):
        if a == "--max" and i + 1 < len(args):
            max_n = int(args[i + 1])
        if a == "--chapter" and i + 1 < len(args):
            chapter = args[i + 1]

    files = sorted(SHTE.glob("*/four/*.xml"))
    if chapter:
        files = [f for f in files if f.parent.parent.name == chapter]

    rhythm_bad = []
    pitch_bad = []
    skipped = []
    total_notes = 0
    chord_hits = 0
    chord_n = 0
    n_files = 0

    for fp in files:
        if max_n and n_files >= max_n:
            break
        key = parse_key_from_filename(fp.name)
        if key is None:
            continue
        # 有的章节缺 original/ 答案 (ch10-ch13): 仍跑节奏/音高往返, 只是不算和弦一致率.
        orig = SHTE / fp.parent.parent.name / "original" / fp.name
        orig = orig if orig.exists() else None
        try:
            r_ok, p_ok, hits, n, n_notes = process_file(fp, orig, key)
        except ValueError as e:
            # 空旋律 / 数据质量问题 (如 ch22-09 多 part 结构), 跳过不判 FAIL.
            if "empty" in str(e):
                skipped.append(fp.name)
                continue
            print(f"[ERROR] {fp.name}: {type(e).__name__}: {e}")
            rhythm_bad.append(fp.name)
            pitch_bad.append(fp.name)
            n_files += 1
            continue
        except Exception as e:
            print(f"[ERROR] {fp.name}: {type(e).__name__}: {e}")
            rhythm_bad.append(fp.name)
            pitch_bad.append(fp.name)
            n_files += 1
            continue
        n_files += 1
        total_notes += n_notes
        if not r_ok:
            rhythm_bad.append(fp.name)
        if not p_ok:
            pitch_bad.append(fp.name)
        chord_hits += hits
        chord_n += n

    if skipped:
        print(f"跳过 (空旋律/数据问题): {len(skipped)} 个: {skipped[:10]}")
        print()

    print(f"例题数: {n_files}")
    print()
    r_rate = 100.0 if total_notes == 0 else 100.0
    print(f"节奏保真: {n_files - len(rhythm_bad)}/{n_files} 文件通过 (硬门=100%)")
    if rhythm_bad:
        print(f"  失败: {rhythm_bad[:10]}")
    print(f"音高保真: {n_files - len(pitch_bad)}/{n_files} 文件通过 (硬门=100%)")
    if pitch_bad:
        print(f"  失败: {pitch_bad[:10]}")
    print()
    if chord_n:
        print(f"和弦一致率 (根音档, 软信号): {chord_hits}/{chord_n} = {chord_hits/chord_n*100:.1f}%")
    else:
        print("和弦一致率: N/A")

    hard_pass = (not rhythm_bad) and (not pitch_bad)
    print()
    print("结论:", "PASS" if hard_pass else "FAIL")
    sys.exit(0 if hard_pass else 1)


if __name__ == "__main__":
    main()
