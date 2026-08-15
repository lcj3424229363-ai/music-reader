"""
P22.5-Symbol-A.2 — annotation 排版层 (静态契约测试)

目标: 验证 createVexNote 内 modifier addModifier 顺序按 slot 规则排列,
        chordSymbol 改 LEFT+BOTTOM, helper 暴露给测试 + 文档。

slot 规则 (用户指定):
    ABOVE (从近到远): articulation / fingering / textMark / ornament / fermata
    BELOW (从近到远): dynamic / pedal / breath
    grace 独立 (在 ABOVE 和 BELOW 之间)
    chordSymbol 独立 (LEFT+BOTTOM 错开 stack)

纪律: 纯静态 grep + Python 字符串分析, 零依赖, 零运行。
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
    paren_depth = 1
    i = start_match.end()
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
    j = i + 1
    while j < len(content) and brace_depth > 0:
        if content[j] == "{":
            brace_depth += 1
        elif content[j] == "}":
            brace_depth -= 1
        j += 1
    return content[start_match.start() : j]


def _extract_function(content, name):
    """提取指定函数 (name) 完整 body"""
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


class TestHelperExists(unittest.TestCase):
    def test_helper_function_defined(self):
        content = _read_app()
        self.assertIn(
            "function pickAnnotationOrder(",
            content,
            "pickAnnotationOrder helper should be defined",
        )

    def test_helper_above_order_constant(self):
        content = _read_app()
        helper = _extract_function(content, "pickAnnotationOrder")
        self.assertIsNotNone(helper, "pickAnnotationOrder function should exist")
        for name in ("articulation", "fingering", "textMark", "ornament", "fermata"):
            self.assertIn(
                f'"{name}"',
                helper,
                f"ABOVE order should include {name}",
            )

    def test_helper_below_order_constant(self):
        content = _read_app()
        helper = _extract_function(content, "pickAnnotationOrder")
        self.assertIsNotNone(helper)
        for name in ("dynamic", "pedal", "breath"):
            self.assertIn(
                f'"{name}"',
                helper,
                f"BELOW order should include {name}",
            )

    def test_helper_above_array_order(self):
        """ABOVE 数组顺序: articulation → fingering → textMark → ornament → fermata"""
        content = _read_app()
        helper = _extract_function(content, "pickAnnotationOrder")
        self.assertIsNotNone(helper)
        above = re.search(
            r'\[(.*?articulation.*?fingering.*?textMark.*?ornament.*?fermata.*?)\]',
            helper,
            re.DOTALL,
        )
        self.assertIsNotNone(
            above, "ABOVE array should contain articulation → ... → fermata in order"
        )
        self.assertLess(
            above.start(1), helper.find("dynamic"),
            "ABOVE array should be defined BEFORE BELOW array",
        )

    def test_helper_below_array_order(self):
        """BELOW 数组顺序: dynamic → pedal → breath"""
        content = _read_app()
        helper = _extract_function(content, "pickAnnotationOrder")
        self.assertIsNotNone(helper)
        below = re.search(
            r'\[(.*?dynamic.*?pedal.*?breath.*?)\]',
            helper,
            re.DOTALL,
        )
        self.assertIsNotNone(
            below, "BELOW array should contain dynamic → pedal → breath in order"
        )


class TestCreateVexNoteModifierOrder(unittest.TestCase):
    """createVexNote 内 8 个 if 块按 slot 顺序排列"""

    @classmethod
    def setUpClass(cls):
        content = _read_app()
        cls.createVexNote = _extract_createVexNote(content)
        assert cls.createVexNote is not None, "createVexNote function not found"

    def test_articulation_if_first_in_above_block(self):
        """articulation if 块在 ABOVE 区第 1 位"""
        above_section = self.createVexNote.split("grace")[0]
        first_if = re.search(r"if \(entry\.kind === \"note\" && entry\.\w+", above_section)
        self.assertIsNotNone(first_if, "should have at least one if block before grace")
        self.assertIn(
            "articulation",
            first_if.group(0),
            "first ABOVE if block should be articulation",
        )

    def test_fingering_after_articulation(self):
        """fingering if 块在 articulation 之后"""
        art_pos = self.createVexNote.find("entry.articulation")
        fing_pos = self.createVexNote.find("entry.fingering")
        self.assertGreater(
            fing_pos, art_pos,
            "fingering should come after articulation",
        )

    def test_textMark_after_fingering(self):
        fing_pos = self.createVexNote.find("entry.fingering")
        tm_pos = self.createVexNote.find("entry.textMark")
        self.assertGreater(
            tm_pos, fing_pos,
            "textMark should come after fingering",
        )

    def test_ornament_after_textMark(self):
        tm_pos = self.createVexNote.find("entry.textMark")
        orn_pos = self.createVexNote.find("entry.ornament")
        self.assertGreater(
            orn_pos, tm_pos,
            "ornament should come after textMark",
        )

    def test_fermata_after_ornament(self):
        orn_pos = self.createVexNote.find("entry.ornament")
        ferm_pos = self.createVexNote.find("entry.fermata")
        self.assertGreater(
            ferm_pos, orn_pos,
            "fermata should come after ornament",
        )

    def test_grace_between_fermata_and_dynamic(self):
        ferm_pos = self.createVexNote.find("entry.fermata")
        grace_pos = self.createVexNote.find("entry.grace")
        dyn_pos = self.createVexNote.find("entry.dynamic")
        self.assertGreater(
            grace_pos, ferm_pos,
            "grace should come after fermata",
        )
        self.assertLess(
            grace_pos, dyn_pos,
            "grace should come before dynamic (BELOW 区)",
        )

    def test_dynamic_before_pedal(self):
        dyn_pos = self.createVexNote.find("entry.dynamic")
        ped_pos = self.createVexNote.find("entry.pedal")
        self.assertGreater(
            ped_pos, dyn_pos,
            "pedal should come after dynamic",
        )

    def test_pedal_before_breath(self):
        ped_pos = self.createVexNote.find("entry.pedal")
        br_pos = self.createVexNote.find("entry.breath")
        self.assertGreater(
            br_pos, ped_pos,
            "breath should come after pedal",
        )

    def test_chordSymbol_last(self):
        """chordSymbol 总是最后 (独立处理)"""
        br_pos = self.createVexNote.find("entry.breath")
        cs_pos = self.createVexNote.find("entry.chordSymbol")
        self.assertGreater(
            cs_pos, br_pos,
            "chordSymbol should come after breath",
        )

    def test_all_10_modifier_blocks_present(self):
        """10 个 modifier if 块全在 createVexNote 内"""
        for name in (
            "articulation", "fingering", "textMark", "ornament", "fermata",
            "grace", "dynamic", "pedal", "breath", "chordSymbol",
        ):
            self.assertIn(
                f"entry.{name}",
                self.createVexNote,
                f"createVexNote should reference entry.{name}",
            )


class TestChordSymbolPosition(unittest.TestCase):
    """chordSymbol 改 LEFT + BOTTOM"""

    @classmethod
    def setUpClass(cls):
        content = _read_app()
        cls.createVexNote = _extract_createVexNote(content)
        assert cls.createVexNote is not None

    def test_chordSymbol_uses_LEFT_horizontal(self):
        """chordSymbol setHorizontal 改 LEFT (不再 CENTER_STEM)"""
        # 找 chordSymbol 的 setHorizontal 那一行
        match = re.search(
            r"entry\.chordSymbol[\s\S]{0,300}\.setHorizontal\(([^)]+)\)",
            self.createVexNote,
        )
        self.assertIsNotNone(match, "chordSymbol setHorizontal should be present")
        self.assertIn(
            "LEFT",
            match.group(1),
            "chordSymbol should use HorizontalJustify.LEFT",
        )
        self.assertNotIn(
            "CENTER_STEM",
            match.group(1),
            "chordSymbol should NOT use CENTER_STEM anymore",
        )

    def test_chordSymbol_uses_BOTTOM_vertical(self):
        """chordSymbol setVertical 改 BOTTOM (不再 TOP)"""
        match = re.search(
            r"entry\.chordSymbol[\s\S]{0,300}\.setVertical\(([^)]+)\)",
            self.createVexNote,
        )
        self.assertIsNotNone(match, "chordSymbol setVertical should be present")
        self.assertIn(
            "BOTTOM",
            match.group(1),
            "chordSymbol should use VerticalJustify.BOTTOM",
        )
        self.assertNotIn(
            "TOP",
            match.group(1),
            "chordSymbol should NOT use TOP anymore",
        )

    def test_chordSymbol_unchanged_other_code(self):
        """chordSymbol addText 仍然在 (不变)"""
        self.assertIn(
            ".addText(entry.chordSymbol)",
            self.createVexNote,
            "chordSymbol addText should still be present",
        )


class TestSignatureStability(unittest.TestCase):
    """不改变 createVexNote 签名"""

    def test_createVexNote_signature_unchanged(self):
        content = _read_app()
        match = re.search(r"function\s+createVexNote\s*\(([^)]*)\)", content)
        self.assertIsNotNone(match)
        params = [p.strip().split("=")[0].strip() for p in match.group(1).split(",")]
        self.assertEqual(
            params, ["entry", "clef", "timeSignature", "stemDirection", "voiceId"],
            f"createVexNote signature changed: {params}",
        )

    def test_helper_doesnt_call_createVexNote(self):
        """helper 不被 createVexNote 调用 (避免循环依赖)"""
        content = _read_app()
        helper = _extract_function(content, "pickAnnotationOrder")
        createVex = _extract_createVexNote(content)
        self.assertNotIn(
            "pickAnnotationOrder(entry)",
            createVex,
            "createVexNote should not call pickAnnotationOrder helper (避免循环依赖)",
        )

    def test_p22_5_a1_fermata_preserved(self):
        """A.1 改的 fermata "a@fermata" 仍然在"""
        content = _read_app()
        self.assertIn(
            'new VF.Articulation("a@fermata")',
            content,
            "A.1 fermata code 'a@fermata' should be preserved",
        )
        self.assertNotIn(
            'new VF.Articulation("a@a")',
            content,
            "A.1 old fermata code 'a@a' should NOT come back",
        )

    def test_articulationCodes_and_ornamentCodes_unchanged(self):
        """两张 codes 表不变"""
        content = _read_app()
        self.assertIn(
            "const articulationCodes = {",
            content,
        )
        self.assertIn(
            "const ornamentCodes = {",
            content,
        )
        for key in ("staccato", "accent", "tenuto", "marcato"):
            self.assertIn(f"{key}:", content)
        for key in ("mordent", "trill", "turn", "upprall", "downprall", "lineprall"):
            self.assertIn(f"{key}:", content)


if __name__ == "__main__":
    unittest.main()
