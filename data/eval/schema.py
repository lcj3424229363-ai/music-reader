"""EvalCase Schema — 评价数据集的核心 dataclass。

每个 gold JSON 文件描述一个经典作品片段的人工标准答案。
被 benchmark runner + Agent 对比用。

字段设计原则：
- analysis_framework 字段：jazz 必须用 jazz_functional，不能混 sposobin
- alternative_analysis 字段：音乐理论非唯一答案（多解并存）
- needs_expert_review 字段：标记我手写不准确的字段，等 expert 校

P20.3.7 增加 provenance 字段 (evidence chain):
- 没有 source_score + annotator + evidence 的 gold = "手写猜测", 不可信
- provenance 字段让 benchmark 区分 "可信 gold" (有谱面 + 人工标注) vs "占位 gold" (待标)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, Literal


# ----- 子结构 -----

@dataclass
class Metadata:
    id: str
    composer: str
    title: str
    opus: str = ""
    period: str = ""  # 例 "Classical (1750-1820)" / "Jazz Standard (1945)"
    style_profile: str = "functional_classical"  # functional_classical/sposobin/schenkerian/jazz/modal
    analysis_framework: str = "functional"  # functional / jazz_functional / modal / schenkerian
    excerpt: str = ""  # 例 "mm.1-8 (opening)" / "A section"
    difficulty: int = 1  # 1-5 (1=简单, 5=难)
    source_url: str = ""  # IMSLP / 公开乐谱来源 (legacy, 详见 provenance)


@dataclass
class Provenance:
    """P20.3.7 引入 — evidence chain.

    没有 provenance 字段的 gold = "手写猜测" 不可信.
    有 provenance 的 gold = "谱面 + 人工标注" 可信.

    字段说明:
    - source_score: MusicXML/mxl/mscz 文件名 (相对 scores/ 目录)
    - source_url: IMSLP / 公开来源 URL
    - measure_range: 例 "mm.1-8"
    - annotator: "human/<name>" / "music21-auto" / "ai/<model>"
    - annotate_date: "2026-..." (ISO 8601)
    - confidence: 0-1 (标记者自信度)
    - evidence_chain: 列出 ["music21 corpus", "IMSLP", "Riemenschneider"] 等依据
    - acquired_status: "available" / "needs_imslp" / "needs_humdrum" / "needs_pdf_ocr"
    - review_status: "raw" / "human_annotated" / "expert_reviewed"
    """
    source_score: str = ""        # 例 "mozart_k545.mxl"
    source_url: str = ""          # IMSLP URL
    source_format: str = ""       # "musicxml" / "midi" / "kern" / "pdf" / "mscz"
    measure_range: str = ""       # 例 "mm.1-8"
    annotator: str = ""           # "human/<name>" / "music21-auto" / "ai/<model>"
    annotate_date: str = ""       # ISO 8601
    confidence: float = 0.0       # 0-1
    evidence_chain: list[str] = field(default_factory=list)  # 例 ["music21 corpus", "IMSLP"]
    acquired_status: str = "needs_imslp"  # "available" / "needs_imslp" / "needs_humdrum" / "needs_pdf_ocr"
    review_status: str = "raw"    # "raw" / "human_annotated" / "expert_reviewed"
    notes: str = ""               # 备注


@dataclass
class PhraseStructure:
    type: str = ""  # "period" / "sentence" / "ternary" / "continuous" / "32-bar-form" / ...
    length: str = ""  # 例 "4+4" / "8+8+8+8" / "16+8+8+8"
    antecedent: str = ""
    consequent: str = ""


@dataclass
class Harmony:
    roman_progression: list[str] = field(default_factory=list)  # 例 ["I", "V7", "I", "IV"]
    functional_analysis: list[str] = field(default_factory=list)  # 例 ["T", "D", "T", "S"]


@dataclass
class Cadence:
    type: str  # "PAC" / "IAC" / "HC" / "DC" / "deceptive" / "no functional cadence" / "modal-end"
    measure: int  # 0 表示"无功能终止"（modal/whole-tone 类）
    confidence: float = 1.0  # 0-1
    notes: str = ""


@dataclass
class Analysis:
    key: str = ""  # 例 "C major" / "c minor" / "D dorian" / "G minor"
    key_changes: list[dict] = field(default_factory=list)  # 例 [{"measure": 5, "new_key": "G major"}]
    phrase_structure: PhraseStructure = field(default_factory=PhraseStructure)
    harmony: Harmony = field(default_factory=Harmony)
    cadences: list[Cadence] = field(default_factory=list)
    form_role: str = ""  # 例 "1st theme (sonata-allegro exposition)"


@dataclass
class AlternativeAnalysis:
    """音乐理论非唯一答案：多解并存。"""
    framework: str  # "sposobin" / "schenkerian" / "modal" / "jazz_functional" / ...
    interpretation: str  # 此框架下的解释
    confidence: float = 1.0
    notes: str = ""  # 备注（例 "Debussy does NOT use this — leads to wrong analysis"）


@dataclass
class EvalCase:
    """一个 gold benchmark 案例。"""
    metadata: Metadata
    analysis: Analysis
    errors_expected: list[str] = field(default_factory=list)  # 期望 Agent 标出的错误
    teaching_points: list[str] = field(default_factory=list)  # 教学要点
    expected_agent_behavior: str = ""  # Agent 在该 case 上应该做到什么 (P20.3 必填)
    failure_modes: list[str] = field(default_factory=list)  # 已知/常见失败模式 (P20.3 必填)
    alternative_analysis: list[AlternativeAnalysis] = field(default_factory=list)
    needs_expert_review: bool = False  # 标记待 expert 校
    review_notes: str = ""  # expert review 时的备注
    provenance: Provenance = field(default_factory=Provenance)  # P20.3.7 evidence chain

    @classmethod
    def from_json_file(cls, path: str) -> "EvalCase":
        """从 JSON 文件加载。"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, d: dict) -> "EvalCase":
        """从 dict 构造。"""
        meta = Metadata(**d["metadata"])
        ana_d = d["analysis"]

        # PhraseStructure
        ps_d = ana_d.get("phrase_structure", {})
        ps = PhraseStructure(**ps_d) if ps_d else PhraseStructure()

        # Harmony
        h_d = ana_d.get("harmony", {})
        harmony = Harmony(
            roman_progression=h_d.get("roman_progression", []),
            functional_analysis=h_d.get("functional_analysis", []),
        )

        # Cadences
        cadences = [Cadence(**c) for c in ana_d.get("cadences", [])]

        # Key changes
        kc = ana_d.get("key_changes", [])

        ana = Analysis(
            key=ana_d.get("key", ""),
            key_changes=kc,
            phrase_structure=ps,
            harmony=harmony,
            cadences=cadences,
            form_role=ana_d.get("form_role", ""),
        )

        # Alternative analysis
        alts = [AlternativeAnalysis(**a) for a in d.get("alternative_analysis", [])]

        # P20.3.7 Provenance — 兼容旧 JSON (无 provenance 字段时给空 Provenance)
        prov_d = d.get("provenance", {})
        provenance = Provenance(**prov_d) if prov_d else Provenance()

        return cls(
            metadata=meta,
            analysis=ana,
            errors_expected=d.get("errors_expected", []),
            teaching_points=d.get("teaching_points", []),
            expected_agent_behavior=d.get("expected_agent_behavior", ""),
            failure_modes=d.get("failure_modes", []),
            alternative_analysis=alts,
            needs_expert_review=d.get("needs_expert_review", False),
            review_notes=d.get("review_notes", ""),
            provenance=provenance,
        )

    def to_dict(self) -> dict:
        """导出为 dict (供 benchmark runner 用)。"""
        return {
            "metadata": asdict(self.metadata),
            "analysis": {
                "key": self.analysis.key,
                "key_changes": self.analysis.key_changes,
                "phrase_structure": asdict(self.analysis.phrase_structure),
                "harmony": asdict(self.analysis.harmony),
                "cadences": [asdict(c) for c in self.analysis.cadences],
                "form_role": self.analysis.form_role,
            },
            "errors_expected": self.errors_expected,
            "teaching_points": self.teaching_points,
            "expected_agent_behavior": self.expected_agent_behavior,
            "failure_modes": self.failure_modes,
            "alternative_analysis": [asdict(a) for a in self.alternative_analysis],
            "needs_expert_review": self.needs_expert_review,
            "review_notes": self.review_notes,
            "provenance": asdict(self.provenance),
        }


