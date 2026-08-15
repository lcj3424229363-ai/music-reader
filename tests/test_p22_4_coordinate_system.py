"""
P22.4 CoordinateSystem v1 — 静态契约测试

检查 web/coordinate-system.js 的结构契约:
  - IIFE 包装
  - window + module.exports 双暴露
  - constructor 无参 (不绑 DOM)
  - 12 个核心方法存在
  - 内部 LayoutGeometry / MusicMapping 私有 helper
  - DURATION_UNITS scale 正确 (4 分 = 8 units, capacity 4/4 = 32)
  - 数值常量对齐 app.js (PITCH_RANGE_PADDING=42, UNIT_EPSILON=0.001)
  - 不绑 canvas 引用 (this._canvas 不存在)

零依赖: 纯 Python 字符串分析
"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CS_PATH = os.path.join(ROOT, "web", "coordinate-system.js")

REQUIRED_METHODS = [
    "viewportToCanvas",
    "staffAtPoint",
    "canvasToStave",
    "canvasToBeat",
    "beatToCanvasX",
    "isInNoteRange",
    "isInPitchRange",
    "localYToPitch",
    "unitsForDuration",
    "unitsForEntry",
    "sumUnits",
    "exceedsUnits",
    "sameUnits",
    "normalizeUnits",
    "capacity",
    "updateLayout",
    "clearLayout",
]


def _read_cs():
    with open(CS_PATH, "r", encoding="utf-8") as f:
        return f.read()


class TestCSFileExists(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(os.path.exists(CS_PATH), f"coordinate-system.js not found at {CS_PATH}")

    def test_file_nonempty(self):
        content = _read_cs()
        self.assertGreater(len(content), 5000, "coordinate-system.js too small (<5KB)")


class TestCSIIFE(unittest.TestCase):
    """IIFE 包装 + 双暴露"""

    def test_iife_wrapper(self):
        content = _read_cs()
        # 允许前面有注释行, 找第一个 (function (root, factory) 出现位置
        self.assertRegex(content, r"\(function\s*\(root,\s*factory\)", "Should contain IIFE (function(root, factory)")
        self.assertIn("root.CoordinateSystem = exported.CoordinateSystem;", content)

    def test_module_exports(self):
        content = _read_cs()
        self.assertIn("module.exports = exported;", content, "Should export via module.exports for Node tests")

    def test_no_canvas_in_constructor(self):
        """用户明确要求: 不绑 DOM. constructor 无参"""
        content = _read_cs()
        # 找 class CoordinateSystem { constructor() { ... } }
        m = re.search(r"class\s+CoordinateSystem\s*\{[\s\S]*?constructor\s*\(([^)]*)\)", content)
        self.assertIsNotNone(m, "CoordinateSystem class not found")
        params = m.group(1).strip()
        self.assertEqual(params, "", f"constructor should be no-arg, got ({params})")

    def test_no_canvas_reference(self):
        """this._canvas 不应存在"""
        content = _read_cs()
        self.assertNotIn("this._canvas", content, "CoordinateSystem should NOT hold canvas reference (this._canvas)")


class TestCSCoreMethods(unittest.TestCase):
    """12 个核心方法 (P22.4-A 设计) 全部存在"""

    def setUp(self):
        self.content = _read_cs()

    def test_all_methods_present(self):
        for method in REQUIRED_METHODS:
            pattern = rf"(?:^|\s){method}\s*\("
            self.assertRegex(self.content, pattern, f"Method {method} not found")


class TestCSDurationUnits(unittest.TestCase):
    """DURATION_UNITS scale 必须对齐 app.js:112"""

    def test_duration_units_scale(self):
        content = _read_cs()
        # 真实值 (app.js:112): "0":64, "1":32, "2":16, "4":8, "8":4, "16":2, "32":1, "64":0.5
        self.assertIn("'0': 64", content, "'0': 64 (二全) must be present")
        self.assertIn("'1': 32", content, "'1': 32 (全) must be present")
        self.assertIn("'2': 16", content, "'2': 16 (二分) must be present")
        self.assertIn("'4': 8", content, "'4': 8 (四分) must be present")
        self.assertIn("'8': 4", content, "'8': 4 (八分) must be present")
        self.assertIn("'16': 2", content, "'16': 2 (十六分) must be present")
        self.assertIn("'32': 1", content, "'32': 1 (三十二分) must be present")
        self.assertIn("'64': 0.5", content, "'64': 0.5 (六十四分) must be present")


class TestCSConstants(unittest.TestCase):
    """数值常量对齐 app.js"""

    def test_pitch_range_padding(self):
        """app.js:2066, 2695 — pitch 区域上下 padding = 42"""
        content = _read_cs()
        self.assertIn("PITCH_RANGE_PADDING = 42", content)

    def test_unit_epsilon(self):
        """app.js:1952 — 容量比较 epsilon = 0.001"""
        content = _read_cs()
        self.assertIn("UNIT_EPSILON = 0.001", content)

    def test_clef_bottom_lines(self):
        """app.js:111 — treble=E4, bass=G2"""
        content = _read_cs()
        self.assertIn("treble: 'E4'", content)
        self.assertIn("bass: 'G2'", content)


class TestCSCapacityFormula(unittest.TestCase):
    """capacity = numerator * (32/denominator) — app.js:1867"""

    def test_capacity_formula_present(self):
        content = _read_cs()
        self.assertIn("numerator * (32 / denominator)", content, "capacity formula must match app.js:1867")

    def test_beatunit_formula_present(self):
        content = _read_cs()
        self.assertIn("beatUnit: 32 / denominator", content, "beatUnit formula must match app.js:1868")


class TestCSDotCount(unittest.TestCase):
    """dotCount 公式 — app.js:1905"""

    def test_dot_count_formula(self):
        content = _read_cs()
        # dotCount(value === true ? 1 : Number(value) || 0)
        self.assertRegex(content, r"value\s*===\s*true\s*\?\s*1\s*:\s*Number\(value\)\s*\|\|\s*0")


class TestCSDiatonicIndex(unittest.TestCase):
    """diatonicIndex 公式 — app.js:2167-2171"""

    def test_diatonic_index_present(self):
        content = _read_cs()
        self.assertRegex(content, r"function\s+diatonicIndex")
        # regex: /^([A-G])(-?\d+)$/
        self.assertIn(r'/^([A-G])(-?\d+)$/', content)
        # fallback: STEP_INDEX.E + 4 * 7
        self.assertIn("STEP_INDEX.E + 4 * 7", content)
        # 计算: Number(match[2]) * 7 + STEP_INDEX[match[1]]
        self.assertIn("Number(match[2]) * 7 + STEP_INDEX[match[1]]", content)


class TestCSLayoutGeometry(unittest.TestCase):
    """LayoutGeometry 内部 helper 存在"""

    def test_class_defined(self):
        content = _read_cs()
        self.assertRegex(content, r"class\s+LayoutGeometry\s*\{")

    def test_required_methods(self):
        content = _read_cs()
        for method in ["update", "clear", "staffAtPoint", "canvasToStave", "canvasToBeat", "beatToCanvasX", "isInNoteRange", "isInPitchRange"]:
            self.assertRegex(content, rf"class\s+LayoutGeometry\s*\{{[\s\S]*?(?:^|\s){method}\s*\(", f"LayoutGeometry.{method} not found")

    def test_staffAtPoint_uses_measureRects(self):
        """staffAtPoint 内部必须用 measureRects.find"""
        content = _read_cs()
        m = re.search(r"staffAtPoint\s*\([^)]*\)\s*\{([\s\S]*?)\n\s*\}", content)
        self.assertIsNotNone(m, "staffAtPoint body not found")
        body = m.group(1)
        self.assertIn("this.measureRects.find", body, "staffAtPoint must use this.measureRects.find")
        self.assertIn("m.x", body, "must check m.x")
        self.assertIn("m.width", body, "must check m.width")
        self.assertIn("m.y", body, "must check m.y")
        self.assertIn("m.height", body, "must check m.height")


class TestCSMusicMapping(unittest.TestCase):
    """MusicMapping 内部 helper 存在"""

    def test_class_defined(self):
        content = _read_cs()
        self.assertRegex(content, r"class\s+MusicMapping\s*\{")

    def test_required_methods(self):
        content = _read_cs()
        for method in ["setMeter", "clear", "localYToPitch", "unitsForDuration", "unitsForEntry", "sumUnits", "exceedsUnits", "sameUnits", "normalizeUnits", "capacity"]:
            self.assertRegex(content, rf"class\s+MusicMapping\s*\{{[\s\S]*?(?:^|\s){method}\s*\(", f"MusicMapping.{method} not found")

    def test_unitsForDuration_uses_DURATION_UNITS(self):
        content = _read_cs()
        m = re.search(r"unitsForDuration\s*\([^)]*\)\s*\{([\s\S]*?)\n\s*\}", content)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertIn("DURATION_UNITS[duration]", body)
        self.assertIn("* 1.5", body, "must have 1-dot formula (×1.5)")
        self.assertIn("* 1.75", body, "must have 2-dot formula (×1.75)")

    def test_localYToPitch_uses_geometry_bottomY_and_halfStep(self):
        content = _read_cs()
        m = re.search(r"localYToPitch\s*\([^)]*\)\s*\{([\s\S]*?)\n\s*\}", content)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertIn("geometry.bottomY", body)
        self.assertIn("geometry.halfStep", body)
        self.assertIn("diatonicIndex", body)


class TestCSUpdateLayoutSignature(unittest.TestCase):
    """updateLayout payload 必含字段"""

    def test_destructures_required_fields(self):
        content = _read_cs()
        m = re.search(r"updateLayout\s*\([^)]*\)\s*\{([\s\S]*?)\n\s*\}", content)
        self.assertIsNotNone(m, "updateLayout body not found")
        body = m.group(1)
        for field in ["staffGeometry", "trebleGeometry", "bassGeometry", "measureRects", "currentMeasureIndex", "timeSignature"]:
            self.assertIn(field, body, f"updateLayout must destructure {field}")


class TestCSPureLocalYToPitchComment(unittest.TestCase):
    """localYToPitch 注释必须明确: caller 传 localY (相对 staveY), 不是 canvas 坐标"""

    def test_doc_warns_localY(self):
        content = _read_cs()
        m = re.search(r"localYToPitch\s*\([^)]*\)\s*\{([\s\S]*?)\n\s*\}", content)
        self.assertIsNotNone(m)
        # 取 JSDoc (在方法上一段)
        idx = m.start()
        before = content[max(0, idx - 500):idx]
        self.assertTrue(
            "localY" in before or "local" in before.lower(),
            "localYToPitch should have JSDoc warning that input is localY (not canvas)"
        )


class TestCSBrowserWindowExport(unittest.TestCase):
    """window + module.exports 双暴露"""

    def test_window_export(self):
        content = _read_cs()
        self.assertRegex(content, r"root\.CoordinateSystem\s*=\s*exported\.CoordinateSystem")

    def test_module_export(self):
        content = _read_cs()
        self.assertRegex(content, r"module\.exports\s*=\s*exported")


class TestCSInternalsExposedForTests(unittest.TestCase):
    """_internals 字段 (测试用, 业务不要用)"""

    def test_internals_field(self):
        content = _read_cs()
        self.assertIn("_internals:", content, "Should expose _internals for test access")


if __name__ == "__main__":
    unittest.main(verbosity=2)
