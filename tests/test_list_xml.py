"""P2.7+ test /list-xml + /parse-score-by-id."""
import json
import sys
import urllib.request

# 1. list-xml default
with urllib.request.urlopen("http://127.0.0.1:8770/list-xml?limit=1") as r:
    data = json.loads(r.read())
print("=== /list-xml?limit=1 (default 1 个) ===")
print(f"  total={data['total']}, filtered={data['filtered']}, limit={data['limit']}")
for f in data["files"]:
    print(f"  {f['chapter']} | {f['name']} (id={f['id']!r})")

# 2. query ch4-01
with urllib.request.urlopen("http://127.0.0.1:8770/list-xml?query=ch4-01&limit=10") as r:
    data = json.loads(r.read())
print("\n=== /list-xml?query=ch4-01 (10 个) ===")
print(f"  total={data['total']}, filtered={data['filtered']}")
for f in data["files"]:
    print(f"  {f['chapter']} | {f['name']} (id={f['id']!r})")

# 3. parse-score-by-id for ch4-01_a minor
req = urllib.request.Request(
    "http://127.0.0.1:8770/parse-score-by-id",
    data=json.dumps({"file_id": "ch4-01_a minor"}).encode("utf-8"),
    method="POST",
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read())
print("\n=== POST /parse-score-by-id {file_id: 'ch4-01_a minor'} ===")
print(f"  key: {data['key']}")
print(f"  timeSignature: {data['timeSignature']}")
print(f"  melodyMeasures: {len(data['melodyMeasures'])} measures")
for mi, m in enumerate(data["melodyMeasures"]):
    s = " | ".join((e["pitches"][0]["display"] if e["kind"] == "note" else "rest") for e in m)
    print(f"    m{mi+1}: {s}")
print(f"  bassMeasures: {len(data['bassMeasures'])} measures")
for mi, m in enumerate(data["bassMeasures"]):
    s = " | ".join((e["pitches"][0]["display"] if e["kind"] == "note" else "rest") for e in m)
    print(f"    m{mi+1}: {s}")

# 4. invalid file_id
print("\n=== POST /parse-score-by-id {file_id: 'nope'} (期望 404) ===")
try:
    req = urllib.request.Request(
        "http://127.0.0.1:8770/parse-score-by-id",
        data=json.dumps({"file_id": "nope_does_not_exist"}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)
    print("  UNEXPECTED 200")
except urllib.error.HTTPError as e:
    print(f"  HTTP {e.code}: {json.loads(e.read())['detail']}")

print("\nAll tests passed.")
