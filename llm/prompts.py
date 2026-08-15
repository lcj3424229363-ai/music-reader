"""System Prompt 工程 — 和声教师式回答。

按用户要求，System Prompt 结构：
1. 角色 (Role) — 中央音乐学院 / 斯波索宾和声学教授
2. 分析原则 (Analysis Principles) — 教学式，引用规则
3. 和声规则库 (Harmony Rules Library) — RAG 注入

User Prompt 结构：
- 调性 + 拍号 + 转调
- 旋律 (拍位序列)
- solver 输出的 4 部和声 (S/A/T/B 每声部每个音 + 罗马数字 + 转位)
- 终止式标签
- 输出格式约束
"""
from __future__ import annotations

import json
from typing import Any

# ----- System Prompt 模板 -----

SYSTEM_PROMPT_HEADER = """你是中央音乐学院和声教研室的资深教师，专攻斯波索宾《和声学教程》体系。"""


SYSTEM_PROMPT_PRINCIPLES = """## 你的分析原则

1. **以课本为准**：所有判断必须基于斯波索宾《和声学教程》或伊·杜波夫斯基、斯·叶甫谢耶夫、依·斯波索宾、符·索科洛夫《和声学练习指南》的传统体系，不引入爵士/现代和声逻辑。
2. **教学式表达**：用"老师给本科生讲题"的口吻写。先说和弦是什么，再说为什么这里用它，最后说声部处理/声部进行。不要堆砌术语。
3. **引用规则**：每个判断后面用方括号标出依据，例如 [依据: 终止 64 是装饰的 V, K64]。引用要从下方"和声规则库"中找，不要自己编造规则。
4. **有重点，不平均用力**：终止式（最末小节）要重点讲；正格进行关键位置（V → I）要细讲；经过和弦可以一笔带过。
5. **中文为主**：输出 90% 以上中文，关键术语保留英文/意大利文（如 "PAC", "V76/5", "K64"）。
6. **结构化**：用 Markdown 二级标题分小节，每小节讲一个小节的功能和声部。
7. **指出问题**：如果四部和声有任何不完美（声部大跳、平行五度可能性、终止不规范等），明确指出并给出建议。
8. **不要编造**：如果和声结果有你不理解的地方，直接说"这点课本没有特别要求"或"这取决于风格选择"，不要硬解释。
"""


SYSTEM_PROMPT_RULES_INJECTION_HDR = """## 和声规则库（仅从下列条目引用，不要自创）

以下条目按 RAG 检索结果注入，只包含当前问题相关的规则：
"""


def build_system_prompt(rules_text: str) -> str:
    """拼装完整 System Prompt。"""
    if not rules_text:
        rules_text = "（无相关规则）"
    return "\n\n".join(
        [
            SYSTEM_PROMPT_HEADER,
            SYSTEM_PROMPT_PRINCIPLES,
            SYSTEM_PROMPT_RULES_INJECTION_HDR + rules_text,
        ]
    )


# ----- User Prompt 模板 -----

USER_PROMPT_TEMPLATE = """# 题目

**调性**: {key}
**拍号**: {time}
**转调点**: {key_changes}
**旋律** ({measure_count} 小节):
```
{melody_text}
```

# 算法初步解（已通过课本规则校验，可信度高）

**置信度**: {confidence}%
**评分**: {score}
**算法**: {algorithm}

# 四部和声（小节级别）

{measures_text}

# 终止式序列

{cadences_text}

# 你的任务

请用教学式中文讲解这个四部和声方案，**重点回答以下问题**：

1. **整体布局**：和声进行是否符合 Sposobin 课本对此类旋律的"标准答案"风格？差异在哪里？
2. **小节逐讲**（重点 1、2 小节和终止式小节）：每个和弦的选型理由是什么？这里为什么用 V76/5 而不是 V6？这里为什么用 IV6/4 而不是 IV？
3. **声部进行**：女高/女低/男高/男低 的声部进行是否流畅？有没有大跳或隐藏的平行五度？
4. **终止式**：终止式是什么类型 (PAC/IAC/HC/DC)？是否规范？
5. **学习建议**：如果学生拿这个方案来交作业，你能给他/她什么改进建议？

输出格式（务必遵守）：
- 标题用 `## 一、` `## 二、` `## 三、`...
- 引用规则用 `[依据: 规则名称]`
- 长度 400-700 字，不要写废话
"""


