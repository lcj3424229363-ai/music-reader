import io
import json
from pathlib import Path

from PIL import Image
from fastapi.testclient import TestClient

import server
from musicxml_quality import audit_musicxml
from omr_review_pipeline import (
    assess_omr_readiness,
    crop_measure_region,
    extract_measure_candidate,
    prepend_previous_system_context,
    save_review_run,
    select_review_measures,
    summarize_recognition_confidence,
)
from scripts.audit_omr_review_runs import audit_review_runs


SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "data" / "omr-training" / "sposobin-shte-v1" / "musicxml"
    / "ch4__ch4-01_a_minor.musicxml"
)
client = TestClient(server.app)


def test_gold_sposobin_musicxml_passes_semantic_audit():
    result = audit_musicxml(SAMPLE)

    assert result["status"] == "clean"
    assert result["score"] == 100
    assert result["stats"]["partCount"] >= 2
    assert result["stats"]["measureCount"] == 4


def test_audit_flags_measure_overflow():
    xml = """<?xml version="1.0"?>
    <score-partwise version="4.0"><part-list><score-part id="P1"><part-name>P1</part-name></score-part></part-list>
    <part id="P1"><measure number="1"><attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <note><pitch><step>C</step><octave>4</octave></pitch><duration>5</duration><voice>1</voice><type>whole</type></note>
    </measure></part></score-partwise>"""

    result = audit_musicxml(xml)

    assert result["status"] == "invalid"
    assert "1" in result["flaggedMeasures"]
    assert "MEASURE_OVERFLOW" in {issue["code"] for issue in result["issues"]}


def test_audit_prioritizes_implausible_omr_pitch_and_voice_order():
    xml = """<?xml version="1.0"?>
    <score-partwise version="4.0"><part-list><score-part id="P1"><part-name>P1</part-name></score-part></part-list>
    <part id="P1"><measure number="1"><attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><voice>1</voice><staff>1</staff><type>quarter</type></note>
    <note><pitch><step>G</step><octave>5</octave></pitch><duration>3</duration><voice>1</voice><staff>1</staff><type>half</type><dot/></note>
    <backup><duration>4</duration></backup>
    <note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><voice>2</voice><staff>1</staff><type>whole</type></note>
    </measure></part></score-partwise>"""

    result = audit_musicxml(xml)
    codes = {issue["code"] for issue in result["issues"]}

    assert result["status"] == "review"
    assert result["flaggedMeasures"] == ["1"]
    assert "SUSPICIOUS_MELODIC_LEAP" in codes
    assert "VOICE_ORDER_REVERSAL" in codes
    assert select_review_measures(result, 1) == [1]


def test_review_selection_includes_flagged_then_page_sentinels():
    audit = {"flaggedMeasures": ["4"], "stats": {"measureCount": 12}}

    assert select_review_measures(audit, 3) == [4, 1, 6]


def test_low_decoder_confidence_is_prioritized_before_sentinels():
    audit = {"flaggedMeasures": [], "stats": {"measureCount": 12}}
    pages = [{
        "page": 1,
        "measureCount": 12,
        "recognitionConfidence": {
            "systems": [
                {"index": 0, "branches": {"rhythm": {"mean": 0.91}}},
                {"index": 1, "branches": {"rhythm": {"mean": 0.88}}},
            ],
        },
    }]

    assert select_review_measures(audit, 3, pages) == [9, 1, 6]
    summary = summarize_recognition_confidence(pages)
    assert summary["status"] == "review"
    assert summary["reviewSystemCount"] == 1


def test_missing_decoder_confidence_is_not_reported_as_high_confidence():
    summary = summarize_recognition_confidence([])

    assert summary["available"] is False
    assert summary["status"] == "unavailable"


def test_omr_readiness_blocks_unresolved_visual_review():
    readiness = assess_omr_readiness(
        {"status": "clean", "reviewRequired": False},
        {"available": True, "status": "model-stable"},
        {
            "enabled": True,
            "errors": [],
            "reviewedRegions": [{
                "measure": 2,
                "review": {"final": {
                    "decision": "uncertain",
                    "validator": {"accepted": True},
                }},
            }],
        },
    )

    assert readiness["status"] == "needs-review"
    assert readiness["solverAllowed"] is False
    assert "OMR_VISION_UNRESOLVED" in readiness["blockingCodes"]