# ----- 加载器 -----

GOLD_DIR = os.path.join(os.path.dirname(__file__), "gold")


def load_all_gold() -> list[EvalCase]:
    """加载 gold/ 目录下所有 JSON。"""
    cases = []
    if not os.path.isdir(GOLD_DIR):
        return cases
    for name in sorted(os.listdir(GOLD_DIR)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(GOLD_DIR, name)
        try:
            cases.append(EvalCase.from_json_file(path))
        except Exception as e:
            print(f"[warn] failed to load {name}: {e}")
    return cases


def get_gold(case_id: str) -> Optional[EvalCase]:
    """按 ID 取 gold 案例。"""
    path = os.path.join(GOLD_DIR, f"{case_id}.json")
    if not os.path.exists(path):
        return None
    return EvalCase.from_json_file(path)


def find_by_style(style_profile: str) -> list[EvalCase]:
    """按 style_profile 过滤。"""
    return [c for c in load_all_gold() if c.metadata.style_profile == style_profile]


def find_needs_expert_review() -> list[EvalCase]:
    """返回所有 needs_expert_review=True 的案例。"""
    return [c for c in load_all_gold() if c.needs_expert_review]


def gold_summary() -> dict:
    """返回数据集统计。"""
    cases = load_all_gold()
    by_style = {}
    by_review = {"needs_review": 0, "reviewed": 0}
    for c in cases:
        s = c.metadata.style_profile
        by_style[s] = by_style.get(s, 0) + 1
        if c.needs_expert_review:
            by_review["needs_review"] += 1
        else:
            by_review["reviewed"] += 1
    return {
        "n_total": len(cases),
        "by_style": by_style,
        "by_review": by_review,
    }


# ----- P20.3.7 Provenance helpers -----

def find_needs_provenance() -> list[EvalCase]:
    """返回所有还没谱面的 case (acquired_status != "available")."""
    return [
        c for c in load_all_gold()
        if c.provenance.acquired_status != "available"
    ]


def find_by_provenance_status(status: str) -> list[EvalCase]:
    """按 acquired_status 过滤. status 例: 'needs_imslp' / 'available'."""
    return [
        c for c in load_all_gold()
        if c.provenance.acquired_status == status
    ]


def find_fully_reviewed() -> list[EvalCase]:
    """返回谱面 + 人工标注 + expert review 都齐的 case (可进 benchmark)."""
    return [
        c for c in load_all_gold()
        if c.provenance.acquired_status == "available"
        and c.provenance.review_status == "expert_reviewed"
    ]


def gold_provenance_summary() -> dict:
    """返回 P20.3.7 provenance 状态统计."""
    cases = load_all_gold()
    by_acquired = {}
    by_review = {}
    for c in cases:
        a = c.provenance.acquired_status or "unknown"
        r = c.provenance.review_status or "unknown"
        by_acquired[a] = by_acquired.get(a, 0) + 1
        by_review[r] = by_review.get(r, 0) + 1
    return {
        "n_total": len(cases),
        "by_acquired_status": by_acquired,
        "by_review_status": by_review,
    }
