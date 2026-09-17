"""Endpoint tests for MusicXML -> editor -> solver data flow."""

from pathlib import Path

from fastapi.testclient import TestClient

import server


client = TestClient(server.app)
SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "data" / "external" / "sposobin-shte" / "SHTE_V1"
    / "hamony dataset" / "ch4" / "original" / "ch4-01_a minor.xml"
)


def parse_sample() -> dict:
    with SAMPLE.open("rb") as handle:
        response = client.post(
            "/parse-score",
            files={"file": (SAMPLE.name, handle, "application/vnd.recordare.musicxml+xml")},
        )
    assert response.status_code == 200
    return response.json()


def test_parse_score_returns_editor_payload_and_canonical_source():
    payload = parse_sample()

    assert payload["key"] == "A minor"
    assert payload["timeSignature"] == "2/4"
    assert len(payload["melodyMeasures"]) == 4
    assert len(payload["bassMeasures"]) == 4
    assert "rawSummary" in payload
    assert payload["scoreIr"]["schemaVersion"] == "score-ir-v1"
    assert payload["scoreIrValidation"]["valid"] is True
    assert "path" not in payload["scoreIr"]["source"]
    assert payload["importRoute"] == "reader-projection"
    assert "<score-partwise" in payload["sourceMusicXml"]


def test_parse_score_payload_can_reach_solver_gate():
    payload = parse_sample()
    response = client.post(
        "/solve-melody",
        json={
            "key": payload["key"],
            "timeSignature": payload["timeSignature"],
            "questionType": "melody",
            "chordPoolProfile": "auto",
            "keyChanges": [],
            "melodyMeasures": payload["melodyMeasures"],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result.get("errorCode") != "INPUT_NOT_SOLVER_READY"
    assert result["summary"]["status"] == "complete"
    assert len(result["fourPart"]["voices"]) == 4
