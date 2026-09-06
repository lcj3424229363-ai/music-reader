"""Step 3 e2e test — /read-score → reader_to_editor → /solve-melody."""
import json
import sys
import urllib.request
import mimetypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from reader_to_editor import reader_payload_to_editor

URL_READ = "http://127.0.0.1:8770/read-score"
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
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.status, json.loads(resp.read())


def post_json(url, body):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.status, json.loads(resp.read())


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
print("Step 3 e2e: /read-score → reader_to_editor → /solve-melody")
print("=" * 60)

# 1) /read-score
print("\n1) POST /read-score")
s1, payload = post_multipart(URL_READ, XML)
check("/read-score HTTP 200", s1 == 200)
check("summary present", "summary" in payload)
check("parts present", "parts" in payload)
check(f"summary key = A minor", payload["summary"].get("analyzedKey", {}).get("label") == "A minor")

# 2) reader_to_editor
print("\n2) reader_to_editor conversion")
editor = reader_payload_to_editor(payload)
check("editor.key = A minor", editor["key"] == "A minor")
check("editor.timeSignature = 2/4", editor["timeSignature"] == "2/4")
check("editor.melodyMeasures = 4 measures", len(editor["melodyMeasures"]) == 4)
check("editor.bassMeasures = 4 measures", len(editor["bassMeasures"]) == 4)

# Verify entry shape per ENTRY_SCHEMA §2
def validate_entry(e, expected_voice):
    if e["kind"] == "rest":
        return "pitches" not in e
    if e["kind"] == "note":
        if "pitches" not in e or not e["pitches"]:
            return False
        p = e["pitches"][0]
        return (p.get("step") and p.get("octave") is not None
                and p.get("display") == f"{p.get('step')}{p.get('accidental', '')}{p.get('octave')}"
                and e.get("voice") == expected_voice)
    return False

melody_ok = all(
    validate_entry(e, "soprano") for m in editor["melodyMeasures"] for e in m
)
bass_ok = all(
    validate_entry(e, "bass") for m in editor["bassMeasures"] for e in m
)
check("all melody entries conform to schema §2", melody_ok)
check("all bass entries conform to schema §2", bass_ok)

# Print melody/bass
print("\n  melody (per measure):")
for mi, m in enumerate(editor["melodyMeasures"]):
    s = " | ".join((e["pitches"][0]["display"] if e["kind"] == "note" else "rest") for e in m)
    print(f"    m{mi+1}: {s}")
print("  bass (per measure):")
for mi, m in enumerate(editor["bassMeasures"]):
    s = " | ".join((e["pitches"][0]["display"] if e["kind"] == "note" else "rest") for e in m)
    print(f"    m{mi+1}: {s}")

# 3) /solve-melody
print("\n3) POST /solve-melody (melody + bass)")
# Add questionType=melody, drop bassMeasures (melody-only mode, P0-P7)
# OR pass both for P8 bass-given.  Try melody-only first.
payload_solve_melody = {
    "key": editor["key"],
    "timeSignature": editor["timeSignature"],
    "questionType": "melody",
    "chordPoolProfile": "auto",
    "keyChanges": [],
    "melodyMeasures": editor["melodyMeasures"],
}
s2, r2 = post_json(URL_SOLVE, payload_solve_melody)
check("/solve-melody HTTP 200", s2 == 200)
check("summary present", "summary" in r2)
if "error" in r2 and r2.get("error"):
    print(f"  ERROR: {r2['error']}")
    failed += 1
else:
    sm = r2.get("summary", {})
    check("summary.status = complete", sm.get("status") == "complete")
    check(f"summary.qualify = True", sm.get("qualify") == True)
    check(f"summary.score is a number", isinstance(sm.get("score"), (int, float)))
    print(f"    score = {sm.get('score')}")
    print(f"    cadences = {sm.get('cadences')}")
    print(f"    alternativesCount = {r2.get('alternativesCount')}")
    check("alternativesCount = 49 (v1.6 K=50)", r2.get("alternativesCount") == 49)
    fp = r2.get("fourPart", {})
    check("fourPart.voices = 4", len(fp.get("voices", [])) == 4)
    if fp.get("voices"):
        voice_ids = [v.get("id") for v in fp["voices"]]
        check("voice ids = [soprano, alto, tenor, bass]", voice_ids == ["soprano", "alto", "tenor", "bass"])

# 4) Test also bass-given mode (P8)
print("\n4) POST /solve-melody (bass-given mode, P8)")
payload_solve_bass = {
    "key": editor["key"],
    "timeSignature": editor["timeSignature"],
    "questionType": "bass",
    "chordPoolProfile": "auto",
    "keyChanges": [],
    "bassMeasures": editor["bassMeasures"],
}
s3, r3 = post_json(URL_SOLVE, payload_solve_bass)
check("/solve-melody (bass) HTTP 200", s3 == 200)
if "error" in r3 and r3.get("error"):
    print(f"  ERROR: {r3['error']}")
    failed += 1
else:
    sm3 = r3.get("summary", {})
    check("(bass) summary.status = complete", sm3.get("status") == "complete")
    check(f"(bass) summary.qualify = True", sm3.get("qualify") == True)
    print(f"    score = {sm3.get('score')}")
    print(f"    cadences = {sm3.get('cadences')}")

# Save
with open(r"C:\Users\Administrator\Documents\try\music-reader\tests\solve_via_reader.json", "w", encoding="utf-8") as f:
    json.dump({
        "editor_payload": editor,
        "solve_melody_response": r2,
        "solve_bass_response": r3,
    }, f, ensure_ascii=False, indent=2)

print()
print(f"Total: {passed + failed}, Passed: {passed}, Failed: {failed}")
if failed:
    print("\nFAIL")
    if __name__ == "__main__":
        sys.exit(1)
    raise AssertionError(f"reader e2e: {failed} checks failed")
else:
    print("\nPASS — reader_to_editor + /solve-melody e2e works")
    if __name__ == "__main__":
        sys.exit(0)
