from fastapi.testclient import TestClient

import server
from score_render import render_answer_svg


client = TestClient(server.app)


SIMPLE_ANSWER = {
    "fourPart": {
        "timeSignature": "4/4",
        "voices": [
            {
                "id": "soprano",
                "measures": [{"number": 1, "entries": [
                    {"kind": "note", "pitches": [{"step": "C", "octave": 5}], "duration": "4"}
                ]}],
            },
            {
                "id": "alto",
                "measures": [{"number": 1, "entries": [
                    {"kind": "note", "pitches": [{"step": "G", "octave": 4}], "duration": "4"}
                ]}],
            },
            {
                "id": "tenor",
                "measures": [{"number": 1, "entries": [
                    {"kind": "note", "pitches": [{"step": "E", "octave": 4}], "duration": "4"}
                ]}],
            },
            {
                "id": "bass",
                "measures": [{"number": 1, "entries": [
                    {"kind": "note", "pitches": [{"step": "C", "octave": 3}], "duration": "4"}
                ]}],
            },
        ],
        "harmonies": [{"measure": 1, "harmonies": [{"romanNumeral": "I"}]}],
    }
}


def test_render_answer_svg_contains_score_markup():
    svg = render_answer_svg(SIMPLE_ANSWER)

    assert svg.startswith("<svg")
    assert "Four-Part Answer" in svg
    assert "<ellipse" in svg


def test_render_answer_png_endpoint_returns_image():
    response = client.post("/api/render/answer.png", json=SIMPLE_ANSWER)

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
