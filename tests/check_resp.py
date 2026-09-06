"""Inspect last_response.json — print key summary + alternatives stats."""
import json
from pathlib import Path

p = Path(r"C:\Users\Administrator\Documents\try\music-reader\tests\last_response.json")
obj = json.loads(p.read_text(encoding="utf-8"))

s = obj["source"]
print("source:", s)
sm = obj["summary"]
print("summary keys:", list(sm.keys()))
for k in ("status", "partCount", "measureCount", "cadence", "qualify",
          "violations", "score", "confidence", "keyPerMeasure", "cadences"):
    print(f"  {k}: {sm.get(k)}")
print(f"  confidenceEvidence: {sm.get('confidenceEvidence')}")

print(f"\nalternativesCount: {obj['alternativesCount']}")
alts = obj["alternatives"]
print(f"len(alternatives): {len(alts)}")
print(f"first alt: rank={alts[0]['rank']} deltaScore={alts[0]['deltaScore']}")
print(f"last  alt: rank={alts[-1]['rank']} deltaScore={alts[-1]['deltaScore']}")
print(f"score deltas: min={min(a['deltaScore'] for a in alts):.2f} "
      f"max={max(a['deltaScore'] for a in alts):.2f} "
      f"mean={sum(a['deltaScore'] for a in alts)/len(alts):.2f}")

print(f"\nwarnings: {obj['warnings']}")
print(f"fourPart.qualityStatus: {obj['fourPart']['qualityStatus']}")
print("voices:")
for v in obj["fourPart"]["voices"]:
    print(f"  {v['id']}: {len(v['entries'])} entries (clef={v['clef']})")
print("harmonies per measure:")
for hm in obj["harmonyTimeline"]:
    romans = [h["commonName"] for h in hm["harmonies"]]
    print(f"  m{hm['measure']}: {romans}")
