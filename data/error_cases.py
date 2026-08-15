"""四部和声写作常见错误案例库。

每条 ErrorCase = 一个具体的错误类型
- 错误描述
- 何时出现
- 正确做法
- 哪些流派会判为错 (style_relevance)

用于：
- ReAct Agent 工具 `find_error_cases(rule_name, style)` 检索
- solver 评分时引用（"本例违反 Sposobin 体系下的'禁止平行五度'规则"）
- 教学时举例
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ErrorCase:
    """一个错误案例。"""

    id: str
    error_type: str  # "parallel_5" / "parallel_8" / "voice_crossing" / ...
    severity: str  # "fatal" / "warning" / "note"
    description_zh: str  # 错误描述
    when_occurs: str  # 出现条件 / 场景
    correct_approach: str  # 正确做法
    style_relevance: tuple[str, ...]  # 哪些流派判为错 (空 tuple = 所有流派都判错)
    example_voices: str = ""  # 例: "S:C→C, A:G→G  (平行 5 度: C-G → C-G)"
    reference: str = ""  # 参考文献
    tags: tuple[str, ...] = field(default_factory=tuple)


# ============================================================
# 10 个核心错误案例
# ============================================================

ERROR_CASES: tuple[ErrorCase, ...] = (
    # ----- 1. 平行五度 -----
    ErrorCase(
        id="err-parallel-5",
        error_type="parallel_5",
        severity="fatal",
        description_zh="平行五度：两个声部向同方向移动，相隔纯五度。古典和声中禁止。",
        when_occurs="任何两声部以相同方向做纯五度进行时；最常发生在 I → IV 或 V → I 时的低声部与次中音部。",
        correct_approach="反向 (contrary motion) 或对斜 (oblique motion) 进行；或换其中一个声部到不同的和弦音。",
        style_relevance=("sposobin", "functional"),  # 勋伯格/调式/爵士允许
        example_voices="S:C→C, A:G→G  (C-G 是纯 5；下一和弦还是 C-G = 平行 5)",
        reference="斯波索宾上册 §15 '和声进行中禁止的进行'",
        tags=("voice-leading", "fatal", "sposobin"),
    ),
    # ----- 2. 平行八度 -----
    ErrorCase(
        id="err-parallel-8",
        error_type="parallel_8",
        severity="fatal",
        description_zh="平行八度：两个声部向同方向移动，相隔纯八度。比平行五度更严重。",
        when_occurs="任何两声部以相同方向做纯八度进行；常因低声部根音与高声部根音同步移动。",
        correct_approach="改一个声部到不同的和弦音 (例如从根音改到 3 音或 5 音)；或反向进行。",
        style_relevance=("sposobin", "functional"),
        example_voices="S:C5→C5, B:C4→C4",
        reference="斯波索宾上册 §15",
        tags=("voice-leading", "fatal", "sposobin"),
    ),
    # ----- 3. 反向八度 (八度对斜) -----
    ErrorCase(
        id="err-direct-8",
        error_type="direct_8_to_1",
        severity="fatal",
        description_zh="反向八度：两声部反向移动到纯八度。也称'到达八度'。",
        when_occurs="当一个声部从非根音位置反向跳到八度时；最常在 V → I 终止中。",
        correct_approach="不要反向跳到八度；用三度或同度。",
        style_relevance=("sposobin", "functional"),
        example_voices="S:E5→C5, A:C4→C3  (反向到八度)",
        reference="斯波索宾上册 §15",
        tags=("voice-leading", "fatal", "sposobin"),
    ),
    # ----- 4. 反向五度 -----
    ErrorCase(
        id="err-direct-5",
        error_type="direct_5_to_1",
        severity="warning",
        description_zh="反向五度：两声部反向移动到纯五度。比平行五度轻。",
        when_occurs="当一个声部反向跳到五度时；古典学派多禁止，浪漫派有时允许。",
        correct_approach="改换进行方向，或调整一个声部使其到达三度或六度。",
        style_relevance=("sposobin",),
        example_voices="S:C5→E5, A:G4→C4  (反向到 5 度)",
        reference="斯波索宾上册 §15",
        tags=("voice-leading", "warning", "sposobin"),
    ),
    # ----- 5. 声部交叉 -----
    ErrorCase(
        id="err-voice-crossing",
        error_type="voice_crossing",
        severity="warning",
        description_zh="声部交叉：相邻声部的音高关系错位 (例如女低音高于女高音)。",
        when_occurs="相邻声部音域不清晰时；多见于转位和弦或经过音。",
        correct_approach="保持 S > A > T > B 的相对音域。",
        style_relevance=("sposobin", "functional"),
        example_voices="S:E4, A:F4  (A 高于 S，交叉)",
        reference="斯波索宾上册 §14 '四声部排列'",
        tags=("voice-leading", "warning", "sposobin"),
    ),
    # ----- 6. 声部超越 -----
    ErrorCase(
        id="err-voice-overlapping",
        error_type="voice_overlapping",
        severity="warning",
        description_zh="声部超越：一个声部的音高于相邻上方声部前一拍的音。",
        when_occurs="前一拍 S:E5，后一拍 S:F5, A:G5 (A 超过前 S)。",
        correct_approach="保持各声部在合理音域内。",
        style_relevance=("sposobin",),
        reference="斯波索宾上册 §14",
        tags=("voice-leading", "warning", "sposobin"),
    ),
    # ----- 7. 隐伏五八度 (隐蔽) -----
    ErrorCase(
        id="err-hidden-5",
        error_type="hidden_5_in_outer_voices",
        severity="warning",
        description_zh="隐伏五度 (或隐伏八度)：两外声部同向跳进到五度/八度。",
        when_occurs="S 和 B 同向跳进到纯 5/8 关系；多在终止式 V → I 跳进时。",
        correct_approach="改其中一个外声部为级进；或其中一个声部反向进行。",
        style_relevance=("sposobin",),
        example_voices="S:D5→C5, B:G4→C4  (同向跳进到 8 度)",
        reference="斯波索宾上册 §15.3 '隐伏五度'",
        tags=("voice-leading", "warning", "sposobin"),
    ),
    # ----- 8. 导音未解决 -----
    ErrorCase(
        id="err-leading-tone-unresolved",
        error_type="leading_tone_unresolved",
        severity="fatal",
        description_zh="导音 (7 音) 未上行解决到主音。V → vi 的阻碍终止除外。",
        when_occurs="V7 → IV 时 7 音 (B 在 C 大调) 错误地保留或下行到 5 音。",
        correct_approach="V7 → I 时 7 音必须上行到 1 音；如要阻碍到 vi，7 音可以下行到 5 音 (阻碍终止的许可)。",
        style_relevance=("sposobin", "functional"),
        example_voices="V7:B4 → I:C5 (上行解决 OK) / V7:B4 → I:B4 (未解决) / V7:B4 → IV:A4 (下行到 4 错)",
        reference="斯波索宾上册 §11 '属七和弦的解决'",
        tags=("leading-tone", "fatal", "sposobin"),
    ),
    # ----- 9. 三全音错位 (爵士/浪漫允许) -----
    ErrorCase(
        id="err-tritone-misplacement",
        error_type="tritone_misplacement",
        severity="note",
        description_zh="三全音 (属七的 3-7 音, B-F) 错位：S 和 B 都跳进而非其中一个级进。",
        when_occurs="V7 → I 时，如果 S 的 B 和 B 的 F 都跳进 (而非其中一个级进)，三全音展开到同度，破坏和声张力。",
        correct_approach="V7 → I 时让 7 音 (B) 级进上行到 1 音 (C)；3 音 (F) 可保留或跳进。",
        style_relevance=("sposobin", "functional"),  # 爵士/调式允许
        example_voices="V7: S:B4, B:F4 → I: S:C5, B:C4  (三全音都跳进)",
        reference="斯波索宾上册 §11.3",
        tags=("voice-leading", "note", "sposobin", "jazz-allows"),
    ),
    # ----- 10. 和弦重复音错误 (根音被错误省略) -----
    ErrorCase(
        id="err-doubled-leading_tone",
        error_type="doubled_leading_tone",
        severity="warning",
        description_zh="重复导音：V 或 V7 中导音被重复，造成双重解决冲突。",
        when_occurs="V 或 V7 在四部和声中误将 7 音 (B) 放两个声部。",
        correct_approach="V 重复根音 (5 音)；V7 完全 (root 3 5 7 各一次)。",
        style_relevance=("sposobin", "functional"),
        example_voices="V: S:B4, A:B4, T:D5, B:G4  (B 重复了)",
        reference="斯波索宾上册 §10 '属和弦的重复音'",
        tags=("doubling", "warning", "sposobin"),
    ),
)


def find_by_error_type(error_type: str) -> list[ErrorCase]:
    """按 error_type 检索错误案例。"""
    return [c for c in ERROR_CASES if c.error_type == error_type]


def find_by_style_relevance(style: str) -> list[ErrorCase]:
    """检索在指定流派下被判定为错误的案例。"""
    return [c for c in ERROR_CASES if style in c.style_relevance or not c.style_relevance]


def find_by_severity(severity: str) -> list[ErrorCase]:
    """按严重度检索。"""
    return [c for c in ERROR_CASES if c.severity == severity]


def get_case(case_id: str):
    """按 ID 取案例。"""
    for c in ERROR_CASES:
        if c.id == case_id:
            return c
    return None
