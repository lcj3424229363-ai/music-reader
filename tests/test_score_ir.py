from pathlib import Path

from fastapi.testclient import TestClient

import server
from reader import read_score
from reader_to_editor import _pitch_sort_key, _voice_sort_key, reader_payload_to_editor
from score_ir import SCHEMA_VERSION, score_ir_from_reader_payload, validate_score_ir


client = TestClient(server.app)
SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "data" / "external" / "sposobin-shte" / "SHTE_V1"
    / "hamony dataset" / "ch4" / "original" / "ch4-01_a minor.xml"
)


def test_reader_emits_valid_exact_score_ir():
    payload = read_score(SAMPLE)
    score_ir = payload["scoreIr"]

    assert score_ir["schemaVersion"] == SCHEMA_VERSION
    assert validate_score_ir(score_ir)["valid"] is True
    event = score_ir["parts"][0]["measures"][0]["events"][0]
    assert event["onset"] == "0/1"
    assert event["duration"] == "1/1"
    assert event["pitches"][0]["display"] == "E5"


def test_duplicate_printed_measure_numbers_still_get_unique_event_ids():
    payload = {
        "source": {},
        "summary": {},
        "parts": [{
            "id": "P1",
            "measures": [
                {"number": 1, "events": [{"type": "rest", "offset": 0, "duration": 1}]},
                {"number": 1, "events": [{"type": "rest", "offset": 0, "duration": 1}]},
            ],
        }],
    }
    score_ir = score_ir_from_reader_payload(payload)
    ids = [measure["events"][0]["id"] for measure in score_ir["parts"][0]["measures"]]

    assert len(set(ids)) == 2
    assert validate_score_ir(score_ir)["valid"] is True


def test_duplicate_reader_part_ids_are_stably_uniquified():
    payload = {
        "summary": {},
        "parts": [
            {"id": "Voice", "name": "Voice", "measures": []},
            {"id": "Voice", "name": "Voice", "measures": []},
        ],
    }

    score_ir = score_ir_from_reader_payload(payload)

    assert [part["id"] for part in score_ir["parts"]] == ["Voice", "Voice-2"]


def test_four_single_voice_parts_project_directly_to_satb():
    def part(part_id: str, pitch: str) -> dict:
        return {
            "id": part_id,
            "measures": [{
                "number": 1,
                "timeSignature": {"ratio": "4/4", "barDurationQuarterLength": 4},
                "events": [{"type": "note", "voice": "1", "offset": 0, "duration": 4, "pitch": pitch}],
            }],
        }

    payload = {
        "summary": {"analyzedKey": {"label": "C major"}},
        "parts": [part("S", "C5"), part("A", "G4"), part("T", "E3"), part("B", "C3")],
    }
    payload["scoreIr"] = score_ir_from_reader_payload(payload)
    editor = reader_payload_to_editor(payload)

    assert editor["sopranoMeasures"][0][0]["pitches"][0]["display"] == "C5"
    assert editor["altoMeasures"][0][0]["pitches"][0]["display"] == "G4"
    assert editor["tenorMeasures"][0][0]["pitches"][0]["display"] == "E3"
    assert editor["bassMeasures"][0][0]["pitches"][0]["display"] == "C3"
    assert editor["editorProjection"] == {"lossless": True, "losses": []}


def test_editor_projection_uses_numeric_voice_and_absolute_pitch_order():
    assert sorted(["10", "2", "1"], key=_voice_sort_key) == ["1", "2", "10"]
    assert max(["B3", "C4"], key=_pitch_sort_key) == "C4"


def test_editor_payload_carries_score_ir_and_projection_report():
    editor = reader_payload_to_editor(read_score(SAMPLE))

    assert editor["scoreIr"]["schemaVersion"] == SCHEMA_VERSION
    assert editor["scoreIrValidation"]["valid"] is True
    assert editor["editorProjection"] == {"lossless": True, "losses": []}


def test_score_ir_validation_endpoint():
    score_ir = read_score(SAMPLE)["scoreIr"]
    response = client.post("/api/score-ir/validate", json=score_ir)

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_score_ir_validation_rejects_an_empty_score():
    result = validate_score_ir({"schemaVersion": SCHEMA_VERSION, "parts": []})

    assert result["valid"] is False
    assert result["errors"][0]["code"] == "NO_PARTS"


def test_single_lower_staff_line_maps_to_bass_not_tenor():
    def part(part_id: str, pitch: str) -> dict:
        return {
            "id": part_id,
            "measures": [{
                "number": 1,
                "timeSignature": {"ratio": "4/4", "barDurationQuarterLength": 4},
                "events": [{
                    "type": "note", "voice": "1", "offset": 0,
                    "duration": 4, "pitch": pitch,
                }],
            }],
        }

    editor = reader_payload_to_editor({
        "summary": {"analyzedKey": {"label": "C major"}},
        "parts": [part("treble", "C5"), part("bass", "C3")],
    })

    assert editor["bassMeasures"][0][0]["pitches"][0]["display"] == "C3"
    assert editor["tenorMeasures"][0][0]["kind"] == "rest"


def test_complex_tuplets_remain_valid_but_projection_is_declared_lossy():
    candidates = list(
        (SAMPLE.parents[2]).rglob("*ch23-06*.xml")
    )
    assert candidates
    editor = reader_payload_to_editor(read_score(candidates[0]))

    assert editor["scoreIrValidation"]["valid"] is True
    codes = {item["code"] for item in editor["editorProjection"]["losses"]}
    assert "TUPLET_METADATA_DROPPED" in codes
    assert "DURATION_QUANTIZED" in codes
