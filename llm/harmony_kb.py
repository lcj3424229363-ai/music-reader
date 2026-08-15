"""和声知识库 — RAG 的数据源。

每条 KB 记录是一个"和声规则单元"，可被检索后注入到 LLM prompt。

来源：
- theory/ 模块里的 Sposobin 规则（functions/roman_analyzer/cadence/voice_leading/secondary）
- 18 个课本例题（app.js EXAMPLE_PRESETS）的预期解

schema：
    {
        "id": str,                    # 唯一 id
        "category": str,              # "triad" | "seventh" | "secondary" | "cadence" | ...
        "roman": str,                 # "I" | "V7" | "V76/5" | "V/V" | "*"  (通配)
        "name_zh": str,               # 中文名
        "function": str,              # "T" | "S" | "D" | "T/S/D"
        "description": str,           # 详细规则说明
        "voice_leading": [str, ...],  # 声部进行规则（中文短句）
        "common_uses": [str, ...],    # 常见用法 / 触发条件
        "tags": [str, ...],           # 用于更细的检索
    }

检索：KBEntry.match(solver_chord) → bool
- 匹配规则：roman 完全相同 OR 通用规则（roman='*'）

检索 prompt 时：直接遍历 solver 输出每个 chord 调 match()，取所有匹配。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class KBEntry:
    id: str
    category: str
    roman: str
    name_zh: str
    function: str
    description: str
    voice_leading: list[str] = field(default_factory=list)
    common_uses: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def matches(self, roman: str) -> bool:
        """判断此 KB 条目是否与指定罗马数字相关。"""
        if self.roman == "*":
            return True  # 通用规则
        return self.roman == roman


# ----- 三和弦 (Triads) -----
TRIAD_ENTRIES: list[KBEntry] = [
    KBEntry(
        id="triad-I",
        category="triad",
        roman="I",
        name_zh="主和弦 (T)",
        function="T",
        description="调式一级三和弦，由主音、3 音、5 音构成。最稳定的功能，是其他所有和弦的回归点。在大调中是 I (大三和弦)，小调中为 i (小三和弦)。",
        voice_leading=[
            "根音常出现在低声部，作为和声进行的基础",
            "上方三声部可以自由排列，但避免连续 4 度叠置",
        ],
        common_uses=[
            "终止式的终点 (PAC / IAC 都在 I 上结束)",
            "乐段开始的稳定",
            "副属和弦解决后的归属",
        ],
        tags=["tonic", "stable", "cadence-target"],
    ),
    KBEntry(
        id="triad-iv",
        category="triad",
        roman="IV",
        name_zh="下属和弦 (S)",
        function="S",
        description="调式四级三和弦。在大调中为大三和弦 (IV)，小调中为 iv (小三和弦)。功能上属'下属'，最常作为 V 之前的准备。",
        voice_leading=[
            "低音常做 4-5 上行解决到 V 的根音",
            "高音部如有 4 音，常上行 4-5 或下行 4-3 进入 V 的 3 音",
        ],
        common_uses=[
            "正格终止前的准备 (IV → V → I)",
            "变格终止 (IV → I)",
            "经过和弦",
        ],
        tags=["subdominant", "preparation"],
    ),
    KBEntry(
        id="triad-V",
        category="triad",
        roman="V",
        name_zh="属和弦 (D)",
        function="D",
        description="调式五级三和弦。大调为大三和弦 (V)，小调中常用 V (大调 V，借用导音)。在四部和声中常以三声部或四声部呈现。",
        voice_leading=[
            "V → I 时：根音 5→1（强进行），3 音 7→1（导音必须解决到主音）",
            "V → I 时：5 音 2→1（上三度）或 2→3（保留）",
            "V 前常加 IV 或 ii 增加准备",
        ],
        common_uses=[
            "正格终止 (V → I)",
            "半终止 (终止在 V 上)",
            "副属和弦的暂时主",
        ],
        tags=["dominant", "leading-tone", "resolution"],
    ),
    KBEntry(
        id="triad-vi",
        category="triad",
        roman="vi",
        name_zh="下中音和弦 (T-S)",
        function="T",
        description="调式六级三和弦。大调中为小三和弦 (vi)，小调中为 VI (大三和弦)。功能上属于 T 系（自然下属关系），但常作为下属准备。",
        voice_leading=[
            "常与 I 互换：vi → I 类似 IV → V",
            "vi → ii 可作为 IV → V 的变体",
        ],
        common_uses=[
            "和声小调的 VI (借用的下属功能)",
            "deceptive 终止：V → vi 代替 V → I",
        ],
        tags=["tonic-substitute", "deceptive"],
    ),
    KBEntry(
        id="triad-ii",
        category="triad",
        roman="ii",
        name_zh="上主音和弦 (S)",
        function="S",
        description="调式二级三和弦。大调中为小三和弦 (ii)，小调中为 ii°(减三和弦)。功能上属于 S 系，是 iv 的下属变体。",
        voice_leading=[
            "ii → V 是教科书式的下属准备，比 IV → V 更柔和",
            "ii°(小调) → V 时 5 音必须上行 (减五度扩张)",
        ],
        common_uses=[
            "柔和的下属进行 (ii → V → I)",
            "小调终止前的减和弦扩张",
        ],
        tags=["subdominant", "mild-preparation"],
    ),
    KBEntry(
        id="triad-iii",
        category="triad",
        roman="III",
        name_zh="中音和弦 (T)",
        function="T",
        description="调式三级三和弦。大调中为小三和弦 (III)，小调中为 iii (大三和弦)。功能上属 T 系，但较少用作和声骨干。",
        voice_leading=[
            "III → vi 是常见的连锁进行",
            "III 后常接 vi 或 IV",
        ],
        common_uses=[
            "作为经过和弦",
            "大小调交替中作为借用",
        ],
        tags=["tonic", "weak"],
    ),
    # 6 和弦（三和弦的第一转位）
    KBEntry(
        id="first-inversion-6",
        category="first-inversion",
        roman="*",  # 通配：所有 6 和弦都有共同特征
        name_zh="第一转位 (6 和弦)",
        function="*",
        description="三和弦的第一转位，标记为 6（低音是 3 音）。6 和弦的功能常被'软化'，常作为经过或连接。",
        voice_leading=[
            "低音常做级进 (经过 6 和弦)",
            "6 和弦 → 5/3 和弦 时低音下行 1 度",
        ],
        common_uses=[
            "经过性的下属 (IV6 → V)",
            "终止 64 (cadential 6/4) — 实际是 V 上的装饰",
            "阻碍进行 (V6 → vi)",
        ],
        tags=["inversion", "softening", "passing"],
    ),
    # 终止 64
    KBEntry(
        id="cadential-64",
        category="cadential",
        roman="I64",  # 终止 64 标记为 I64
        name_zh="终止六四和弦 (Cadential 6/4)",
        function="D",  # 实际功能属 D
        description="出现在 V 上方的 6/4 和弦（通常是 I 的 6/4 形式，但功能是属准备）。标记为 I64，但常被理解为'装饰的 V'。",
        voice_leading=[
            "上方声部保持或微动",
            "6/4 → 5/3 时低音保持 V 的根音不变",
            "上方的 6/4 解决到 5/3 时声部自然下行",
        ],
        common_uses=[
            "终止式中 V 之前的准备 (K64)",
            "延长属功能",
        ],
        tags=["cadence", "dominant-extension", "ornamental"],
    ),
]


# ----- 七和弦 (Sevenths) -----
SEVENTH_ENTRIES: list[KBEntry] = [
    KBEntry(
        id="seventh-V7",
        category="seventh",
        roman="V7",
        name_zh="属七和弦 (D7)",
        function="D",
        description="调式五级七和弦，最重要的不协和和弦。包含 3 个音程倾向性强的声部（3 音/导音上行解决，7 音下行解决）。",
        voice_leading=[
            "7 音必须下行 1 度解决到 I 的 3 音",
            "3 音/导音必须上行 1 度解决到 I 的根音",
            "5 音 可上可下，常下行 1 度",
            "根音 5 → 1（强进行）",
        ],
        common_uses=[
            "正格终止 V7 → I",
            "所有属功能进行中的核心",
            "副属和弦的临时 V",
        ],
        tags=["dominant", "dissonance", "resolution-required"],
    ),
    KBEntry(
        id="seventh-V65",
        category="seventh",
        roman="V65",  # V6/5 第一转位
        name_zh="属七和弦第一转位 (V6/5)",
        function="D",
        description="属七和弦的第一转位，低音是 3 音。低音上行倾向强（从 7 音位置上行），常出现在强拍。",
        voice_leading=[
            "低音 7→1（上行级进解决到 I 的根音）",
            "上方声部正常解决：3→1, 5→1/3, 7→3",
        ],
        common_uses=[
            "终止式 V65 → I（强拍位置）",
            "阻碍进行 V65 → vi",
        ],
        tags=["dominant", "inversion", "strong-beat"],
    ),
    KBEntry(
        id="seventh-V43",
        category="seventh",
        roman="V43",  # V4/3 第二转位
        name_zh="属七和弦第二转位 (V4/3)",
        function="D",
        description="属七和弦的第二转位，低音是 5 音。是 V7 中最弱的转位，常作为经过和弦。",
        voice_leading=[
            "低音 2→1（下行半音到 I 的根音）",
            "低音 2→3（保持到 I 的 3 音）",
        ],
        common_uses=[
            "经过和弦 (ii → V4/3 → I6 → IV)",
            "连接两个根音相距 5 度的和弦",
        ],
        tags=["dominant", "inversion", "passing"],
    ),
    KBEntry(
        id="seventh-V42",
        category="seventh",
        roman="V42",  # V4/2 第三转位
        name_zh="属七和弦第三转位 (V4/2)",
        function="D",
        description="属七和弦的第三转位，低音是 7 音。最具倾向性的转位，7 音必须在低音主动下行解决。",
        voice_leading=[
            "低音 7→6（必须下行半音到 I 的 3 音，或到 vi 的根音）",
            "7 音下行解决不可省略",
        ],
        common_uses=[
            "延留 (suspension)",
            "阻碍终止 V4/2 → vi",
            "I 的 6 度音延留到 V4/2 再下行",
        ],
        tags=["dominant", "inversion", "suspension", "resolution-required"],
    ),
    KBEntry(
        id="seventh-V76",
        category="seventh",
        roman="V76/5",  # V7 的第一转位 = V65 (同物异名)
        name_zh="属七和弦第一转位 (V76/5 = V6/5)",
        function="D",
        description="属七和弦第一转位的德国式标记，功能上等同 V65。低音是 3 音，主动上行倾向强。",
        voice_leading=[
            "低音 7→1（半音上行解决到 I 的根音，强倾向）",
            "上方 3→1（导音解决），7→3（下行），根音 5→1",
        ],
        common_uses=[
            "终止式 V76/5 → I（最标准）",
            "在 PAC 中常在倒数第二小节",
        ],
        tags=["dominant", "german-notation", "strong"],
    ),
]


# ----- 终止式 (Cadences) -----
CADENCE_ENTRIES: list[KBEntry] = [
    KBEntry(
        id="cadence-PAC",
        category="cadence",
        roman="*",
        name_zh="正格完全终止 (PAC)",
        function="*",
        description="Perfect Authentic Cadence. 模式: V (或 V7) → I，最低音为 1→1 (根音到根音)，高音为 3→1。最稳定、最强的终止。",
        voice_leading=[
            "V 的根音 5 必须下行到 I 的根音 1",
            "V 的 3 音/导音 7 上行到 I 的根音 1",
            "高音部：V 的 3 音必须下行到 I 的根音 1（最关键）",
        ],
        common_uses=[
            "终止式最常见形式",
            "乐段结束",
            "重要的调性确立点",
        ],
        tags=["cadence", "strong", "root-position-required"],
    ),
    KBEntry(
        id="cadence-IAC",
        category="cadence",
        roman="*",
        name_zh="正格不完全终止 (IAC)",
        function="*",
        description="Imperfect Authentic Cadence. V → I，但低音不是根音到根音 (V6 → I, V → I6 等)，或高音不是 3→1。",
        voice_leading=[
            "V 的根音或高音位置与 PAC 不同",
            "终止感比 PAC 弱",
        ],
        common_uses=[
            "较弱的乐段结束",
            "连续终止（半终止和 PAC 之间的过渡）",
        ],
        tags=["cadence", "weaker", "non-root-position"],
    ),
    KBEntry(
        id="cadence-HC",
        category="cadence",
        roman="*",
        name_zh="半终止 (HC)",
        function="*",
        description="Half Cadence. 任何和弦 → V。最常见的是 ii → V 或 IV → V。",
        voice_leading=[
            "V 在强拍上",
            "前面的和弦常做属准备",
        ],
        common_uses=[
            "乐段中间的停顿",
            "问句的结束",
            "对比 PAC 的稳定性",
        ],
        tags=["cadence", "pause", "question"],
    ),
    KBEntry(
        id="cadence-DC",
        category="cadence",
        roman="*",
        name_zh="阻碍终止 (Deceptive Cadence)",
        function="*",
        description="V → vi (或 VI)。V 期待解决到 I 但落到下中音，造成'意外'。",
        voice_leading=[
            "V → vi 时 V 的导音仍上行到 vi 的根音 (3 音位置上)",
            "低音 5→6 (级进上行)",
        ],
        common_uses=[
            "避免终止感突然",
            "扩展乐段",
            "制造'意犹未尽'",
        ],
        tags=["cadence", "deceptive", "extension"],
    ),
    KBEntry(
        id="cadence-Plagal",
        category="cadence",
        roman="*",
        name_zh="变格终止 (Plagal)",
        function="*",
        description="IV → I (或 iv → i)。也被称为'Amen 终止'，常见于赞美诗。",
        voice_leading=[
            "低音 4→1（下行 5 度或上行 4 度）",
            "高音部 4→1（下行 3 度）",
        ],
        common_uses=[
            "赞美诗风格",
            "在正格终止后附加的'Plagal 加尾'",
        ],
        tags=["cadence", "soft", "amen"],
    ),
]


# ----- 副属/借用 (Secondary / Borrowed) -----
SECONDARY_ENTRIES: list[KBEntry] = [
    KBEntry(
        id="secondary-V/V",
        category="secondary",
        roman="V/V",  # 也写作 V7/V
        name_zh="V 的副属 (V/V)",
        function="D-of-D",
        description="V 的副属和弦 — 临时把 V 当成'主'，对它做属准备。通常是 D 大调（或其平行小调）的 V 解决到 V。",
        voice_leading=[
            "V/V 的 3 音 (A#) 上行解决到 V 的根音 (G)",
            "V/V → V 是标准的副属解决",
        ],
        common_uses=[
            "强化属准备",
            "增加和声色彩",
            "在正格终止前的'加强'",
        ],
        tags=["secondary-dominant", "intensification"],
    ),
    KBEntry(
        id="secondary-V/IV",
        category="secondary",
        roman="V/IV",
        name_zh="IV 的副属 (V/IV)",
        function="D-of-IV",
        description="IV 的副属和弦 — 临时把 IV 当成'主'，对它做属准备。在大调中是 C 大调的 V/IV。",
        voice_leading=[
            "V/IV → IV 是直接的副属解决",
        ],
        common_uses=[
            "强调下属",
            "在变格终止前的强化",
        ],
        tags=["secondary-dominant"],
    ),
    KBEntry(
        id="secondary-vii/V",
        category="secondary",
        roman="vii°/V",
        name_zh="V 的减七导音和弦 (vii°/V)",
        function="D-of-D",
        description="V 的减七导音和弦 — 比 V/V 更尖锐的副属准备。在大调中是小三和弦减小七度。",
        voice_leading=[
            "三个音程倾向性强的声部都需解决",
            "vii°/V → V 是强进行",
        ],
        common_uses=[
            "在终止前最尖锐的属准备",
            "增加不协和色彩",
        ],
        tags=["secondary-dominant", "dissonance", "leading-tone"],
    ),
    KBEntry(
        id="borrowed-bVI",
        category="borrowed",
        roman="bVI",
        name_zh="借用 bVI (降六级大三)",
        function="S",
        description="从小调（或平行小调）借用的降六级大三和弦。在 C 大调中是 Ab 大三。功能上属下属。",
        voice_leading=[
            "bVI 的根音常做小调色彩",
            "bVI 后常接 bVII 或 V",
        ],
        common_uses=[
            "突然转向小调色彩",
            "模态借用 (Modal mixture)",
            "增加浪漫派色彩",
        ],
        tags=["modal-mixture", "borrowed", "color"],
    ),
    KBEntry(
        id="borrowed-bIII",
        category="borrowed",
        roman="bIII",
        name_zh="借用 bIII (降三级大三)",
        function="T",
        description="从小调借用的降三级大三和弦。在 C 大调中是 Eb 大三。功能上等同大调的 I。",
        voice_leading=[
            "bIII → vi 是常见的同主音小调色彩",
        ],
        common_uses=[
            "突然同主音小调化",
            "在 III → vi 的连锁中",
        ],
        tags=["modal-mixture", "borrowed", "color"],
    ),
    KBEntry(
        id="borrowed-bVII",
        category="borrowed",
        roman="bVII",
        name_zh="借用 bVII (降七级大三)",
        function="S",
        description="从小调借用的降七级大三和弦。在 C 大调中是 Bb 大三。功能上等同大调的 S。",
        voice_leading=[
            "bVII 常作为下属准备",
            "bVII → I 类似 IV → I 的下属进行",
        ],
        common_uses=[
            "摇滚/流行常用",
            "下属变体",
        ],
        tags=["modal-mixture", "borrowed"],
    ),
]


# ----- 通用规则 (General rules, roman='*') -----
GENERAL_ENTRIES: list[KBEntry] = [
    KBEntry(
        id="general-voice-leading",
        category="general",
        roman="*",
        name_zh="声部进行通则",
        function="*",
        description="四部和声的 5 条基本通则：1) 保持共同音；2) 最近音区进；3) 处理不协和音程 (7 音下行，导音上行)；4) 避免平行五八度；5) 避免声部交叉和超越。",
        voice_leading=[
            "共同音保持不动",
            "上方三声部优先做最近音程移动",
            "7 音下行，4 音上行（不协和音程各自方向的解决）",
            "严格禁止：平行 P5/P8，隐伏 P5/P8，声部交叉",
        ],
        common_uses=[
            "四部和声编配基本规则",
            "任何和弦连接都需遵守",
        ],
        tags=["voice-leading", "fundamental"],
    ),
    KBEntry(
        id="general-textbook-style",
        category="general",
        roman="*",
        name_zh="课本例题风格 (Sposobin)",
        function="*",
        description="Sposobin《和声学教程》强调：1) 声部经济（共同音保持）；2) 旋律流畅（避免大跳）；3) 功能清晰（主/属/下属分明）；4) 终止式标准 (PAC/HC)。",
        voice_leading=[
            "声部之间距离合理：上三声部紧凑，间距多在 8 度内",
            "尽量保持声部独立性",
        ],
        common_uses=[
            "教学标准答案风格",
            "在考试中默认期望风格",
        ],
        tags=["textbook", "sposobin", "style"],
    ),
]


# ----- 课本例题 (Textbook examples) -----
TEXTBOOK_ENTRIES: list[KBEntry] = [
    KBEntry(
        id="textbook-P0",
        category="textbook",
        roman="*",
        name_zh="P0 - I-IV-V-I 经典终止 (C 大调)",
        function="*",
        description="大调最简单的正格终止。每个小节 4 个四分音符, 旋律下行级进, 最低音 C-G-C。常见和声: m1 I, m2 IV (F 大三), m3 V (G 大三), m4 I。",
        common_uses=[
            "入门级终止",
            "C 大调调性建立",
        ],
        tags=["P0", "beginner", "C-major"],
    ),
    KBEntry(
        id="textbook-P5",
        category="textbook",
        roman="*",
        name_zh="P5 - a 小调和声终止",
        function="*",
        description="a 小调 (自然/和声/旋律) 的和声终止。和声小调要升高 7 级 (G#)。终止中常用 V (大调) 借用解决到 i。",
        common_uses=[
            "小调终止入门",
            "和声小调导音处理",
        ],
        tags=["P5", "a-minor", "harmonic-minor"],
    ),
    KBEntry(
        id="textbook-P7.5",
        category="textbook",
        roman="*",
        name_zh="P7.5 - 转调终止",
        function="*",
        description="在终止前或终止中通过副属/中介和弦转调到新调。常见模式: I (C) → V/V (D 大三) → V (G) → I (G)，或通过共同和弦转调。",
        common_uses=[
            "转调终止 (Modulating cadence)",
            "段落对比",
        ],
        tags=["P7.5", "modulation"],
    ),
    KBEntry(
        id="textbook-P3",
        category="textbook",
        roman="*",
        name_zh="P3 - 增六和弦 (Ger+6 / It+6 / Fr+6)",
        function="*",
        description="增六和弦是特殊的属准备和弦，包含 b6 度音程。Ger+6 (德国增六) 解决到 V，It+6 (意大利增六) 解决到 i 或 V，Fr+6 (法国增六) 解决到 V 但多一个 4 音。",
        common_uses=[
            "强调属功能",
            "增加色彩",
        ],
        tags=["P3", "augmented-sixth"],
    ),
    KBEntry(
        id="textbook-P24",
        category="textbook",
        roman="*",
        name_zh="P24+ - 副属体系",
        function="*",
        description="连续或嵌套的副属和弦: V/V → V, V/IV → IV, V/vi → vi, vii°/V → V 等。系统化的'连锁属准备'。",
        common_uses=[
            "浪漫派/印象派手法",
            "延迟解决以增加紧张度",
        ],
        tags=["P24", "secondary-system"],
    ),
]


ALL_ENTRIES: list[KBEntry] = (
    TRIAD_ENTRIES + SEVENTH_ENTRIES + CADENCE_ENTRIES + SECONDARY_ENTRIES + GENERAL_ENTRIES + TEXTBOOK_ENTRIES
)


class HarmonyKB:
    """RAG 检索入口。"""

    def __init__(self, entries: list[KBEntry] | None = None) -> None:
        self.entries = list(entries) if entries is not None else list(ALL_ENTRIES)

    def lookup(self, roman: str, *, include_general: bool = True) -> list[KBEntry]:
        """根据罗马数字查找相关 KB 条目。"""
        hits: list[KBEntry] = []
        for entry in self.entries:
            if entry.matches(roman):
                if entry.roman == "*" and not include_general:
                    continue
                hits.append(entry)
        # 通配规则放最后
        hits.sort(key=lambda e: (0 if e.roman != "*" else 1, e.id))
        return hits

    def lookup_many(self, romans: Iterable[str], *, max_per: int = 2) -> list[KBEntry]:
        """对多个罗马数字逐个查，按出现顺序去重。"""
        seen: set[str] = set()
        out: list[KBEntry] = []
        for r in romans:
            for hit in self.lookup(r)[:max_per]:
                if hit.id in seen:
                    continue
                seen.add(hit.id)
                out.append(hit)
        return out

    def format_for_prompt(self, entries: list[KBEntry]) -> str:
        """把 KB 条目格式化成可塞进 LLM prompt 的中文文本。"""
        if not entries:
            return "（无相关规则）"
        lines: list[str] = []
        for e in entries:
            block = [f"### {e.name_zh} ({e.roman}) — {e.id}"]
            if e.function and e.function != "*":
                block.append(f"功能：{e.function}")
            block.append(f"说明：{e.description}")
            if e.voice_leading:
                block.append("声部进行：" + "；".join(e.voice_leading))
            if e.common_uses:
                block.append("常见用法：" + "；".join(e.common_uses))
            lines.append("\n".join(block))
        return "\n\n".join(lines)


_DEFAULT_KB: HarmonyKB | None = None


def get_default_kb() -> HarmonyKB:
    """懒加载默认 KB（避免启动开销）。"""
    global _DEFAULT_KB
    if _DEFAULT_KB is None:
        _DEFAULT_KB = HarmonyKB()
    return _DEFAULT_KB
