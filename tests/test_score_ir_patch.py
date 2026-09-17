import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server
from reader import read_score
from score_ir import validate_score_ir
from score_ir_patch import ScoreIrPatchError, apply_confirmed_corrections


client = TestClient(server.app)
SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "data" / "external" / "sposobin-shte" / "SHTE_V1"
    / "hamony dataset" / "ch4" / "original" / "ch4-01_a minor.xml"
)


def correction(duration: str = "1/4") -> dict:
    return {
        "measure": 1,
        "voice": "soprano",
        "onset": "0/1",
        "duration": duration,
        "kind": "note",
        "pitches": [{"step": "F", "alter": 1, "octave": 5}],
    }


def test_confirmed_patch_is_atomic_and_records_provenance():
    original = read_score(SAMPLE)["scoreIr"]
    snapshot = copy.deepcopy(original)

    result = apply_confirmed_corrections(
        original, [correction()], confirmed=True, source="vlm", review_id="review-1"
    )
    event = result["scoreIr"]["parts"][0]["measures"][0]["events"][0]

    assert original == snapshot
    assert result["validation"]["valid"] is True
    assert event["pitches"][0]["display"] == "F#5"
    assert event["duration"] == "1/1"
    assert event["provenance"]["corrections"][-1]["reviewId"] == "review-1"


def test_patch_requires_confirmation():
    score_ir = read_score(SAMPLE)["scoreIr"]

    with pytest.raises(ScoreIrPatchError, match="confirmation"):
        apply_confirmed_corrections(score_ir, [correction()], confirmed=False)


def test_patch_rejects_a_change_that_overflows_the_measure():
    score_ir = read_score(SAMPLE)["scoreIr"]

    with pytest.raises(ScoreIrPatchError, match="EVENT_OUTSIDE_MEASURE"):
        apply_confirmed_corrections(score_ir, [correction("1/1")], confirmed=True)


def test_correction_endpoint_applies_a_confirmed_patch():
    score_ir = read_score(SAMPLE)["scoreIr"]
    response = client.post("/api/score-ir/apply-corrections", json={
        "scoreIr": score_ir,
        "corrections": [correction()],
        "confirmed": True,
        "reviewId": "api-review",
    })

    assert response.status_code == 200
    assert response.json()["applied"][0]["voice"] == "soprano"
    editor_payload = response.json()["editorPayload"]
    assert editor_payload["scoreIrValidation"]["valid"] is True
    assert editor_payload["sopranoMeasures"][0][0]["pitches"][0]["display"] == "F#5"
    assert editor_payload["importRoute"] == "score-ir-correction"


def test_review_run_only_persists_its_own_confirmed_proposal(tmp_path, monkeypatch):
    run_id = "a" * 32
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    proposed = correction()
    record = {
        "vision": {
            "reviewedRegions": [{
                "review": {"final": {
                    "decision": "replace_candidate",
                    "corrections": [proposed],
                }},
            }],
        },
    }
    (run_dir / "review.json").write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(server, "OMR_REVIEW_ROOT", tmp_path)
    score_ir = read_score(SAMPLE)["scoreIr"]

    response = client.post("/api/score-ir/apply-corrections", json={
        "scoreIr": score_ir,
        "corrections": [proposed],
        "confirmed": True,
        "source": "vlm",
        "reviewId": run_id,
    })

    assert response.status_code == 200
    assert response.json()["reviewRunUpdated"] is True
    assert (run_dir / "vlm-confirmed.score-ir.json").is_file()
    updated_record = json.loads((run_dir / "review.json").read_text(encoding="utf-8"))
    assert updated_record["vlmConfirmedAvailable"] is True

    foreign = copy.deepcopy(proposed)
    foreign["pitches"][0]["step"] = "G"
    rejected = client.post("/api/score-ir/apply-corrections", json={
        "scoreIr": score_ir,
        "corrections": [foreign],
        "confirmed": True,
        "source": "vlm",
        "reviewId": run_id,
    })
    assert rejected.status_code == 422
    assert "selected from this OMR review run" in rejected.json()["detail"]


def test_validator_detects_overlap_from_event_timeline():
    score_ir = read_score(SAMPLE)["scoreIr"]
    first_measure = score_ir["parts"][0]["measures"][0]
    first_measure["events"][1]["onset"] = "1/2"

    validation = validate_score_ir(score_ir)

    assert validation["valid"] is False
    assert "VOICE_OVERLAP" in {item["code"] for item in validation["errors"]}
