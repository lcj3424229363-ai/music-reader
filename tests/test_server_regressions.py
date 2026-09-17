from fastapi.testclient import TestClient

import omr
import server


client = TestClient(server.app)


def test_all_routes_are_registered_when_server_module_finishes_loading():
    paths = {getattr(route, "path", None) for route in server.app.routes}
    assert "/api/explain" in paths
    assert "/agent/explain" in paths
    assert "/agent/trace/{trace_id}" in paths


def test_trace_ids_cannot_escape_trace_directory():
    assert client.get("/agent/trace/valid-id_1").json()["found"] is False
    assert client.get("/agent/trace/%2e%2e%5cescape").status_code in (200, 404)
    assert server._safe_upload_name("../outside.xml", ".xml") == "outside.xml"
    assert server._safe_upload_name(r"..\outside.xml", ".xml") == "outside.xml"


def test_bad_time_signature_has_stable_public_error():
    response = client.post(
        "/solve-melody",
        json={
            "key": "C",
            "timeSignature": "x",
            "melodyEntries": [{"step": "C", "octave": 4, "duration": "4"}],
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["errorCode"] == "BAD_TIME_SIGNATURE"
    assert "not enough values" not in " ".join(payload["warnings"])


def test_native_musicxml_is_not_routed_through_omr():
    assert ".xml" not in omr.SUPPORTED_OMR_EXTENSIONS
    assert ".musicxml" not in omr.SUPPORTED_OMR_EXTENSIONS


def test_uploaded_source_path_is_removed():
    payload = {"source": {"fileName": "score.xml", "path": r"C:\temp\score.xml"}}
    assert "path" not in server._remove_source_path(payload)["source"]


def test_frontend_only_labels_solver_output_as_a_rule_guided_draft():
    source = (server.CURRENT_DIR / "web" / "app.js").read_text(encoding="utf-8")
    assert "已生成规则草案" in source
    assert "这不是严格批改结果" in source
