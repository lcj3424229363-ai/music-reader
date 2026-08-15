"""P20.3.7 — Gold Provenance & Score Acquisition 测试.

核心原则:
- gold benchmark 必须有 evidence chain (provenance) 才能可信
- 没有 provenance 的 gold = "手写猜测", 不可信
- find_fully_reviewed() 才是真正可进 benchmark 的 case

测试范围:
1. Provenance dataclass 字段完整性
2. from_dict 兼容旧 JSON (无 provenance 字段 → 默认空 Provenance)
3. helper 函数: find_needs_provenance / find_by_provenance_status / find_fully_reviewed
4. 8 个 gold 全部有 provenance 字段 (acquired_status != "available")
5. 不破坏现有 35 个 test_p20_3_eval.py 测试
"""
from __future__ import annotations

import json
import os
import sys
import pytest

# 让 data.eval 可导入
HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from data.eval.schema import (
    Provenance,
    EvalCase,
    load_all_gold,
    find_needs_provenance,
    find_by_provenance_status,
    find_fully_reviewed,
    gold_provenance_summary,
)


# ----- 单元测试 -----

class TestProvenanceDataclass:
    """Provenance dataclass 字段完整性."""

    def test_default_provenance_empty(self):
        p = Provenance()
        assert p.source_score == ""
        assert p.source_url == ""
        assert p.source_format == ""
        assert p.measure_range == ""
        assert p.annotator == ""
        assert p.annotate_date == ""
        assert p.confidence == 0.0
        assert p.evidence_chain == []
        assert p.acquired_status == "needs_imslp"  # 默认 = 还没谱面
        assert p.review_status == "raw"
        assert p.notes == ""

    def test_provenance_with_values(self):
        p = Provenance(
            source_score="mozart_k545.mxl",
            source_url="https://imslp.org/...",
            source_format="musicxml",
            measure_range="mm.1-8",
            annotator="human/alice",
            annotate_date="2026-08-11",
            confidence=0.95,
            evidence_chain=["music21 corpus", "IMSLP"],
            acquired_status="available",
            review_status="expert_reviewed",
            notes="Sposobin V1 gold",
        )
        assert p.source_score == "mozart_k545.mxl"
        assert p.confidence == 0.95
        assert p.acquired_status == "available"
        assert p.review_status == "expert_reviewed"
        assert len(p.evidence_chain) == 2


class TestProvenanceBackwardCompat:
    """兼容旧 JSON (无 provenance 字段 → 默认空 Provenance)."""

    def test_from_dict_without_provenance(self):
        """旧 JSON 没有 provenance 字段也能加载."""
        old_dict = {
            "metadata": {
                "id": "test_case",
                "composer": "Test",
                "title": "Test",
            },
            "analysis": {
                "key": "C major",
                "harmony": {
                    "roman_progression": ["I", "V7", "I"],
                    "functional_analysis": ["T", "D", "T"],
                },
                "cadences": [],
            },
        }
        case = EvalCase.from_dict(old_dict)
        # 必须有 default provenance
        assert isinstance(case.provenance, Provenance)
        assert case.provenance.acquired_status == "needs_imslp"
        assert case.provenance.review_status == "raw"

    def test_from_dict_with_provenance(self):
        """新 JSON 有 provenance 字段能正确加载."""
        new_dict = {
            "metadata": {"id": "test_case", "composer": "Test", "title": "Test"},
            "analysis": {"key": "C major", "harmony": {"roman_progression": [], "functional_analysis": []}, "cadences": []},
            "provenance": {
                "source_score": "test.mxl",
                "source_url": "https://imslp.org/test",
                "acquired_status": "available",
                "review_status": "human_annotated",
                "confidence": 0.85,
            },
        }
        case = EvalCase.from_dict(new_dict)
        assert case.provenance.source_score == "test.mxl"
        assert case.provenance.acquired_status == "available"
        assert case.provenance.review_status == "human_annotated"
        assert case.provenance.confidence == 0.85


class TestProvenanceHelpers:
    """provenance helper 函数."""

    def test_find_needs_provenance(self):
        """P20.3.7 当前所有 8 个 gold 都 needs_imslp."""
        needs = find_needs_provenance()
        # 8 个 gold, 全部 needs_imslp
        assert len(needs) == 8
        for c in needs:
            assert c.provenance.acquired_status != "available"
            assert c.provenance.acquired_status == "needs_imslp"

    def test_find_by_provenance_status(self):
        """按 acquired_status 过滤."""
        needs = find_by_provenance_status("needs_imslp")
        assert len(needs) == 8
        avail = find_by_provenance_status("available")
        assert len(avail) == 0

    def test_find_fully_reviewed(self):
        """P20.3.7 当前 0 个 fully reviewed (没谱面 + 没 expert review)."""
        reviewed = find_fully_reviewed()
        assert len(reviewed) == 0

    def test_gold_provenance_summary(self):
        """统计报告."""
        summary = gold_provenance_summary()
        assert summary["n_total"] == 8
        assert summary["by_acquired_status"].get("needs_imslp", 0) == 8
        assert summary["by_review_status"].get("raw", 0) == 8


