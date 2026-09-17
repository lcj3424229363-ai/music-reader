from fastapi.testclient import TestClient

import server


client = TestClient(server.app)


def entry(step: str, octave: int, units: int = 32) -> dict:
    return {
        "kind": "note",
        "duration": "1",
        "units": units,
        "pitches": [{"step": step, "octave": octave, "accidental": ""}],
    }


def test_solver_eligibility_accepts_a_single_in_range_complete_measure():
    result = server._solver_input_eligibility([[entry("C", 4)]], [], "4/4", "melody")

    assert result["eligible"] is True
    assert result["issues"] == []


def test_solver_eligibility_accepts_sposobin_low_eb_bass():
    bass = entry("E", 2)
    bass["pitches"][0]["accidental"] = "b"

    result = server._solver_input_eligibility([], [[bass]], "4/4", "bass")

    assert result["eligible"] is True
    assert result["issues"] == []


def test_solver_eligibility_rejects_damaged_omr_rhythm_and_range():
    result = server._solver_input_eligibility([[entry("A", 6, 28)]], [], "4/4", "melody")

    assert result["eligible"] is False
    assert [issue["code"] for issue in result["issues"]] == [
        "MEASURE_DURATION_MISMATCH",
        "OUT_OF_RANGE",
    ]


def test_solve_endpoint_returns_a_stable_gate_error_before_solver_execution():
    response = client.post(
        "/solve-melody",
        json={
            "key": "C major",
            "timeSignature": "4/4",
            "melodyMeasures": [[entry("A", 6, 28)]],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["errorCode"] == "INPUT_NOT_SOLVER_READY"
    assert payload["summary"]["status"] == "error"


def test_solve_endpoint_supports_inner_voice_given_exercises():
    cases = (("alto", "C", 4), ("tenor", "G", 3))
    for voice, step, octave in cases:
        response = client.post(
            "/solve-melody",
            json={
                "key": "C major",
                "timeSignature": "4/4",
                "questionType": voice,
                f"{voice}Measures": [[entry(step, octave)]],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        tracks = payload["fourPart"]["voices"]
        assert len(tracks) == 4
        anchored = next(track for track in tracks if track["id"] == voice)
        assert anchored["entries"][0]["pitches"][0]["display"] == f"{step}{octave}"
        assert anchored["entries"][0]["duration"] == "1"


def test_inner_voice_eligibility_uses_the_correct_vocal_range():
    result = server._solver_input_eligibility(
        [], [], "4/4", "alto", alto_measures=[[entry("C", 4)]],
    )

    assert result["eligible"] is True
    assert result["mode"] == "alto"


def test_solve_endpoint_rejects_a_lossy_import_projection():
    response = client.post(
        "/solve-melody",
        json={
            "key": "C major",
            "timeSignature": "4/4",
            "melodyMeasures": [[entry("C", 4)]],
            "sourceProjection": {
                "scoreIrValid": True,
                "lossless": False,
                "losses": [{"code": "DURATION_QUANTIZED"}],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["errorCode"] == "SOURCE_PROJECTION_LOSS"


def test_noncritical_notation_loss_does_not_block_solver():
    blocker = server._source_projection_blocker({
        "scoreIrValid": True,
        "lossless": False,
        "losses": [{"code": "TIE_NOTATION_DROPPED"}],
    })

    assert blocker is None


def test_end_to_end_solver_runs_only_for_unambiguous_ready_exercise(monkeypatch):
    captured = {}

    def fake_solver(request):
        captured["request"] = request
        return {
            "fourPart": {
                "voices": [{"id": role} for role in ("soprano", "alto", "tenor", "bass")],
                "answerContract": {"valid": True},
            },
            "summary": {"status": "complete"},
        }

    monkeypatch.setattr(server, "solve_melody_endpoint", fake_solver)
    melody = [[entry("C", 4)]]
    payload = {
        "key": "C major",
        "timeSignature": "4/4",
        "melodyMeasures": melody,
        "bassMeasures": [],
        "exerciseExtraction": {
            "kind": "melody-given",
            "recommendedQuestionType": "melody",
        },
        "solverEligibility": {"melody": {"eligible": True, "issues": []}},
        "omr": {"transcriptionReadiness": {"solverAllowed": True, "issues": []}},
    }

    result = server._solve_imported_exercise(payload)

    assert result["status"] == "complete"
    assert result["questionType"] == "melody"
    assert captured["request"].melodyMeasures == melody


def test_end_to_end_solver_stops_before_solver_when_omr_needs_review(monkeypatch):
    def unexpected_solver(_request):
        raise AssertionError("solver must not run")

    monkeypatch.setattr(server, "solve_melody_endpoint", unexpected_solver)
    result = server._solve_imported_exercise({
        "exerciseExtraction": {
            "kind": "bass-given",
            "recommendedQuestionType": "bass",
        },
        "solverEligibility": {"bass": {"eligible": True, "issues": []}},
        "omr": {"transcriptionReadiness": {
            "solverAllowed": False,
            "issues": [{"code": "OMR_CORRECTION_PENDING", "message": "review"}],
        }},
    })

    assert result["status"] == "review-required"
    assert result["stage"] == "recognition"
    assert result["issues"][0]["code"] == "OMR_CORRECTION_PENDING"


def test_end_to_end_reports_key_confirmation_instead_of_generic_ambiguity():
    assessment = {
        "key": "D major",
        "confidence": "low",
        "source": "pitch-analysis-only",
        "correlation": 0.71,
        "candidates": [],
    }
    result = server._solve_imported_exercise({
        "exerciseExtraction": {
            "kind": "ambiguous-key",
            "recommendedQuestionType": None,
            "keyAssessment": assessment,
        },
    })

    assert result["status"] == "selection-required"
    assert result["issues"][0]["code"] == "KEY_CONFIRMATION_REQUIRED"
    assert result["issues"][0]["key"] == "D major"


def test_end_to_end_reports_voice_assignment_review_without_losing_notes():
    assignment = {"confidence": "low", "method": "single-stream-classification"}
    result = server._solve_imported_exercise({
        "unassignedVoices": [{"measures": [[entry("F", 4)]]}],
        "exerciseExtraction": {
            "kind": "ambiguous-voice-assignment",
            "recommendedQuestionType": None,
            "voiceAssignment": assignment,
        },
    })

    assert result["status"] == "selection-required"
    assert result["issues"][0]["code"] == "VOICE_ASSIGNMENT_REQUIRED"
    assert result["issues"][0]["assignment"] == assignment
