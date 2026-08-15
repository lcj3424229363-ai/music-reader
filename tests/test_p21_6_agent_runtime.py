"""P21.6: Agent Runtime Layer — server endpoint + trace 落盘 + 错误降级。

覆盖范围（不重复 P20 test_p20_2_agent.py 的工具 / pipeline / helpers）:
- POST /agent/explain 入参 / 返回 shape / 错误降级
- GET /agent/trace/{id} 200 + 404
- trace 落盘 (_save_trace 行为)
- trace 防重写
- trace_id UUID 格式
- 空 melody 拒绝
- 内部异常 → 200 safe response
- 集成: 不依赖 LLM (mock MusicTheoryAgent)
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# server.py 用相对路径: 必须在项目根目录跑
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def client():
    """FastAPI TestClient 包装 server.app.

    用 TestClient 避免启动真实 uvicorn; trace 落盘走 tmp_path 隔离.
    """
    from fastapi.testclient import TestClient
    from server import app
    return TestClient(app)


@pytest.fixture
def isolated_traces(monkeypatch, tmp_path):
    """隔离 trace 落盘目录到 tmp_path，不污染 data/agent_traces/.

    monkeypatch server.AGENT_TRACES_DIR + 同时改 _save_trace/_load_trace
    内部的 path 解析（用 module reference 替换）.
    """
    import server
    monkeypatch.setattr(server, "AGENT_TRACES_DIR", tmp_path)
    return tmp_path


# ============================================================
# /agent/explain endpoint — basic shape
# ============================================================

class TestAgentExplainBasic:
    """基本入参 + 返回 shape 测试 (mock LLM, 走 dry-run)"""

    def test_post_returns_200(self, client, isolated_traces):
        """POST /agent/explain → 200 OK."""
        with patch("server.MusicTheoryAgent") as mock_cls:
            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.explanation = "test explanation"
            mock_result.rules_used = ["I", "V7"]
            mock_result.cases_cited = ["Bach WTC I (BWV 846)"]
            mock_result.errors = []
            mock_result.trace.to_dict.return_value = {
                "style": "sposobin",
                "n_steps": 5,
                "tool_call_count": 5,
                "steps": [],
                "final_explanation": "test explanation",
            }
            mock_agent.run.return_value = mock_result
            mock_cls.return_value = mock_agent

            resp = client.post("/agent/explain", json={
                "score": {"key": "C major"},
                "melody": [{"pitch": 60, "duration": 1.0, "measure": 1}],
                "key": "C major",
            })
            assert resp.status_code == 200

    def test_response_shape(self, client, isolated_traces):
        """返回字段: traceId, agentAvailable, explanation, trace, rulesUsed, casesCited, errors."""
        with patch("server.MusicTheoryAgent") as mock_cls:
            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.explanation = "exp"
            mock_result.rules_used = ["rule1"]
            mock_result.cases_cited = ["case1"]
            mock_result.errors = []
            mock_result.trace.to_dict.return_value = {
                "style": "sposobin", "n_steps": 5, "tool_call_count": 5,
                "steps": [], "final_explanation": "exp",
            }
            mock_agent.run.return_value = mock_result
            mock_cls.return_value = mock_agent

            resp = client.post("/agent/explain", json={
                "score": {}, "melody": [{"pitch": 60}], "key": "C major",
            })
            data = resp.json()
            assert "traceId" in data
            assert "agentAvailable" in data
            assert "explanation" in data
            assert "trace" in data
            assert "rulesUsed" in data
            assert "casesCited" in data
            assert "errors" in data

    def test_trace_id_is_uuid4(self, client, isolated_traces):
        """traceId 默认生成 UUID4."""
        with patch("server.MusicTheoryAgent") as mock_cls:
            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.explanation = ""
            mock_result.rules_used = []
            mock_result.cases_cited = []
            mock_result.errors = []
            mock_result.trace.to_dict.return_value = {"style": "sposobin", "n_steps": 0, "tool_call_count": 0, "steps": []}
            mock_agent.run.return_value = mock_result
            mock_cls.return_value = mock_agent

            resp = client.post("/agent/explain", json={
                "score": {}, "melody": [{"pitch": 60}], "key": "C major",
            })
            data = resp.json()
            uuid4_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
            assert uuid4_pattern.match(data["traceId"]), f"traceId 不是 UUID4: {data['traceId']}"

    def test_custom_trace_id_respected(self, client, isolated_traces):
        """客户端传 traceId 时，endpoint 不覆盖."""
        custom_id = "my-trace-001"
        with patch("server.MusicTheoryAgent") as mock_cls:
            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.explanation = ""
            mock_result.rules_used = []
            mock_result.cases_cited = []
            mock_result.errors = []
            mock_result.trace.to_dict.return_value = {"style": "sposobin", "n_steps": 0, "tool_call_count": 0, "steps": []}
            mock_agent.run.return_value = mock_result
            mock_cls.return_value = mock_agent

            resp = client.post("/agent/explain", json={
                "score": {}, "melody": [{"pitch": 60}], "key": "C major",
                "traceId": custom_id,
            })
            data = resp.json()
            assert data["traceId"] == custom_id


# ============================================================
# /agent/explain — 错误降级
# ============================================================

class TestAgentExplainErrorHandling:
    """错误降级: 任何异常都返回 200 + safe response"""

    def test_llm_unavailable_returns_safe(self, client, monkeypatch):
        """llm 模块未加载时, agentAvailable=False + errors 提示."""
        import server
        monkeypatch.setattr(server, "_LLM_AVAILABLE", False)
        monkeypatch.setattr(server, "MusicTheoryAgent", None)

        resp = client.post("/agent/explain", json={
            "score": {}, "melody": [{"pitch": 60}], "key": "C major",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["agentAvailable"] is False
        assert len(data["errors"]) > 0
        assert "未启用" in data["errors"][0] or "失败" in data["errors"][0]
        assert data["explanation"] == ""

    def test_empty_melody_rejected(self, client):
        """空 melody → 200 + errors 提示 (P19 同款不抛 4xx)."""
        with patch("server.MusicTheoryAgent") as mock_cls:
            resp = client.post("/agent/explain", json={
                "score": {}, "melody": [], "key": "C major",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "melody" in str(data["errors"]) or "需要" in str(data["errors"])

    def test_deepseek_error_returns_safe(self, client, isolated_traces):
        """DeepSeekError 抛出 → 200 + safe response, traceId 仍返回."""
        from llm import DeepSeekError
        with patch("server.MusicTheoryAgent") as mock_cls:
            mock_agent = MagicMock()
            mock_agent.run.side_effect = DeepSeekError("rate limit exceeded")
            mock_cls.return_value = mock_agent

            resp = client.post("/agent/explain", json={
                "score": {}, "melody": [{"pitch": 60}], "key": "C major",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["agentAvailable"] is True
            assert "暂时不可用" in data["errors"][0]
            # traceId 仍要返回（即使 agent 失败，前端可能要拿来 debug）
            assert data["traceId"] is not None

    def test_unexpected_exception_returns_safe(self, client, isolated_traces):
        """任意 Exception → 200 + safe response (不暴露堆栈 / type name)."""
        with patch("server.MusicTheoryAgent") as mock_cls:
            mock_agent = MagicMock()
            mock_agent.run.side_effect = RuntimeError("internal bug with secret data")
            mock_cls.return_value = mock_agent

            resp = client.post("/agent/explain", json={
                "score": {}, "melody": [{"pitch": 60}], "key": "C major",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "内部错误" in data["errors"][0] or "稍后" in data["errors"][0]
            # 不暴露 "RuntimeError" 类型名 / "internal bug" 内部细节 / secret data
            assert "RuntimeError" not in data["errors"][0]
            assert "internal bug" not in data["errors"][0]
            assert "secret data" not in data["errors"][0]

    def test_request_validation_422(self, client):
        """缺 melody 字段 → FastAPI 422 (schema 校验, 不是我们的 200 兜底)."""
        # Pydantic melody 字段有默认值 []，不会触发 422.
        # 改成用 styleId 类型错误触发 422:
        resp = client.post("/agent/explain", json={
            "score": {}, "key": "C major", "styleId": 12345,  # 应该是 string
        })
        assert resp.status_code == 422


# ============================================================
# /agent/trace/{id} endpoint
# ============================================================

class TestAgentTraceGet:
    """trace 读取 + 404 行为"""

    def test_get_existing_trace(self, client, isolated_traces):
        """GET /agent/trace/{id} → 200 + trace JSON."""
        import server
        trace_id = "test-trace-001"
        server._save_trace(trace_id, {
            "traceId": trace_id,
            "explanation": "saved explanation",
            "trace": {"style": "sposobin", "steps": []},
        })
        resp = client.get(f"/agent/trace/{trace_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["traceId"] == trace_id
        assert data["explanation"] == "saved explanation"

    def test_get_nonexistent_trace_returns_not_found(self, client, isolated_traces):
        """GET /agent/trace/{不存在的id} → 200 + found=False (P19 同款不抛 404)."""
        resp = client.get("/agent/trace/nonexistent-id-xyz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is False
        assert "不存在" in data["error"] or "失败" in data["error"]

    def test_get_then_post_round_trip(self, client, isolated_traces):
        """POST 后 GET 能读回 (落盘 + 读取 round-trip)."""
        with patch("server.MusicTheoryAgent") as mock_cls:
            mock_agent = MagicMock()
            mock_result = MagicMock()
            mock_result.explanation = "round-trip exp"
            mock_result.rules_used = ["I"]
            mock_result.cases_cited = []
            mock_result.errors = []
            mock_result.trace.to_dict.return_value = {
                "style": "sposobin", "n_steps": 5, "tool_call_count": 5,
                "steps": [{"step": 1, "tool": "lookup_style"}],
                "final_explanation": "round-trip exp",
            }
            mock_agent.run.return_value = mock_result
            mock_cls.return_value = mock_agent

            # POST
            post_resp = client.post("/agent/explain", json={
                "score": {}, "melody": [{"pitch": 60}], "key": "C major",
            })
            trace_id = post_resp.json()["traceId"]

            # GET
            get_resp = client.get(f"/agent/trace/{trace_id}")
            assert get_resp.json()["found"] is True
            assert get_resp.json()["explanation"] == "round-trip exp"
            assert get_resp.json()["rulesUsed"] == ["I"]
            assert len(get_resp.json()["trace"]["steps"]) == 1


# ============================================================
# _save_trace / _load_trace 行为
# ============================================================

class TestSaveLoadTrace:
    """trace 落盘 / 防重写 / IO 错误处理"""

    def test_save_creates_file(self, isolated_traces):
        """_save_trace 创建文件, 返回 True."""
        import server
        result = server._save_trace("test-001", {"foo": "bar"})
        assert result is True
        path = isolated_traces / "test-001.json"
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8")) == {"foo": "bar"}

    def test_save_does_not_overwrite(self, isolated_traces):
        """_save_trace 防重写: 同 trace_id 第二次返回 False, 文件不变."""
        import server
        server._save_trace("test-002", {"version": 1})
        result = server._save_trace("test-002", {"version": 2})
        assert result is False
        path = isolated_traces / "test-002.json"
        assert json.loads(path.read_text(encoding="utf-8")) == {"version": 1}

    def test_save_creates_dir_if_missing(self, tmp_path):
        """目录不存在时, _save_trace 自动创建."""
        import server
        nested = tmp_path / "deep" / "nested" / "traces"
        assert not nested.exists()
        # 直接 monkeypatch AGENT_TRACES_DIR 后调用
        import importlib
        server.AGENT_TRACES_DIR = nested
        try:
            result = server._save_trace("deep-test", {"x": 1})
            assert result is True
            assert nested.exists()
            assert (nested / "deep-test.json").exists()
        finally:
            server.AGENT_TRACES_DIR = tmp_path  # restore

    def test_save_atomic_write_no_leftover_tmp(self, isolated_traces):
        """原子写不留 .tmp 文件."""
        import server
        server._save_trace("test-atomic", {"a": 1})
        # 不应该有 .tmp 文件残留
        tmp_files = list(isolated_traces.glob("*.json.tmp"))
        assert tmp_files == [], f"残留 .tmp: {tmp_files}"

    def test_load_existing(self, isolated_traces):
        """_load_trace 读已存在文件."""
        import server
        server._save_trace("test-load", {"data": 123})
        loaded = server._load_trace("test-load")
        assert loaded == {"data": 123}

    def test_load_nonexistent_returns_none(self, isolated_traces):
        """_load_trace 读不存在文件 → None."""
        import server
        loaded = server._load_trace("nonexistent-id")
        assert loaded is None

    def test_load_corrupt_json_returns_none(self, isolated_traces):
        """_load_trace 读损坏 JSON → None (不抛)."""
        import server
        bad_path = isolated_traces / "corrupt.json"
        bad_path.write_text("{not valid json", encoding="utf-8")
        loaded = server._load_trace("corrupt")
        assert loaded is None


# ============================================================
# AgentResult.to_dict() 序列化完整 (P20 测过 to_dict 基础, 这里测 P21.6 集成形状)
# ============================================================

class TestAgentResultSerialization:
    """AgentResult.to_dict() 序列化 + JSON 兼容性."""

    def test_to_dict_contains_all_fields(self):
        """AgentResult.to_dict() 含 explanation/trace/rulesUsed/casesCited/errors."""
        from llm.agent import AgentResult, AgentTrace, StepTrace
        trace = AgentTrace(style="sposobin")
        trace.steps.append(StepTrace(step=1, tool="lookup_style", args={"x": 1}, observation={"y": 2}))
        trace.tool_call_count = 1
        trace.final_explanation = "final"
        result = AgentResult(
            explanation="exp",
            trace=trace,
            rules_used=["I", "V7"],
            cases_cited=["Bach"],
            errors=[],
        )
        d = result.trace.to_dict()
        assert d["style"] == "sposobin"
        assert d["n_steps"] == 1
        assert d["tool_call_count"] == 1
        assert d["final_explanation"] == "final"
        assert len(d["steps"]) == 1
        # AgentResult 本身没有 to_dict, 但所有字段可独立序列化
        assert result.explanation == "exp"
        assert result.rules_used == ["I", "V7"]
        assert result.cases_cited == ["Bach"]
        assert result.errors == []

    def test_to_dict_json_round_trip(self):
        """to_dict() → JSON 序列化 → 反序列化不丢信息."""
        from llm.agent import AgentResult, AgentTrace, StepTrace
        trace = AgentTrace(style="sposobin")
        trace.steps.append(StepTrace(
            step=2, tool="analyze_music_structure",
            args={"score": {"key": "C"}}, observation={"n_measures": 4},
        ))
        trace.tool_call_count = 1
        result = AgentResult(
            explanation="json test", trace=trace,
            rules_used=["I"], cases_cited=[], errors=["warn1"],
        )
        # trace.to_dict() 走 JSON
        d = result.trace.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        loaded = json.loads(json_str)
        assert loaded["style"] == "sposobin"
        assert loaded["n_steps"] == 1
        assert loaded["steps"][0]["tool"] == "analyze_music_structure"
        assert loaded["steps"][0]["observation"]["n_measures"] == 4


# ============================================================
# 集成: agent.run() 真跑 (不 mock) — 走 fallback 路径
# ============================================================

class TestAgentRunFallback:
    """端到端: agent.run() 走完 5 步 + 落到 fallback (LLM 不可用).

    这测的是 endpoint 之外的真实 agent 行为, 确保 P21.6 集成没破坏 P21.1-P21.5.
    """

    def test_run_with_no_client_returns_fallback(self):
        """LLM 不可用 → run 仍返回, 走 fallback explanation (5 步 pipeline 跑完)."""
        from llm.agent import MusicTheoryAgent
        from llm import DeepSeekError
        # 强制 _ensure_client 抛 DeepSeekError → agent.run 抓 DeepSeekError → 走 fallback
        agent = MusicTheoryAgent(client=None)
        with patch.object(agent, "_ensure_client", side_effect=DeepSeekError("no api key")):
            result = agent.run(
                score={"key": "C major", "melody_notes": []},
                melody=[{"pitch": 60, "duration": 1.0, "measure": 1}],
                key="C major",
                style_id="sposobin",
                time_signature="4/4",
            )
        # run 仍返回 AgentResult
        assert result.explanation  # fallback explanation 非空
        # pipeline 跑了至少 4 步 (Step 4 check_voice_leading 是条件性的:
        # 需要 solver_voices truthy — 单元测试不构造, 所以跳过)
        assert len(result.trace.steps) >= 4
        # trace 含 errors 或 fallback 解释
        assert result.trace.final_explanation == result.explanation
        # errors 列表记录了 LLM 失败
        assert any("LLM" in e for e in result.errors)
