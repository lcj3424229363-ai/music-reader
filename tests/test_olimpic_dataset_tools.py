from pathlib import Path

from scripts.audit_olimpic_dataset import audit_dataset
from scripts.benchmark_homr_olimpic import _select_by_document, confidence_router_calibration
from scripts.benchmark_homr_sposobin import aggregate_recognition


MINIMAL_XML = """<?xml version="1.0"?><score-partwise version="3.1"><part-list/></score-partwise>"""


def write_sample(root: Path, sample: str) -> None:
    stem = root / sample
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".png").write_bytes(b"png")
    stem.with_suffix(".musicxml").write_text(MINIMAL_XML, encoding="utf-8")
    stem.with_suffix(".lmx").write_text("measure", encoding="utf-8")


def test_audit_accepts_complete_document_disjoint_triplets(tmp_path):
    write_sample(tmp_path, "samples/doc-dev/p1-s1")
    write_sample(tmp_path, "samples/doc-test/p1-s1")
    (tmp_path / "samples.dev.txt").write_text("samples/doc-dev/p1-s1\n", encoding="utf-8")
    (tmp_path / "samples.test.txt").write_text("samples/doc-test/p1-s1\n", encoding="utf-8")

    report = audit_dataset(tmp_path)

    assert report["valid"] is True
    assert report["splitRecords"] == {"dev": 1, "test": 1}
    assert all(record["trainingAllowed"] is False for record in report["manifest"])


def test_audit_rejects_document_leakage_and_missing_pair(tmp_path):
    write_sample(tmp_path, "samples/shared/p1-s1")
    (tmp_path / "samples.dev.txt").write_text("samples/shared/p1-s1\n", encoding="utf-8")
    (tmp_path / "samples.test.txt").write_text("samples/shared/p1-s2\n", encoding="utf-8")

    report = audit_dataset(tmp_path)

    assert report["valid"] is False
    assert report["documentSplitOverlap"] == ["shared"]
    assert report["missingTriplets"]


def test_benchmark_selection_uses_distinct_documents():
    records = [
        {"id": "a/1", "documentId": "a", "split": "test"},
        {"id": "a/2", "documentId": "a", "split": "test"},
        {"id": "b/1", "documentId": "b", "split": "test"},
        {"id": "c/1", "documentId": "c", "split": "test"},
    ]

    selected = _select_by_document(records, "test", 2)

    assert [record["documentId"] for record in selected] == ["a", "c"]


def test_edit_recognition_rate_is_micro_averaged():
    results = [{
        **{f"{name}Distance": 2 for name in ("token", "note", "rhythm", "pitch", "accidental")},
        **{f"reference{name.title()}Count": 10 for name in ("token", "note", "rhythm", "pitch", "accidental")},
        **{f"prediction{name.title()}Count": 8 for name in ("token", "note", "rhythm", "pitch", "accidental")},
    }]

    rates = aggregate_recognition(results)

    assert rates["noteEditRecognitionRate"] == 0.8
    assert rates["noteExactSystemRate"] == 0.0


def test_edit_recognition_rate_uses_corpus_totals_for_denominator():
    results = []
    for reference, prediction in ((10, 2), (2, 10)):
        results.append({
            **{f"{name}Distance": 2 for name in ("token", "note", "rhythm", "pitch", "accidental")},
            **{f"reference{name.title()}Count": reference for name in ("token", "note", "rhythm", "pitch", "accidental")},
            **{f"prediction{name.title()}Count": prediction for name in ("token", "note", "rhythm", "pitch", "accidental")},
        })

    rates = aggregate_recognition(results)

    assert rates["noteEditRecognitionRate"] == round(1 - 4 / 12, 6)


def test_confidence_router_calibration_separates_precision_and_recall():
    def row(mean, pitch, rhythm):
        return {
            "recognitionConfidence": {"overall": {"rhythm": {"mean": mean}}},
            "orderedPitchEditRecognitionRate": pitch,
            "normalizedRhythmEditRecognitionRate": rhythm,
        }

    result = confidence_router_calibration([
        row(0.88, 0.7, 0.9),
        row(0.88, 0.9, 0.9),
        row(0.91, 0.7, 0.9),
        row(0.91, 0.9, 0.9),
    ])

    assert result["truePositive"] == 1
    assert result["falsePositive"] == 1
    assert result["falseNegative"] == 1
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5


def test_confidence_router_prefers_voice_aware_pitch_risk():
    result = confidence_router_calibration([{
        "recognitionConfidence": {"overall": {"rhythm": {"mean": 0.95}}},
        "orderedPitchEditRecognitionRate": 1.0,
        "voicePitchEditRecognitionRate": 0.5,
        "normalizedRhythmEditRecognitionRate": 1.0,
    }])

    assert result["falseNegative"] == 1
    assert result["riskDefinition"].startswith("voice-aware pitch")
