"""Reader projection tests without a separately running HTTP server."""

from pathlib import Path

from reader import read_score
from reader_to_editor import reader_payload_to_editor


SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "data" / "external" / "sposobin-shte" / "SHTE_V1"
    / "hamony dataset" / "ch4" / "original" / "ch4-01_a minor.xml"
)


def test_reader_to_editor_preserves_satb_anchor_voices():
    raw = read_score(SAMPLE)
    editor = reader_payload_to_editor(raw)

    assert raw["summary"]["analyzedKey"]["label"] == "A minor"
    assert editor["key"] == "A minor"
    assert editor["timeSignature"] == "2/4"
    assert len(editor["melodyMeasures"]) == 4
    assert len(editor["bassMeasures"]) == 4
    assert [part["staffNumber"] for part in raw["parts"]] == [1, 2]
    assert raw["parts"][0]["measures"][0]["clef"]["sign"] == "G"
    assert raw["parts"][1]["measures"][0]["clef"]["sign"] == "F"
    assert all(
        event["staff"] == part["staffNumber"]
        for part in raw["parts"]
        for measure in part["measures"]
        for event in measure["events"]
    )
    assert raw["scoreIr"]["parts"][1]["staffNumber"] == 2
    assert raw["scoreIr"]["parts"][1]["measures"][0]["clef"]["sign"] == "F"

    melody_entries = [entry for measure in editor["melodyMeasures"] for entry in measure]
    bass_entries = [entry for measure in editor["bassMeasures"] for entry in measure]
    assert all(entry.get("voice") == "soprano" for entry in melody_entries if entry["kind"] == "note")
    assert all(entry.get("voice") == "bass" for entry in bass_entries if entry["kind"] == "note")
