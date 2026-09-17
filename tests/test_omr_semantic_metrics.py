from pathlib import Path

import pytest

from omr_semantic_metrics import score_musicxml_semantics


SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "data/external/sposobin-shte/SHTE_V1/hamony dataset/ch4/original/ch4-01_a minor.xml"
)

pytestmark = pytest.mark.skipif(
    not SAMPLE.exists(),
    reason="optional SHTE dataset is not installed",
)


def test_identical_musicxml_has_perfect_semantic_recognition():
    result = score_musicxml_semantics(SAMPLE, SAMPLE)

    assert result["tokenDistance"] == 0
    assert result["noteEditRecognitionRate"] == 1.0
    assert result["rhythmEditRecognitionRate"] == 1.0
    assert result["pitchEditRecognitionRate"] == 1.0
    assert result["accidentalEditRecognitionRate"] == 1.0
    assert result["orderedPitchEditRecognitionRate"] == 1.0
    assert result["normalizedRhythmEditRecognitionRate"] == 1.0
    assert result["voicePitchEditRecognitionRate"] == 1.0
    assert result["voiceRhythmEditRecognitionRate"] == 1.0


def test_semantic_metric_detects_a_pitch_change(tmp_path):
    changed = tmp_path / "changed.musicxml"
    text = SAMPLE.read_text(encoding="utf-8")
    changed.write_text(text.replace("<step>E</step>", "<step>F</step>", 1), encoding="utf-8")

    result = score_musicxml_semantics(SAMPLE, changed)

    assert result["pitchDistance"] > 0
    assert result["pitchEditRecognitionRate"] < 1.0


def test_voice_aware_metric_detects_wrong_voice_with_correct_pitches(tmp_path):
    changed = tmp_path / "wrong-voice.musicxml"
    text = SAMPLE.read_text(encoding="utf-8")
    changed.write_text(text.replace("<voice>1</voice>", "<voice>9</voice>", 1), encoding="utf-8")

    result = score_musicxml_semantics(SAMPLE, changed)

    assert result["voicePitchEditRecognitionRate"] < 1.0
    assert result["voiceRhythmEditRecognitionRate"] < 1.0
