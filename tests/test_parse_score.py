"""Step 4 e2e — /parse-score endpoint."""
import json
import sys
import urllib.request
import mimetypes
from pathlib import Path

URL_PARSE = "http://127.0.0.1:8770/parse-score"
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
print("Step 4 e2e: /parse-score")
print("=" * 60)

# 1) /parse-score
print("\n1) POST /parse-score")
s, payload = post_multipart(URL_PARSE, XML)
check("HTTP 200", s == 200)
check("editor.key = A minor", payload.get("key") == "A minor")
check("editor.timeSignature = 2/4", payload.get("timeSignature") == "2/4")
check("editor.melodyMeasures = 4 measures", len(payload.get("melodyMeasures", [])) == 4)
check("editor.bassMeasures = 4 measures", len(payload.get("bassMeasures", [])) == 4)
check("rawSummary included", "rawSummary" in payload)

# 2) feed to /solve-melody directly
print("\n2) Use /parse-score output to feed /solve-melody (no manual conversion)")
solve_payload = {
    "key": payload["key"],
    "timeSignature": payload["timeSignature"],
    "questionType": "melody",
    "chordPoolProfile": "auto",
    "keyChanges": [],
    "melodyMeasures": payload["melodyMeasures"],
}
s2, r2 = post_json(URL_SOLVE, solve_payload)
check("HTTP 200", s2 == 200)
if "error" in r2 and r2.get("error"):
    print(f"  ERROR: {r2['error']}")
    failed += 1
else:
    sm = r2.get("summary", {})
    check("summary.status = complete", sm.get("status") == "complete")
    check("summary.qualify = True", sm.get("qualify") == True)
    check("score is a number", isinstance(sm.get("score"), (int, float)))
    print(f"    score = {sm.get('score')}")
    print(f"    cadences = {sm.get('cadences')}")
    print(f"    alternativesCount = {r2.get('alternativesCount')}")
    check("alternativesCount = 49", r2.get("alternativesCount") == 49)

# Save response
with open(r"C:\Users\Administrator\Documents\try\music-reader\tests\parse_score_response.json", "w", encoding="utf-8") as f:
    json.dump({"parse_score": payload, "solve_melody": r2}, f, ensure_ascii=False, indent=2)

print()
print(f"Total: {passed + failed}, Passed: {passed}, Failed: {failed}")
if failed:
    if __name__ == "__main__":
        sys.exit(1)
    raise AssertionError(f"parse-score e2e: {failed} checks failed")
else:
    print("\nPASS — /parse-score works end-to-end")
    if __name__ == "__main__":
        sys.exit(0)
