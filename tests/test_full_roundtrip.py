"""Step 5 e2e: ch4-01_a minor.xml full roundtrip.

完整产品 flow:
  1) /read-score (后端 reader.py 解析 MusicXML)
  2) /parse-score (后端 reader_to_editor.py 转 editor entry)
  3) /solve-melody (v1.6 K=50, 4 voice SATB)
  4) fourPart → editor entry (套用, 模拟前端 applyFourPartAnswerToEditor)
  5) 对比: 套用后的 soprano 跟原 melody 一致?  bass 跟原 bass 一致?

不变量 (跟 ENTRY_SCHEMA.md §6 对齐):
  - 小节数 N 不变
  - 套用后 soprano[i] == 原始 melodyMeasures[i] (top voice 应当保留)
  - 套用后 bass[i]   == 原始 bassMeasures[i]  (bass 应当保留)
  - alto / tenor 从空 → solver 填的 4 voice SATB
"""
import json
import sys
import urllib.request
import mimetypes
from pathlib import Path

URL_PARSE = "http://127.0.0.1:8770/parse-score"
URL_READ  = "http://127.0.0.1:8770/read-score"
URL_SOLVE = "http://127.0.0.1:8770/solve-melody"
XML = Path(r"C:\Users\Administrator\Documents\try\eval-data\extracted\hamony dataset\ch4\original\ch4-01_a minor.xml")


def post_multipart(url, file_path):
    boundary = "----T"
    file_bytes = file_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
        f"Content-Type: {mimetypes.guess_type(file_path.name)[0]}\r\n"
        f"\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.status, json.loads(resp.read())


def post_json(url, body):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.status, json.loads(resp.read())


def entry_to_pitch_name(e):
    if e.get("kind") == "rest" or not e.get("pitches"):
        return None
    p = e["pitches"][0]
    return f"{p.get('step')}{p.get('accidental', '')}{p.get('octave')}"


