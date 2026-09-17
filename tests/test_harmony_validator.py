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


def test_independent_validator_uses_local_key_and_rejects_doubled_leading_tone():
    data = solution(("F#5", "F#4", "D4", "B2"))
    data["measures"][0]["beats"][0]["localTonicPitchClass"] = 7

    report = validate_four_part_solution(data, key="C major")

    assert "DOUBLED_LEADING_TONE" in codes(report)


def test_independent_validator_checks_seventh_chord_completeness_and_resolution():
    data = solution(
        ("F5", "B4", "G4", "G3"),
        ("G5", "C5", "E4", "C3"),
    )
    first, second = data["measures"][0]["beats"]
    first.update({
        "chordKind": "seventh",
        "chordPitchClasses": [2, 5, 7, 11],
        "chordSeventhPitchClass": 5,
        "chordIdentity": "G7",
    })
    second.update({
        "chordKind": "triad",
        "chordPitchClasses": [0, 4, 7],
        "chordIdentity": "C",
    })

    report = validate_four_part_solution(data, key="C major", question_type="bass")

    assert "CHORDAL_SEVENTH_RESOLUTION" in codes(report)


def test_dominant_leading_tone_cannot_be_held_when_harmony_changes():
    data = solution(
        ("B4", "G4", "D4", "G3"),
        ("B4", "G4", "E4", "C3"),
    )
    first, second = data["measures"][0]["beats"]
    first.update({
        "function": "D", "chordIdentity": "G", "localTonicPitchClass": 0,
    })
    second.update({
        "function": "T", "chordIdentity": "C", "localTonicPitchClass": 0,
    })

    report = validate_four_part_solution(data, key="C major", question_type="bass")

    assert "LEADING_TONE_RESOLUTION" in codes(report)