def test_omr_readiness_is_only_provisional_after_clean_acceptance():
    readiness = assess_omr_readiness(
        {"status": "clean", "reviewRequired": False},
        {"available": True, "status": "model-stable"},
        {
            "enabled": True,
            "errors": [],
            "reviewedRegions": [{
                "measure": 2,
                "review": {"final": {
                    "decision": "accept_candidate",
                    "validator": {"accepted": True},
                }},
            }],
        },
    )

    assert readiness["status"] == "provisional"
    assert readiness["solverAllowed"] is True


def test_visual_acceptance_clears_only_matching_quality_review_measure():
    quality = {
        "status": "review",
        "reviewRequired": True,
        "issues": [{
            "code": "SUSPICIOUS_MELODIC_LEAP", "severity": "warning", "measure": "2",
        }],
    }
    confidence = {"available": True, "status": "model-stable"}
    accepted = {
        "enabled": True,
        "errors": [],
        "reviewedRegions": [{
            "measure": 2,
            "review": {"final": {
                "decision": "accept_candidate",
                "validator": {"accepted": True},
            }},
        }],
    }

    resolved = assess_omr_readiness(quality, confidence, accepted)
    unresolved = assess_omr_readiness(
        {**quality, "issues": [*quality["issues"], {
            "code": "VOICE_ORDER_REVERSAL", "severity": "warning", "measure": "3",
        }]},
        confidence,
        accepted,
    )

    assert resolved["solverAllowed"] is True
    assert unresolved["solverAllowed"] is False
    assert "OMR_STRUCTURE_REVIEW" in unresolved["blockingCodes"]


def test_confirmed_vlm_correction_clears_only_its_pending_blocker():
    proposed = {
        "measure": 2,
        "voice": "soprano",
        "onset": "0/1",
        "duration": "1/4",
        "kind": "note",
        "pitches": [{"step": "C", "alter": 0, "octave": 5}],
    }
    readiness = assess_omr_readiness(
        {"status": "clean", "reviewRequired": False},
        {"available": True, "status": "model-stable"},
        {
            "enabled": True,
            "errors": [],
            "confirmedCorrections": [proposed],
            "reviewedRegions": [{
                "measure": 2,
                "review": {"final": {
                    "decision": "replace_candidate",
                    "corrections": [proposed],
                    "validator": {"accepted": True},
                }},
            }],
        },
    )

    assert readiness["solverAllowed"] is True
    assert "OMR_CORRECTION_PENDING" not in readiness["blockingCodes"]


def test_measure_candidate_groups_chords_and_uses_whole_note_units(tmp_path):
    score = tmp_path / "grand-staff.musicxml"
    score.write_text("""<?xml version="1.0"?>
<score-partwise version="4.0">
  <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
  <part id="P1"><measure number="1">
    <attributes><divisions>12</divisions><staves>2</staves></attributes>
    <note><pitch><step>C</step><octave>5</octave></pitch><duration>12</duration><voice>1</voice><staff>1</staff></note>
    <note><chord/><pitch><step>E</step><octave>5</octave></pitch><duration>12</duration><voice>1</voice><staff>1</staff></note>
    <backup><duration>12</duration></backup>
    <note><pitch><step>C</step><octave>3</octave></pitch><duration>12</duration><voice>5</voice><staff>2</staff></note>
  </measure></part>
</score-partwise>""", encoding="utf-8")

    candidate = extract_measure_candidate(score, 1)
    events = candidate["parts"][0]["events"]

    assert candidate["timeUnit"] == "whole-note"
    assert len(events) == 2
    assert events[0]["role"] == "soprano"
    assert events[0]["onset"] == "0/1"
    assert events[0]["duration"] == "1/4"
    assert [pitch["step"] for pitch in events[0]["pitches"]] == ["C", "E"]
    assert events[1]["role"] == "bass"


def test_crop_uses_homr_staff_coordinates_and_stays_in_image():
    output = io.BytesIO()
    Image.new("RGB", (1000, 600), "white").save(output, format="PNG")
    positions = [
        {"page": 1, "centerX": 0.5, "centerY": y, "width": 0.8, "height": 0.08}
        for y in (0.2, 0.32, 0.44, 0.56)
    ]

    crop, metadata = crop_measure_region(output.getvalue(), "image/png", positions, 2, 4, 4)

    with Image.open(io.BytesIO(crop)) as image:
        assert 0 < image.width < 1000
        assert 0 < image.height < 600
    assert metadata["mappingConfidence"] == 0.7
    assert metadata["systemIndex"] == 0
    assert all(value >= 0 for value in metadata["box"])


