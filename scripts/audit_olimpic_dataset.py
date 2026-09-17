"""Audit the real-scanned OLiMPiC holdout and build a reproducible manifest."""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "external" / "olimpic" / "olimpic-1.0-scanned"
DEFAULT_OUTPUT = ROOT / "data" / "omr-benchmark" / "olimpic-scanned-audit.json"


def _sample_lines(dataset: Path, split: str) -> list[str]:
    return [
        line.strip().replace("\\", "/")
        for line in (dataset / f"samples.{split}.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def audit_dataset(dataset: Path) -> dict[str, Any]:
    dataset = dataset.resolve()
    records: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    invalid_xml: list[dict[str, str]] = []
    documents: dict[str, set[str]] = {"dev": set(), "test": set()}

    for split in ("dev", "test"):
        for sample in _sample_lines(dataset, split):
            stem = dataset / sample
            document_id = Path(sample).parent.name
            documents[split].add(document_id)
            paths = {
                "image": stem.with_suffix(".png"),
                "musicxml": stem.with_suffix(".musicxml"),
                "lmx": stem.with_suffix(".lmx"),
            }
            absent = [name for name, path in paths.items() if not path.is_file()]
            if absent:
                missing.append({"sample": sample, "files": ",".join(absent)})
                continue
            try:
                ET.parse(paths["musicxml"])
            except (ET.ParseError, OSError) as exc:
                invalid_xml.append({"sample": sample, "error": str(exc)})
                continue
            records.append({
                "id": sample.removeprefix("samples/"),
                "documentId": document_id,
                "split": split,
                "image": paths["image"].relative_to(dataset).as_posix(),
                "musicxml": paths["musicxml"].relative_to(dataset).as_posix(),
                "lmx": paths["lmx"].relative_to(dataset).as_posix(),
                "sourceType": "real-scan",
                "trainingAllowed": False,
            })

    overlap = sorted(documents["dev"] & documents["test"])
    return {
        "dataset": "OLiMPiC 1.0 Scanned",
        "datasetRoot": str(dataset),
        "license": "CC BY-SA",
        "source": "http://hdl.handle.net/11234/1-5419",
        "policy": "evaluation-only; dev/test records must not be used for training",
        "records": len(records),
        "splitRecords": {
            split: sum(record["split"] == split for record in records)
            for split in ("dev", "test")
        },
        "documentCounts": {split: len(values) for split, values in documents.items()},
        "documentSplitOverlap": overlap,
        "missingTriplets": missing,
        "invalidMusicXml": invalid_xml,
        "valid": not missing and not invalid_xml and not overlap,
        "manifest": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = audit_dataset(args.dataset)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "manifest"}, indent=2))
    if not report["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
