"""RAG + LLM 主控：solver 输出 → 和声讲解。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deepseek_client import DeepSeekClient, DeepSeekConfig, DeepSeekError
from .harmony_kb import HarmonyKB, get_default_kb
from .prompts import build_system_prompt, build_user_prompt


@dataclass
class ExplanationResult:
    """LLM 讲解结果。"""

    explanation: str  # 中文讲解正文 (markdown)
    rules_used: list[str]  # 引用到的 KB 规则 id 列表（用于审计）
    model: str  # 实际用的模型名
    raw_response: str | None = None  # 原始 LLM 响应（debug 用）
    error: str | None = None  # 如果失败，记录 error

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.explanation)


class HarmonyExplainer:
    """和声讲解器 — 串联 KB + LLM。"""

    def __init__(
        self,
        *,
        kb: HarmonyKB | None = None,
        client: DeepSeekClient | None = None,
    ) -> None:
        self.kb = kb or get_default_kb()
        self.client = client or DeepSeekClient()

    def explain(self, solver_output: dict[str, Any]) -> ExplanationResult:
        """给一个 solver 输出生成教师式中文讲解。"""
        # 1. 提取所有罗马数字（小节级 + 终止式）
        romans: list[str] = []
        for m in solver_output.get("measures", []) or []:
            chord = m.get("chord")
            if chord and chord != "?":
                # V76/5, V7, IV6/4 等都直接传
                romans.append(str(chord))
        # 终止式标签也算一种"指向"
        for c in solver_output.get("cadences", []) or []:
            if c:
                romans.append(c)

        # 2. RAG：去 KB 查相关条目
        rules = self.kb.lookup_many(romans, max_per=2)
        rules_text = self.kb.format_for_prompt(rules)

        # 3. 拼 system + user prompt
        system = build_system_prompt(rules_text)
        user = build_user_prompt(solver_output)

        # 4. 调 LLM
        try:
            text = self.client.chat(system, user)
        except DeepSeekError as e:
            return ExplanationResult(
                explanation="",
                rules_used=[r.id for r in rules],
                model=self.client.config.model,
                error=f"deepseek 调用失败：{e}",
            )
        except Exception as e:  # noqa: BLE001
            return ExplanationResult(
                explanation="",
                rules_used=[r.id for r in rules],
                model=self.client.config.model,
                error=f"LLM 异常：{type(e).__name__}: {e}",
            )

        return ExplanationResult(
            explanation=text,
            rules_used=[r.id for r in rules],
            model=self.client.config.model,
            raw_response=text,
        )