def test_previous_system_context_is_stacked_above_target_crop():
    page_output = io.BytesIO()
    Image.new("RGB", (1000, 600), "white").save(page_output, format="PNG")
    target_output = io.BytesIO()
    Image.new("RGB", (240, 120), "white").save(target_output, format="PNG")
    positions = [
        {"centerX": 0.5, "centerY": 0.25, "width": 0.8, "height": 0.15},
        {"centerX": 0.5, "centerY": 0.65, "width": 0.8, "height": 0.15},
    ]

    combined, metadata = prepend_previous_system_context(
        target_output.getvalue(), page_output.getvalue(), positions, 0
    )

    with Image.open(io.BytesIO(combined)) as image:
        assert image.width >= 800
        assert image.height > 120
    assert metadata["included"] is True
    assert metadata["contextSystemIndex"] == 0
    assert metadata["targetBox"][1] > metadata["contextBox"][1]
    assert metadata["targetBox"][3] == metadata["height"]


def test_musicxml_audit_endpoint_accepts_valid_score():
    with SAMPLE.open("rb") as handle:
        response = client.post(
            "/api/omr/audit-musicxml",
            files={"file": (SAMPLE.name, handle, "application/xml")},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "clean"


def test_review_run_persists_vlm_crop_artifacts(tmp_path):
    run_id = "b" * 32
    run_dir = save_review_run(
        tmp_path,
        run_id,
        b"image",
        ".png",
        SAMPLE.read_text(encoding="utf-8-sig"),
        {"quality": {}},
        artifacts={"review-crops/measure-0001.png": b"crop"},
    )

    record = json.loads((run_dir / "review.json").read_text(encoding="utf-8"))
    assert record["reviewArtifacts"] == ["review-crops/measure-0001.png"]
    assert (run_dir / "review-crops" / "measure-0001.png").read_bytes() == b"crop"


def test_review_crop_endpoint_serves_only_recorded_artifacts(monkeypatch, tmp_path):
    run_id = "c" * 32
    save_review_run(
        tmp_path,
        run_id,
        b"image",
        ".png",
        SAMPLE.read_text(encoding="utf-8-sig"),
        {"quality": {}},
        artifacts={"review-crops/measure-0001.png": b"crop-image"},
    )
    monkeypatch.setattr(server, "OMR_REVIEW_ROOT", tmp_path)

    response = client.get(
        f"/api/omr/review-runs/{run_id}/artifacts/review-crops/measure-0001.png"
    )
    missing = client.get(
        f"/api/omr/review-runs/{run_id}/artifacts/review-crops/unlisted.png"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content == b"crop-image"
    assert missing.status_code == 404


def test_human_final_is_stored_beside_immutable_homr_result(monkeypatch, tmp_path):
    run_id = "a" * 32
    xml = SAMPLE.read_text(encoding="utf-8-sig")
    save_review_run(tmp_path, run_id, b"image", ".png", xml, {"quality": {}})
    monkeypatch.setattr(server, "OMR_REVIEW_ROOT", tmp_path)

    response = client.post(
        f"/api/omr/review-runs/{run_id}/final-musicxml",
        files={"file": ("final.musicxml", xml.encode("utf-8"), "application/xml")},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["revision"] == 1
    assert result["idempotent"] is False
    assert result["scoreIrValidation"]["valid"] is True
    assert result["homrVsHuman"]["tokenEditRecognitionRate"] == 1.0
    assert (tmp_path / run_id / "homr.musicxml").read_text(encoding="utf-8") == xml
    assert (tmp_path / run_id / "human-final.musicxml").is_file()

    repeated = client.post(
        f"/api/omr/review-runs/{run_id}/final-musicxml",
        files={"file": ("final.musicxml", xml.encode("utf-8"), "application/xml")},
    )
    assert repeated.status_code == 200
    assert repeated.json()["revision"] == 1
    assert repeated.json()["idempotent"] is True

    revised_xml = xml.replace("<step>E</step>", "<step>F</step>", 1)
    revised = client.post(
        f"/api/omr/review-runs/{run_id}/final-musicxml",
        files={"file": ("revised.musicxml", revised_xml.encode("utf-8"), "application/xml")},
    )
    assert revised.status_code == 200
    assert revised.json()["revision"] == 2
    assert revised.json()["idempotent"] is False
    assert list((tmp_path / run_id / "human-final-revisions").glob("revision-0001-*.musicxml"))

    record = json.loads((tmp_path / run_id / "review.json").read_text(encoding="utf-8"))
    assert record["labelStatus"] == "gold-human"
    assert record["humanFinalRevision"] == 2
    assert record["trainingEvidence"]["realImageAligned"] is False

    audit = audit_review_runs(tmp_path)
    assert audit["statusCounts"] == {"ready": 1}
    assert audit["goldHumanCount"] == 1
    assert audit["alignedRealImageCount"] == 0
