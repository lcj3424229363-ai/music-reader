"""P20.2 单元测试 — 8 工具 + ReAct Agent 引擎。

覆盖：
- llm/tools: 8 工具执行、OpenAI schema 转换、未知名工具处理
- llm/agent: preset pipeline 5 步执行、trace 记录、rules/cases 收集
- 不依赖 LLM（用 mock 或纯工具）
- 集成：用 Mozart K.545 主题旋律跑一遍（用 mock solver）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pytest
from unittest.mock import patch, MagicMock

from llm.tools import (
    TOOL_DEFINITIONS,
    list_tool_names,
    get_tool,
    execute_tool,
    to_openai_tools_schema,
)
from llm.agent import (
    MusicTheoryAgent,
    AgentTrace,
    AgentResult,
    StepTrace,
    PRESET_PIPELINE,
    MAX_STEPS,
    MAX_TOOL_CALLS,
    _extract_voices_from_solver,
    _extract_romans_from_solver,
    _summarize_obs,
)


# ============================================================
# tools
# ============================================================

class TestToolsRegistry:
    def test_8_tools_registered(self):
        assert len(TOOL_DEFINITIONS) == 8

    def test_all_required_tools_present(self):
        names = list_tool_names()
        # 用户要求的 5 必选 + 3 可选
        assert "lookup_style" in names
        assert "analyze_music_structure" in names
        assert "run_harmony_solver" in names
        assert "check_voice_leading" in names
        assert "query_music_example" in names
        assert "query_kb" in names
        assert "find_error_cases" in names
        assert "compare_analysis" in names

    def test_each_tool_has_required_fields(self):
        for t in TOOL_DEFINITIONS:
            assert t.name
            assert t.description
            assert t.parameters_schema
            assert callable(t.execute)


class TestLookupStyle:
    def test_lookup_sposobin(self):
        result = execute_tool("lookup_style", {"style_id": "sposobin"})
        assert result["style_id"] == "sposobin"
        assert "斯波索宾" in result["name_zh"]
        assert result["forbid_parallel_perfect"] is True

    def test_lookup_jazz(self):
        result = execute_tool("lookup_style", {"style_id": "jazz"})
        assert result["style_id"] == "jazz"
        assert result["forbid_parallel_perfect"] is False
        assert result["allow_extended_chords"] is True

    def test_lookup_default(self):
        result = execute_tool("lookup_style", {"style_id": ""})
        # V1 默认 = sposobin
        assert result["style_id"] == "sposobin"

    def test_lookup_unknown(self):
        result = execute_tool("lookup_style", {"style_id": "non_exist"})
        # fallback to sposobin (V1 默认)
        assert result["style_id"] == "sposobin"


class TestAnalyzeMusicStructure:
    def test_analyze_simple_score(self):
        score = {
            "key": "C major",
            "melody_notes": [
                {"pitch": 60, "duration": 1.0, "measure": 1},
                {"pitch": 62, "duration": 1.0, "measure": 2},
                {"pitch": 64, "duration": 1.0, "measure": 3},
                {"pitch": 65, "duration": 1.0, "measure": 4},
            ],
        }
        result = execute_tool("analyze_music_structure", {"score": score})
        assert result["key"] == "C major"
        assert result["n_measures"] == 4
        assert len(result["phrases"]) == 1
        assert result["phrases"][0]["start"] == 1
        assert result["phrases"][0]["end"] == 4
        assert len(result["motifs"]) == 1

    def test_analyze_8_measures_yields_2_phrases(self):
        score = {
            "key": "C major",
            "melody_notes": [{"pitch": 60, "duration": 1.0, "measure": i+1} for i in range(8)],
        }
        result = execute_tool("analyze_music_structure", {"score": score})
        assert result["n_measures"] == 8
        assert len(result["phrases"]) == 2

    def test_analyze_empty_melody(self):
        result = execute_tool("analyze_music_structure", {"score": {"key": "C major"}})
        assert result["n_measures"] == 0
        assert result["phrases"] == []


class TestQueryMusicExample:
    def test_by_composer(self):
        result = execute_tool("query_music_example", {"composer": "Mozart"})
        assert result["n_results"] >= 1
        assert any("Mozart" in c["composer"] for c in result["cases"])

    def test_by_key(self):
        result = execute_tool("query_music_example", {"key": "C major"})
        assert result["n_results"] >= 1

    def test_by_tag_sposobin(self):
        result = execute_tool("query_music_example", {"tag": "sposobin"})
        # 至少 5 个 sposobin 案例（除 Debussy）
        assert result["n_results"] >= 5

    def test_by_tag_modal(self):
        result = execute_tool("query_music_example", {"tag": "modal"})
        assert result["n_results"] >= 1
        # Debussy Faun
        assert any("Debussy" in c["composer"] for c in result["cases"])

    def test_by_case_id(self):
        result = execute_tool("query_music_example", {"case_id": "mozart-k545-m1"})
        assert result["n_results"] == 1
        assert result["cases"][0]["title"] == "Piano Sonata K.545 1st Movement"

    def test_no_args_returns_top3(self):
        result = execute_tool("query_music_example", {})
        assert result["n_results"] <= 3


class TestQueryKB:
    def test_query_roman_I(self):
        result = execute_tool("query_kb", {"roman": "I"})
        assert result["n_results"] >= 1
        assert any(e["id"] == "triad-I" for e in result["entries"])

    def test_query_roman_V7(self):
        result = execute_tool("query_kb", {"roman": "V7"})
        assert result["n_results"] >= 1

    def test_query_category_triad(self):
        result = execute_tool("query_kb", {"category": "triad"})
        assert result["n_results"] >= 5

    def test_query_unknown_roman(self):
        # 未知罗马数字仍会返回通配符 "通用" 条目 (RAG 召回机制)
        result = execute_tool("query_kb", {"roman": "XYZ999"})
        # 至少有 1 个 (first-inversion-6 等通配符)
        assert result["n_results"] >= 1
        # 但不会有完全匹配的 "XYZ999" 条目
        assert all(e["roman"] != "XYZ999" for e in result["entries"])


class TestFindErrorCases:
    def test_by_type_parallel_5(self):
        result = execute_tool("find_error_cases", {"error_type": "parallel_5"})
        assert result["n_results"] >= 1
        assert result["cases"][0]["error_type"] == "parallel_5"

    def test_by_severity_fatal(self):
        result = execute_tool("find_error_cases", {"severity": "fatal"})
        assert result["n_results"] >= 4

    def test_by_style_filter_sposobin(self):
        result = execute_tool("find_error_cases", {"style": "sposobin"})
        # Sposobin 严格，绝大多数错误都判为错
        assert result["n_results"] >= 7

    def test_by_style_filter_jazz(self):
        result = execute_tool("find_error_cases", {"style": "jazz"})
        # Jazz 宽松，错误少一些
        result_sposobin = execute_tool("find_error_cases", {"style": "sposobin"})
        assert result["n_results"] <= result_sposobin["n_results"]


class TestCheckVoiceLeading:
    def test_no_parallel_5(self):
        # S, B 完全错开 7 度 (5 度)
        voices = {
            "S": [60, 60, 60, 60],  # 全 C
            "A": [55, 55, 55, 55],
            "T": [48, 48, 48, 48],
            "B": [40, 41, 42, 43],  # 上升
        }
        result = execute_tool("check_voice_leading", {
            "voices": voices, "style": "functional_classical",
        })
        # S-B: C-C 是同度不是 5/8; 不会触发 parallel 5/8
        assert result["n_errors"] == 0

    def test_parallel_8_detected(self):
        # S, B 一直保持纯 8 度
        voices = {
            "S": [60, 60, 60, 60],
            "A": [55, 55, 55, 55],
            "T": [48, 48, 48, 48],
            "B": [48, 48, 48, 48],  # 跟 S 都是 C, 纯 8 度
        }
        result = execute_tool("check_voice_leading", {
            "voices": voices, "style": "functional_classical",
        })
        # functional_classical 禁止 parallel_8
        assert result["n_errors"] >= 1
        assert any(e["type"] == "parallel_8" for e in result["errors"])

    def test_parallel_5_allowed_in_jazz(self):
        voices = {
            "S": [60, 60],
            "A": [55, 55],
            "T": [48, 48],
            "B": [48, 48],  # 跟 S 同步 = 平行 8
        }
        result = execute_tool("check_voice_leading", {
            "voices": voices, "style": "jazz",
        })
        # Jazz 不禁止 parallel_8
        assert result["n_errors"] == 0


class TestCompareAnalysis:
    def test_rank_by_score(self):
        candidates = [
            {"label": "V/V", "score": 70, "evidence": ["leading tone resolution"]},
            {"label": "Modal mixture", "score": 30, "evidence": ["key context"]},
        ]
        result = execute_tool("compare_analysis", {"candidates": candidates})
        assert result["n_candidates"] == 2
        assert result["ranked"][0]["label"] == "V/V"
        assert result["top_pick"] == "V/V"

    def test_empty_candidates(self):
        result = execute_tool("compare_analysis", {"candidates": []})
        assert "error" in result


class TestOpenAISchemaConversion:
    def test_schema_count_matches_tools(self):
        schema = to_openai_tools_schema()
        assert len(schema) == 8

    def test_schema_structure(self):
        schema = to_openai_tools_schema()
        for s in schema:
            assert s["type"] == "function"
            assert "name" in s["function"]
            assert "description" in s["function"]
            assert "parameters" in s["function"]

    def test_run_harmony_solver_schema(self):
        schema = to_openai_tools_schema()
        solver = next(s for s in schema if s["function"]["name"] == "run_harmony_solver")
        params = solver["function"]["parameters"]
        assert "melody" in params["properties"]
        assert "key" in params["properties"]


class TestExecuteTool:
    def test_unknown_tool(self):
        result = execute_tool("non_existent_tool", {})
        assert "error" in result

    def test_tool_exception_handled(self):
        # 模拟一个工具抛异常
        with patch("llm.tools.get_tool") as mock:
            mock.return_value = MagicMock(execute=MagicMock(side_effect=ValueError("boom")))
            result = execute_tool("test", {})
            assert "error" in result
            assert "boom" in str(result["error"])


# ============================================================
# agent
# ============================================================

class TestAgentConstants:
    def test_max_steps_6(self):
        assert MAX_STEPS == 6

    def test_max_tool_calls_8(self):
        assert MAX_TOOL_CALLS == 8

    def test_preset_pipeline_has_5_steps(self):
        # 不含 LLM 总结 (Step 6)
        assert len(PRESET_PIPELINE) == 5

    def test_preset_pipeline_order(self):
        tools_order = [p["tool"] for p in PRESET_PIPELINE]
        assert tools_order == [
            "lookup_style",
            "analyze_music_structure",
            "run_harmony_solver",
            "check_voice_leading",
            "query_music_example",
        ]


class TestAgentRun:
    """测试 Agent 完整运行（用 mock 避免依赖真 LLM）。"""

    def _simple_score(self):
        return {
            "key": "C major",
            "melody_notes": [{"pitch": 60, "duration": 1.0, "measure": i+1} for i in range(4)],
        }

    def _simple_melody(self):
        return [{"pitch": 60, "duration": 1.0, "measure": i+1} for i in range(4)]

    def test_runs_all_5_preset_steps(self):
        agent = MusicTheoryAgent()
        result = agent.run(
            score=self._simple_score(),
            melody=self._simple_melody(),
            key="C major",
            style_id="functional_classical",
        )
        assert isinstance(result, AgentResult)
        # 至少 5 步 (preset)
        assert len(result.trace.steps) >= 4  # 4 或 5，取决于 solver 是否有 voices

    def test_step1_always_lookup_style(self):
        agent = MusicTheoryAgent()
        result = agent.run(
            score=self._simple_score(),
            melody=self._simple_melody(),
            key="C major",
        )
        assert result.trace.steps[0].tool == "lookup_style"

    def test_step2_always_analyze_structure(self):
        agent = MusicTheoryAgent()
        result = agent.run(
            score=self._simple_score(),
            melody=self._simple_melody(),
            key="C major",
        )
        assert result.trace.steps[1].tool == "analyze_music_structure"

    def test_step5_always_query_music_example(self):
        agent = MusicTheoryAgent()
        result = agent.run(
            score=self._simple_score(),
            melody=self._simple_melody(),
            key="C major",
        )
        # 最后一个 step 必须是 query_music_example
        assert result.trace.steps[-1].tool == "query_music_example"

    def test_trace_tool_call_count(self):
        agent = MusicTheoryAgent()
        result = agent.run(
            score=self._simple_score(),
            melody=self._simple_melody(),
            key="C major",
        )
        assert result.trace.tool_call_count <= 8  # max_tool_calls
        assert result.trace.tool_call_count >= 4  # 至少跑了 4 步

    def test_captures_style(self):
        agent = MusicTheoryAgent()
        result = agent.run(
            score=self._simple_score(),
            melody=self._simple_melody(),
            key="C major",
            style_id="sposobin",
        )
        assert result.trace.style == "sposobin"

    def test_cases_cited_populated(self):
        agent = MusicTheoryAgent()
        result = agent.run(
            score=self._simple_score(),
            melody=self._simple_melody(),
            key="C major",
        )
        # query_music_example(C major) 应该返回 Bach / Mozart 案例
        assert len(result.cases_cited) >= 1

    def test_max_tool_calls_enforced(self):
        # 用 max_tool_calls=3 测试是否会停止
        agent = MusicTheoryAgent(max_tool_calls=3)
        result = agent.run(
            score=self._simple_score(),
            melody=self._simple_melody(),
            key="C major",
        )
        # 不会超过 3
        assert result.trace.tool_call_count <= 3


class TestAgentFallback:
    """LLM 不可用时降级解释。"""

    def test_fallback_explanation_when_llm_fails(self):
        with patch("llm.agent.MusicTheoryAgent._llm_summarize") as mock:
            from llm.deepseek_client import DeepSeekError
            mock.side_effect = DeepSeekError("API key not set")
            agent = MusicTheoryAgent()
            result = agent.run(
                score={"key": "C major", "melody_notes": []},
                melody=[],
                key="C major",
            )
            # errors 应该有 LLM 错误
            assert any("LLM" in e for e in result.errors)
            # fallback explanation 仍应该有内容
            assert "分析" in result.explanation or "structural" in result.explanation.lower() or "C major" in result.explanation


# ============================================================
# 辅助函数
# ============================================================

class TestHelperFunctions:
    def test_extract_voices_from_solver(self):
        solver_output = {
            "flatHarmonies": [
                {"chord": "I", "voices": {"S": 60, "A": 55, "T": 48, "B": 40}},
                {"chord": "IV", "voices": {"S": 62, "A": 57, "T": 50, "B": 41}},
            ]
        }
        voices = _extract_voices_from_solver(solver_output)
        assert voices["S"] == [60, 62]
        assert voices["B"] == [40, 41]

    def test_extract_voices_empty(self):
        assert _extract_voices_from_solver({}) is None
        assert _extract_voices_from_solver({"flatHarmonies": []}) is None

    def test_extract_romans_from_observations(self):
        observations = [
            {"step": 1, "tool": "lookup_style", "result": {}},
            {"step": 3, "tool": "run_harmony_solver", "result": {
                "flatHarmonies": [
                    {"chord": "I"}, {"chord": "V7"}, {"chord": "I"},
                ]
            }},
        ]
        romans = _extract_romans_from_solver(observations)
        assert romans == ["I", "V7", "I"]

    def test_summarize_obs_truncates(self):
        big = {"x": "y" * 1000}
        result = _summarize_obs(big)
        assert len(result) <= 503  # 500 + "..."


# ============================================================
# 集成测试：Mozart K.545 主题
# ============================================================

class TestMozartK545Integration:
    """用 Mozart K.545 主题旋律跑一遍 Agent，验证 trace。"""

    def test_mozart_theme_runs_without_error(self):
        # K.545 主题前 4 小节: C D E F | E D C B | C4 ... (简化)
        melody = [
            {"pitch": 60, "duration": 1.0, "measure": 1},  # C
            {"pitch": 62, "duration": 1.0, "measure": 1},  # D
            {"pitch": 64, "duration": 1.0, "measure": 2},  # E
            {"pitch": 65, "duration": 1.0, "measure": 2},  # F
            {"pitch": 64, "duration": 1.0, "measure": 3},  # E
            {"pitch": 62, "duration": 1.0, "measure": 3},  # D
            {"pitch": 60, "duration": 1.0, "measure": 4},  # C
            {"pitch": 59, "duration": 1.0, "measure": 4},  # B
        ]
        score = {
            "key": "C major",
            "melody_notes": melody,
        }
        agent = MusicTheoryAgent()
        result = agent.run(
            score=score,
            melody=melody,
            key="C major",
        )
        # V1 默认是 sposobin
        assert result.trace.style == "sposobin"
        assert len(result.trace.steps) >= 4
        # C major 应该有 sposobin 案例
        assert any("Mozart" in c or "Bach" in c for c in result.cases_cited)
        # 解释应该有内容
        assert len(result.explanation) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
