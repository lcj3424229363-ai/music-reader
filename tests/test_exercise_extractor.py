from exercise_extractor import extract_exercise_constraints


def voice() -> list[list[dict]]:
    return [[{"kind": "note", "pitches": [{"step": "C", "octave": 4}]}]]


def test_extracts_an_unambiguous_melody_given_exercise():
    result = extract_exercise_constraints({"sopranoMeasures": voice()})

    assert result["kind"] == "melody-given"
    assert result["recommendedQuestionType"] == "melody"
    assert result["requiresUserConfirmation"] is False


def test_complete_score_is_not_silently_treated_as_an_exercise():
    result = extract_exercise_constraints({
        "sopranoMeasures": voice(), "altoMeasures": voice(),
        "tenorMeasures": voice(), "bassMeasures": voice(),
    })

    assert result["kind"] == "complete-score"
    assert result["recommendedQuestionType"] is None
    assert result["requiresUserConfirmation"] is True
    assert {item["questionType"] for item in result["candidates"]} == {
        "melody", "alto", "tenor", "bass",
    }


def test_single_inner_voice_is_an_unambiguous_exercise():
    alto = extract_exercise_constraints({"altoMeasures": voice()})
    tenor = extract_exercise_constraints({"tenorMeasures": voice()})

    assert (alto["kind"], alto["recommendedQuestionType"]) == ("alto-given", "alto")
    assert (tenor["kind"], tenor["recommendedQuestionType"]) == ("tenor-given", "tenor")


def test_rests_do_not_make_a_voice_known():
    result = extract_exercise_constraints({
        "sopranoMeasures": [[{"kind": "rest", "pitches": []}]],
        "bassMeasures": voice(),
    })

    assert result["kind"] == "bass-given"
    assert result["knownVoices"] == ["bass"]


def test_low_confidence_voice_assignment_requires_confirmation():
    result = extract_exercise_constraints({
        "sopranoMeasures": voice(),
        "voiceAssignment": {
            "method": "single-stream-classification",
            "confidence": "low",
        },
    })

    assert result["kind"] == "ambiguous-voice-assignment"
    assert result["recommendedQuestionType"] is None
    assert result["requiresUserConfirmation"] is True
    assert result["voiceAssignmentConfidence"] == "low"


def test_low_confidence_key_requires_confirmation_before_solving():
    result = extract_exercise_constraints({
        "bassMeasures": voice(),
        "keyAssessment": {
            "key": "D major",
            "source": "pitch-analysis-only",
            "confidence": "low",
            "correlation": 0.71,
        },
    })

    assert result["kind"] == "ambiguous-key"
    assert result["recommendedQuestionType"] is None
    assert result["requiresUserConfirmation"] is True
    assert result["keyConfidence"] == "low"
