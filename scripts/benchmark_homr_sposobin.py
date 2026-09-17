"""Run a reproducible HOMR token-NED baseline on the SHTE test split."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
HOMR_SOURCE = ROOT / "data" / "omr-benchmark" / "homr-source"
load_dotenv(ROOT / ".env")
sys.path[:0] = [str(ROOT), str(HOMR_SOURCE)]

from omr import transcribe_with_audiveris  # noqa: E402
from training.omr_datasets.music_xml_parser import music_xml_file_to_tokens  # noqa: E402


def _distance(left: list[Any], right: list[Any]) -> int:
    if len(left) > len(right):
        left, right = right, left
    previous = list(range(len(left) + 1))
    for row, right_value in enumerate(right, start=1):
        current = [row]
        for column, left_value in enumerate(left, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (left_value != right_value),
            ))
        previous = current
    return previous[-1]


def _flatten(
    path: Path,
    field: str | None = None,
    *,
    notes_only: bool = False,
) -> list[Any]:
    parts = music_xml_file_to_tokens(str(path))
    flattened = []
    for part_index, part in enumerate(parts):
        for measure_index, measure in enumerate(part):
            for symbol in measure:
                if notes_only and not symbol.rhythm.startswith(("note", "rest")):
                    continue
                value = getattr(symbol, field) if field else (
                    symbol.rhythm, symbol.pitch, symbol.lift,
                    symbol.articulation, symbol.slur,
                )
                flattened.append((part_index, measure_index, value))
    return flattened


def _score(reference: Path, prediction: Path) -> dict[str, float | int]:
    result: dict[str, float | int] = {}
    metrics = (
        ("token", None, False),
        ("note", None, True),
        ("rhythm", "rhythm", True),
        ("pitch", "pitch", True),
        ("accidental", "lift", True),
    )
    for name, field, notes_only in metrics:
        expected = _flatten(reference, field, notes_only=notes_only)
        actual = _flatten(prediction, field, notes_only=notes_only)
        distance = _distance(expected, actual)
        denominator = len(expected) + len(actual)
        result[f"{name}Distance"] = distance
        result[f"{name}Ned"] = round(distance / denominator if denominator else 0.0, 6)
        result[f"reference{name.title()}Count"] = len(expected)
        result[f"prediction{name.title()}Count"] = len(actual)
    return result


def aggregate_recognition(
    results: list[dict[str, Any]],
    metric_names: tuple[str, ...] = ("token", "note", "rhythm", "pitch", "accidental"),
) -> dict[str, float | None]:
    """Return micro-averaged edit recognition and exact-system rates."""
    summary: dict[str, float | None] = {}
    for name in metric_names:
        title = name.title()
        distance = sum(int(result[f"{name}Distance"]) for result in results)
        reference = sum(int(result[f"reference{title}Count"]) for result in results)
        prediction = sum(int(result[f"prediction{title}Count"]) for result in results)
        denominator = max(reference, prediction)
        summary[f"{name}EditRecognitionRate"] = (
            round(max(0.0, 1.0 - distance / denominator), 6) if denominator else None
        )
        summary[f"{name}ExactSystemRate"] = (
            round(sum(result[f"{name}Distance"] == 0 for result in results) / len(results), 6)
            if results else None
        )
    return summary


def _camera_degrade(source: Path, target: Path, sample_id: str, hard: bool = False) -> None:
    """Deterministic mild phone-photo degradation for robustness testing."""
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read {source}")
    height, width = image.shape[:2]
    seed = int(hashlib.sha256(sample_id.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    amount = max(3, int(min(width, height) * (0.025 if hard else 0.012)))
    source_points = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    offsets = rng.integers(-amount, amount + 1, size=(4, 2)).astype(np.float32)
    matrix = cv2.getPerspectiveTransform(source_points, source_points + offsets)
    image = cv2.warpPerspective(image, matrix, (width, height), borderValue=(245, 245, 245))
    if hard:
        image = cv2.resize(image, None, fx=0.68, fy=0.68, interpolation=cv2.INTER_AREA)
        image = cv2.resize(image, (width, height), interpolation=cv2.INTER_LINEAR)
    image = cv2.GaussianBlur(image, (5, 5) if hard else (3, 3), 1.15 if hard else 0.65)
    gradient = np.linspace(0.64 if hard else 0.82, 1.04, width, dtype=np.float32)[None, :, None]
    image = np.clip(image.astype(np.float32) * gradient, 0, 255).astype(np.uint8)
    noise = rng.normal(0, 4.5 if hard else 2.2, image.shape).astype(np.float32)
    image = np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    if not cv2.imwrite(str(target), image, [cv2.IMWRITE_JPEG_QUALITY, 46 if hard else 68]):
        raise ValueError(f"Could not write {target}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--split", default="test")
    parser.add_argument("--degradation", choices=("clean", "camera", "camera-hard"), default="clean")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    dataset = ROOT / "data" / "omr-training" / "sposobin-shte-v1"
    records = [
        json.loads(line) for line in (dataset / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = [item for item in records if item["split"] == args.split][:max(0, args.limit)]
    results = []
    for index, item in enumerate(selected, start=1):
        image = dataset / item["image"]
        reference = dataset / item["musicxml"]
        print(f"[{index}/{len(selected)}] {item['id']}", flush=True)
        try:
            with tempfile.TemporaryDirectory(prefix="homr-sposobin-benchmark-") as temp_dir:
                omr_input = image
                if args.degradation != "clean":
                    omr_input = Path(temp_dir) / f"{item['id']}-camera.jpg"
                    _camera_degrade(image, omr_input, item["id"], hard=args.degradation == "camera-hard")
                transcription = transcribe_with_audiveris(omr_input, temp_dir, timeout_seconds=300)
                score = _score(reference, Path(transcription["exportedPath"]))
            results.append({"id": item["id"], "status": "ok", **score})
        except Exception as exc:  # noqa: BLE001
            results.append({"id": item["id"], "status": "error", "error": str(exc)[:500]})
    successful = [item for item in results if item["status"] == "ok"]
    summary = {
        "benchmarkScope": "synthetic-render upper bound; not real-world OMR accuracy",
        "metricDefinition": (
            "NED is Levenshtein distance divided by reference plus prediction length; "
            "it is an error rate, not classification accuracy"
        ),
        "datasetRecords": len(records),
        "splitRecords": sum(item["split"] == args.split for item in records),
        "syntheticRenderRecords": sum(bool(item.get("synthetic_render")) for item in selected),
        "split": args.split,
        "degradation": args.degradation,
        "requested": len(selected),
        "successful": len(successful),
        "meanTokenNed": round(sum(item["tokenNed"] for item in successful) / len(successful), 6) if successful else None,
        "meanNoteNed": round(sum(item["noteNed"] for item in successful) / len(successful), 6) if successful else None,
        "meanRhythmNed": round(sum(item["rhythmNed"] for item in successful) / len(successful), 6) if successful else None,
        "meanPitchNed": round(sum(item["pitchNed"] for item in successful) / len(successful), 6) if successful else None,
        "meanAccidentalNed": round(sum(item["accidentalNed"] for item in successful) / len(successful), 6) if successful else None,
        **aggregate_recognition(successful),
        "results": results,
    }
    output = args.output or (
        ROOT / "data" / "omr-benchmark" / f"sposobin-homr-{args.degradation}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    main()
