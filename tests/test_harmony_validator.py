from harmony_validator import validate_four_part_solution


def solution(*frames: tuple[str, str, str, str]) -> dict:
    return {
        "measures": [{
            "beats": [
                {"soprano": s, "alto": a, "tenor": t, "bass": b}
                for s, a, t, b in frames
            ],
        }],
    }


def codes(report: dict) -> set[str]:
    return {item["code"] for item in report["errors"]}


def test_independent_validator_accepts_clean_satb_motion():
    report = validate_four_part_solution(
        solution(("C5", "G4", "E4", "C3"), ("D5", "A4", "F4", "B2")),
        key="C major",
    )

    assert report["valid"] is True
    assert report["checkedFrames"] == 2


def test_independent_validator_detects_crossing_and_spacing():
    report = validate_four_part_solution(
        solution(("D5", "C4", "G4", "C3")),
        key="C major",
    )

    assert report["valid"] is False
    assert {"VOICE_CROSSING", "UPPER_VOICE_SPACING"} <= codes(report)


def test_independent_validator_detects_parallel_fifths():
    report = validate_four_part_solution(
        solution(("C5", "G4", "E4", "C3"), ("D5", "A4", "F4", "D3")),
        key="C major",
    )

    assert "PARALLEL_FIFTH" in codes(report)


def test_independent_validator_detects_unresolved_free_leading_tone():
    report = validate_four_part_solution(
        solution(("G5", "B4", "G4", "G3"), ("E5", "A4", "C4", "C3")),
        key="C major",
        question_type="melody",
    )

    assert "LEADING_TONE_RESOLUTION" in codes(report)


def test_independent_validator_skips_user_anchored_leading_tone():
    report = validate_four_part_solution(
        solution(("B4", "G4", "E4", "C3"), ("A4", "F4", "C4", "F2")),
        key="C major",
        question_type="melody",
    )

    assert "LEADING_TONE_RESOLUTION" not in codes(report)
