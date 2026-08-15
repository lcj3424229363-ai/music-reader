"""P20.3 V1 单元测试 — 斯波索宾核心评价集。

V1 范围（不再扩 jazz/modal/pop）：
- 8 个 gold case, 全部 Sposobin 体系
- 不再要求覆盖 jazz/modal
- P20.3 报告目标 = 斯波索宾体系下准确率
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from data.eval.schema import (
    EvalCase, Metadata, Analysis, PhraseStructure, Harmony, Cadence,
    AlternativeAnalysis, load_all_gold, get_gold, find_by_style,
    find_needs_expert_review, gold_summary,
)
from data.eval.music21_draft import generate_draft


V1_CASE_IDS = {
    "bach_wtc_prelude_bwv846",
    "bach_wtc_fugue_bwv846",
    "mozart_k545_m1",
    "beethoven_pathetique_m1",
    "haydn_hobxvi52_m1",
    "chopin_op9_no2",
    "chopin_op28_no20",
    "schubert_op90_no3",
}


# ============================================================
# Schema 数据类
# ============================================================

class TestSchemaDataclasses:
    def test_metadata_construct(self):
        m = Metadata(
            id="test_1", composer="Test Composer", title="Test Piece",
            opus="Op.1", style_profile="sposobin",
        )
        assert m.id == "test_1"
        assert m.style_profile == "sposobin"

    def test_phrase_structure(self):
        ps = PhraseStructure(type="period", length="4+4")
        assert ps.type == "period"

    def test_harmony(self):
        h = Harmony(roman_progression=["I", "V7", "I"], functional_analysis=["T", "D", "T"])
        assert len(h.roman_progression) == 3

    def test_cadence(self):
        c = Cadence(type="PAC", measure=8, confidence=0.95)
        assert c.type == "PAC"

    def test_eval_case_with_new_fields(self):
        ec = EvalCase(
            metadata=Metadata(id="t", composer="c", title="t"),
            analysis=Analysis(),
            expected_agent_behavior="do X",
            failure_modes=["Y", "Z"],
        )
        assert ec.expected_agent_behavior == "do X"
        assert len(ec.failure_modes) == 2


class TestSchemaFromDict:
    def test_load_with_new_fields(self):
        d = {
            "metadata": {
                "id": "minimal",
                "composer": "X",
                "title": "Y",
                "style_profile": "sposobin",
            },
            "analysis": {"key": "C major"},
            "expected_agent_behavior": "test",
            "failure_modes": ["fail1", "fail2"],
        }
        c = EvalCase.from_dict(d)
        assert c.expected_agent_behavior == "test"
        assert c.failure_modes == ["fail1", "fail2"]

    def test_to_dict_round_trip_preserves_new_fields(self):
        d = {
            "metadata": {
                "id": "rt", "composer": "X", "title": "Y",
                "style_profile": "sposobin",
            },
            "analysis": {"key": "C major"},
            "expected_agent_behavior": "do X",
            "failure_modes": ["fail1"],
        }
        c = EvalCase.from_dict(d)
        d2 = c.to_dict()
        assert d2["expected_agent_behavior"] == "do X"
        assert d2["failure_modes"] == ["fail1"]


# ============================================================
# V1 评价集 — 8 个 Sposobin 核心
# ============================================================

class TestV1GoldSet:
    def test_exactly_8_v1_cases(self):
        cases = load_all_gold()
        assert len(cases) == 8, f"V1 期望 8 个 Sposobin 核心 case, 实际 {len(cases)}"

    def test_v1_case_ids(self):
        ids = {c.metadata.id for c in load_all_gold()}
        assert ids == V1_CASE_IDS

    def test_all_sposobin(self):
        """V1 决策: 所有 V1 case 必须是 sposobin。"""
        for c in load_all_gold():
            assert c.metadata.style_profile == "sposobin", \
                f"{c.metadata.id} style_profile={c.metadata.style_profile} (应 sposobin)"

    def test_all_sposobin_framework(self):
        for c in load_all_gold():
            assert c.metadata.analysis_framework == "sposobin", \
                f"{c.metadata.id} framework={c.metadata.analysis_framework}"

    def test_all_have_roman_progression(self):
        for c in load_all_gold():
            assert c.analysis.harmony.roman_progression, \
                f"{c.metadata.id} 缺 roman_progression"

    def test_all_have_functional_analysis_t_s_d(self):
        """V1 决策: functional_analysis 必须用 T/S/D 标签。"""
        valid_labels = {"T", "S", "D"}
        for c in load_all_gold():
            for label in c.analysis.harmony.functional_analysis:
                assert label in valid_labels, \
                    f"{c.metadata.id} functional_analysis 包含非 T/S/D 标签: {label}"

    def test_all_have_cadence(self):
        for c in load_all_gold():
            assert c.analysis.cadences, f"{c.metadata.id} 缺 cadence"

    def test_all_have_teaching_points(self):
        for c in load_all_gold():
            assert c.teaching_points, f"{c.metadata.id} 缺 teaching_points"

    def test_all_have_expected_agent_behavior(self):
        """V1 决策: 每个 case 必须有 expected_agent_behavior (P20.3 必填)。"""
        for c in load_all_gold():
            assert c.expected_agent_behavior, \
                f"{c.metadata.id} 缺 expected_agent_behavior"

    def test_all_have_failure_modes(self):
        """V1 决策: 每个 case 必须有 failure_modes (≥1)。"""
        for c in load_all_gold():
            assert len(c.failure_modes) >= 1, \
                f"{c.metadata.id} failure_modes 至少 1 条"

    def test_all_marked_needs_expert_review(self):
        """V1 决策: 所有 8 个 gold 都标 needs_expert_review=true (等人工校)。"""
        for c in load_all_gold():
            assert c.needs_expert_review is True, \
                f"{c.metadata.id} 必须 needs_expert_review=true"

    def test_no_jazz_modal_in_v1(self):
        """V1 不再覆盖 jazz/modal — 那些已移到 later_profiles/。"""
        cases = load_all_gold()
        styles = {c.metadata.style_profile for c in cases}
        assert "jazz" not in styles
        assert "modal" not in styles

    def test_loaders(self):
        cases = load_all_gold()
        assert len(cases) == 8
        for c in cases:
            assert c in load_all_gold()

    def test_get_gold_by_id(self):
        c = get_gold("mozart_k545_m1")
        assert c is not None
        assert c.metadata.composer == "W.A. Mozart"
        assert c.metadata.style_profile == "sposobin"

    def test_gold_summary(self):
        s = gold_summary()
        assert s["n_total"] == 8
        assert s["by_style"] == {"sposobin": 8}
        # 全部 needs_expert_review
        assert s["by_review"]["needs_review"] == 8
        assert s["by_review"]["reviewed"] == 0


# ============================================================
# 特定 case 验证
# ============================================================

class TestSpecificV1Cases:
    def test_mozart_k545_cadences(self):
        c = get_gold("mozart_k545_m1")
        types = [cd.type for cd in c.analysis.cadences]
        assert "HC" in types
        assert "PAC" in types

    def test_chopin_op28_no20_no_pac(self):
        """送葬进行 — 没有 PAC。"""
        c = get_gold("chopin_op28_no20")
        for cd in c.analysis.cadences:
            assert cd.type != "PAC", f"Op.28 No.20 永不到 PAC, 但有 {cd.type}"

    def test_chopin_op28_no20_excerpt_consistent(self):
        """excerpt mm.1-16 与 cadence m.4, 8, 12, 16 一致。"""
        c = get_gold("chopin_op28_no20")
        # excerpt 写 mm.1-16 (complete prelude)
        assert "1-16" in c.metadata.excerpt or "16" in c.metadata.excerpt
        for cd in c.analysis.cadences:
            assert cd.measure <= 16, f"cadence m.{cd.measure} 超出 excerpt"

    def test_bach_prelude_pac_at_35(self):
        c = get_gold("bach_wtc_prelude_bwv846")
        pacs = [cd for cd in c.analysis.cadences if cd.type == "PAC"]
        assert len(pacs) >= 1
        assert pacs[0].measure == 35

    def test_pathetique_intro_ends_hc(self):
        c = get_gold("beethoven_pathetique_m1")
        # 慢引子 m.1-4 结束在 V (HC)
        first_cadence = c.analysis.cadences[0]
        assert first_cadence.measure == 4
        assert first_cadence.type == "HC"

    def test_schubert_v_v_tonicization(self):
        c = get_gold("schubert_op90_no3")
        # m.5 应有 V/V → V 转调
        assert len(c.analysis.key_changes) >= 1
        assert c.analysis.key_changes[0]["measure"] == 5

    def test_chopin_op9_no2_vi_in_sposobin(self):
        """Chopin Op.9 No.2 的 VI 在 Sposobin 体系下归 T (Sposobin 上册)。"""
        c = get_gold("chopin_op9_no2")
        for r, f in zip(c.analysis.harmony.roman_progression,
                        c.analysis.harmony.functional_analysis):
            if r == "VI":
                # Sposobin 上册: VI 归 T 组
                assert f == "T", f"VI 应归 T (Sposobin 上册), 实际 {f}"


# ============================================================
# music21 draft
# ============================================================

class TestMusic21Draft:
    def test_draft_returns_dict(self):
        result = generate_draft("bach_wtc_prelude_bwv846")
        assert isinstance(result, dict)
        if "error" not in result:
            assert "key" in result
            assert result.get("needs_expert_review") is True


# ============================================================
# 完整性
# ============================================================

class TestGoldCompleteness:
    def test_all_have_difficulty_1_to_5(self):
        for c in load_all_gold():
            assert 1 <= c.metadata.difficulty <= 5

    def test_all_have_excerpt(self):
        for c in load_all_gold():
            assert c.metadata.excerpt

    def test_all_have_period(self):
        for c in load_all_gold():
            assert c.metadata.period

    def test_all_have_key(self):
        for c in load_all_gold():
            assert c.analysis.key

    def test_all_have_form_role(self):
        for c in load_all_gold():
            assert c.analysis.form_role

    def test_all_cadences_have_measure(self):
        for c in load_all_gold():
            for cd in c.analysis.cadences:
                assert cd.measure >= 0

    def test_all_have_review_notes(self):
        """V1 决策: 全部 needs_expert_review=true, 应该有 review_notes 解释待校内容。"""
        for c in load_all_gold():
            assert c.review_notes, f"{c.metadata.id} 缺 review_notes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
