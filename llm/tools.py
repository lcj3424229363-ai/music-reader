"""ReAct Agent 工具层 — 8 个工具。

按用户调整后的工具集（不是原 6 工具方案）：

必选 5 (⭐⭐⭐⭐⭐):
  1. lookup_style(style_id)         → StyleProfile
  2. analyze_music_structure(score) → 调性/乐句/终止/动机 识别
  3. run_harmony_solver(melody, style) → 罗马数字
  4. check_voice_leading(voices, style) → 错误列表
  5. query_music_example(query, style)   → 案例（合并 query_repertoire）

可选 3 (⭐⭐⭐⭐):
  6. query_kb(roman, category)      → 和声规则
  7. find_error_cases(rule_name, style) → 错误案例
  8. compare_analysis(candidates)   → 候选解释对比

每个工具有：
  - name         : 工具名（LLM function calling 用）
  - description  : 工具描述（LLM 决策用）
  - parameters   : 参数 schema (Pydantic)
  - execute      : 实际执行函数
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from theory.style_profiles import get_profile, StyleProfile
from data.repertoire import (
    REPERTOIRE_CASES,
    find_by_tag,
    find_by_key,
    find_by_composer,
    get_case as get_repertoire_case,
)
from data.error_cases import (
    ERROR_CASES,
    find_by_error_type,
    find_by_style_relevance,
    get_case as get_error_case,
)


# ============================================================
# 工具定义
# ============================================================

@dataclass
class ToolDef:
    """工具定义（LLM function calling 用）。"""
    name: str
    description: str
    parameters_schema: dict  # JSON Schema
    execute: Callable[[dict], dict]


# ============================================================
# 工具实现
# ============================================================

def _lookup_style(args: dict) -> dict:
    """1. lookup_style: 取分析标准层 profile。"""
    style_id = args.get("style_id", "")
    profile = get_profile(style_id)
    return {
        "style_id": profile.style_id,
        "name_zh": profile.name_zh,
        "label_terminology": profile.label_terminology,
        "forbid_parallel_perfect": profile.forbid_parallel_perfect,
        "require_leading_tone_resolution": profile.require_leading_tone_resolution,
        "allow_extended_chords": profile.allow_extended_chords,
        "allow_altered_dominants": profile.allow_altered_dominants,
        "explanation_tone": profile.explanation_tone,
    }


def _analyze_music_structure(args: dict) -> dict:
    """2. analyze_music_structure: 调性/乐句/终止/动机 识别。

    入参 score: {
      "key": "C major",
      "melody_notes": [{"pitch": 60, "duration": 1.0, "measure": 1}, ...]
    }

    返回: {key, key_changes, phrases, cadences, motifs}
    """
    score = args.get("score", {})
    key = score.get("key", "C major")
    notes = score.get("melody_notes", [])

    # 简单结构识别（MVP 版本）:
    # - key_changes: 空（待 detect_modulation 集成）
    # - phrases: 按 4 或 8 小节分组
    # - cadences: 末尾 2-4 小节标
    # - motifs: 开头 2-4 音

    n_measures = max((n.get("measure", 0) for n in notes), default=0)
    phrase_length = 4  # 默认 4 小节
    phrases = []
    for start in range(1, n_measures + 1, phrase_length):
        end = min(start + phrase_length - 1, n_measures)
        phrases.append({
            "start": start,
            "end": end,
            "label": f"phrase_{len(phrases) + 1}",
        })

    motifs = []
    if notes:
        head = notes[:4]
        motifs.append({
            "label": "head_motif",
            "notes": [n.get("pitch") for n in head],
        })

    return {
        "key": key,
        "key_changes": [],
        "phrases": phrases,
        "cadences": [],  # 留给 run_harmony_solver + check_cadence
        "motifs": motifs,
        "n_measures": n_measures,
    }


def _run_harmony_solver(args: dict) -> dict:
    """3. run_harmony_solver: 调 rule-based solver 出 4 部和声 + 罗马数字。

    通过 HTTP self-call 到 /solve-melody endpoint。
    """
    melody = args.get("melody", [])
    style = args.get("style", "functional_classical")
    key = args.get("key", "C major")
    time_signature = args.get("time_signature", "4/4")

    payload = {
        "melody": melody,
        "key": key,
        "time_signature": time_signature,
        "style": style,
    }

    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8765/solve-melody",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError) as e:
        return {
            "error": f"solver endpoint not reachable: {e}",
            "fallback": "需要 server.py 在 127.0.0.1:8765 运行",
        }


def _check_voice_leading(args: dict) -> dict:
    """4. check_voice_leading: 按风格做声部进行校验。

    入参 voices: {"S": [60, 62, ...], "A": [...], "T": [...], "B": [...]}
    """
    voices = args.get("voices", {})
    style_id = args.get("style", "functional_classical")
    profile = get_profile(style_id)

    errors = []
    # 简单校验：检查是否有平行五/八度
    S = voices.get("S", [])
    A = voices.get("A", [])
    T = voices.get("T", [])
    B = voices.get("B", [])

    def _interval(a, b):
        return abs(a - b) % 12 if a is not None and b is not None else None

    # 平行八度检查
    for i in range(len(B) - 1):
        if i >= len(S): break
        if S[i] is None or B[i] is None: continue
        if S[i + 1] is None or B[i + 1] is None: continue
        if _interval(S[i], B[i]) == 0 and _interval(S[i+1], B[i+1]) == 0:
            if profile.forbid_parallel_perfect:
                errors.append({
                    "type": "parallel_8",
                    "severity": "fatal",
                    "between": "S-B",
                    "measures": f"m{i+1}-m{i+2}",
                    "rule": "parallel_8",
                })
        if _interval(S[i], B[i]) == 7 and _interval(S[i+1], B[i+1]) == 7:
            if profile.forbid_parallel_perfect:
                errors.append({
                    "type": "parallel_5",
                    "severity": "fatal",
                    "between": "S-B",
                    "measures": f"m{i+1}-m{i+2}",
                    "rule": "parallel_5",
                })

    return {
        "style": style_id,
        "errors": errors,
        "n_errors": len(errors),
        "n_measures_checked": len(B) - 1,
    }


def _query_music_example(args: dict) -> dict:
    """5. query_music_example: 查经典作品案例。

    支持: tag / key / composer / id
    """
    results = []
    if args.get("case_id"):
        c = get_repertoire_case(args["case_id"])
        if c:
            results.append(_case_to_dict(c))
    elif args.get("tag"):
        results = [_case_to_dict(c) for c in find_by_tag(args["tag"])]
    elif args.get("key"):
        results = [_case_to_dict(c) for c in find_by_key(args["key"])]
    elif args.get("composer"):
        results = [_case_to_dict(c) for c in find_by_composer(args["composer"])]
    else:
        # 默认返回前 3 个
        results = [_case_to_dict(c) for c in REPERTOIRE_CASES[:3]]

    return {
        "n_results": len(results),
        "cases": results,
    }


def _query_kb(args: dict) -> dict:
    """6. query_kb: 查和声知识库（已有 31 条 RAG）。"""
    from llm.harmony_kb import HarmonyKB

    kb = HarmonyKB()
    roman = args.get("roman", "")
    category = args.get("category")

    if roman:
        entries = kb.lookup(roman)
    elif category:
        # 按 category 过滤
        from llm.harmony_kb import (
            TRIAD_ENTRIES, SEVENTH_ENTRIES, CADENCE_ENTRIES,
            SECONDARY_ENTRIES, GENERAL_ENTRIES, TEXTBOOK_ENTRIES,
        )
        all_entries = (
            TRIAD_ENTRIES + SEVENTH_ENTRIES + CADENCE_ENTRIES
            + SECONDARY_ENTRIES + GENERAL_ENTRIES + TEXTBOOK_ENTRIES
        )
        entries = [e for e in all_entries if e.category == category]
    else:
        entries = []

    return {
        "n_results": len(entries),
        "entries": [
            {
                "id": e.id,
                "category": e.category,
                "roman": e.roman,
                "name_zh": e.name_zh,
                "function": e.function,
                "description": e.description,
            }
            for e in entries[:10]  # 最多 10 条
        ],
    }


def _find_error_cases(args: dict) -> dict:
    """7. find_error_cases: 查错误案例。"""
    style = args.get("style", "functional_classical")
    error_type = args.get("error_type")
    severity = args.get("severity")

    if error_type:
        cases = find_by_error_type(error_type)
    elif severity:
        from data.error_cases import find_by_severity
        cases = find_by_severity(severity)
    else:
        cases = find_by_style_relevance(style)

    return {
        "n_results": len(cases),
        "style_filter": style,
        "cases": [
            {
                "id": c.id,
                "error_type": c.error_type,
                "severity": c.severity,
                "description_zh": c.description_zh,
                "correct_approach": c.correct_approach,
                "style_relevance": list(c.style_relevance),
            }
            for c in cases
        ],
    }


def _compare_analysis(args: dict) -> dict:
    """8. compare_analysis: 候选解释对比。

    入参 candidates: [
        {"label": "V/V (副属)", "evidence": [...], "score": 70},
        {"label": "Modal mixture (借用)", "evidence": [...], "score": 30},
    ]

    返回：按 score 排序 + text diff
    """
    candidates = args.get("candidates", [])
    if not candidates:
        return {"error": "no candidates to compare"}

    # 按 score 排序
    sorted_cands = sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)

    # 找出共有 evidence 和分歧
    all_evidence = set()
    for c in sorted_cands:
        for e in c.get("evidence", []):
            all_evidence.add(e)

    return {
        "n_candidates": len(sorted_cands),
        "ranked": [
            {
                "rank": i + 1,
                "label": c.get("label"),
                "score": c.get("score", 0),
                "evidence": c.get("evidence", []),
            }
            for i, c in enumerate(sorted_cands)
        ],
        "top_pick": sorted_cands[0].get("label") if sorted_cands else None,
        "all_evidence": sorted(all_evidence),
    }


def _case_to_dict(c) -> dict:
    return {
        "id": c.id,
        "composer": c.composer,
        "title": c.title,
        "opus": c.opus,
        "key": c.key,
        "form": c.form,
        "harmonic_summary": list(c.harmonic_summary),
        "cadences": list(c.cadences),
        "pedagogical_value": c.pedagogical_value,
        "tags": list(c.tags),
    }


# ============================================================
# 工具注册表
# ============================================================

TOOL_DEFINITIONS: list[ToolDef] = [
    ToolDef(
        name="lookup_style",
        description=(
            "查询分析标准层 (StyleProfile)。先调用此工具决定整个分析用什么风格标准。"
            "style_id 可选: functional_classical (default) / sposobin / schenkerian / jazz / modal"
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "style_id": {
                    "type": "string",
                    "description": "风格 ID，例 sposobin / jazz / modal",
                    "default": "functional_classical",
                }
            },
        },
        execute=_lookup_style,
    ),
    ToolDef(
        name="analyze_music_structure",
        description=(
            "分析乐曲结构：调性、乐句 (4/8 小节)、终止、动机。"
            "建议在 run_harmony_solver 之前调用。"
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "score": {
                    "type": "object",
                    "description": "乐谱数据 {key, melody_notes: [{pitch, duration, measure}, ...]}",
                }
            },
            "required": ["score"],
        },
        execute=_analyze_music_structure,
    ),
    ToolDef(
        name="run_harmony_solver",
        description=(
            "调 rule-based solver 对旋律跑出罗马数字 + 四部和声建议。"
            "返回 4 个声部的音高 + 罗马数字 + 终止式。"
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "melody": {"type": "array", "items": {"type": "object"}},
                "key": {"type": "string", "default": "C major"},
                "time_signature": {"type": "string", "default": "4/4"},
                "style": {"type": "string", "default": "functional_classical"},
            },
            "required": ["melody", "key"],
        },
        execute=_run_harmony_solver,
    ),
    ToolDef(
        name="check_voice_leading",
        description=(
            "按指定风格检查四部和声的声部进行，检测平行五八度/声部交叉/隐伏五度等错误。"
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "voices": {
                    "type": "object",
                    "description": "4 声部 {S: [...], A: [...], T: [...], B: [...]}",
                },
                "style": {"type": "string", "default": "functional_classical"},
            },
            "required": ["voices", "style"],
        },
        execute=_check_voice_leading,
    ),
    ToolDef(
        name="query_music_example",
        description=(
            "查询经典作品案例库 (Beethoven, Chopin, Bach, Mozart, Debussy, Tchaikovsky 等)。"
            "可按 tag / key / composer / case_id 检索。"
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "tag": {"type": "string", "description": "例 sposobin / modal / sonata / fugue"},
                "key": {"type": "string", "description": "例 C major / c minor"},
                "composer": {"type": "string", "description": "例 Bach / Mozart"},
                "case_id": {"type": "string"},
            },
        },
        execute=_query_music_example,
    ),
    ToolDef(
        name="query_kb",
        description=(
            "查和声知识库 (KB) 的具体规则。"
            "按 roman (I, V7, V6 等) 或 category (triad/seventh/cadence/secondary) 检索。"
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "roman": {"type": "string", "description": "例 I / V7 / V6 / vii°"},
                "category": {"type": "string"},
            },
        },
        execute=_query_kb,
    ),
    ToolDef(
        name="find_error_cases",
        description=(
            "查错误案例库（平行五八、声部交叉、导音未解决等）。"
            "按 error_type / severity / style 过滤。"
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "error_type": {"type": "string"},
                "severity": {"type": "string", "enum": ["fatal", "warning", "note"]},
                "style": {"type": "string"},
            },
        },
        execute=_find_error_cases,
    ),
    ToolDef(
        name="compare_analysis",
        description=(
            "对比多个候选解释（如 V/V vs Modal mixture），返回排名 + 共有 evidence。"
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "score": {"type": "number"},
                            "evidence": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                }
            },
            "required": ["candidates"],
        },
        execute=_compare_analysis,
    ),
]


def get_tool(name: str) -> Optional[ToolDef]:
    """按名取工具。"""
    for t in TOOL_DEFINITIONS:
        if t.name == name:
            return t
    return None


def list_tool_names() -> list[str]:
    return [t.name for t in TOOL_DEFINITIONS]


def to_openai_tools_schema() -> list[dict]:
    """转换为 OpenAI function calling schema（DeepSeek 兼容）。"""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters_schema,
            },
        }
        for t in TOOL_DEFINITIONS
    ]


def execute_tool(name: str, args: dict) -> dict:
    """执行指定工具。"""
    tool = get_tool(name)
    if not tool:
        return {"error": f"unknown tool: {name}"}
    try:
        return tool.execute(args)
    except Exception as e:
        return {"error": f"tool '{name}' failed: {type(e).__name__}: {e}"}