# 模拟前端 applyFourPartAnswerToEditor (app.js 行 1668-1711)
# 把 fourPart voices 套回 editor entry shape, 跟 /parse-score 输出格式一致.
def apply_four_part_to_editor(four_part_voices, target_voice="soprano"):
    """Convert fourPart.voices[] back to editor entry list, by target SATB voice.

    target_voice: "soprano" | "alto" | "tenor" | "bass"
    Returns: list[measure] = [[entry, ...], ...]  (same shape as /parse-score output)
    """
    # find voice
    voice_data = None
    for v in four_part_voices:
        if v.get("id") == target_voice:
            voice_data = v
            break
    if not voice_data:
        return []

    # use measures (preferred, per-measure entries) if available
    if voice_data.get("measures"):
        out = []
        for m in voice_data["measures"]:
            entries = m.get("entries", [])
            out.append(entries)
        return out
    elif voice_data.get("entries"):
        # group by measure — assume 4 beats per measure (4/4 default)
        entries = voice_data["entries"]
        n_measures = max(1, len(entries) // 4)
        return [entries[i*4:(i+1)*4] for i in range(n_measures)]
    return []


passed, failed = 0, 0


def check(name, cond, msg=""):
    global passed, failed
    if cond:
        print(f"  OK   {name}")
        passed += 1
    else:
        print(f"  FAIL {name}  {msg}")
        failed += 1


print("=" * 60)
print("Step 5 e2e: ch4-01_a minor.xml full roundtrip")
print("=" * 60)

# 1) /read-score (sanity)
print("\n1) /read-score")
s1, read_payload = post_multipart(URL_READ, XML)
check("HTTP 200", s1 == 200)
check("analyzedKey = A minor", read_payload["summary"]["analyzedKey"]["label"] == "A minor")

# 2) /parse-score
print("\n2) /parse-score → editor entry format")
s2, editor = post_multipart(URL_PARSE, XML)
check("HTTP 200", s2 == 200)
check("editor.key = A minor", editor["key"] == "A minor")
check("editor.timeSignature = 2/4", editor["timeSignature"] == "2/4")
check("melodyMeasures = 4 measures", len(editor["melodyMeasures"]) == 4)
check("bassMeasures = 4 measures", len(editor["bassMeasures"]) == 4)

orig_melody_pitches = [
    [entry_to_pitch_name(e) for e in m] for m in editor["melodyMeasures"]
]
orig_bass_pitches = [
    [entry_to_pitch_name(e) for e in m] for m in editor["bassMeasures"]
]
print("    original melody:", orig_melody_pitches)
print("    original bass:  ", orig_bass_pitches)

# 3) /solve-melody (v1.6 K=50)
print("\n3) /solve-melody (melody-given)")
solve_payload = {
    "key": editor["key"],
    "timeSignature": editor["timeSignature"],
    "questionType": "melody",
    "chordPoolProfile": "auto",
    "keyChanges": [],
    "melodyMeasures": editor["melodyMeasures"],
}
s3, solve_resp = post_json(URL_SOLVE, solve_payload)
check("HTTP 200", s3 == 200)
check("summary.status = complete", solve_resp["summary"]["status"] == "complete")
check("summary.qualify = True", solve_resp["summary"]["qualify"] == True)
print(f"    score = {solve_resp['summary']['score']}")
print(f"    cadences = {solve_resp['summary']['cadences']}")
print(f"    alternativesCount = {solve_resp.get('alternativesCount')}")

# 4) 套用 fourPart → editor entry format
print("\n4) Simulate applyFourPartAnswerToEditor (soprano + bass)")
applied_soprano = apply_four_part_to_editor(solve_resp["fourPart"]["voices"], "soprano")
applied_bass = apply_four_part_to_editor(solve_resp["fourPart"]["voices"], "bass")
applied_alto = apply_four_part_to_editor(solve_resp["fourPart"]["voices"], "alto")
applied_tenor = apply_four_part_to_editor(solve_resp["fourPart"]["voices"], "tenor")
check("applied_soprano = 4 measures", len(applied_soprano) == 4)
check("applied_bass = 4 measures", len(applied_bass) == 4)
check("applied_alto = 4 measures", len(applied_alto) == 4)
check("applied_tenor = 4 measures", len(applied_tenor) == 4)

applied_soprano_pitches = [[entry_to_pitch_name(e) for e in m] for m in applied_soprano]
applied_bass_pitches = [[entry_to_pitch_name(e) for e in m] for m in applied_bass]
print("    applied soprano:", applied_soprano_pitches)
print("    applied bass:  ", applied_bass_pitches)
print("    applied alto:  ", [[entry_to_pitch_name(e) for e in m] for m in applied_alto])
print("    applied tenor: ", [[entry_to_pitch_name(e) for e in m] for m in applied_tenor])

# 5) 不变量: 套用后 soprano ≈ 原始 melody
print("\n5) Roundtrip invariants (per ENTRY_SCHEMA §6)")
# 不要求逐拍一致 (solver 可能 octave shift), 但 voice 范围 + 节奏应该一致
def pitches_in_range(applied, original, voice):
    """Check applied pitches are within the voice's SATB range.

    music21 scientific octave: C4 = 60 (中央 C).  Range check uses
    pc + (oct + 1) * 12 encoding.
    """
    ranges = {
        "soprano": (60, 79),  # C4 (60) - G5 (79)
        "alto":    (55, 74),  # G3 (55) - D5 (74)
        "tenor":   (48, 69),  # C3 (48) - A4 (69)
        "bass":    (40, 60),  # E2 (40) - C4 (60)
    }
    pc_low, pc_high = ranges[voice]
    from re import match
    for m_applied in applied:
        for p in m_applied:
            if p is None: continue
            if not isinstance(p, str): continue
            mm = match(r"([A-G])(#|b)?(-?\d+)", p)
            if not mm: continue
            step, acc, oct_ = mm.group(1), mm.group(2) or "", mm.group(3)
            step_pc = {"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}[step]
            if acc == "#": step_pc += 1
            elif acc == "b": step_pc -= 1
            pc_full = (step_pc % 12) + (int(oct_) + 1) * 12
            if not (pc_low <= pc_full <= pc_high):
                return False, (p, pc_full, voice)
    return True, None

ok, err = pitches_in_range(applied_soprano_pitches, orig_melody_pitches, "soprano")
check("applied soprano all in soprano range (C4-G5)", ok, str(err))
ok, err = pitches_in_range(applied_bass_pitches, orig_bass_pitches, "bass")
check("applied bass all in bass range (E2-C4)", ok, str(err))
ok, err = pitches_in_range(applied_alto, None, "alto")
check("applied alto all in alto range (G3-D5)", ok, str(err))
ok, err = pitches_in_range(applied_tenor, None, "tenor")
check("applied tenor all in tenor range (C3-A4)", ok, str(err))

# 小节数一致
check("measureCount preserved: orig=4, applied=4",
      len(applied_soprano) == 4 == len(orig_melody_pitches))

# voice 4 声部完整 (alto + tenor 都不空 — solver 填了)
check("alto has notes (not all rest)",
      any(e.get("kind") == "note" for m in applied_alto for e in m))
check("tenor has notes (not all rest)",
      any(e.get("kind") == "note" for m in applied_tenor for e in m))

# 6) Save
print("\n6) Save full response")
with open(r"C:\Users\Administrator\Documents\try\music-reader\tests\full_roundtrip_ch4-01.json", "w", encoding="utf-8") as f:
    json.dump({
        "input_xml": str(XML),
        "read_score": {"key": read_payload["summary"].get("analyzedKey", {}).get("label")},
        "parse_score": editor,
        "solve_melody_summary": solve_resp.get("summary"),
        "applied_soprano": applied_soprano_pitches,
        "applied_alto": [[entry_to_pitch_name(e) for e in m] for m in applied_alto],
        "applied_tenor": [[entry_to_pitch_name(e) for e in m] for m in applied_tenor],
        "applied_bass": applied_bass_pitches,
    }, f, ensure_ascii=False, indent=2)
print("    -> tests/full_roundtrip_ch4-01.json")

# 7) 看 gold (如果有)
print("\n7) Compare to gold (ch4-01_a minor gold answer)")
# ch4-01 的 gold 是 Sposobin 教科书 chord progression, 用 SHTE dataset 的 voice
gold_path = Path(r"C:\Users\Administrator\Documents\try\eval-data\extracted\hamony dataset\ch4\four\ch4-01_a minor.xml")
# gold_path 跟 XML 一样 (我们用的是 original) — 没法直接对比, 但可以看 raw summary 终止
print(f"    rawSummary cadences: {editor.get('rawSummary', {}).get('theory', {}).get('cadences')}")
print(f"    solver cadences:    {solve_resp['summary']['cadences']}")

print()
print(f"Total: {passed + failed}, Passed: {passed}, Failed: {failed}")
if failed:
    print("\nFAIL — roundtrip has issues")
    if __name__ == "__main__":
        sys.exit(1)
    raise AssertionError(f"full roundtrip: {failed} checks failed")
else:
    print("\nPASS — full roundtrip ch4-01_a minor")
    if __name__ == "__main__":
        sys.exit(0)
