"""ReAct Agent 引擎 — 多步工具调用循环 + preset pipeline。

设计哲学（按用户调整）：
- LLM 自主决策调用哪个工具（function calling）
- 但 system prompt 里**软提示**一个 5 步 preset pipeline：
  1. lookup_style      → 决定风格
  2. analyze_music_structure → 调性/乐句
  3. run_harmony_solver → 罗马数字
  4. check_voice_leading → 声部检查
  5. query_music_example → 类似作品
  最后：LLM 综合总结

约束：
- max_steps=6  (LLM 思考轮数)
- max_tool_calls=8  (工具总调用数，防无限循环)

中间状态：
- AgentTrace 记录每步：Thought / Action / Observation / Citation

工作模式（两档）：
- "preset": 严格按 5 步 pipeline（每步必须用指定工具）
- "free":   LLM 自由选择工具

MVP 阶段只实现 "preset"（最稳）；"free" 留给 P20.4。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from llm.tools import (
    TOOL_DEFINITIONS,
    get_tool,
    execute_tool,
    to_openai_tools_schema,
)
from llm.deepseek_client import DeepSeekClient, DeepSeekConfig, DeepSeekError


# ============================================================
# 常量
# ============================================================

MAX_STEPS = 6
MAX_TOOL_CALLS = 8


# ============================================================
# 5 步 preset pipeline
# ============================================================

PRESET_PIPELINE: list[dict] = [
    {
        "step": 1,
        "tool": "lookup_style",
        "purpose": "决定分析标准",
        "args": {"style_id": "sposobin"},  # V1 默认
    },
    {
        "step": 2,
        "tool": "analyze_music_structure",
        "purpose": "识别调性/乐句/终止/动机",
        "args": {"score": "<<USER_SCORE>>"},
    },
    {
        "step": 3,
        "tool": "run_harmony_solver",
        "purpose": "出 4 部和声 + 罗马数字",
        "args": {"melody": "<<USER_MELODY>>", "key": "<<USER_KEY>>", "style": "sposobin"},
    },
    {
        "step": 4,
        "tool": "check_voice_leading",
        "purpose": "按风格校验声部（斯波索宾严格）",
        "args": {"voices": "<<FROM_SOLVER>>", "style": "sposobin"},
    },
    {
        "step": 5,
        "tool": "query_music_example",
        "purpose": "找类似经典作品（斯波索宾体系内）",
        "args": {"key": "<<USER_KEY>>", "tag": "sposobin"},
    },
    # Step 6 由 LLM 总结
]


# ============================================================
# Agent 中间状态
# ============================================================

@dataclass
class StepTrace:
    """一轮 LLM 思考的完整 trace。"""
    step: int
    tool: str
    args: dict
    observation: dict
    purpose: str = ""


@dataclass
class AgentTrace:
    """完整 Agent 运行 trace。"""
    style: str = "functional_classical"
    steps: list[StepTrace] = field(default_factory=list)
    tool_call_count: int = 0
    final_explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "style": self.style,
            "n_steps": len(self.steps),
            "tool_call_count": self.tool_call_count,
            "steps": [
                {
                    "step": s.step,
                    "tool": s.tool,
                    "args": s.args,
                    "observation": s.observation,
                    "purpose": s.purpose,
                }
                for s in self.steps
            ],
            "final_explanation": self.final_explanation,
        }


# ============================================================
# Agent 引擎
# ============================================================

@dataclass
class AgentResult:
    """Agent 运行的最终结果。"""
    explanation: str
    trace: AgentTrace
    rules_used: list[str] = field(default_factory=list)
    cases_cited: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class MusicTheoryAgent:
    """Music Theory Reasoning Engine 的 ReAct Agent。

    MVP 模式：preset pipeline（5 步固定顺序）。
    不调 LLM 做工具选择（避免幻觉 + 加快响应）。
    最后用 LLM 综合生成 explanation。
    """

    def __init__(
        self,
        client: Optional[DeepSeekClient] = None,
        max_steps: int = MAX_STEPS,
        max_tool_calls: int = MAX_TOOL_CALLS,
    ):
        # client 可为 None —— 运行时检查；如果 None，会走 fallback
        self.client = client
        self.max_steps = max_steps
        self.max_tool_calls = max_tool_calls

    def _ensure_client(self) -> DeepSeekClient:
        """Lazy 创建 client。如果 .env 缺 key 抛 DeepSeekError。"""
        if self.client is None:
            config = DeepSeekConfig.from_env()
            self.client = DeepSeekClient(config=config)
        return self.client

    def run(
        self,
        score: dict,
        melody: list[dict],
        key: str = "C major",
        style_id: str = "sposobin",
        time_signature: str = "4/4",
    ) -> AgentResult:
        """执行 Agent 推理。

        入参:
          score: {"key": "C major", "melody_notes": [...]}
          melody: [{"pitch": 60, "duration": 1.0, "measure": 1}, ...]
          key: 主调
          style_id: 风格 ID
          time_signature: 拍号
        """
        trace = AgentTrace(style=style_id)
        rules_used: list[str] = []
        cases_cited: list[str] = []
        errors: list[str] = []
        collected_observations: list[dict] = []

        # ====== Step 1: lookup_style ======
        if trace.tool_call_count < self.max_tool_calls:
            obs = execute_tool("lookup_style", {"style_id": style_id})
            trace.steps.append(StepTrace(
                step=1, tool="lookup_style",
                args={"style_id": style_id}, observation=obs,
                purpose=PRESET_PIPELINE[0]["purpose"],
            ))
            trace.tool_call_count += 1
            collected_observations.append({"step": 1, "tool": "lookup_style", "result": obs})

        # ====== Step 2: analyze_music_structure ======
        if trace.tool_call_count < self.max_tool_calls:
            obs = execute_tool("analyze_music_structure", {"score": score})
            trace.steps.append(StepTrace(
                step=2, tool="analyze_music_structure",
                args={"score": score}, observation=obs,
                purpose=PRESET_PIPELINE[1]["purpose"],
            ))
            trace.tool_call_count += 1
            collected_observations.append({"step": 2, "tool": "analyze_music_structure", "result": obs})

        # ====== Step 3: run_harmony_solver ======
        solver_voices = None
        if trace.tool_call_count < self.max_tool_calls:
            obs = execute_tool("run_harmony_solver", {
                "melody": melody,
                "key": key,
                "time_signature": time_signature,
                "style": style_id,
            })
            trace.steps.append(StepTrace(
                step=3, tool="run_harmony_solver",
                args={"key": key, "n_notes": len(melody)}, observation=obs,
                purpose=PRESET_PIPELINE[2]["purpose"],
            ))
            trace.tool_call_count += 1
            collected_observations.append({"step": 3, "tool": "run_harmony_solver", "result": obs})

            # 提取 voices 给 Step 4 用
            if "flatHarmonies" in obs and obs["flatHarmonies"]:
                solver_voices = _extract_voices_from_solver(obs)
            elif "voices" in obs:
                solver_voices = obs["voices"]

        # ====== Step 4: check_voice_leading ======
        if trace.tool_call_count < self.max_tool_calls and solver_voices:
            obs = execute_tool("check_voice_leading", {
                "voices": solver_voices,
                "style": style_id,
            })
            trace.steps.append(StepTrace(
                step=4, tool="check_voice_leading",
                args={"style": style_id, "n_measures": obs.get("n_measures_checked", 0)},
                observation=obs,
                purpose=PRESET_PIPELINE[3]["purpose"],
            ))
            trace.tool_call_count += 1
            collected_observations.append({"step": 4, "tool": "check_voice_leading", "result": obs})

        # ====== Step 5: query_music_example ======
        if trace.tool_call_count < self.max_tool_calls:
            obs = execute_tool("query_music_example", {"key": key})
            trace.steps.append(StepTrace(
                step=5, tool="query_music_example",
                args={"key": key}, observation=obs,
                purpose=PRESET_PIPELINE[4]["purpose"],
            ))
            trace.tool_call_count += 1
            collected_observations.append({"step": 5, "tool": "query_music_example", "result": obs})
            # 收集 case 引用
            for c in obs.get("cases", [])[:3]:
                cases_cited.append(f"{c['composer']} {c['title']} ({c['opus']})")

        # ====== 收集 KB 规则（从 solver 输出提取罗马数字，查 KB） ======
        if trace.tool_call_count < self.max_tool_calls:
            romans = _extract_romans_from_solver(collected_observations)
            if romans:
                # 一次查所有
                all_rules = []
                for r in romans[:3]:  # 最多 3 个
                    obs = execute_tool("query_kb", {"roman": r})
                    for e in obs.get("entries", []):
                        all_rules.append(e["id"])
                rules_used = list(set(all_rules))[:10]

        # ====== Step 6: LLM 综合解释 ======
        try:
            explanation = self._llm_summarize(
                style_id=style_id,
                score=score,
                observations=collected_observations,
                cases_cited=cases_cited,
                rules_used=rules_used,
            )
            trace.final_explanation = explanation
        except DeepSeekError as e:
            errors.append(f"LLM error: {e}")
            explanation = self._fallback_explanation(collected_observations, style_id)
            trace.final_explanation = explanation

        return AgentResult(
            explanation=explanation,
            trace=trace,
            rules_used=rules_used,
            cases_cited=cases_cited,
            errors=errors,
        )

    # -------- LLM 总结 --------

    def _llm_summarize(
        self,
        style_id: str,
        score: dict,
        observations: list[dict],
        cases_cited: list[str],
        rules_used: list[str],
    ) -> str:
        """用 LLM 生成最终解释。"""
        from theory.style_profiles import get_profile
        from llm.prompts import build_user_prompt, build_system_prompt
        from theory.style_profiles import style_explainer_prefix

        profile = get_profile(style_id)

        system_prompt = build_system_prompt(
            rules_text=style_explainer_prefix(profile) + "\n\n以下是工具调用结果：\n"
        )

        # 构造 user prompt: 压缩 observations
        obs_text = json.dumps(
            [{"step": o["step"], "tool": o["tool"], "result_summary": _summarize_obs(o["result"])}
             for o in observations],
            ensure_ascii=False, indent=2,
        )
        cases_text = "、".join(cases_cited) if cases_cited else "（无）"
        rules_text = "、".join(rules_used) if rules_used else "（无）"

        user_prompt = (
            f"## 乐曲信息\n主调：{score.get('key', 'C major')}\n\n"
            f"## 工具调用结果\n{obs_text}\n\n"
            f"## 引用案例\n{cases_text}\n\n"
            f"## 引用规则\n{rules_text}\n\n"
            f"请按 {profile.name_zh} 体系，给出教师式中文讲解：\n"
            f"1. 整体结构（调性 / 乐句 / 终止）\n"
            f"2. 和声进行（罗马数字 + 风格判断）\n"
            f"3. 声部进行（按规则评估）\n"
            f"4. 教学建议"
        )

        client = self._ensure_client()
        resp = client.chat(system=system_prompt, user=user_prompt)
        return resp.strip()

    def _fallback_explanation(self, observations: list[dict], style_id: str) -> str:
        """LLM 不可用时的降级解释。"""
        lines = [f"## 分析（{style_id} 体系）", ""]
        for o in observations:
            t = o["tool"]
            r = o["result"]
            if t == "lookup_style":
                lines.append(f"**分析标准**: {r.get('name_zh', '')}")
            elif t == "analyze_music_structure":
                lines.append(f"**结构**: {r.get('n_measures', 0)} 小节, {len(r.get('phrases', []))} 个乐句")
            elif t == "run_harmony_solver":
                if "flatHarmonies" in r:
                    chords = [h.get("chord", "?") for h in r["flatHarmonies"][:8]]
                    lines.append(f"**和声进行**: {', '.join(chords)}")
                elif "error" in r:
                    lines.append(f"**和声**: solver 不可用 - {r['error']}")
            elif t == "check_voice_leading":
                lines.append(f"**声部检查**: {r.get('n_errors', 0)} 个错误")
            elif t == "query_music_example":
                cases = r.get("cases", [])
                if cases:
                    lines.append(f"**类似案例**: {', '.join(c['title'] for c in cases[:3])}")
        return "\n".join(lines)


# ============================================================
# 辅助函数
# ============================================================

def _extract_voices_from_solver(solver_output: dict) -> Optional[dict]:
    """从 solver 输出提取 4 声部 voices。"""
    flat = solver_output.get("flatHarmonies", [])
    if not flat:
        return None
    S, A, T, B = [], [], [], []
    for h in flat:
        v = h.get("voices", {})
        S.append(v.get("S"))
        A.append(v.get("A"))
        T.append(v.get("T"))
        B.append(v.get("B"))
    return {"S": S, "A": A, "T": T, "B": B}


def _extract_romans_from_solver(observations: list[dict]) -> list[str]:
    """从 solver observation 提取罗马数字列表。"""
    for o in observations:
        if o["tool"] == "run_harmony_solver":
            flat = o["result"].get("flatHarmonies", [])
            return [h.get("chord", "") for h in flat if h.get("chord")]
    return []


def _summarize_obs(obs: dict) -> str:
    """压缩一个 observation 用于 LLM prompt。"""
    # 截断到 500 字符
    text = json.dumps(obs, ensure_ascii=False, indent=1)
    if len(text) > 500:
        text = text[:500] + "..."
    return text
