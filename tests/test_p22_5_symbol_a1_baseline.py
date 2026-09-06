"""
P22.5-Symbol-A.1 — 单音符 modifier 渲染基线 (静态契约测试)

目标: 确认 createVexNote() 中每个单音符 modifier 单独存在时
能正确调用对应的 VexFlow class。

范围: createVexNote() (app.js L3006-3122) + articulationCodes/ornamentCodes 表。

纪律: 静态字符串分析, 零依赖, 零运行。
不测: 浏览器实测 (Browser 验收) / 排版 / 跨小节 / 大谱表。
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


def _extract_createVexNote(content):
    """截取 createVexNote 完整函数体 (配对计数, 处理嵌套 () 和 {})"""
    start_match = re.search(r"function\s+createVexNote\s*\(", content)
    if not start_match:
        return None
    # 1. 配对 () 找参数结束
    paren_depth = 1
    i = start_match.end()
    while i < len(content) and paren_depth > 0:
        if content[i] == "(":
            paren_depth += 1
        elif content[i] == ")":
            paren_depth -= 1
        i += 1
    # 2. 跳过空白找 {
    while i < len(content) and content[i] != "{":
        i += 1
    if i >= len(content):
        return None
    # 3. 配对 {} 找函数结束
    brace_depth = 1
    j = i + 1
    while j < len(content) and brace_depth > 0:
        if content[j] == "{":
            brace_depth += 1
        elif content[j] == "}":
            brace_depth -= 1
        j += 1
    return content[start_match.start() : j]


def _extract_object(content, var_name):
    """截取 const varName = { ... }; 完整字面量 (L126 / L138 那种)"""
    pattern = rf"const\s+{var_name}\s*=\s*\{{(.*?)\}};"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return None
    return match.group(0)


class TestFileExists(unittest.TestCase):
    def test_app_js_exists(self):
        self.assertTrue(os.path.exists(APP_PATH), f"app.js not found at {APP_PATH}")

    def test_app_js_nonempty(self):
        content = _read_app()
        self.assertGreater(len(content), 100_000, "app.js too small (<100KB)")


class TestFermataCode(unittest.TestCase):
    """P22.5-Symbol-A.1 唯一代码改动: fermata 用 "a@fermata" 而不是 "a@a" """

    def test_fermata_uses_correct_code(self):
        content = _read_app()
        self.assertIn(
            'new VF.Articulation("a@fermata")',
            content,
            "ferrmata should use VexFlow 'a@fermata' code (P22.5-A.1)",
        )

    def test_no_old_fermata_code(self):
        content = _read_app()
        # 旧的 "a@a" 字面量不应该再出现
        self.assertNotIn(
            'new VF.Articulation("a@a")',
            content,
            'old fermata code "a@a" should be removed',
        )


class TestArticulationCodes(unittest.TestCase):
    def test_articulationCodes_object_exists(self):
        content = _read_app()
        obj = _extract_object(content, "articulationCodes")
        self.assertIsNotNone(obj, "articulationCodes const should exist")

    def test_articulationCodes_has_4_entries(self):
        content = _read_app()
        obj = _extract_object(content, "articulationCodes")
        self.assertIsNotNone(obj)
        for key in ("staccato", "accent", "tenuto", "marcato"):
            self.assertIn(
                key,
                obj,
                f"articulationCodes missing '{key}'",
            )

    def test_articulationCodes_values_are_vexflow_codes(self):
        content = _read_app()
        obj = _extract_object(content, "articulationCodes")
        # 4 个 VexFlow codename 应该是 "a.", "a>", "a-", "a^"
        for expected in ('"a."', '"a>"', '"a-"', '"a^"'):
            self.assertIn(
                expected,
                obj,
                f"articulationCodes should include VexFlow code {expected}",
            )


class TestOrnamentCodes(unittest.TestCase):
    def test_ornamentCodes_object_exists(self):
        content = _read_app()
        obj = _extract_object(content, "ornamentCodes")
        self.assertIsNotNone(obj, "ornamentCodes const should exist")

    def test_ornamentCodes_has_8_entries(self):
        content = _read_app()
        obj = _extract_object(content, "ornamentCodes")
        self.assertIsNotNone(obj)
        for key in (
            "mordent",
            "mordent-inverted",
            "trill",
            "turn",
            "turn-inverted",
            "upprall",
            "downprall",
            "lineprall",
        ):
            self.assertIn(
                key,
                obj,
                f"ornamentCodes missing '{key}'",
            )


class TestCreateVexNoteModifierPaths(unittest.TestCase):
    """每个单音符 modifier 都必须走对应的 VexFlow class"""

    @classmethod
    def setUpClass(cls):
        content = _read_app()
        cls.createVexNote = _extract_createVexNote(content)
        assert cls.createVexNote is not None, "createVexNote function not found in app.js"

    def test_dot_path(self):
        self.assertIn(
            "VF.Dot.buildAndAttach",
            self.createVexNote,
            "createVexNote should use VF.Dot.buildAndAttach for dotted notes",
        )

    def test_articulation_path(self):
        self.assertIn(
            "new VF.Articulation(",
            self.createVexNote,
            "createVexNote should use VF.Articulation for articulation/fermata",
        )

    def test_ornament_path(self):
        self.assertIn(
            "new VF.Ornament(",
            self.createVexNote,
            "createVexNote should use VF.Ornament for ornaments",
        )

    def test_grace_note_path(self):
        self.assertIn(
            "new VF.GraceNote(",
            self.createVexNote,
            "createVexNote should use VF.GraceNote for grace notes",
        )

    def test_grace_note_group_path(self):
        self.assertIn(
            "new VF.GraceNoteGroup(",
            self.createVexNote,
            "createVexNote should use VF.GraceNoteGroup for grace notes",
        )

    def test_annotation_path(self):
        # Annotation 用于 pedal/textMark/breath/dynamic — 4 个调用
        annotation_calls = self.createVexNote.count("new VF.Annotation(")
        self.assertGreaterEqual(
            annotation_calls,
            4,
            f"createVexNote should call new VF.Annotation(...) at least 4 times (pedal/textMark/breath/dynamic), got {annotation_calls}",
        )

    def test_fret_hand_finger_path(self):
        self.assertIn(
            "new VF.FretHandFinger(",
            self.createVexNote,
            "createVexNote should use VF.FretHandFinger for fingering",
        )

    def test_chord_symbol_path(self):
        self.assertIn(
            "new VF.ChordSymbol(",
            self.createVexNote,
            "createVexNote should use VF.ChordSymbol for chord symbols",
        )


class TestSignatureStability(unittest.TestCase):
    """不改变旧行为"""

    def test_createVexNote_signature_unchanged(self):
        content = _read_app()
        # 5 个参数: entry, clef, timeSignature, stemDirection, voiceId
        match = re.search(
            r"function\s+createVexNote\s*\(([^)]*)\)",
            content,
        )
        self.assertIsNotNone(match)
        params = [p.strip().split("=")[0].strip() for p in match.group(1).split(",")]
        self.assertEqual(
            params,
            ["entry", "clef", "timeSignature", "stemDirection", "voiceId"],
            f"createVexNote signature changed: {params}",
        )

    def test_note_entry_shape_unchanged(self):
        """note entry 写入 (L2091-2107) 字段不变"""
        content = _read_app()
        for field in (
            "kind: \"note\"",
            "voice:",
            "pitches: [pitch]",
            "duration,",
            "dotted,",
            "units,",
            "tieStart: false",
            "tieStop: false",
            "slurStart: false",
            "slurStop: false",
            "fermata: false",
            "tupletType: \"\"",
            "tupletGroup: \"\"",
            "tupletPosition: \"\"",
            "dynamic: \"\"",
        ):
            self.assertIn(
                field,
                content,
                f"note entry shape changed: '{field}' not found",
            )

    def test_renderFourPartScore_unchanged(self):
        """4 部画布不动 (P22.5-A.4 才动)"""
        content = _read_app()
        # 关键调用: createVexNote 在 4 部画布里被调
        self.assertIn(
            "function renderFourPartScore(",
            content,
            "renderFourPartScore function should still exist",
        )
        # 内部调用 createVexNote 不变
        self.assertRegex(
            content,
            r"entries\.map\(\((\w+)\)\s*=>\s*createVexNote\(\1,",
            "renderFourPartScore should still call createVexNote per entry",
        )

    def test_no_a2_layout_changes(self):
        """A.1 不动 annotation 排版层 (A.2 才动)"""
        content = _read_app()
        # 守卫: 没有 "slot picker" 之类的新概念
        self.assertNotIn(
            "AnnotationSlotPicker",
            content,
            "P22.5-A.1 should not introduce AnnotationSlotPicker (that's A.2)",
        )
        # 也没有 "slotN" 之类的临时变量
        self.assertNotIn(
            "slotN",
            content,
            "P22.5-A.1 should not introduce slotN variables (that's A.2)",
        )


class TestEntryFieldCoverage(unittest.TestCase):
    """确认 createVexNote 读 12 个 entry 字段 (单音符 modifier 全部)"""

    @classmethod
    def setUpClass(cls):
        content = _read_app()
        cls.createVexNote = _extract_createVexNote(content)

    def test_fermata_field(self):
        self.assertIn("entry.fermata", self.createVexNote)

    def test_articulation_field(self):
        self.assertIn("entry.articulation", self.createVexNote)

    def test_ornament_field(self):
        self.assertIn("entry.ornament", self.createVexNote)

    def test_grace_field(self):
        self.assertIn("entry.grace", self.createVexNote)

    def test_pedal_field(self):
        self.assertIn("entry.pedal", self.createVexNote)

    def test_fingering_field(self):
        self.assertIn("entry.fingering", self.createVexNote)

    def test_textMark_field(self):
        self.assertIn("entry.textMark", self.createVexNote)

    def test_breath_field(self):
        self.assertIn("entry.breath", self.createVexNote)

    def test_dynamic_field(self):
        self.assertIn("entry.dynamic", self.createVexNote)

    def test_chordSymbol_field(self):
        self.assertIn("entry.chordSymbol", self.createVexNote)

    def test_dotted_field(self):
        self.assertIn("entry.dotted", self.createVexNote)

    def test_pitches_field(self):
        # accidental 通过 entry.pitches 解析
        self.assertIn("entry.pitches", self.createVexNote)


if __name__ == "__main__":
    unittest.main()
