"""Run one real image through HOMR, validation, extraction, and SATB solving."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import server


EXPECTED_VOICES = {"soprano", "alto", "tenor", "bass"}


def run(image_path: Path, use_vision: bool = False) -> dict[str, object]:
    image_path = image_path.resolve()
    if not image_path.is_file():
        raise FileNotFoundError(image_path)

    started = time.perf_counter()
    with TestClient(server.app) as client, image_path.open("rb") as handle:
        response = client.post(
            "/api/omr/enhanced-parse",
            files={"file": (image_path.name, handle, "application/octet-stream")},
            data={
                "useVision": str(use_vision).lower(),
                "autoSolve": "true",
            },
        )
    elapsed = round(time.perf_counter() - started, 3)
    response.raise_for_status()

    payload = response.json()
    workflow = payload.get("endToEnd") or {}
    solution = workflow.get("solution") or {}
    four_part = solution.get("fourPart") or {}
    solution_summary = solution.get("summary") or {}
    voices = four_part.get("voices") or []
    voice_ids = {voice.get("id") for voice in voices}
    readiness = (payload.get("omr") or {}).get("transcriptionReadiness") or {}
    result = {
        "input": str(image_path),
        "elapsedSeconds": elapsed,
        "engine": (payload.get("omr") or {}).get("engine"),
        "readiness": readiness.get("status"),
        "solverAllowed": readiness.get("solverAllowed"),
        "workflowStatus": workflow.get("status"),
        "workflowStage": workflow.get("stage"),
        "questionType": workflow.get("questionType"),
        "key": payload.get("key"),
        "timeSignature": payload.get("timeSignature"),
        "measureCount": solution_summary.get("measureCount"),
        "voiceIds": sorted(role for role in voice_ids if role),
        "qualify": solution_summary.get("qualify"),
        "validation": solution_summary.get("independentValidation"),
        "issues": workflow.get("issues") or readiness.get("issues") or [],
    }

    failures = []
    if workflow.get("status") != "complete":
        failures.append(f"workflow status is {workflow.get('status')!r}")
    if workflow.get("stage") != "answer":
        failures.append(f"workflow stage is {workflow.get('stage')!r}")
    if voice_ids != EXPECTED_VOICES:
        failures.append(f"expected SATB voices, received {sorted(role for role in voice_ids if role)}")
    if solution_summary.get("qualify") is not True:
        failures.append("solver result did not qualify")
    validation = solution_summary.get("independentValidation") or {}
    if validation.get("valid") is not True:
        failures.append("independent SATB validation failed")
    if failures:
        raise RuntimeError("; ".join(failures) + "\n" + json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="PNG/JPEG/TIFF/PDF score input")
    parser.add_argument("--vision", action="store_true", help="also run the configured VLM review")
    parser.add_argument("--output", type=Path, help="optional JSON summary path")
    args = parser.parse_args()

    result = run(args.image, args.vision)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
