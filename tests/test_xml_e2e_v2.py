"""P2.7+ XML import e2e test v2 — full dump + voice extraction."""
import json
import urllib.request
import mimetypes
from pathlib import Path

URL_READ = "http://127.0.0.1:8770/read-score"
URL_SOLVE = "http://127.0.0.1:8770/solve-melody"
XML_PATH = Path(r"C:\Users\Administrator\Documents\try\eval-data\extracted\hamony dataset\ch4\original\ch4-01_a minor.xml")


def post_multipart(url, file_path):
    boundary = "----TestBoundary12345"
    file_bytes = file_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
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


def parse_pitch(p):
    """'E5' -> ('E', 5).  'F#4' -> ('F#', 4)."""
    p = p.strip()
    octave = int(p[-1])
    name = p[:-1]
    # accidental
    if len(name) > 1 and name[-1] in "#b":
        step = name[:-1]
        acc = name[-1]
    else:
        step = name
        acc = ""
    return step, acc, octave


def main():
    print("STEP 1: /read-score")
    status, obj = post_multipart(URL_READ, XML_PATH)
    print(f"HTTP {status}")
    print(f"  summary: {obj.get('summary')}")
    print(f"  parts: {len(obj.get('parts', []))}")

    # Dump every part fully
    for pi, part in enumerate(obj.get("parts", [])):
        print(f"\n  Part {pi}: {part.get('name')} ({part.get('measureCount')} measures)")
        for mi, m in enumerate(part.get("measures", [])):
            evs = m.get("events", [])
            print(f"    m{mi+1}: {len(evs)} events")
            for e in evs:
                t = e.get("type", "?")
                p = e.get("pitch") or e.get("rest", "?")
                off = e.get("offset", 0)
                dur = e.get("duration", 0)
                # step+octave
                sp = parse_pitch(p) if t == "note" and isinstance(p, str) else None
                print(f"      off={off} dur={dur} type={t} pitch={p} step={sp[0] if sp else '-'} oct={sp[2] if sp else '-'}")

    # Try extracting melody: top voice (highest pitch per measure per beat)
    print("\n\nSTEP 2: extract melody (highest pitch per offset) → /solve-melody")
    part0 = obj["parts"][0]
    melody_measures = []
    for m in part0["measures"]:
        # group events by offset
        by_off = {}
        for e in m["events"]:
            if e.get("type") != "note":
                continue
            off = e.get("offset", 0)
            by_off.setdefault(off, []).append(e)
        # for each offset, pick the topmost (highest pitch)
        entries = []
        for off in sorted(by_off.keys()):
            notes = by_off[off]
            top = max(notes, key=lambda n: parse_pitch(n["pitch"])[2] * 12 + (1 if "#" in n["pitch"] else 0))
            step, acc, oct_ = parse_pitch(top["pitch"])
            entries.append({
                "kind": "note",
                "voice": 0,
                "pitches": [{"step": step, "octave": oct_, "accidental": acc, "display": top["pitch"]}],
                "duration": "4",
                "dotted": False,
                "units": 8,
            })
        melody_measures.append(entries)

    print(f"  extracted melody: {len(melody_measures)} measures")
    for mi, ms in enumerate(melody_measures):
        print(f"    m{mi+1}: {len(ms)} entries")
        for e in ms:
            p = e["pitches"][0]
            print(f"      {p['display']} (step={p['step']}, oct={p['octave']})")

    key = obj.get("summary", {}).get("analyzedKey", {}).get("label", "C major")
    ts = obj.get("summary", {}).get("timeSignature", "4/4")
    payload = {
        "key": key, "timeSignature": ts, "questionType": "melody",
        "chordPoolProfile": "auto", "keyChanges": [],
        "melodyMeasures": melody_measures,
    }
    print(f"\n  POST /solve-melody (key={key}, ts={ts}, measures={len(melody_measures)})")
    s2, o2 = post_json(URL_SOLVE, payload)
    print(f"  HTTP {s2}")
    if "error" in o2 and o2.get("error"):
        print(f"  ERROR: {o2['error']}")
    else:
        sm = o2.get("summary", {})
        print(f"  status={sm.get('status')}, qualify={sm.get('qualify')}, score={sm.get('score')}")
        print(f"  cadences: {sm.get('cadences')}")
        print(f"  violations: {sm.get('violations')}")
        print(f"  alternativesCount: {o2.get('alternativesCount')}")

    with open(r"C:\Users\Administrator\Documents\try\music-reader\tests\solve_from_xml.json", "w", encoding="utf-8") as f:
        json.dump(o2, f, ensure_ascii=False, indent=2)
    print("\n  /solve-melody response -> tests/solve_from_xml.json")


if __name__ == "__main__":
    main()