class TestAllGoldHaveProvenance:
    """8 个 gold 必须全部有 provenance 字段 (P20.3.7 后置)."""

    def test_all_gold_loaded(self):
        cases = load_all_gold()
        assert len(cases) == 8

    def test_all_gold_have_provenance_field(self):
        """8 个 gold JSON 全部含 provenance key."""
        cases = load_all_gold()
        for c in cases:
            assert hasattr(c, "provenance")
            assert isinstance(c.provenance, Provenance)

    def test_all_gold_have_measure_range(self):
        """measure_range 必须从 excerpt 解析出来."""
        cases = load_all_gold()
        for c in cases:
            mr = c.provenance.measure_range
            assert mr.startswith("mm."), f"{c.metadata.id} measure_range 异常: {mr!r}"

    def test_all_gold_have_imslp_url(self):
        """source_url 沿用 metadata.source_url (IMSLP 入口)."""
        cases = load_all_gold()
        for c in cases:
            assert c.provenance.source_url != ""
            assert c.provenance.source_url == c.metadata.source_url

    def test_all_gold_provenance_status_is_needs_imslp(self):
        """P20.3.7 结论: 8 个 case 都需要从 IMSLP 获取谱面."""
        cases = load_all_gold()
        for c in cases:
            assert c.provenance.acquired_status == "needs_imslp", (
                f"{c.metadata.id} status={c.provenance.acquired_status!r} 期望 needs_imslp"
            )

    def test_all_gold_review_status_is_raw(self):
        """没人工校过."""
        cases = load_all_gold()
        for c in cases:
            assert c.provenance.review_status == "raw"


class TestProvenanceJsonRoundTrip:
    """JSON 序列化往返不丢失."""

    def test_to_dict_includes_provenance(self):
        cases = load_all_gold()
        for c in cases:
            d = c.to_dict()
            assert "provenance" in d
            assert d["provenance"]["acquired_status"] == c.provenance.acquired_status

    def test_json_file_round_trip(self, tmp_path):
        """存盘 → 读回 数据一致."""
        cases = load_all_gold()
        c = cases[0]  # mozart (alphabetical)
        # 写
        path = tmp_path / "test.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(c.to_dict(), f, ensure_ascii=False)
        # 读
        c2 = EvalCase.from_json_file(str(path))
        assert c2.metadata.id == c.metadata.id
        assert c2.provenance.acquired_status == c.provenance.acquired_status
        assert c2.provenance.measure_range == c.provenance.measure_range


class TestProvenanceQuery:
    """query 类测试 (类似 P20.3 的 find_by_style)."""

    def test_provenance_statuses_defined(self):
        """4 种 acquired_status 应当被允许."""
        allowed = {"available", "needs_imslp", "needs_humdrum", "needs_pdf_ocr"}
        cases = load_all_gold()
        for c in cases:
            assert c.provenance.acquired_status in allowed, (
                f"{c.metadata.id} 未知 status: {c.provenance.acquired_status!r}"
            )

    def test_review_statuses_defined(self):
        """3 种 review_status 应当被允许."""
        allowed = {"raw", "human_annotated", "expert_reviewed"}
        cases = load_all_gold()
        for c in cases:
            assert c.provenance.review_status in allowed


# ----- 文档化测试: P20.3.7 当前状态快照 -----

def test_p20_3_7_snapshot():
    """P20.3.7 状态快照: 8 个 gold 全部 needs_imslp, 0 fully reviewed.

    这是文档化测试, 提醒后续 P20.4/P20.5:
    - 拿到 IMSLP MusicXML → acquired_status 改 "available"
    - 人工标注 → review_status 改 "human_annotated"
    - expert 审定 → review_status 改 "expert_reviewed"
    - 完全满足才能进 benchmark.
    """
    cases = load_all_gold()
    assert len(cases) == 8
    n_available = len([c for c in cases if c.provenance.acquired_status == "available"])
    n_reviewed = len([c for c in cases if c.provenance.review_status == "expert_reviewed"])
    assert n_available == 0, f"当前应有 0 个 available, 实际 {n_available}"
    assert n_reviewed == 0, f"当前应有 0 个 expert_reviewed, 实际 {n_reviewed}"
