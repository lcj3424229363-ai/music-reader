"""P20.1 单元测试 — 分析标准层 + 经典案例库 + 错误案例库。

覆盖：
- theory/style_profiles: 5 流派注册、规则允许/禁止、默认 profile、explainer prefix
- data/repertoire: 8 个案例、tag/key/composer/id 检索
- data/error_cases: 10 个错误案例、error_type/style_relevance/severity 检索
- 跨模块集成: 用 sposobin profile 过滤错例库
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from theory.style_profiles import (
    PROFILES,
    FUNCTIONAL_CLASSICAL_PROFILE,
    SPOSOBIN_PROFILE,
    SCHENKERIAN_PROFILE,
    FUNCTIONAL_PROFILE,  # backward-compat alias
    MODAL_PROFILE,
    JAZZ_PROFILE,
    DEFAULT_STYLE,
    StyleProfile,
    get_profile,
    list_styles,
    style_explainer_prefix,
)
from data.repertoire import (
    REPERTOIRE_CASES,
    find_by_tag,
    find_by_key,
    find_by_composer,
    get_case,
)
from data.error_cases import (
    ERROR_CASES,
    find_by_error_type,
    find_by_style_relevance,
    find_by_severity,
    get_case as get_error_case,
)


# ============================================================
# style_profiles
# ============================================================

class TestStyleProfilesRegistry:
    def test_all_5_profiles_registered(self):
        assert len(PROFILES) == 5
        assert set(PROFILES.keys()) == {
            "functional_classical", "sposobin", "schenkerian", "jazz", "modal"
        }

    def test_sposobin_is_v1_default(self):
        # V1 默认 — 必须在 PROFILES 里,必须 = DEFAULT_STYLE
        assert "sposobin" in PROFILES
        assert PROFILES[DEFAULT_STYLE] is SPOSOBIN_PROFILE

    def test_default_is_sposobin(self):
        # V1 决策: 斯波索宾体系是 V1 默认 (中央音乐学院标准)
        assert DEFAULT_STYLE == "sposobin"
        # 未知 ID / None 都应回退到 sposobin
        assert get_profile(None) is SPOSOBIN_PROFILE
        assert get_profile("") is SPOSOBIN_PROFILE
        assert get_profile("unknown_style") is SPOSOBIN_PROFILE
        assert get_profile("sposobin") is SPOSOBIN_PROFILE

    def test_functional_classical_kept_as_compat_profile(self):
        # functional_classical 保留作为兼容 profile,非 V1 默认
        assert "functional_classical" in PROFILES
        assert get_profile("functional_classical") is FUNCTIONAL_CLASSICAL_PROFILE
        assert get_profile("functional_classical") is not SPOSOBIN_PROFILE

    def test_functional_profile_alias(self):
        # 向后兼容别名
        assert FUNCTIONAL_PROFILE is FUNCTIONAL_CLASSICAL_PROFILE

    def test_list_styles_returns_all(self):
        styles = list_styles()
        assert len(styles) == 5
        ids = {s.style_id for s in styles}
        assert ids == {"functional_classical", "sposobin", "schenkerian", "jazz", "modal"}

    def test_all_profiles_have_required_fields(self):
        for s in list_styles():
            assert isinstance(s, StyleProfile)
            assert s.style_id
            assert s.name_zh
            assert s.description
            assert s.label_terminology
            assert s.explanation_tone in {"academic", "intuitive", "jazzy", "modal-poetic"}


class TestStyleProfileRules:
    """验证 5 流派在核心规则上的差异。"""

    def test_sposobin_forbids_parallel_5_8(self):
        assert SPOSOBIN_PROFILE.forbids("parallel_5")
        assert SPOSOBIN_PROFILE.forbids("parallel_8")
        assert SPOSOBIN_PROFILE.forbids("voice_crossing")
        assert SPOSOBIN_PROFILE.forbids("hidden_5")

    def test_sposobin_requires_leading_tone_resolution(self):
        assert SPOSOBIN_PROFILE.require_leading_tone_resolution is True

    def test_sposobin_pac_strict(self):
        assert SPOSOBIN_PROFILE.pac_requires_root_position is True
        assert SPOSOBIN_PROFILE.pac_requires_bass_tonic is True

    def test_sposobin_does_not_allow_altered_dominants(self):
        assert SPOSOBIN_PROFILE.forbids("altered_dominant")
        assert SPOSOBIN_PROFILE.forbids("extended_chord")

    def test_jazz_allows_parallel_5_8(self):
        # 爵士/流行允许平行五八度作色彩
        assert JAZZ_PROFILE.allows("parallel_5")
        assert JAZZ_PROFILE.allows("parallel_8")
        assert JAZZ_PROFILE.allows("voice_crossing")

    def test_jazz_allows_extended_and_altered(self):
        assert JAZZ_PROFILE.allows("extended_chord")
        assert JAZZ_PROFILE.allows("altered_dominant")
        assert JAZZ_PROFILE.allows("secondary_dominant")
        assert JAZZ_PROFILE.allows("borrowed_chord")

    def test_jazz_does_not_require_leading_tone(self):
        # altered dominants 不要求导音解决
        assert JAZZ_PROFILE.require_leading_tone_resolution is False

    def test_modal_no_functional_labels(self):
        assert MODAL_PROFILE.use_functional_labels is False
        assert MODAL_PROFILE.prefer_functional_analysis is False
        assert MODAL_PROFILE.label_terminology == "调式"

    def test_modal_allows_parallel(self):
        # 调式允许平行五八度作色彩
        assert MODAL_PROFILE.allows("parallel_5")
        assert MODAL_PROFILE.allows("parallel_8")

    def test_modal_does_not_allow_secondary_dominants(self):
        # 副属是功能体系术语，调式不用
        assert MODAL_PROFILE.forbids("secondary_dominant")

    def test_schenkerian_allows_parallel_5(self):
        # 申克允许平行五八度作延长段
        assert SCHENKERIAN_PROFILE.allows("parallel_5")
        # 但仍禁止声部交叉
        assert SCHENKERIAN_PROFILE.forbids("voice_crossing")

    def test_functional_classical_is_default_and_allows_altered(self):
        # functional_classical (default) 允许变化属
        assert FUNCTIONAL_CLASSICAL_PROFILE.allows("altered_dominant")
        # 但仍禁止平行五八度（比 sposobin 稍宽松但仍禁止）
        assert FUNCTIONAL_CLASSICAL_PROFILE.forbids("parallel_5")
        # sposobin 禁止变化属
        assert SPOSOBIN_PROFILE.forbids("altered_dominant")


class TestStyleProfileMisc:
    def test_allows_unknown_rule_returns_true(self):
        # 未知规则默认允许（保守）
        for s in list_styles():
            assert s.allows("unknown_rule") is True

    def test_forbids_is_inverse_of_allows(self):
        for s in list_styles():
            for rule in ["parallel_5", "parallel_8", "voice_crossing", "borrowed_chord"]:
                assert s.forbids(rule) == (not s.allows(rule))


class TestStyleExplainerPrefix:
    def test_prefix_contains_style_name(self):
        text = style_explainer_prefix(SPOSOBIN_PROFILE)
        assert "斯波索宾" in text
        assert "分析标准" in text

    def test_prefix_contains_rule_status(self):
        text = style_explainer_prefix(SPOSOBIN_PROFILE)
        assert "禁止平行五八度" in text
        text2 = style_explainer_prefix(JAZZ_PROFILE)
        assert "允许平行五八度" in text2

    def test_prefix_contains_citations(self):
        text = style_explainer_prefix(SPOSOBIN_PROFILE)
        assert "斯波索宾" in text  # 在 cite_sources 里

    def test_prefix_has_tone_indicator(self):
        text = style_explainer_prefix(JAZZ_PROFILE)
        assert "jazzy" in text


# ============================================================
# repertoire
# ============================================================

class TestRepertoire:
    def test_at_least_8_cases(self):
        assert len(REPERTOIRE_CASES) >= 5
        assert len(REPERTOIRE_CASES) == 8  # 当前 8

    def test_all_cases_have_required_fields(self):
        for c in REPERTOIRE_CASES:
            assert c.id
            assert c.composer
            assert c.title
            assert c.key
            assert c.form
            assert c.harmonic_summary  # 至少 1 个和弦
            assert c.pedagogical_value

    def test_famous_pieces_present(self):
        ids = {c.id for c in REPERTOIRE_CASES}
        assert "beethoven-pathetique-op13-m1" in ids
        assert "chopin-nocturne-op9-2" in ids
        assert "bach-wtc1-cPrelude-bwv846" in ids
        assert "mozart-k545-m1" in ids
        assert "debussy-faun-excerpt" in ids

    def test_find_by_tag_sposobin(self):
        cases = find_by_tag("sposobin")
        assert len(cases) >= 3  # 至少 3 个 sposobin 案例
        for c in cases:
            assert "sposobin" in c.tags

    def test_find_by_tag_modal(self):
        cases = find_by_tag("modal")
        # debussy faun 是 modal 案例
        ids = [c.id for c in cases]
        assert "debussy-faun-excerpt" in ids

    def test_find_by_key_c_minor(self):
        cases = find_by_key("c minor")
        assert any(c.id == "beethoven-pathetique-op13-m1" for c in cases)

    def test_find_by_key_C_major(self):
        cases = find_by_key("C major")
        # 至少 Bach WTC + Mozart + Bach Fugue
        assert len(cases) >= 2

    def test_find_by_composer_bach(self):
        cases = find_by_composer("bach")
        assert len(cases) >= 2  # Prelude + Fugue

    def test_find_by_composer_beethoven(self):
        cases = find_by_composer("beethoven")
        assert len(cases) >= 2  # Pathétique mvt 1 + mvt 2

    def test_get_case_by_id(self):
        c = get_case("mozart-k545-m1")
        assert c is not None
        assert c.composer == "Mozart"
        assert c.key == "C major"

    def test_get_case_unknown_returns_none(self):
        assert get_case("unknown-case-id") is None

    def test_cadences_parsed(self):
        c = get_case("beethoven-pathetique-op13-m1")
        assert "PAC" in c.cadences
        # 至少包含 PAC
        assert any("PAC" in cad for cad in c.cadences)


# ============================================================
# error_cases
# ============================================================

class TestErrorCases:
    def test_at_least_10_cases(self):
        assert len(ERROR_CASES) >= 5
        assert len(ERROR_CASES) == 10

    def test_fatal_errors_present(self):
        fatal = find_by_severity("fatal")
        assert len(fatal) >= 4  # 至少 4 个 fatal
        ids = {c.id for c in fatal}
        assert "err-parallel-5" in ids
        assert "err-parallel-8" in ids
        assert "err-direct-8" in ids
        assert "err-leading-tone-unresolved" in ids

    def test_warning_errors_present(self):
        warnings = find_by_severity("warning")
        assert len(warnings) >= 3
        ids = {c.id for c in warnings}
        assert "err-voice-crossing" in ids
        assert "err-hidden-5" in ids

    def test_find_by_error_type_parallel_5(self):
        cases = find_by_error_type("parallel_5")
        assert len(cases) == 1
        assert cases[0].id == "err-parallel-5"

    def test_find_by_error_type_voice_crossing(self):
        cases = find_by_error_type("voice_crossing")
        assert len(cases) >= 1
        assert cases[0].error_type == "voice_crossing"

    def test_find_by_style_relevance_sposobin(self):
        cases = find_by_style_relevance("sposobin")
        # 大部分案例都标 sposobin 流派
        assert len(cases) >= 5

    def test_find_by_style_relevance_jazz(self):
        # 爵士/流行：除了 tritone-misplacement，其他都不一定
        cases = find_by_style_relevance("jazz")
        # 至少有 1 个 (空 tuple = 所有流派都判错)
        # 但 tritone-misplacement 标 jazz-allows 但 style_relevance 还是 sposobin
        # 所以 jazz 流派下应该少一些
        sposobin_cases = find_by_style_relevance("sposobin")
        assert len(cases) <= len(sposobin_cases)

    def test_get_case_by_id(self):
        c = get_error_case("err-parallel-5")
        assert c is not None
        assert c.error_type == "parallel_5"
        assert c.severity == "fatal"

    def test_get_case_unknown_returns_none(self):
        assert get_error_case("err-unknown") is None

    def test_all_cases_have_descriptions(self):
        for c in ERROR_CASES:
            assert c.description_zh
            assert c.when_occurs
            assert c.correct_approach


# ============================================================
# 跨模块集成
# ============================================================

class TestIntegration:
    """用 sposobin profile 过滤 + 与 error_cases 互动。"""

    def test_sposobin_strict_profile_filters_more_errors(self):
        # Sposobin 比 Jazz 严格，应该"判为错"的案例更多
        sposobin_errors = find_by_style_relevance("sposobin")
        jazz_errors = find_by_style_relevance("jazz")
        assert len(sposobin_errors) >= len(jazz_errors)

    def test_sposobin_forbids_match_error_cases(self):
        """Sposobin 禁止的规则应该在 error_cases 里有对应案例。"""
        sposobin_forbidden = [
            "parallel_5",
            "parallel_8",
            "voice_crossing",
            "leading_tone_unresolved",  # 用 error_type 名字
        ]
        for rule in ["parallel_5", "parallel_8", "voice_crossing"]:
            # Sposobin 禁止此规则
            assert SPOSOBIN_PROFILE.forbids(rule)
            # error_cases 里有对应案例
            error_type_map = {
                "parallel_5": "parallel_5",
                "parallel_8": "parallel_8",
                "voice_crossing": "voice_crossing",
            }
            cases = find_by_error_type(error_type_map[rule])
            assert len(cases) >= 1

    def test_jazz_allows_no_violation_in_strict_error_cases(self):
        """Jazz 流派下，parallel_5 不算错 —— 验证数据一致。"""
        # parallel_5 案例的 style_relevance = ("sposobin", "functional") 不含 "jazz"
        c = get_error_case("err-parallel-5")
        assert "jazz" not in c.style_relevance
        # 所以 jazz 流派下，这个案例**不**应被识别为错
        jazz_cases = find_by_style_relevance("jazz")
        assert c not in jazz_cases

    def test_explainer_prefix_for_each_style(self):
        """5 个流派都能生成前缀。"""
        for s in list_styles():
            text = style_explainer_prefix(s)
            assert s.name_zh in text
            assert "分析标准" in text
            assert "教学术语" in text
            assert "解释语气" in text
            assert "参考文献" in text

    def test_repertoire_has_sposobin_and_modal_markers(self):
        """案例库的 tag 同时覆盖 sposobin 和 modal，让 ReAct Agent 能跨风格检索。"""
        sposobin_cases = find_by_tag("sposobin")
        modal_cases = find_by_tag("modal")
        assert len(sposobin_cases) >= 3
        assert len(modal_cases) >= 1
        # Mozart K.545 是 sposobin 教科书
        assert any(c.id == "mozart-k545-m1" for c in sposobin_cases)
        # Debussy Faun 是 modal 案例
        assert any(c.id == "debussy-faun-excerpt" for c in modal_cases)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
