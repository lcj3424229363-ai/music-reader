"""P1-1: 和弦一致率指标 (根音档宽松判等).

对每个例题:
  - gold:  从 original/ (人工标准答案) 用 music21 抽罗马数字 (根音度 1-7)
  - solver: solve_melody 输出的罗马数字 (根音度 1-7)
  - 判等:  忽略转位/七音/性质, 同根音度即算对 (V ≈ V6 ≈ V7 ≈ V65)

报告: 每题一致率 + 总体一致率 (根音档).

用法:
  python scripts/chord_consistency.py [--max N] [--chapter ch4]
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from music21 import converter, roman, chord as m21chord, stream as m21stream, key as m21key

from reader import read_score
from editor_to_solver import appjs_measures_subdivision, appjs_measures_to_solver_melody
import solver as S

SHTE = Path(r"C:\Users\Administrator\Documents\try\eval-data\extracted\hamony dataset")


def parse_key_from_filename(fname: str):
    stem = Path(fname).stem
    m = re.search(r'_([A-Ga-g])([#\-]?)\s*(major|minor)\s*$', stem)
    if not m:
        return None
    tonic = m.group(1).upper()
    acc = "b" if m.group(2) == "-" else m.group(2)
    return f"{tonic}{acc} {m.group(3)}"


def _degree_from_roman(r: str) -> int | None:
    """'I'/'V6'/'V7/VI'/'iv6'/'viiø43' → 根音度 1-7."""
    if not r:
        return None
    s = str(r).split("/")[0].lstrip("#b").strip()
    m = re.match(r'(?i)(vii|vi|iv|v|iii|ii|i)', s)
    if not m:
        return None
    return {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7}[m.group(1).lower()]


def _m21_key(key_name: str):
    """'Ab major' / 'f# minor' → music21 Key (大写=大调, 小写=小调, b→-)."""
    tonic, mode = key_name.split(" ", 1)
    letter = tonic[0].upper() if mode == "major" else tonic[0].lower()
    acc = tonic[1:] if len(tonic) > 1 else ""
    if acc == "b":
        acc = "-"
    return m21key.Key(letter + acc)


def gold_degrees(path: str, key_name: str) -> list[int]:
    """从 original/ 抽每小节每和弦的根音度 (用 filename key 保证与 solver 同调)."""
    score = converter.parse(path)
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


def solver_degrees(four_path: str, key_name: str, ts: str, measures) -> list[int]:
    subdiv = appjs_measures_subdivision(measures, ts)
    melody = appjs_measures_to_solver_melody(measures, ts)
    res = S.solve_melody(key_name, ts, melody, subdivision=subdiv,
                         chord_pool_profile="full_p0-p7")
    out: list[int] = []
    for m in res.measures:
        for b in m["beats"]:
            d = _degree_from_roman(b.get("roman", ""))
            if d is not None:
                out.append(d)
    return out


def consistency(gold: list[int], solver: list[int]) -> tuple[int, int]:
    n = min(len(gold), len(solver))
    if n == 0:
        return 0, 0
    hits = sum(1 for g, s in zip(gold[:n], solver[:n]) if g == s)
    return hits, n


def main():
    args = sys.argv[1:]
    max_n = None
    chapter = None
    for i, a in enumerate(args):
        if a == "--max" and i + 1 < len(args):
            max_n = int(args[i + 1])
        if a == "--chapter" and i + 1 < len(args):
            chapter = args[i + 1]

    files = sorted(SHTE.glob("*/original/*.xml"))
    results = []
    for fp in files:
        if chapter and fp.parent.parent.name != chapter:
            continue
        key = parse_key_from_filename(fp.name)
        if key is None:
            continue
        four = SHTE / fp.parent.parent.name / "four" / fp.name
        if not four.exists():
            continue
        try:
            gold = gold_degrees(str(fp), key)
            from reader_to_editor import reader_payload_to_editor
            mel = reader_payload_to_editor(read_score(str(four)))
            measures = mel["sopranoMeasures"]
            ts = mel["timeSignature"]
            solv = solver_degrees(str(four), key, ts, measures)
            hits, n = consistency(gold, solv)
            rate = (hits / n) if n else 0.0
            results.append((fp.name, key, n, hits, rate))
        except Exception as e:
            results.append((fp.name, key, 0, 0, 0.0))
        if max_n and len(results) >= max_n:
            break

    if not results:
        print("无结果")
        return
    total_n = sum(r[2] for r in results)
    total_hits = sum(r[3] for r in results)
    print(f"例题数: {len(results)}  比较和弦总数: {total_n}  命中: {total_hits}")
    print(f"总体根音档一致率: {total_hits / total_n * 100:.1f}%" if total_n else "N/A")
    print()
    print("=== 每题一致率 (降序) ===")
    for name, key, n, hits, rate in sorted(results, key=lambda r: -r[4]):
        print(f"  {rate*100:5.1f}%  {name:28s} {key:10s} ({hits}/{n})")


if __name__ == "__main__":
    main()
