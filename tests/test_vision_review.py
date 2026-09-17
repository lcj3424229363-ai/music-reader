import io
import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

import server
import vision_review


client = TestClient(server.app)


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (16, 12), "white").save(output, format="PNG")
    return output.getvalue()


def valid_model_result() -> dict:
    return {
        "decision": "replace_candidate",
        "confidence": 0.94,
        "observations": ["The upper note is F-sharp."],
        "corrections": [{
            "measure": 2,
            "voice": "soprano",
            "onset": "1/4",
            "duration": "1/4",
            "kind": "note",
            "pitches": [{"step": "F", "alter": 1, "octave": 5}],
        }],
        "warnings": [],
    }


def test_validator_accepts_bounded_symbolic_correction():
    result = vision_review.validate_model_review(valid_model_result())

    assert result["validator"] == {"accepted": True, "issues": []}
    assert result["corrections"][0]["pitches"][0] == {
        "step": "F", "alter": 1, "octave": 5
    }
    assert result["requiresHumanConfirmation"] is True


def test_validator_rejects_low_confidence_replacement_and_discards_changes():
    value = valid_model_result()
    value["confidence"] = 0.61

    result = vision_review.validate_model_review(value)

    assert result["decision"] == "uncertain"
    assert result["corrections"] == []
    assert result["validator"]["accepted"] is False


def test_validator_discards_corrections_when_model_is_uncertain():
    value = valid_model_result()
    value["decision"] = "uncertain"
    value["confidence"] = 0.75

    result = vision_review.validate_model_review(value)

    assert result["decision"] == "uncertain"
    assert result["corrections"] == []
    assert result["validator"]["accepted"] is True


def test_validator_rejects_correction_outside_candidate_event_slots():
    candidate = {
        "measure": 2,
        "parts": [{
            "events": [{"role": "soprano", "onset": "0/1"}],
        }],
    }
    value = valid_model_result()

    result = vision_review.validate_model_review(
        value, candidate, {"measure": 2}
    )

    assert result["decision"] == "uncertain"
    assert result["corrections"] == []
    assert any(
        "does not match a candidate event slot" in issue
        for issue in result["validator"]["issues"]
    )


def test_validator_accepts_correction_at_candidate_event_slot():
    candidate = {
        "measure": 2,
        "parts": [{
            "events": [{"role": "soprano", "onset": "1/4"}],
        }],
    }

    result = vision_review.validate_model_review(
        valid_model_result(), candidate, {"measure": 2}
    )

    assert result["validator"]["accepted"] is True
    assert len(result["corrections"]) == 1


def test_validator_treats_equivalent_rational_slot_text_as_equal():
    candidate = {
        "measure": 2,
        "parts": [{"events": [{"role": "soprano", "onset": "1/4"}]}],
    }
    value = valid_model_result()
    value["corrections"][0]["onset"] = "2/8"

    result = vision_review.validate_model_review(value, candidate, {"measure": 2})

    assert result["validator"]["accepted"] is True


def test_status_does_not_expose_api_key(monkeypatch):
    monkeypatch.setenv("OMR_API_KEY", "top-secret-value")
    monkeypatch.setenv("OMR_API_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OMR_VISION_MODEL", "vision-test")
    monkeypatch.setenv("OMR_NOTATION_VISION_MODEL", "vision-test")

    response = client.get("/api/vision/status")

    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "provider": "example.test",
        "model": "vision-test",
        "apiStyle": "chat",
    }
    assert "top-secret-value" not in response.text


def test_notation_model_overrides_generic_ocr_model(monkeypatch):
    monkeypatch.setenv("OMR_API_KEY", "test-key")
    monkeypatch.setenv("OMR_VISION_MODEL", "qwen-vl-ocr-latest")
    monkeypatch.setenv("OMR_NOTATION_VISION_MODEL", "qwen3.6-flash")

    assert vision_review.VisionConfig.from_env().model == "qwen3.6-flash"


def test_review_endpoint_rejects_fake_image_before_provider_call(monkeypatch):
    monkeypatch.setattr(server, "review_score_region", vision_review.review_score_region)

    response = client.post(
        "/api/vision/review-region",
        files={"image": ("crop.png", b"not an image", "image/png")},
    )

    assert response.status_code == 400
    assert "readable image" in response.json()["detail"]


