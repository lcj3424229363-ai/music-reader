import json
import hashlib
from pathlib import Path

from PIL import Image

from scripts.build_homr_finetune_dataset import (
    collect_human_review_records,
    collect_published_records,
    musical_fingerprint,
    split_for_group,
    write_outputs,
)


def _musicxml(step: str = "C", credit: str = "layout text") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <credit><credit-words>{credit}</credit-words></credit>
  <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
  <part id="P1"><measure number="99">
    <attributes><divisions>1</divisions><key><fifths>0</fifths></key>
      <time><beats>4</beats><beat-type>4</beat-type></time>
      <clef><sign>G</sign><line>2</line></clef></attributes>
    <note><pitch><step>{step}</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice></note>
  </measure></part>
</score-partwise>"""


def _write_pair(root: Path, sample_id: str = "sample") -> tuple[Path, Path]:
    image_dir = root / "images"
    score_dir = root / "musicxml"
    image_dir.mkdir(parents=True, exist_ok=True)
    score_dir.mkdir(parents=True, exist_ok=True)
    image = image_dir / f"{sample_id}.png"
    score = score_dir / f"{sample_id}.musicxml"
    Image.new("L", (32, 16), "white").save(image)
    score.write_text(_musicxml(), encoding="utf-8")
    return image, score


def test_musical_fingerprint_ignores_credit_and_measure_number(tmp_path):
    first = tmp_path / "first.musicxml"
    second = tmp_path / "second.musicxml"
    first.write_text(_musicxml(credit="first"), encoding="utf-8")
    second.write_text(_musicxml(credit="second").replace('number="99"', 'number="1"'), encoding="utf-8")

    assert musical_fingerprint(first) == musical_fingerprint(second)


def test_musical_fingerprint_changes_with_notated_pitch(tmp_path):
    first = tmp_path / "first.musicxml"
    second = tmp_path / "second.musicxml"
    first.write_text(_musicxml("C"), encoding="utf-8")
    second.write_text(_musicxml("D"), encoding="utf-8")

    assert musical_fingerprint(first) != musical_fingerprint(second)


def test_published_duplicates_share_content_split(tmp_path):
    image_a, score_a = _write_pair(tmp_path, "a")
    image_b, score_b = _write_pair(tmp_path, "b")
    manifest = tmp_path / "manifest.jsonl"
    rows = [
        {"id": "a", "image": str(image_a.relative_to(tmp_path)), "musicxml": str(score_a.relative_to(tmp_path))},
        {"id": "b", "image": str(image_b.relative_to(tmp_path)), "musicxml": str(score_b.relative_to(tmp_path))},
    ]
    manifest.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    records, rejected = collect_published_records(tmp_path)

    assert rejected == []
    assert len(records) == 2
    assert records[0]["group"] == records[1]["group"]
    assert records[0]["split"] == records[1]["split"] == split_for_group(records[0]["group"])


def test_review_data_requires_explicit_human_final(tmp_path):
    unconfirmed = tmp_path / "unconfirmed"
    unconfirmed.mkdir()
    (unconfirmed / "review.json").write_text(
        json.dumps({"humanFinalAvailable": False, "vision": {"final": {"confidence": 0.99}}}),
        encoding="utf-8",
    )
    Image.new("L", (32, 16), "white").save(unconfirmed / "source.png")
    (unconfirmed / "homr.musicxml").write_text(_musicxml(), encoding="utf-8")

    confirmed = tmp_path / "confirmed"
    confirmed.mkdir()
    (confirmed / "review.json").write_text(json.dumps({"humanFinalAvailable": True}), encoding="utf-8")
    Image.new("L", (32, 16), "white").save(confirmed / "source.png")
    (confirmed / "human-final.musicxml").write_text(_musicxml("D"), encoding="utf-8")

    records, rejected = collect_human_review_records(tmp_path)

    assert [record["id"] for record in records] == ["human-confirmed"]
    assert records[0]["labelTier"] == "gold-human"
    assert {item["source"]: item["reason"] for item in rejected} == {
        "unconfirmed": "missing_human_final"
    }


def test_review_data_rejects_tampered_human_final(tmp_path):
    run = tmp_path / "tampered"
    run.mkdir()
    source = run / "source.png"
    final = run / "human-final.musicxml"
    Image.new("L", (32, 16), "white").save(source)
    final.write_text(_musicxml(), encoding="utf-8")
    (run / "review.json").write_text(json.dumps({
        "humanFinalAvailable": True,
        "labelStatus": "gold-human",
        "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "humanFinalSha256": "0" * 64,
    }), encoding="utf-8")

    records, rejected = collect_human_review_records(tmp_path)

    assert records == []
    assert rejected[0]["source"] == "tampered"
    assert "human final hash" in rejected[0]["reason"]


def test_review_data_accepts_pdf_source_for_synthetic_label_rendering(tmp_path):
    run = tmp_path / "pdf-review"
    run.mkdir()
    (run / "source.pdf").write_bytes(b"%PDF-1.4\nreview-source")
    (run / "human-final.musicxml").write_text(_musicxml(), encoding="utf-8")
    (run / "review.json").write_text(json.dumps({
        "humanFinalAvailable": True,
        "labelStatus": "gold-human",
    }), encoding="utf-8")

    records, rejected = collect_human_review_records(tmp_path)

    assert rejected == []
    assert records[0]["sourceType"] == "pdf"
    assert records[0]["realImageAligned"] is False


def test_quality_report_detects_cross_split_group_leakage(tmp_path):
    image, score = _write_pair(tmp_path / "source")
    samples = [
        {"id": "a", "group": "same", "split": "train", "image": image, "tokens": score},
        {"id": "b", "group": "same", "split": "test", "image": image, "tokens": score},
    ]

    report = write_outputs(
        tmp_path / "out", tmp_path, [{"split": "train", "labelTier": "gold-published"}], samples, []
    )

    assert report["crossSplitLeakage"] == ["same"]
    assert report["readyForTraining"] is False


def test_quality_report_requires_all_three_splits(tmp_path):
    image, score = _write_pair(tmp_path / "source")
    samples = [{"id": "a", "group": "one", "split": "train", "image": image, "tokens": score}]

    report = write_outputs(
        tmp_path / "out", tmp_path, [{"split": "train", "labelTier": "gold-published"}], samples, []
    )

    assert report["readyForTraining"] is False
    assert "Missing generated split(s): validation, test." in report["warnings"]
