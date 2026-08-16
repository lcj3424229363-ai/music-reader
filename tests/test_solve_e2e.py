"""P2.7 → v1.6 端到端测试 (server PID 16392, port 8770).

用 Python 构造正确 payload (entry 都有 kind=note) 调 /solve-melody,
看返回的 alternatives 数量 + L3 合法性.

测试: C major 4 小节 4/4
  m1: C5 D5 E5 F5
  m2: G5 A5 G5 F5
  m3: E5 D5 C5 D5
  m4: E5 F5 E5 D5
"""
import json
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8770/solve-melody"


def make_entry(step, octave, duration="4"):
    """构造 app.js 单个 note entry (含 kind=note + voice + units)."""
    return {
        "kind": "note",
        "voice": 0,
        "pitches": [{"step": step, "octave": octave, "accidental": "", "display": f"{step}{octave}"}],
        "duration": duration,
        "dotted": 0,
        "units": 8,
        "tieStart": False,
        "tieStop": False,
    }


def make_measure(pitches):
    """[step, octave, ...] -> 4 quarter entries."""
    return [make_entry(s, o) for s, o in pitches]


PAYLOAD = {
    "key": "C major",
    "timeSignature": "4/4",
    "questionType": "melody",
    "chordPoolProfile": "auto",
    "keyChanges": [],
    "melodyMeasures": [
        make_measure([("C", 5), ("D", 5), ("E", 5), ("F", 5)]),
        make_measure([("G", 5), ("A", 5), ("G", 5), ("F", 5)]),
        make_measure([("E", 5), ("D", 5), ("C", 5), ("D", 5)]),
        make_measure([("E", 5), ("F", 5), ("E", 5), ("D", 5)]),
    ],
}


def main():
    body = json.dumps(PAYLOAD, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
        status = resp.status
    elapsed = time.time() - t0
    print(f"HTTP {status}, elapsed {elapsed*1000:.0f} ms")
    obj = json.loads(data)

    # 顶层结构
    print("top-level keys:", sorted(obj.keys()))

    # 错误检查
    if "error" in obj and obj.get("error"):
        print("ERROR:", obj["error"])
        return 1

    # fourPart 字段
    fp = obj.get("fourPart") or obj.get("four_part") or obj
    print("fourPart keys:", sorted(fp.keys()) if isinstance(fp, dict) else type(fp))

    # alternatives
    alts = obj.get("alternatives") or fp.get("alternatives") or []
    print(f"alternatives count: {len(alts)}")

    # primary / first result
    if isinstance(fp, dict):
        # 找 chord field
        for k in ("chords", "chordProgression", "voicing", "measures", "solution"):
            if k in fp:
                print(f"  {k}: {type(fp[k]).__name__} len={len(fp[k]) if hasattr(fp[k], '__len__') else '?'}")
        # 评分
        for k in ("score", "totalScore", "legality", "metrics"):
            if k in fp:
                print(f"  {k}: {fp[k]}")
        # 任何数字字段
        for k, v in fp.items():
            if isinstance(v, (int, float, bool, str)) and k not in ("error", "warning", "message"):
                if len(str(v)) < 200:
                    print(f"  {k}: {v}")

    # alternatives 第一个的概要
    if alts:
        print("\nalternative[0] keys:", sorted(alts[0].keys()) if isinstance(alts[0], dict) else type(alts[0]))
        a0 = alts[0]
        if isinstance(a0, dict):
            for k, v in a0.items():
                if isinstance(v, (int, float, bool, str)) and len(str(v)) < 200:
                    print(f"  alt[0].{k}: {v}")
                elif isinstance(v, list):
                    print(f"  alt[0].{k}: list len={len(v)}, first={v[0] if v else None}")

    # 输出给后续
    with open(r"C:\Users\Administrator\Documents\try\music-reader\tests\last_response.json", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print("\nfull response -> tests/last_response.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