def test_review_endpoint_passes_validated_multipart_data(monkeypatch):
    seen = {}

    def fake_review(image_bytes, mime_type, candidate, context):
        seen.update({
            "bytes": image_bytes,
            "mime": mime_type,
            "candidate": candidate,
            "context": context,
        })
        return {"status": "reviewed", "decision": "uncertain"}

    monkeypatch.setattr(server, "review_score_region", fake_review)
    response = client.post(
        "/api/vision/review-region",
        files={"image": ("crop.png", png_bytes(), "image/png")},
        data={
            "candidate": json.dumps({"measure": 2}),
            "context": json.dumps({"key": "G major"}),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "reviewed"
    assert seen["mime"] == "image/png"
    assert seen["candidate"] == {"measure": 2}
    assert seen["context"] == {"key": "G major"}


def test_chat_connector_sends_image_and_validates_provider_output(monkeypatch):
    monkeypatch.setenv("OMR_API_KEY", "test-key")
    monkeypatch.setenv("OMR_API_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OMR_API_STYLE", "chat")
    monkeypatch.setenv("OMR_VISION_MODEL", "vision-test")
    monkeypatch.setenv("OMR_NOTATION_VISION_MODEL", "vision-test")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            provider = {
                "choices": [{"message": {"content": json.dumps(valid_model_result())}}]
            }
            return json.dumps(provider).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(vision_review.urllib.request, "urlopen", fake_urlopen)
    result = vision_review.review_score_region(
        png_bytes(), "image/png", {"measure": 2}, {"key": "G major"}
    )

    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    image_url = captured["body"]["messages"][0]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")
    assert result["validator"]["accepted"] is True
    assert result["decision"] == "replace_candidate"
    assert result["provider"] == "example.test"


def test_escalation_calls_stronger_model_only_for_unresolved_review(monkeypatch):
    calls = []

    def fake_review(_image, _mime, _candidate, _context, model_override=None):
        calls.append(model_override)
        if model_override:
            return {
                "model": model_override,
                "decision": "accept_candidate",
                "validator": {"accepted": True, "issues": []},
            }
        return {
            "model": "flash",
            "decision": "uncertain",
            "validator": {"accepted": True, "issues": []},
        }

    monkeypatch.setenv("OMR_VISION_ESCALATION_MODEL", "plus")
    monkeypatch.setattr(vision_review, "review_score_region", fake_review)
    result = vision_review.review_score_region_with_escalation(
        png_bytes(), "image/png", {}, {}
    )

    assert calls == [None, "plus"]
    assert result["attemptCount"] == 2
    assert result["final"]["decision"] == "accept_candidate"


def test_stronger_qwen_uses_strict_json_schema():
    config = vision_review.VisionConfig(
        "key", "https://example.test/v1", "qwen3.7-plus", "chat", 30
    )

    body = vision_review._request_body(config, "JSON please", "data:image/png;base64,AA==")

    assert body["enable_thinking"] is False
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True


def test_enhanced_pdf_review_uses_the_matching_rendered_page(tmp_path, monkeypatch):
    sample = (
        Path(__file__).resolve().parents[1]
        / "data" / "external" / "sposobin-shte" / "SHTE_V1"
        / "hamony dataset" / "ch4" / "original" / "ch4-01_a minor.xml"
    )
    page_one = tmp_path / "page-1.png"
    page_two = tmp_path / "page-2.png"
    Image.new("RGB", (240, 120), "white").save(page_one)
    Image.new("RGB", (320, 160), "white").save(page_two)

    def fake_transcribe(_source, _output):
        page_one_positions = [{
            "page": 1, "centerX": 0.5, "centerY": 0.5,
            "width": 0.8, "height": 0.4,
        }]
        page_two_positions = [{
            "page": 2, "centerX": 0.5, "centerY": 0.5,
            "width": 0.8, "height": 0.4,
        }]
        return {
            "engine": "homr+pymupdf",
            "exportedPath": str(sample),
            "staffPositions": page_one_positions + page_two_positions,
            "pages": [
                {
                    "page": 1, "imagePath": str(page_one), "measureCount": 1,
                    "staffPositions": page_one_positions,
                },
                {
                    "page": 2, "imagePath": str(page_two), "measureCount": 99,
                    "staffPositions": page_two_positions,
                },
            ],
        }

    monkeypatch.setattr(server, "transcribe_with_audiveris", fake_transcribe)
    monkeypatch.setattr(
        server, "select_review_measures", lambda _audit, _maximum, _pages: [2]
    )
    monkeypatch.setattr(server, "review_score_region_with_escalation", lambda *_args: {
        "attemptCount": 1,
        "attempts": [],
        "final": {"decision": "accept_candidate", "corrections": []},
    })
    monkeypatch.setattr(server, "OMR_REVIEW_ROOT", tmp_path / "runs")

    response = client.post(
        "/api/omr/enhanced-parse",
        files={"file": ("score.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"useVision": "true", "maxRegions": "1"},
    )

    assert response.status_code == 200
    region = response.json()["omr"]["vision"]["reviewedRegions"][0]
    assert region["measure"] == 2
    assert region["crop"]["page"] == 2
    assert region["crop"]["localMeasure"] == 1
    assert region["crop"]["previousSystemContext"]["included"] is True
    assert region["crop"]["previousSystemContext"]["contextSystemIndex"] == 0
    assert region["candidate"]["measure"] == 2
    assert region["candidate"]["parts"]
    assert response.json()["omr"]["recognitionConfidence"]["status"] == "unavailable"
    assert response.json()["omr"]["transcriptionReadiness"]["status"] == "needs-review"
    assert response.json()["endToEnd"]["status"] == "review-required"
    assert response.json()["endToEnd"]["stage"] == "recognition"
    assert all(
        not mode["eligible"]
        for mode in response.json()["solverEligibility"].values()
    )
