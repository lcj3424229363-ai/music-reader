"""Tests for the in-app SHTE score catalogue."""

from pathlib import Path

import pytest

from fastapi.testclient import TestClient

import server


client = TestClient(server.app)

SHTE_ROOT = Path(__file__).resolve().parents[1] / "data/external/sposobin-shte/SHTE_V1"
pytestmark = pytest.mark.skipif(
    not SHTE_ROOT.exists(),
    reason="optional SHTE dataset is not installed",
)


def test_list_xml_finds_project_local_sposobin_dataset():
    server._XML_FILE_REGISTRY.clear()
    response = client.get("/list-xml", params={"query": "ch4-01", "limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 193
    assert payload["filtered"] >= 1
    assert any(item["id"] == "ch4-01_a minor" for item in payload["files"])


def test_parse_score_by_id_and_unknown_id():
    server._XML_FILE_REGISTRY.clear()
    response = client.post("/parse-score-by-id", json={"file_id": "ch4-01_a minor"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["key"] == "A minor"
    assert payload["timeSignature"] == "2/4"
    assert payload["melodyMeasures"]
    assert payload["bassMeasures"]
    assert payload["sourceMusicXml"].lstrip().startswith("<?xml")

    missing = client.post("/parse-score-by-id", json={"file_id": "does-not-exist"})
    assert missing.status_code == 404
