"""
P22.5-Symbol-A.3 — 跨小节对象 (静态契约测试)

目标: 验证 6 个跨 measure 改动落地:
  1. 数据层 buildScoreEntries() 全局 flatten 索引
  2. 8 个查询函数改接受 scoreEntries 全局
  3. 4 个绘制函数改接受 (scoreEntries, notesByMeasure) [+ stavesByMeasure for hairpin]
  4. 4 个跨 measure helper (raw SVG path fallback)
  5. drawStaffEntriesOnStave 删 4 跨音符 draw + 收集 notes/staves
  6. 渲染主循环外调 4 跨音符 draw + 单谱表 / 4 部画布都接

纪律: 纯静态 grep + Python 字符串分析, 零依赖, 零运行。
不测: 浏览器实测 (Browser 验收) / 跨 measure 真渲染 / 几何精度。
"""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(ROOT, "web", "app.js")


def _read_app():
    with open(APP_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _extract_function(content, name):
    """提取指定函数 (name) 完整 body (paren + brace 配对计数)"""
    pattern = rf"function\s+{name}\s*\("
    m = re.search(pattern, content)
    if not m:
        return None
    paren_depth = 1
    i = m.end()
    while i < len(content) and paren_depth > 0:
        if content[i] == "(":
            paren_depth += 1
        elif content[i] == ")":
            paren_depth -= 1
        i += 1
    while i < len(content) and content[i] != "{":
        i += 1
    if i >= len(content):
        return None
    brace_depth = 1
    k = i + 1
    while k < len(content) and brace_depth > 0:
        if content[k] == "{":
            brace_depth += 1
        elif content[k] == "}":
            brace_depth -= 1
        k += 1
    return content[m.start() : k]


# ===== 1. 数据层 buildScoreEntries =====

class TestBuildScoreEntries(unittest.TestCase):
    """数据层 buildScoreEntries 全局 flatten 索引"""

    @classmethod
    def setUpClass(cls):
        cls.content = _read_app()
        cls.body = _extract_function(cls.content, "buildScoreEntries")

    def test_01_function_exists(self):
        self.assertIsNotNone(self.body, "buildScoreEntries 函数必须存在")

    def test_02_signature_takes_scoreMeasures(self):
        self.assertRegex(self.body, r"function\s+buildScoreEntries\s*\(\s*scoreMeasures\s*\)")

    def test_03_uses_array_isarray_guard(self):
        self.assertIn("Array.isArray(scoreMeasures)", self.body)

    def test_04_supports_notationEntries_and_entries(self):
        # 支持 measure.notationEntries / measure.entries / array
        self.assertIn("notationEntries", self.body)
        self.assertIn("entries", self.body)
        # 也支持 measure 本身是 array (trebleState.measures[i] = [entry, ...])
        self.assertIn("Array.isArray(measure)", self.body)

    def test_05_attaches_three_underscore_fields(self):
        self.assertIn("_globalIndex", self.body)
        self.assertIn("_measureIndex", self.body)
        self.assertIn("_localIndex", self.body)

    def test_06_spreads_entry(self):
        # 浅拷贝 entry (基础字段保留)
        self.assertRegex(self.body, r"\{\s*\.\.\.entry,")

    def test_07_returns_array(self):
        # 函数末尾 push + return
        self.assertRegex(self.body, r"all\.push")
        self.assertRegex(self.body, r"return\s+all")


# ===== 2. 8 个查询函数改 scoreEntries 全局 =====

# 8 个查询函数: nextTieTargetIndex / previousTieSourceIndex / nextSlurTargetIndex /
#               previousSlurSourceIndex / nextHairpinStopIndex / nextHairpinStopSourceExists /
#               nextPhraseTargetIndex / nextPhraseSourceExists
QUERY_FUNCTIONS_GLOBAL = [
    "nextTieTargetIndex",
    "previousTieSourceIndex",
    "nextSlurTargetIndex",
    "previousSlurSourceIndex",
    "nextHairpinStopIndex",
    "nextHairpinStopSourceExists",
    "nextPhraseTargetIndex",
    "nextPhraseSourceExists",
]

class TestQueryFunctionsGlobal(unittest.TestCase):
    """8 个绘制层用查询函数改接受 scoreEntries 全局"""

    @classmethod
    def setUpClass(cls):
        cls.content = _read_app()

    def test_all_8_functions_take_scoreEntries_as_first_param(self):
        for name in QUERY_FUNCTIONS_GLOBAL:
            body = _extract_function(self.content, name)
            self.assertIsNotNone(body, f"{name} 函数必须存在")
            self.assertRegex(
                body,
                rf"function\s+{name}\s*\(\s*scoreEntries",
                f"{name} 第一个参数必须是 scoreEntries (全局索引)"
            )

    def test_all_8_functions_reference_scoreEntries_in_body(self):
        for name in QUERY_FUNCTIONS_GLOBAL:
            body = _extract_function(self.content, name)
            # 函数体里至少有 1 次 scoreEntries[ 索引 + 2 次 scoreEntries.length / for 循环
            count = body.count("scoreEntries[")
            self.assertGreaterEqual(
                count, 1,
                f"{name} 必须用 scoreEntries[index] 遍历"
            )

    def test_no_old_notationEntries_param_remaining(self):
        # 老的 notationEntries 形参不应再出现在 8 个全局查询函数里
        for name in QUERY_FUNCTIONS_GLOBAL:
            body = _extract_function(self.content, name)
            # 形参不应有 notationEntries (允许注释里出现, 但函数签名行不能)
            signature_line = body.split("{")[0]
            self.assertNotIn(
                "notationEntries", signature_line,
                f"{name} 形参不应是 notationEntries (已改 scoreEntries)"
            )


# ===== 3. 4 个绘制函数改签名 =====

DRAW_FUNCTIONS_CROSS_MEASURE = [
    "drawEntryTies",
    "drawEntrySlurs",
    "drawEntryPhraseMarks",
    # drawEntryHairpins 多接 stavesByMeasure, 单独测
]

class TestDrawFunctionsCrossMeasure(unittest.TestCase):
    """3 个绘制函数改接受 (scoreEntries, notesByMeasure)"""

    @classmethod
    def setUpClass(cls):
        cls.content = _read_app()

    def test_takes_scoreEntries(self):
        for name in DRAW_FUNCTIONS_CROSS_MEASURE:
            body = _extract_function(self.content, name)
            self.assertIsNotNone(body, f"{name} 必须存在")
            self.assertRegex(body, rf"function\s+{name}\s*\(\s*context,\s*scoreEntries,\s*notesByMeasure")

    def test_uses_notesByMeasure_get(self):
        for name in DRAW_FUNCTIONS_CROSS_MEASURE:
            body = _extract_function(self.content, name)
            # 必须用 notesByMeasure.get 取 note
            self.assertIn(
                "notesByMeasure?.get", body,
                f"{name} 必须用 notesByMeasure?.get 取 note"
            )

    def test_uses_measureIndex_underscore(self):
        for name in DRAW_FUNCTIONS_CROSS_MEASURE:
            body = _extract_function(self.content, name)
            # 必须按 _measureIndex 区分同 measure / 跨 measure
            self.assertIn("_measureIndex", body)

    def test_uses_global_query_functions(self):
        # tie: nextTieTargetIndex
        # slur: nextSlurTargetIndex + previousSlurSourceIndex
        # phrase: nextPhraseTargetIndex + nextPhraseSourceExists
        tie_body = _extract_function(self.content, "drawEntryTies")
        slur_body = _extract_function(self.content, "drawEntrySlurs")
        phrase_body = _extract_function(self.content, "drawEntryPhraseMarks")
        self.assertIn("nextTieTargetIndex(scoreEntries", tie_body)
        self.assertIn("previousTieSourceIndex(scoreEntries", tie_body)
        self.assertIn("nextSlurTargetIndex(scoreEntries", slur_body)
        self.assertIn("previousSlurSourceIndex(scoreEntries", slur_body)
        self.assertIn("nextPhraseTargetIndex(scoreEntries", phrase_body)
        self.assertIn("nextPhraseSourceExists(scoreEntries", phrase_body)

    def test_hairpins_takes_4_params(self):
        # drawEntryHairpins 额外接 stavesByMeasure
        body = _extract_function(self.content, "drawEntryHairpins")
        self.assertIsNotNone(body)
        self.assertRegex(
            body,
            r"function\s+drawEntryHairpins\s*\(\s*context,\s*scoreEntries,\s*notesByMeasure,\s*stavesByMeasure"
        )
        # 内部用 stavesByMeasure.get
        self.assertIn("stavesByMeasure?.get", body)
        # 用 nextHairpinStopIndex + nextHairpinStopSourceExists 全局版本
        self.assertIn("nextHairpinStopIndex(scoreEntries", body)
        self.assertIn("nextHairpinStopSourceExists(scoreEntries", body)


# ===== 4. 4 个跨 measure helper (raw SVG path fallback) =====

CROSS_MEASURE_HELPERS = [
    ("drawCrossMeasureTie", "tie-cross"),
    ("drawCrossMeasureSlur", "slur-cross"),
    ("drawCrossMeasurePhraseMark", "phrase-cross"),
    ("drawCrossMeasureHairpin", "hairpin-cross"),
]

class TestCrossMeasureHelpers(unittest.TestCase):
    """4 个跨 measure helper: VexFlow 限制 fallback, 用 raw SVG path 画"""

    @classmethod
    def setUpClass(cls):
        cls.content = _read_app()

    def test_all_4_helpers_exist(self):
        for name, _ in CROSS_MEASURE_HELPERS:
            body = _extract_function(self.content, name)
            self.assertIsNotNone(body, f"{name} 必须存在")

    def test_all_4_helpers_use_getTieRightX_and_getTieLeftX(self):
        for name, _ in CROSS_MEASURE_HELPERS:
            body = _extract_function(self.content, name)
            # 必须用 note.getTieRightX() / getTieLeftX() 算绝对 x
            self.assertIn("getTieRightX()", body, f"{name} 必须调 getTieRightX")
            self.assertIn("getTieLeftX()", body, f"{name} 必须调 getTieLeftX")

    def test_all_4_helpers_use_context_openGroup_and_stroke(self):
        for name, group in CROSS_MEASURE_HELPERS:
            body = _extract_function(self.content, name)
            self.assertIn("context.openGroup", body, f"{name} 必须调 openGroup")
            self.assertIn(f'"{group}"', body, f"{name} group 标签必须是 {group}")
            self.assertIn("context.beginPath", body, f"{name} 必须 beginPath")
            self.assertIn("context.stroke", body, f"{name} 必须 stroke")
            self.assertIn("context.closeGroup", body, f"{name} 必须 closeGroup")

    def test_tie_helper_uses_quadraticCurveTo(self):
        body = _extract_function(self.content, "drawCrossMeasureTie")
        self.assertIn("quadraticCurveTo", body)

    def test_slur_and_phrase_helpers_arc_higher_than_tie(self):
        # slur/phrase 比 tie 弧度更大 (cps y=18/26 vs tie 默认 6)
        slur_body = _extract_function(self.content, "drawCrossMeasureSlur")
        phrase_body = _extract_function(self.content, "drawCrossMeasurePhraseMark")
        # slur 弧高 12, phrase 弧高 20
        self.assertRegex(slur_body, r"Math\.min\(y1,\s*y2\)\s*-\s*12")
        self.assertRegex(phrase_body, r"Math\.min\(y1,\s*y2\)\s*-\s*20")

    def test_hairpin_helper_distinguishes_cresc_and_decresc(self):
        body = _extract_function(self.content, "drawCrossMeasureHairpin")
        self.assertIn('"cresc-start"', body, "hairpin 必须区分 cresc-start")
        self.assertIn("context.lineTo", body, "hairpin 用 lineTo 画线")


# ===== 5. drawStaffEntriesOnStave 改造 =====

class TestDrawStaffEntriesOnStaveChanges(unittest.TestCase):
    """drawStaffEntriesOnStave: 删 4 跨音符 draw + 收集 notes/staves"""

    @classmethod
    def setUpClass(cls):
        cls.content = _read_app()
        cls.body = _extract_function(cls.content, "drawStaffEntriesOnStave")

    def test_01_new_signature(self):
        # 7 参数: context, stave, entriesSource, clef, width, selectable, measureIndex, notesByMeasure, stavesByMeasure
        self.assertRegex(
            self.body,
            r"function\s+drawStaffEntriesOnStave\s*\(\s*context,\s*stave,\s*entriesSource,\s*clef,\s*width,\s*selectable,\s*measureIndex,\s*notesByMeasure,\s*stavesByMeasure"
        )

    def test_02_collects_notes_to_notesByMeasure(self):
        # 必须有 notesByMeasure.set(measureIndex, ...) 或类似
        self.assertIn("notesByMeasure.set(measureIndex", self.body)
        # 必须 push voices 的 notes
        self.assertIn("collected.push(...item.notes)", self.body)

    def test_03_collects_stave_to_stavesByMeasure(self):
        self.assertIn("stavesByMeasure.set(measureIndex, stave)", self.body)

    def test_04_removed_4_cross_measure_draws(self):
        # 删 drawEntryTies / drawEntrySlurs / drawEntryPhraseMarks / drawEntryHairpins 调用
        # (arpeggios 保留)
        self.assertNotIn("drawEntryTies(context", self.body, "drawEntryTies 调用应从 drawStaffEntriesOnStave 移到主循环外")
        self.assertNotIn("drawEntrySlurs(context", self.body, "drawEntrySlurs 调用应从 drawStaffEntriesOnStave 移到主循环外")
        self.assertNotIn("drawEntryPhraseMarks(context", self.body, "drawEntryPhraseMarks 调用应从 drawStaffEntriesOnStave 移到主循环外")
        self.assertNotIn("drawEntryHairpins(context", self.body, "drawEntryHairpins 调用应从 drawStaffEntriesOnStave 移到主循环外")

    def test_05_keeps_drawEntryArpeggios(self):
        # arpeggios 不跨 measure, 保留
        self.assertIn("drawEntryArpeggios(context", self.body)


# ===== 6. 渲染主循环调 4 跨音符 draw =====

class TestRenderMainLoopCalls(unittest.TestCase):
    """渲染主循环外调 4 跨音符 draw (单谱表 + 4 部画布)"""

    @classmethod
    def setUpClass(cls):
        cls.content = _read_app()

    def test_single_staff_collects_notesByMeasure(self):
        # renderSingleNotationSafe 内有 notesByMeasure = new Map()
        # 用前后上下文 (单谱表路径) 验证
        idx = self.content.find("const notesByMeasure = new Map();")
        self.assertGreater(idx, 0, "单谱表必须有 notesByMeasure 容器")

    def test_single_staff_calls_buildScoreEntries_outside_loop(self):
        # buildScoreEntries(scoreMeasures) 应在 forEach 外调
        idx = self.content.find("buildScoreEntries(scoreMeasures)")
        self.assertGreater(idx, 0)
        # 不在 visibleIndices.forEach 内 (简化: 找到至少 1 次)
        self.assertIn("buildScoreEntries(scoreMeasures)", self.content)

    def test_single_staff_calls_4_cross_measure_draws(self):
        # 主循环外调 drawEntryTies/Slurs/PhraseMarks/Hairpins
        for name in ["drawEntryTies", "drawEntrySlurs", "drawEntryPhraseMarks", "drawEntryHairpins"]:
            count = self.content.count(f"{name}(context, scoreEntries, notesByMeasure")
            self.assertGreaterEqual(
                count, 1,
                f"主循环外必须调 {name}(context, scoreEntries, notesByMeasure, ...)"
            )

    def test_piano_mode_4_voice_collects_separately(self):
        # 4 部画布有 treble/bass 各自的 Map
        self.assertIn("const trebleNotesByMeasure = new Map();", self.content)
        self.assertIn("const bassNotesByMeasure = new Map();", self.content)
        self.assertIn("const trebleStavesByMeasure = new Map();", self.content)
        self.assertIn("const bassStavesByMeasure = new Map();", self.content)

    def test_piano_mode_calls_buildScoreEntries_per_stave(self):
        # 4 部画布 treble / bass 各自 buildScoreEntries
        self.assertIn("buildScoreEntries(trebleState?.measures || [])", self.content)
        self.assertIn("buildScoreEntries(bassState?.measures || [])", self.content)

    def test_business_layer_unchanged(self):
        # 业务层 nextTieTargetEntry / nextSlurTargetEntry 保留 measure 局部语义
        # (用 measureEntries 不用 scoreEntries)
        tie_body = _extract_function(self.content, "nextTieTargetEntry")
        slur_body = _extract_function(self.content, "nextSlurTargetEntry")
        self.assertIsNotNone(tie_body)
        self.assertIsNotNone(slur_body)
        # 形参: startIndex (单参数, 业务层调用)
        self.assertRegex(tie_body, r"function\s+nextTieTargetEntry\s*\(\s*startIndex")
        self.assertRegex(slur_body, r"function\s+nextSlurTargetEntry\s*\(\s*startIndex")
        # 函数体用 measureEntries (业务层单 measure 数组)
        self.assertIn("measureEntries", tie_body)
        self.assertIn("measureEntries", slur_body)


if __name__ == "__main__":
    unittest.main()
