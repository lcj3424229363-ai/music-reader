"""P2.7+ XML import e2e test.

Goal: POST ch4-01_a minor.xml to /read-score, inspect the response shape,
and check whether it can be fed to /solve-melody directly or needs a
conversion step.
"""
import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path
import io
import mimetypes

URL_READ = "http://127.0.0.1:8770/read-score"
URL_SOLVE = "http://127.0.0.1:8770/solve-melody"

XML_PATH = Path(r"C:\Users\Administrator\Documents\try\eval-data\extracted\hamony dataset\ch4\original\ch4-01_a minor.xml")


def post_multipart(url, file_path, field_name="file"):
    boundary = "----TestBoundary12345"
    file_bytes = file_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{file_path.name}"\r\n'
        f"Content-Type: {mimetypes.guess_type(file_path.name)[0] or 'application/octet-stream'}\r\n"
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
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.status, json.loads(resp.read())


def main():
    print("=" * 60)
    print("STEP 1: POST ch4-01_a minor.xml → /read-score")
    print("=" * 60)
    status, obj = post_multipart(URL_READ, XML_PATH)
    print(f"HTTP {status}")
    print(f"top-level keys: {sorted(obj.keys())}")
    if "summary" in obj:
        print(f"  summary keys: {sorted(obj['summary'].keys())}")
        print(f"  summary.status: {obj['summary'].get('status')}")
        print(f"  partCount: {obj['summary'].get('partCount')}")
        print(f"  measureCount: {obj['summary'].get('measureCount')}")
        print(f"  analyzedKey: {obj['summary'].get('analyzedKey')}")

    if "parts" in obj:
        print(f"\n  parts count: {len(obj['parts'])}")
        for p in obj["parts"][:3]:
            print(f"    - {p.get('name')}: {p.get('measureCount')} measures, keys={sorted(p.keys())}")
            if p.get("measures"):
                m0 = p["measures"][0]
                print(f"      m1 keys: {sorted(m0.keys())}")
                if m0.get("events"):
                    e0 = m0["events"][0]
                    print(f"      m1.events[0]: {json.dumps(e0, ensure_ascii=False)}")

    if "harmonyTimeline" in obj:
        ht = obj["harmonyTimeline"]
        print(f"\n  harmonyTimeline entries: {len(ht)}")
        for item in ht[:2]:
            print(f"    m{item['measure']}: {len(item['harmonies'])} harmonies")
            for h in item["harmonies"][:4]:
                print(f"      {h.get('commonName')} root={h.get('root')}")

    if "warnings" in obj:
        print(f"\n  warnings: {obj['warnings']}")

    print()
    print("=" * 60)
    print("STEP 2: check if /read-score output can feed /solve-melody")
    print("=" * 60)
    # What /solve-melody expects:
    # melodyMeasures: list[list[entry {kind, voice, pitches[{step, octave}], duration, units}]]
    # /read-score gives:
    # parts[].measures[].events[] — same shape?
    if "parts" in obj and obj["parts"]:
        part = obj["parts"][0]
        if part.get("measures"):
            m0 = part["measures"][0]
            ev = m0.get("events", [])
            print(f"  m1 events (first 4):")
            for e in ev[:4]:
                print(f"    {json.dumps(e, ensure_ascii=False)}")

            # Try to build a /solve-melody payload from part 0 events
            melody_measures = []
            for m in part["measures"]:
                entries = []
                for e in m.get("events", []):
                    # /read-score event shape: {step, octave, duration, ...} or {pitches: [...]}
                    if e.get("pitches"):
                        entries.append({
                            "kind": "note",
                            "voice": 0,
                            "pitches": e["pitches"],
                            "duration": e.get("duration", "4"),
                            "dotted": False,
                            "units": 8,
                        })
                    elif e.get("step") and "octave" in e:
                        entries.append({
                            "kind": "note",
                            "voice": 0,
                            "pitches": [{"step": e["step"], "octave": e["octave"], "accidental": "", "display": f"{e['step']}{e['octave']}"}],
                            "duration": e.get("duration", "4"),
                            "dotted": False,
                            "units": 8,
                        })
                    else:
                        # rest?
                        entries.append(None)
                melody_measures.append([x for x in entries if x])

            if melody_measures and any(melody_measures):
                # Get key from summary
                analyzed = obj.get("summary", {}).get("analyzedKey", {})
                key = analyzed.get("label") or "C major"

                payload = {
                    "key": key,
                    "timeSignature": obj.get("summary", {}).get("timeSignature", "4/4"),
                    "questionType": "melody",
                    "chordPoolProfile": "auto",
                    "keyChanges": [],
                    "melodyMeasures": melody_measures,
                }
                print(f"\n  Built /solve-melody payload (m0 first 2 entries):")
                if payload["melodyMeasures"]:
                    for e in payload["melodyMeasures"][0][:2]:
                        print(f"    {json.dumps(e, ensure_ascii=False)}")
                print(f"\n  key={payload['key']}, ts={payload['timeSignature']}, n_measures={len(payload['melodyMeasures'])}")

                print("\n  POST → /solve-melody (using reader output)...")
                s2, o2 = post_json(URL_SOLVE, payload)
                print(f"  HTTP {s2}")
                if "error" in o2 and o2.get("error"):
                    print(f"  ERROR: {o2['error']}")
                else:
                    print(f"  response top keys: {sorted(o2.keys())}")
                    if "summary" in o2:
                        print(f"  summary.score: {o2['summary'].get('score')}")
                        print(f"  summary.qualify: {o2['summary'].get('qualify')}")
                        print(f"  summary.measureCount: {o2['summary'].get('measureCount')}")
                    if "alternativesCount" in o2:
                        print(f"  alternativesCount: {o2['alternativesCount']}")
                    if "warnings" in o2 and o2["warnings"]:
                        print(f"  warnings: {o2['warnings']}")

    # Save full response for inspection
    with open(r"C:\Users\Administrator\Documents\try\music-reader\tests\read_score_resp.json", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print("\nfull /read-score response -> tests/read_score_resp.json")


if __name__ == "__main__":
    main()
