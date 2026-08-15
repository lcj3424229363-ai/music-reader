"""LLM 增强层 — 给和声分析加 teacher-style 中文讲解。

架构：
    solver output (JSON) + RAG over harmony_kb → DeepSeek → 中文讲解

设计原则：
- rule-based solver 是基础（确保和声正确）
- LLM 只做"讲解"和"ambiguity resolution"，不做"和声判定"
- API key 从 .env 读，不进代码
- 所有错误降级为 None，solver 永远能返回（即使 LLM 挂了）
"""
from .deepseek_client import DeepSeekClient, DeepSeekError
from .explainer import HarmonyExplainer, ExplanationResult
from .harmony_kb import HarmonyKB, get_default_kb

__all__ = [
    "DeepSeekClient",
    "DeepSeekError",
    "HarmonyExplainer",
    "ExplanationResult",
    "HarmonyKB",
    "get_default_kb",
]