def _format_pitch(p: Any) -> str:
    """把 solver 的 pitch 表示 (midi int 或 [step, octave, acc]) 格式化。"""
    if isinstance(p, (list, tuple)):
        if len(p) == 3:
            step, octave, acc = p
            acc_str = {"#": "#", "b": "b"}.get(acc, acc) if acc else ""
            return f"{step}{acc_str}{octave}"
        if len(p) == 2:
            midi, _dur = p
            return _midi_to_name(midi)
    if isinstance(p, int):
        return _midi_to_name(p)
    return str(p)


def _midi_to_name(midi: int) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = midi // 12 - 1
    return f"{names[midi % 12]}{octave}"


def _format_measure(idx: int, measure: dict[str, Any]) -> str:
    """格式化单小节：罗马数字 + 4 声部。"""
    chord = measure.get("chord", "?")
    voices = measure.get("voices", {}) or {}
    soprano = voices.get("S") or voices.get("soprano") or []
    alto = voices.get("A") or voices.get("alto") or []
    tenor = voices.get("T") or voices.get("tenor") or []
    bass = voices.get("B") or voices.get("bass") or []
    parts = []
    for label, pitches in [("S", soprano), ("A", alto), ("T", tenor), ("B", bass)]:
        names = [_format_pitch(p) for p in pitches]
        parts.append(f"  {label}: {' → '.join(names) if names else '(空)'}")
    body = "\n".join(parts)
    return f"**小节 {idx + 1}** — `{chord}`\n{body}"


def build_user_prompt(solver_output: dict[str, Any]) -> str:
    """从 solver 的 JSON 输出构造 User Prompt。"""
    # 调性 / 拍号 / 转调
    key = solver_output.get("key", "?")
    time = solver_output.get("time", "?")
    kc = solver_output.get("keyChanges", [])
    key_changes = "无" if not kc else ", ".join(f"m{i+1}→{k}" for i, k in kc)

    # 旋律（solver 的 input 里没回传，从另一字段拿）
    melody = solver_output.get("melodyForDisplay") or solver_output.get("inputMelody") or []
    if melody and isinstance(melody[0], (list, tuple)) and len(melody[0]) == 2:
        # [[midi, dur], ...] — 平铺
        flat = []
        for beat in melody:
            if isinstance(beat, (list, tuple)):
                for p in beat:
                    if isinstance(p, (list, tuple)) and len(p) == 2:
                        flat.append(_format_pitch(p[0]))
                    else:
                        flat.append(_format_pitch(p))
        melody_text = " | ".join(flat[:64]) + ("..." if len(flat) > 64 else "")
    else:
        melody_text = "（未提供）"

    measure_count = len(solver_output.get("measures", []))

    # 元数据
    confidence = solver_output.get("confidence", "?")
    score = solver_output.get("score", "?")
    algorithm = solver_output.get("algorithm", "sposobin-solver")

    # 小节
    measures = solver_output.get("measures", []) or []
    measures_text_parts = []
    for i, m in enumerate(measures):
        measures_text_parts.append(_format_measure(i, m))
    measures_text = "\n\n".join(measures_text_parts) if measures_text_parts else "（无）"

    # 终止式
    cadences = solver_output.get("cadences", []) or []
    if cadences:
        cadence_labels = {
            "PAC": "正格完全终止 (PAC)",
            "IAC": "正格不完全终止 (IAC)",
            "HC": "半终止 (HC)",
            "DC": "阻碍终止 (Deceptive)",
            "Plagal": "变格终止",
        }
        lines = []
        for i, c in enumerate(cadences):
            if c is None:
                lines.append(f"- 小节 {i + 1}: (无终止式)")
            else:
                label = cadence_labels.get(c, c)
                lines.append(f"- 小节 {i + 1}: {label}")
        cadences_text = "\n".join(lines)
    else:
        cadences_text = "（无终止式信息）"

    return USER_PROMPT_TEMPLATE.format(
        key=key,
        time=time,
        key_changes=key_changes,
        melody_text=melody_text,
        measure_count=measure_count,
        confidence=confidence,
        score=score,
        algorithm=algorithm,
        measures_text=measures_text,
        cadences_text=cadences_text,
    )
