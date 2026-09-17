"""Audit persisted OMR review runs before they are used as training evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from musicxml_quality import audit_musicxml
from omr_semantic_metrics import score_musicxml_semantics
from reader import read_score
from score_ir import validate_score_ir


DEFAULT_ROOT = PROJECT_ROOT / "data" / "omr-review-runs"
SOURCE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".pdf"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def audit_review_run(run_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "runId": run_dir.name,
        "status": "invalid",
        "humanFinalAvailable": False,
        "realImageAligned": False,
        "issues": [],
        "warnings": [],
    }
    record_path = run_dir / "review.json"
    if not record_path.is_file():
        result["issues"].append(_issue("MISSING_REVIEW_RECORD", "review.json is missing."))
        return result
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        result["issues"].append(_issue("INVALID_REVIEW_RECORD", str(exc)[:300]))
        return result
    if not isinstance(record, dict):
        result["issues"].append(_issue("INVALID_REVIEW_RECORD", "review.json must contain an object."))
        return result

    source_files = sorted(
        path for path in run_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
    )
    if len(source_files) != 1:
        result["issues"].append(_issue("BAD_SOURCE_COUNT", f"Expected one source file, found {len(source_files)}."))
    elif record.get("sourceSha256") and _sha256(source_files[0]) != record["sourceSha256"]:
        result["issues"].append(_issue("SOURCE_HASH_MISMATCH", "Source hash differs from review.json."))
    else:
        result["sourceFile"] = source_files[0].name

    homr_path = run_dir / "homr.musicxml"
    if not homr_path.is_file():
        result["issues"].append(_issue("MISSING_HOMR_XML", "homr.musicxml is missing."))
    else:
        homr_audit = audit_musicxml(homr_path)
        result["homrAuditStatus"] = homr_audit["status"]
        if homr_audit["status"] == "invalid":
            result["warnings"].append(_issue("INVALID_HOMR_XML", "The immutable HOMR result needs human correction."))

    missing_artifacts = [
        name for name in record.get("reviewArtifacts", [])
        if not (run_dir / str(name)).is_file()
    ]
    if missing_artifacts:
        result["issues"].append(_issue(
            "MISSING_REVIEW_ARTIFACT",
            f"Missing review artifact(s): {', '.join(missing_artifacts[:5])}",
        ))

    has_final_flag = record.get("humanFinalAvailable") is True
    final_path = run_dir / "human-final.musicxml"
    result["humanFinalAvailable"] = has_final_flag and final_path.is_file()
    result["humanFinalRevision"] = int(record.get("humanFinalRevision") or 0)
    result["realImageAligned"] = bool(
        (record.get("trainingEvidence") or {}).get("realImageAligned")
    )
    if not has_final_flag and not final_path.exists():
        result["status"] = "pending" if not result["issues"] else "invalid"
        return result
    if has_final_flag != final_path.is_file():
        result["issues"].append(_issue("FINAL_STATE_MISMATCH", "Final-file presence and review flag disagree."))
        return result
    expected_hash = record.get("humanFinalSha256")
    if expected_hash and _sha256(final_path) != expected_hash:
        result["issues"].append(_issue("FINAL_HASH_MISMATCH", "Human-final hash differs from review.json."))
        return result

    final_audit = audit_musicxml(final_path)
    result["humanFinalAuditStatus"] = final_audit["status"]
    if final_audit["status"] == "invalid":
        result["issues"].append(_issue("INVALID_HUMAN_FINAL_XML", "Human-final MusicXML failed audit."))
        return result
    try:
        parsed = read_score(final_path)
        validation = validate_score_ir(parsed.get("scoreIr", {}))
    except Exception as exc:
        result["issues"].append(_issue("UNREADABLE_HUMAN_FINAL", str(exc)[:300]))
        return result
    result["scoreIrValid"] = validation["valid"]
    if not validation["valid"]:
        result["issues"].append(_issue("INVALID_HUMAN_FINAL_SCORE_IR", "Human-final ScoreIR is invalid."))
        return result
    if homr_path.is_file():
        try:
            result["homrVsHuman"] = score_musicxml_semantics(final_path, homr_path)
        except Exception as exc:
            result["warnings"].append(_issue("SEMANTIC_COMPARISON_FAILED", str(exc)[:300]))
    if record.get("labelStatus") not in {None, "gold-human"}:
        result["issues"].append(_issue("BAD_LABEL_STATUS", "Human final is not marked gold-human."))
        return result
    result["status"] = "ready" if not result["issues"] else "invalid"
    return result


def audit_review_runs(root: Path) -> dict[str, Any]:
    runs = [audit_review_run(path) for path in sorted(root.iterdir()) if path.is_dir()] if root.is_dir() else []
    statuses = Counter(run["status"] for run in runs)
    ready = [run for run in runs if run["status"] == "ready"]
    return {
        "root": str(root.resolve()),
        "runCount": len(runs),
        "statusCounts": dict(statuses),
        "goldHumanCount": len(ready),
        "alignedRealImageCount": sum(run["realImageAligned"] for run in ready),
        "runs": runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit OMR review runs and human-final labels")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_review_runs(args.root)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
