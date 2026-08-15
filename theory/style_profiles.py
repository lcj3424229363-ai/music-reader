"""分析标准层 (Style Profiles) — 音乐分析的流派差异注册。

为什么需要：音乐分析存在流派差异。
不同流派的"对错标准"不同：

  - Sposobin 苏联体系: 严格 T/S/D 功能, 禁止平行五八度, 终止式规范
  - Schoenberg 体系: 强调 prolongation/structural function, 平行五八度常允许 (色彩手段)
  - Functional 传统 (Riemann): 强调 Klangvertretung, T/S/D 是"色彩家族"
  - Modal/Modal-jazz: 不走 T/S/D, 用调式色彩 (Dorian, Mixolydian, ...)
  - 流行/爵士: extended chords (9, 11, 13, b9, #9, #11, b13) 是标配, 平行五度常作色彩

每个 profile 决定:
  - 哪些规则启用 (T/S/D 标签 vs 色彩标签)
  - 哪些规则禁止 (parallel 5/8 在 modal jazz 中是允许的色彩)
  - 终止式识别严格度
  - 错误识别 (parallel 5/8 在哪个流派下不算错)
  - LLM 输出风格 (academic / intuitive / jazzy)

Agent 推理时：先调 lookup_style 确认当前题目的风格 profile, 再决定启用哪些规则。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


# 流派 ID —— 用作 URL/参数/solver 配置
StyleID = Literal["functional_classical", "sposobin", "schenkerian", "jazz", "modal"]


@dataclass(frozen=True)
class StyleProfile:
    """一个流派的分析标准。"""

    style_id: StyleID
    name_zh: str
    description: str

    # ===== 函数标签策略 =====
    use_functional_labels: bool  # True=T/S/D, False=色彩名 (mixolydian, dorian, ...)
    prefer_functional_analysis: bool  # True=优先用 T/S/D 解释, False=允许色彩/调式优先
    label_terminology: str  # 教学术语: "功能" / "色彩" / "调式"

    # ===== 严格度 =====
    forbid_parallel_perfect: bool  # 禁止平行五八度
    forbid_voice_crossing: bool  # 禁止声部交叉
    forbid_hidden_fifths_octaves: bool  # 禁止隐伏五八度 (跳进到强拍同向)
    require_leading_tone_resolution: bool  # 导音必须解决
    forbid_tritone_misplacement: bool  # 禁止三全音错位 (爵士/浪漫允许)

    # ===== 允许的色彩 =====
    allow_borrowed_chords: bool  # 允许借用和弦 (bVI, bIII 等)
    allow_modal_mixture: bool  # 允许调式交替
    allow_altered_dominants: bool  # 允许变化属 (b9, #9, #11, b13)
    allow_extended_chords: bool  # 允许 extended (9, 11, 13)
    allow_secondary_dominants: bool  # 允许副属 (V/x, vii°/x)

    # ===== 终止式严格度 =====
    pac_requires_root_position: bool  # PAC 必须 V 在根音位置
    pac_requires_bass_tonic: bool  # PAC 必须低音是主音
    accept_deceptive_resolution: bool  # 接受阻碍终止 V-vi
    accept_half_cadence: bool  # 接受半终止

    # ===== 输出风格 (LLM 解释用) =====
    explanation_tone: str  # "academic" / "intuitive" / "jazzy" / "modal-poetic"
    cite_sources: list[str] = field(default_factory=list)  # 引用文献

    def allows(self, rule_name: str) -> bool:
        """判断某规则在此风格下是否允许。

        rule_name 例子:
          - "parallel_5"
          - "parallel_8"
          - "voice_crossing"
          - "borrowed_chord"
          - "altered_dominant"
          - "extended_chord"
          - "secondary_dominant"
        """
        if rule_name == "parallel_5" or rule_name == "parallel_8":
            return not self.forbid_parallel_perfect
        if rule_name == "voice_crossing":
            return not self.forbid_voice_crossing
        if rule_name == "hidden_5" or rule_name == "hidden_8":
            return not self.forbid_hidden_fifths_octaves
        if rule_name == "borrowed_chord":
            return self.allow_borrowed_chords
        if rule_name == "modal_mixture":
            return self.allow_modal_mixture
        if rule_name == "altered_dominant":
            return self.allow_altered_dominants
        if rule_name == "extended_chord":
            return self.allow_extended_chords
        if rule_name == "secondary_dominant":
            return self.allow_secondary_dominants
        # 默认允许
        return True

    def forbids(self, rule_name: str) -> bool:
        return not self.allows(rule_name)


# ============================================================
# 5 个默认 profile
# 注意：DEFAULT_STYLE = "functional_classical"，不是 sposobin
# ============================================================

FUNCTIONAL_CLASSICAL_PROFILE = StyleProfile(
    style_id="functional_classical",
    name_zh="通用古典功能和声 (default)",
    description=(
        "Riemann 源头的通用功能和声教学语言，最常见的本科和声学教材体系。"
        "强调 T/S/D 功能分类，但比斯波索宾更宽松；允许更自由的声部进行，"
        "不严格禁止所有平行五度（允许反向/经过性的五度）。"
        "MTRE 项目的默认分析标准。"
    ),
    use_functional_labels=True,
    prefer_functional_analysis=True,
    label_terminology="功能",
    forbid_parallel_perfect=True,
    forbid_voice_crossing=True,
    forbid_hidden_fifths_octaves=True,
    require_leading_tone_resolution=True,
    forbid_tritone_misplacement=True,
    allow_borrowed_chords=True,
    allow_modal_mixture=True,
    allow_altered_dominants=True,  # 通用体系允许变化属
    allow_extended_chords=False,
    allow_secondary_dominants=True,
    pac_requires_root_position=True,
    pac_requires_bass_tonic=True,
    accept_deceptive_resolution=True,
    accept_half_cadence=True,
    explanation_tone="intuitive",
    cite_sources=[
        "Riemann《Vereinfachte Harmonielehre》(1893)",
        "通用功能和声教学法",
    ],
)


SPOSOBIN_PROFILE = StyleProfile(
    style_id="sposobin",
    name_zh="斯波索宾体系 (苏联传统和声学)",
    description=(
        "斯波索宾《和声学教程》（上、下册）体系。严格 T/S/D 功能分类，"
        "禁止平行五八度、声部交叉、隐伏五八度；终止式规范（PAC/IAC/HC/DC）。"
        "是中央音乐学院和声教学的标准。"
    ),
    use_functional_labels=True,
    prefer_functional_analysis=True,
    label_terminology="功能",
    forbid_parallel_perfect=True,
    forbid_voice_crossing=True,
    forbid_hidden_fifths_octaves=True,
    require_leading_tone_resolution=True,
    forbid_tritone_misplacement=True,
    allow_borrowed_chords=True,   # 关系小调借用允许 (bVI 大调中)
    allow_modal_mixture=True,
    allow_altered_dominants=False,  # 变化属不属于上册范围
    allow_extended_chords=False,
    allow_secondary_dominants=True,
    pac_requires_root_position=True,
    pac_requires_bass_tonic=True,
    accept_deceptive_resolution=True,
    accept_half_cadence=True,
    explanation_tone="academic",
    cite_sources=[
        "斯波索宾《和声学教程》（上册）人民音乐出版社",
        "里姆斯基-科萨科夫《和声学实用教程》",
    ],
)


SCHENKERIAN_PROFILE = StyleProfile(
    style_id="schenkerian",
    name_zh="申克分析 (Schenkerian Analysis)",
    description=(
        "Heinrich Schenker 的层次化分析理论：前景/中景/背景 (foreground/middleground/background)。"
        "强调 prolongation (延长) 与结构性功能。"
        "平行五八度在延长段中常作为结构性手段允许。"
        "V→I 的 root position 不强制要求；V7 在任何位置可作为 prolongation。"
    ),
    use_functional_labels=True,
    prefer_functional_analysis=True,
    label_terminology="功能+层次",
    forbid_parallel_perfect=False,  # 延长段允许平行
    forbid_voice_crossing=True,
    forbid_hidden_fifths_octaves=False,
    require_leading_tone_resolution=False,  # 中景不要求
    forbid_tritone_misplacement=False,
    allow_borrowed_chords=True,
    allow_modal_mixture=True,
    allow_altered_dominants=True,
    allow_extended_chords=False,
    allow_secondary_dominants=True,
    pac_requires_root_position=False,  # 申克接受 V7 在任何位置
    pac_requires_bass_tonic=True,
    accept_deceptive_resolution=True,
    accept_half_cadence=True,
    explanation_tone="academic",
    cite_sources=[
        "Heinrich Schenker《Harmony》(1906)",
        "Heinrich Schenker《Free Composition》(1935)",
    ],
)


# 旧的 FUNCTIONAL_PROFILE 别名（向后兼容）
FUNCTIONAL_PROFILE = FUNCTIONAL_CLASSICAL_PROFILE


MODAL_PROFILE = StyleProfile(
    style_id="modal",
    name_zh="调式体系 (教会调式 / Modal Jazz)",
    description=(
        "教会调式 (Dorian/Phrygian/Lydian/Mixolydian/Aeolian/Locrian) "
        "或 Modal Jazz (Miles Davis《Kind of Blue》、Coltrane)。"
        "不走 T/S/D 功能分析，用调式色彩 (mode) 解释。"
        "平行五八度常作为调式色彩手段允许。"
    ),
    use_functional_labels=False,
    prefer_functional_analysis=False,
    label_terminology="调式",
    forbid_parallel_perfect=False,  # 调式允许
    forbid_voice_crossing=False,
    forbid_hidden_fifths_octaves=False,
    require_leading_tone_resolution=False,  # 调式无强导音
    forbid_tritone_misplacement=False,
    allow_borrowed_chords=True,  # 调式交替是调式体系核心
    allow_modal_mixture=True,
    allow_altered_dominants=True,
    allow_extended_chords=True,
    allow_secondary_dominants=False,  # 副属属于功能体系，调式不用
    pac_requires_root_position=False,
    pac_requires_bass_tonic=False,
    accept_deceptive_resolution=True,
    accept_half_cadence=True,
    explanation_tone="modal-poetic",
    cite_sources=[
        "George Russell《Lydian Chromatic Concept》(1953)",
        "Miles Davis《Kind of Blue》(1959)",
    ],
)


JAZZ_PROFILE = StyleProfile(
    style_id="jazz",
    name_zh="爵士 / 流行和声 (Jazz & Pop)",
    description=(
        "Jazz/Pop harmony：extended chords (9, 11, 13) 标配，"
        "altered dominants (b9, #9, #11, b13) 常见，"
        "tritone substitution (bII7 替 V7) 是核心手法，"
        "ii-V-I 是进行的基本单位。"
        "Pop 是 jazz 的简化版本（少 extended，少 altered），共享同一套规则体系。"
    ),
    use_functional_labels=True,
    prefer_functional_analysis=True,
    label_terminology="功能+延伸",
    forbid_parallel_perfect=False,  # 爵士/流行允许
    forbid_voice_crossing=False,
    forbid_hidden_fifths_octaves=False,
    require_leading_tone_resolution=False,  # altered dominants 不要求
    forbid_tritone_misplacement=False,  # tritone sub 是核心
    allow_borrowed_chords=True,
    allow_modal_mixture=True,
    allow_altered_dominants=True,
    allow_extended_chords=True,
    allow_secondary_dominants=True,
    pac_requires_root_position=False,
    pac_requires_bass_tonic=True,
    accept_deceptive_resolution=True,
    accept_half_cadence=True,
    explanation_tone="jazzy",
    cite_sources=[
        "Mark Levine《Jazz Piano Book》",
        "Bert Ligon《Jazz Theory Resources》",
    ],
)


# ============================================================
# 注册表
# ============================================================

PROFILES: dict[StyleID, StyleProfile] = {
    "functional_classical": FUNCTIONAL_CLASSICAL_PROFILE,  # 兼容 profile,非 V1 默认
    "sposobin": SPOSOBIN_PROFILE,  # V1 默认 — 斯波索宾传统和声/曲式
    "schenkerian": SCHENKERIAN_PROFILE,
    "jazz": JAZZ_PROFILE,
    "modal": MODAL_PROFILE,
}


# V1 决策: 斯波索宾体系优先
# 斯波索宾 = 斯波索宾《和声学教程》(上册) — 中央音乐学院和声教学标准
# 这是 V1 的核心市场,必须做到位再扩
DEFAULT_STYLE: StyleID = "sposobin"


def get_profile(style_id: Optional[str]) -> StyleProfile:
    """按 ID 取 profile，未知 ID 或 None 都返回默认 sposobin。"""
    if not style_id:
        return PROFILES[DEFAULT_STYLE]
    return PROFILES.get(style_id, PROFILES[DEFAULT_STYLE])


def list_styles() -> list[StyleProfile]:
    """列出所有 profile（用于 UI 风格切换器）。"""
    return list(PROFILES.values())


# ============================================================
# ReAct Agent 工具：风格感知
# ============================================================

def style_explainer_prefix(profile: StyleProfile) -> str:
    """生成 LLM prompt 前缀，告诉 LLM 当前用什么风格分析。"""
    lines = [
        f"## 分析标准：{profile.name_zh}",
        f"{profile.description}",
        f"",
        f"- 教学术语：{profile.label_terminology}",
        f"- 解释语气：{profile.explanation_tone}",
        f"- {'禁止' if profile.forbid_parallel_perfect else '允许'}平行五八度",
        f"- {'禁止' if profile.forbid_voice_crossing else '允许'}声部交叉",
        f"- {'禁止' if profile.forbid_hidden_fifths_octaves else '允许'}隐伏五八度",
        f"- {'要求' if profile.require_leading_tone_resolution else '不要求'}导音必须解决",
        f"- {'允许' if profile.allow_borrowed_chords else '不允许'}借用和弦",
        f"- {'允许' if profile.allow_modal_mixture else '不允许'}调式交替",
        f"- {'允许' if profile.allow_altered_dominants else '不允许'}变化属",
        f"- {'允许' if profile.allow_extended_chords else '不允许'}延伸和弦 (9, 11, 13)",
        f"- {'允许' if profile.allow_secondary_dominants else '不允许'}副属 (V/x)",
        f"- PAC {'必须' if profile.pac_requires_root_position else '不要求'}根音位置",
        f"- PAC {'必须' if profile.pac_requires_bass_tonic else '不要求'}低音主音",
        f"",
    ]
    if profile.cite_sources:
        lines.append("**参考文献**：")
        for src in profile.cite_sources:
            lines.append(f"- {src}")
    return "\n".join(lines)
