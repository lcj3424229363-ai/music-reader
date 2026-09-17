"""Benchmark the project HOMR wrapper on real Polish Scores scans."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOMR_SOURCE = ROOT / "data" / "omr-benchmark" / "homr-source"
sys.path[:0] = [str(ROOT), str(HOMR_SOURCE)]

from datasets import Image, load_dataset  # noqa: E402
from omr import transcribe_with_audiveris  # noqa: E402
from validation.ned_score import compute_ned  # noqa: E402


def _add_kern_header(kern: str) -> str:
    for line in kern.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("!"):
            continue
        if not stripped.startswith("**"):
            return "\t".join(["**kern"] * len(line.split("\t"))) + "\n" + kern
        break
    return kern


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "omr-benchmark" / "polish-scores-homr.json",
    )
    args = parser.parse_args()

    dataset = load_dataset("btrkeks/polish-scores", split="train")
    dataset = dataset.cast_column("image", Image(decode=False))
    selected = dataset.select(range(min(max(args.limit, 0), len(dataset))))
    results = []
    for index, sample in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] polish-{index - 1}", flush=True)
        try:
            with tempfile.TemporaryDirectory(prefix="homr-polish-benchmark-") as temp_dir:
                work_dir = Path(temp_dir)
                image = work_dir / f"polish-{index - 1}.png"
                image.write_bytes(sample["image"]["bytes"])
                transcription = transcribe_with_audiveris(image, work_dir, timeout_seconds=300)
                output = Path(transcription["exportedPath"]).read_text(encoding="utf-8")
                score = compute_ned(
                    _add_kern_header(sample["transcription_kern"]),
                    output,
                    ignore_unreliable_articulation=True,
                )
            results.append({
                "id": f"polish-{index - 1}",
                "status": "ok",
                "tokenNed": round(score.ned, 6),
                "distance": score.distance,
                "referenceTokenCount": score.kern_len,
                "predictionTokenCount": score.xml_len,
                "rhythmNed": round(score.rhythm_ned, 6),
                "pitchNed": round(score.pitch_ned, 6),
                "accidentalNed": round(score.lift_ned, 6),
            })
        except Exception as exc:  # noqa: BLE001
            results.append({"id": f"polish-{index - 1}", "status": "error", "error": str(exc)[:1000]})

    successful = [item for item in results if item["status"] == "ok"]
    report = {
        "benchmarkScope": "real scanned printed scores",
        "source": "btrkeks/polish-scores",
        "datasetRecords": len(dataset),
        "requested": len(selected),
        "successful": len(successful),
        "meanTokenNed": (
            round(sum(item["tokenNed"] for item in successful) / len(successful), 6)
            if successful else None
        ),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    main()
