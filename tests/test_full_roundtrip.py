"""A bounded MusicXML -> editor -> SATB answer round-trip test."""

from pathlib import Path

from fastapi.testclient import TestClient

import server


client = TestClient(server.app)
SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "data" / "external" / "sposobin-shte" / "SHTE_V1"
    / "hamony dataset" / "ch4" / "original" / "ch4-01_a minor.xml"
)


def _voice_measures(voices: list[dict], voice_id: str) -> list[dict]:
    voice = next(item for item in voices if item.get("id") == voice_id)
    return voice.get("measures", [])


def test_musicxml_editor_solver_roundtrip_has_four_aligned_voices():
    with SAMPLE.open("rb") as handle:
        parsed_response = client.post(
            "/parse-score",
            files={"file": (SAMPLE.name, handle, "application/vnd.recordare.musicxml+xml")},
        )
    assert parsed_response.status_code == 200
    editor = parsed_response.json()

    solved_response = client.post(
        "/solve-melody",
        json={
            "key": editor["key"],
            "timeSignature": editor["timeSignature"],
            "questionType": "melody",
            "chordPoolProfile": "auto",
            "keyChanges": [],
            "melodyMeasures": editor["melodyMeasures"],
        },
    )
    assert solved_response.status_code == 200
    solved = solved_response.json()
    assert solved["summary"]["status"] == "complete"

    voices = solved["fourPart"]["voices"]
    assert [voice["id"] for voice in voices] == ["soprano", "alto", "tenor", "bass"]
    contract = solved["fourPart"]["answerContract"]
    assert contract["valid"] is True
    assert contract["version"] == "satb-grand-staff-v1"
    assert contract["staves"] == [
        {"id": "treble", "number": 1, "clef": "treble", "voices": ["soprano", "alto"]},
        {"id": "bass", "number": 2, "clef": "bass", "voices": ["tenor", "bass"]},
    ]
    measure_counts = {len(_voice_measures(voices, voice_id)) for voice_id in (
        "soprano", "alto", "tenor", "bass"
    )}
    assert measure_counts == {len(editor["melodyMeasures"])}
