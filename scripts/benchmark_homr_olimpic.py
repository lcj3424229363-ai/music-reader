"""Benchmark configured HOMR weights on real scanned OLiMPiC systems."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
HOMR_SOURCE = ROOT / "data" / "omr-benchmark" / "homr-source"
load_dotenv(ROOT / ".env")
sys.path[:0] = [str(ROOT), str(HOMR_SOURCE)]

from omr import find_homr, transcribe_with_audiveris  # noqa: E402
from omr_semantic_metrics import SEMANTIC_METRICS, score_musicxml_semantics  # noqa: E402
from omr_review_pipeline import MODEL_RHYTHM_REVIEW_THRESHOLD  # noqa: E402
from scripts.benchmark_homr_sposobin import aggregate_recognition  # noqa: E402


def _select_by_document(records: list[dict], split: str, limit: int) -> list[dict]:
    eligible = [record for record in records if record["split"] == split]
    first_per_document: list[dict] = []
    seen: set[str] = set()
    for record in eligible:
        if record["documentId"] not in seen:
            seen.add(record["documentId"])
            first_per_document.append(record)
    if limit <= 0 or not first_per_document:
        return []
    if limit >= len(first_per_document):
        return first_per_document
    indices = [round(index * (len(first_per_document) - 1) / max(1, limit - 1)) for index in range(limit)]
    return [first_per_document[index] for index in indices]


def _read_confidence(path: Path) -> dict | None:
    sidecar = path.with_suffix(".confidence.json")
    if not sidecar.is_file():
        return None
    try:
        value = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return (
        value if isinstance(value, dict)
        and value.get("schemaVersion") == "homr-confidence-v1" else None
    )


def confidence_router_calibration(results: list[dict]) -> dict:
    evaluated = []
    for result in results:
        overall = (result.get("recognitionConfidence") or {}).get("overall", {})
        rhythm_mean = (overall.get("rhythm") or {}).get("mean")
        if not isinstance(rhythm_mean, (int, float)):
            continue
        voice_pitch_rate = result.get(
            "voicePitchEditRecognitionRate",
            result["orderedPitchEditRecognitionRate"],
        )
        actual_risk = min(
            voice_pitch_rate,
            result["normalizedRhythmEditRecognitionRate"],
        ) < 0.8
        evaluated.append((rhythm_mean < MODEL_RHYTHM_REVIEW_THRESHOLD, actual_risk))
    true_positive = sum(predicted and actual for predicted, actual in evaluated)
    false_positive = sum(predicted and not actual for predicted, actual in evaluated)
    false_negative = sum(not predicted and actual for predicted, actual in evaluated)
    true_negative = sum(not predicted and not actual for predicted, actual in evaluated)
    return {
        "threshold": MODEL_RHYTHM_REVIEW_THRESHOLD,
        "riskDefinition": "voice-aware pitch or normalized rhythm recognition below 0.80",
        "evaluated": len(evaluated),
        "flagged": true_positive + false_positive,
        "truePositive": true_positive,
        "falsePositive": false_positive,
        "falseNegative": false_negative,
        "trueNegative": true_negative,
        "precision": round(true_positive / (true_positive + false_positive), 6)
        if true_positive + false_positive else None,
        "recall": round(true_positive / (true_positive + false_negative), 6)
        if true_positive + false_negative else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=ROOT / "data/omr-benchmark/olimpic-scanned-audit.json")
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/external/olimpic/olimpic-1.0-scanned")
    parser.add_argument("--split", choices=("dev", "test"), default="test")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output", type=Path, default=ROOT / "data/omr-benchmark/olimpic-scanned-homr.json")
    parser.add_argument("--predictions-dir", type=Path)
    parser.add_argument("--reuse-predictions", action="store_true")
    args = parser.parse_args()

    audit = json.loads(args.audit.resolve().read_text(encoding="utf-8"))
    if not audit.get("valid"):
        raise ValueError("OLiMPiC audit must pass before benchmarking")
    selected = _select_by_document(audit["manifest"], args.split, args.limit)
    dataset = args.dataset.resolve()
    predictions_dir = args.predictions_dir.resolve() if args.predictions_dir else None
    results = []
    for index, record in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {record['id']}", flush=True)
        try:
            prediction = None
            confidence = None
            if predictions_dir is not None:
                prediction = predictions_dir / f"{record['documentId']}__{Path(record['id']).name}.musicxml"
            if not (args.reuse_predictions and prediction is not None and prediction.is_file()):
                with tempfile.TemporaryDirectory(prefix="homr-olimpic-") as temp_dir:
                    transcription = transcribe_with_audiveris(
                        dataset / record["image"], temp_dir, timeout_seconds=300,
                    )
                    generated = Path(transcription["exportedPath"])
                    if prediction is not None:
                        prediction.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(generated, prediction)
                        generated_confidence = generated.with_suffix(".confidence.json")
                        if generated_confidence.is_file():
                            shutil.copy2(
                                generated_confidence,
                                prediction.with_suffix(".confidence.json"),
                            )
                    else:
                        prediction = generated
                    confidence = _read_confidence(prediction)
                    score = score_musicxml_semantics(dataset / record["musicxml"], prediction)
            else:
                confidence = _read_confidence(prediction)
                score = score_musicxml_semantics(dataset / record["musicxml"], prediction)
            results.append({
                "id": record["id"], "documentId": record["documentId"],
                "status": "ok", "recognitionConfidence": confidence, **score,
            })
        except Exception as exc:  # noqa: BLE001
            results.append({
                "id": record["id"], "documentId": record["documentId"],
                "status": "error", "error": str(exc)[:500],
            })

    successful = [record for record in results if record["status"] == "ok"]
    report = {
        "benchmarkScope": "real IMSLP scans; evaluation-only OLiMPiC holdout",
        "metricDefinition": (
            "corpus micro-average: 1 - total ScoreIR semantic edit distance / "
            "max(total reference events, total prediction events)"
        ),
        "metricRepresentation": "part/measure/staff/voice/onset/duration/pitch/alter events from music21 -> ScoreIR",
        "model": {
            "encoder": Path(os.environ.get("HOMR_ENCODER_MODEL", "official")).name,
            "decoder": Path(os.environ.get("HOMR_DECODER_MODEL", "official")).name,
            "executable": str(find_homr() or "unavailable"),
        },
        "split": args.split,
        "requested": len(selected),
        "successful": len(successful),
        "failed": len(selected) - len(successful),
        **{
            f"mean{name[0].upper() + name[1:]}Ned": (
                round(sum(record[f"{name}Ned"] for record in successful) / len(successful), 6)
                if successful else None
            )
            for name in SEMANTIC_METRICS
        },
        **aggregate_recognition(successful, SEMANTIC_METRICS),
        "confidenceRouterCalibration": confidence_router_calibration(successful),
        "results": results,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    main()
