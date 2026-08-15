"""经典作品曲式+和声分析案例库。

每条 RepertoireCase = 一段经典作品的关键片段
- 曲式位置
- 和声进行
- 教学价值

用于：
- ReAct Agent 工具 `query_repertoire(query, style)` 检索相似案例
- LLM 讲解时引用（"参见贝多芬 Op.13 第 1 乐章..."）
- 教学时让学生对照"大师怎么处理这个和声进行"

引用来源清晰，所有案例都是学界公认的典型作品。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class RepertoireCase:
    """一个经典作品案例。"""

    id: str
    composer: str
    title: str
    opus: str  # 例 "Op.13", "BWV 846", "K.545"
    key: str  # 主调 例 "c minor", "Eb major"
    excerpt_location: str  # 例 "1st mvt, mm.1-8 (opening)" / "exposition 2nd theme"
    form: str  # 曲式: "sonata-allegro" / "ternary" / "binary" / "fugue" / "rondo" / "strophic"
    harmonic_summary: tuple[str, ...]  # 罗马数字序列
    key_changes: tuple[str, ...] = field(default_factory=tuple)  # 调性变化 例 ("3:iv", "5:VI")
    cadences: tuple[str, ...] = field(default_factory=tuple)  # 终止式 例 ("PAC", "HC")
    pedagogical_value: str = ""  # 教学价值
    tags: tuple[str, ...] = field(default_factory=tuple)


# ============================================================
# 8 个经典案例
# ============================================================

REPERTOIRE_CASES: tuple[RepertoireCase, ...] = (
    # ----- 1. 贝多芬《悲怆》奏鸣曲 第 1 乐章 -----
    RepertoireCase(
        id="beethoven-pathetique-op13-m1",
        composer="Beethoven",
        title="Piano Sonata No.8 'Pathétique'",
        opus="Op.13",
        key="c minor",
        excerpt_location="1st mvt, mm.1-10 (slow intro + Allegro opening)",
        form="sonata-allegro",
        harmonic_summary=("i", "iv6", "V", "i", "i6", "iv", "V", "i"),
        key_changes=(),
        cadences=("HC", "PAC"),
        pedagogical_value=(
            "c 小调慢引子 4 小节用减七和弦 (vii°7) 引出属七, "
            "Allegro 主题用严格的 T-S-D-T 8 小节乐句, "
            "完美的 Sposobin 范本：终止 64 (cadential 6/4) → V → i 完整呈现"
        ),
        tags=("sposobin", "sonata", "c-minor", "PAC", "textbook"),
    ),
    # ----- 2. 肖邦夜曲 Op.9 No.2 -----
    RepertoireCase(
        id="chopin-nocturne-op9-2",
        composer="Chopin",
        title="Nocturne Op.9 No.2",
        opus="Op.9 No.2",
        key="Eb major",
        excerpt_location="mm.1-8 (A section opening)",
        form="ternary (ABA)",
        harmonic_summary=("I", "V6", "I", "VI", "ii6", "V7", "I"),
        key_changes=(),
        cadences=("PAC",),
        pedagogical_value=(
            "左手分解和弦伴奏的经典；A 段是简单的 I-V6-I-VI-ii6-V7-I 进行，"
            "展示了 Sposobin 体系下'附加六和弦'(added 6th) 与 ii6-V7-I 终止的运用"
        ),
        tags=("chopin", "nocturne", "Eb-major", "ternary", "sposobin"),
    ),
    # ----- 3. 巴赫 WTC Book 1 C 大调前奏曲 -----
    RepertoireCase(
        id="bach-wtc1-cPrelude-bwv846",
        composer="Bach",
        title="The Well-Tempered Clavier, Book 1 — Prelude in C major",
        opus="BWV 846",
        key="C major",
        excerpt_location="mm.1-8 (opening arpeggiated texture)",
        form="continuous (single texture)",
        harmonic_summary=("I", "V6/4", "I6", "ii6/5", "V7", "I"),
        key_changes=(),
        cadences=("PAC",),
        pedagogical_value=(
            "巴赫的分解和弦前奏曲：全曲是 I-V6/4-I6-ii6/5-V7-I 不断重复+扩展。"
            "教学要点：每个和弦的第一转位 (6/4) 强化低音线进行，"
            "V7 的七音必须下行解决到 3 音 (导音)。"
        ),
        tags=("bach", "wtc", "C-major", "arpeggiated", "PEDAGOGY", "sposobin"),
    ),
    # ----- 4. 莫扎特 K.545 奏鸣曲 第 1 乐章 -----
    RepertoireCase(
        id="mozart-k545-m1",
        composer="Mozart",
        title="Piano Sonata K.545 1st Movement",
        opus="K.545",
        key="C major",
        excerpt_location="1st mvt, mm.1-8 (1st theme)",
        form="sonata-allegro",
        harmonic_summary=("I", "V7", "I", "IV", "V7", "I", "vi", "ii6", "V7", "I"),
        key_changes=(),
        cadences=("PAC",),
        pedagogical_value=(
            "古典时期最简明的 sonata-allegro 范本："
            "T-S-D-T 完全进行 + vi-ii6-V7-I 阻碍终止变体。"
            "无变化音，无副属，纯粹的 Sposobin 教科书。"
        ),
        tags=("mozart", "classical", "C-major", "sonata", "TEXTBOOK", "sposobin"),
    ),
    # ----- 5. 德彪西《牧神午后前奏曲》 -----
    RepertoireCase(
        id="debussy-faun-excerpt",
        composer="Debussy",
        title="Prélude à l'après-midi d'un faune",
        opus="L.86",
        key="E major (modal inflection)",
        excerpt_location="opening 8 measures (flute solo)",
        form="free (through-composed)",
        harmonic_summary=("E7", "F#7(b9)", "B7(b9)", "E7(b9)"),
        key_changes=(),
        cadences=(),
        pedagogical_value=(
            "印象派开山之作，**典型的 modal/jazz profile 案例**："
            "全音阶 + 9 音属和弦 + 平行五八度作色彩手段。"
            "Sposobin 体系无法解释（无 T/S/D），需要调式/延伸和声分析。"
        ),
        tags=("debussy", "impressionist", "modal", "extended", "9th-chord"),
    ),
    # ----- 6. 巴赫 WTC Book 1 C 大调赋格 -----
    RepertoireCase(
        id="bach-wtc1-cFugue-bwv846",
        composer="Bach",
        title="The Well-Tempered Clavier, Book 1 — Fugue in C major",
        opus="BWV 846",
        key="C major",
        excerpt_location="mm.1-12 (subject + answer + counter-exposition)",
        form="fugue",
        harmonic_summary=("I", "V", "I", "V7", "I", "IV", "V7", "I"),
        key_changes=(),
        cadences=("PAC",),
        pedagogical_value=(
            "对位法 + 功能和声的完美结合。"
            "主题在主调，下方声部答题 (answer) 在属调；"
            "5 小节处 IV-V7-I 完成第一个明确终止。"
        ),
        tags=("bach", "fugue", "C-major", "contrapuntal", "sposobin"),
    ),
    # ----- 7. 贝多芬 Op.13 慢乐章 -----
    RepertoireCase(
        id="beethoven-pathetique-op13-m2",
        composer="Beethoven",
        title="Piano Sonata No.8 'Pathétique' 2nd Movement",
        opus="Op.13",
        key="Ab major",
        excerpt_location="2nd mvt, mm.1-16 (theme + variation 1)",
        form="theme-and-variations (3 variations)",
        harmonic_summary=("I", "V7", "I", "VI", "V7/V", "V7", "I"),
        key_changes=(),
        cadences=("PAC",),
        pedagogical_value=(
            "降 A 大调的慢乐章展示了副属和弦 V7/V → V → I 的完整应用。"
            "VI 是 Sposobin 体系下的下属准备 (S 功能变体)。"
        ),
        tags=("beethoven", "slow-mvt", "Ab-major", "secondary-dominant", "sposobin"),
    ),
    # ----- 8. 柴可夫斯基《天鹅湖》场景 -----
    RepertoireCase(
        id="tchaikovsky-swan-lake-excerpt",
        composer="Tchaikovsky",
        title="Swan Lake, Act II — Scene",
        opus="Op.20a",
        key="Bb minor (modal mixture)",
        excerpt_location="opening 8 measures (oboe solo)",
        form="scene (through-composed)",
        harmonic_summary=("i", "bII (Neapolitan)", "V7", "i", "iv", "V7", "i"),
        key_changes=(),
        cadences=("PAC",),
        pedagogical_value=(
            "Neapolitan (bII) 在小调终止前的标准用法。"
            "Sposobin 体系下 bII 归 S 组 (substitute)；"
            "教学要点：bII 6 (第一转位) 比根音位置更常用，因为低音下行到 V 根音更流畅。"
        ),
        tags=("tchaikovsky", "ballet", "Bb-minor", "neapolitan", "borrowed", "sposobin"),
    ),
)


def find_by_tag(*tags: str) -> list[RepertoireCase]:
    """按 tag 检索案例 (任一 tag 匹配即返回)。"""
    return [c for c in REPERTOIRE_CASES if any(t in c.tags for t in tags)]


def find_by_key(key: str) -> list[RepertoireCase]:
    """按主调检索 (大小写不敏感，子串匹配)。"""
    key_lower = key.lower()
    return [c for c in REPERTOIRE_CASES if key_lower in c.key.lower()]


def find_by_composer(composer: str) -> list[RepertoireCase]:
    """按作曲家检索。"""
    composer_lower = composer.lower()
    return [c for c in REPERTOIRE_CASES if composer_lower in c.composer.lower()]


def get_case(case_id: str) -> Optional[RepertoireCase]:
    """按 ID 取案例。"""
    for c in REPERTOIRE_CASES:
        if c.id == case_id:
            return c
    return None
