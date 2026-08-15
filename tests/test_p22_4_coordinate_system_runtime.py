"""
P22.4 CoordinateSystem v1 — Runtime 测试 (Node.js)

通过 subprocess 调 node 加载 web/coordinate-system.js, 测纯函数行为.
策略:
  - 不用 jsdom (没有依赖)
  - 测纯函数 (不需要 DOM):
    * meter / capacity
    * unitsForDuration (含 dot 公式)
    * localYToPitch (treble + bass)
    * canvasToStave / canvasToBeat / beatToCanvasX
    * isInNoteRange / isInPitchRange
    * sumUnits / exceedsUnits / sameUnits / normalizeUnits
  - staffAtPoint 测纯函数 (mock measureRects)
  - viewportToCanvas mock canvas 测 (不依赖 jsdom)
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CS_PATH = os.path.join(ROOT, "web", "coordinate-system.js").replace("\\", "/")


def _node_eval(expr):
    """Run `node -e "<expr>"` after requiring coordinate-system.js.
    Returns (stdout, stderr, returncode).
    """
    wrapped = f"const cs = require('{CS_PATH}'); const c = new cs.CoordinateSystem(); {expr}"
    proc = subprocess.run(
        ["node", "-e", wrapped],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=ROOT
    )
    return proc.stdout.strip(), proc.stderr.strip(), proc.returncode


def _assert_node(self, expr, expected):
    """Run expr, expect stdout to equal expected string."""
    out, err, rc = _node_eval(expr)
    if rc != 0:
        self.fail(f"node failed (rc={rc}):\nSTDERR: {err}\nSTDOUT: {out}\nEXPR: {expr}")
    self.assertEqual(out, str(expected),
                     f"Expected {expected!r}, got {out!r}\nEXPR: {expr}")


def _assert_node_json(self, expr, expected_obj):
    """Run expr, expect stdout to parse as JSON equal to expected_obj."""
    out, err, rc = _node_eval(expr)
    if rc != 0:
        self.fail(f"node failed (rc={rc}):\nSTDERR: {err}\nSTDOUT: {out}\nEXPR: {expr}")
    try:
        actual = json.loads(out)
    except json.JSONDecodeError as e:
        self.fail(f"Output not JSON: {out!r}\nError: {e}")
    self.assertEqual(actual, expected_obj,
                     f"Expected {expected_obj!r}, got {actual!r}\nEXPR: {expr}")


class TestCSLoad(unittest.TestCase):
    """cs 模块能否在 Node 加载"""

    def test_module_loads(self):
        # c is instance, so typeof is "object"; capacity is method, so "function"
        out, err, rc = _node_eval("console.log('loaded', typeof c, typeof c.capacity)")
        self.assertEqual(rc, 0, f"load failed: {err}")
        self.assertEqual(out, "loaded object function")

    def test_exposes_classes(self):
        out, err, rc = _node_eval(
            "console.log(typeof cs.CoordinateSystem, typeof cs.LayoutGeometry, typeof cs.MusicMapping)"
        )
        self.assertEqual(rc, 0)
        self.assertEqual(out, "function function function")

    def test_internals_exposed(self):
        out, err, rc = _node_eval(
            "console.log(typeof cs._internals.diatonicIndex, typeof cs._internals.meterForTimeSignature)"
        )
        self.assertEqual(rc, 0)
        self.assertEqual(out, "function function")


class TestCSMeterCapacity(unittest.TestCase):
    """meter / capacity 数值 (app.js:1867-1869)"""

    def test_4_4_capacity(self):
        _assert_node(self, "c.updateLayout({timeSignature: '4/4'}); console.log(c.capacity())", 32)

    def test_3_4_capacity(self):
        _assert_node(self, "c.updateLayout({timeSignature: '3/4'}); console.log(c.capacity())", 24)

    def test_6_8_capacity(self):
        _assert_node(self, "c.updateLayout({timeSignature: '6/8'}); console.log(c.capacity())", 24)

    def test_2_4_capacity(self):
        _assert_node(self, "c.updateLayout({timeSignature: '2/4'}); console.log(c.capacity())", 16)

    def test_4_4_beatUnit(self):
        _assert_node(self, "c.updateLayout({timeSignature: '4/4'}); console.log(c._internal.music.meter.beatUnit)", 8)

    def test_4_4_numerator(self):
        _assert_node(self, "c.updateLayout({timeSignature: '4/4'}); console.log(c._internal.music.meter.numerator)", 4)


class TestCSUnitsForDuration(unittest.TestCase):
    """duration + dotted → units (app.js:1924-1928)"""

    def test_whole_note(self):
        _assert_node(self, "console.log(c.unitsForDuration('0', 0))", 64)

    def test_half_note(self):
        _assert_node(self, "console.log(c.unitsForDuration('2', 0))", 16)

    def test_quarter_note(self):
        _assert_node(self, "console.log(c.unitsForDuration('4', 0))", 8)

    def test_eighth_note(self):
        _assert_node(self, "console.log(c.unitsForDuration('8', 0))", 4)

    def test_sixteenth_note(self):
        _assert_node(self, "console.log(c.unitsForDuration('16', 0))", 2)

    def test_32nd_note(self):
        _assert_node(self, "console.log(c.unitsForDuration('32', 0))", 1)

    def test_quarter_dotted(self):
        """4 分 + 1 dot = 8 * 1.5 = 12"""
        _assert_node(self, "console.log(c.unitsForDuration('4', 1))", 12)

    def test_quarter_double_dotted(self):
        """4 分 + 2 dot = 8 * 1.75 = 14"""
        _assert_node(self, "console.log(c.unitsForDuration('4', 2))", 14)

    def test_eighth_dotted(self):
        """8 分 + 1 dot = 4 * 1.5 = 6"""
        _assert_node(self, "console.log(c.unitsForDuration('8', 1))", 6)

    def test_dotted_as_true(self):
        """dotCount(true) = 1"""
        _assert_node(self, "console.log(c.unitsForDuration('4', true))", 12)


class TestCSLocalYToPitch(unittest.TestCase):
    """localY → {step, octave} (app.js:2155-2165)"""

    GEOM = "{staveX: 20, staveY: 12, noteStartX: 50, noteEndX: 270, topY: 20, bottomY: 60, halfStep: 5}"

    def test_treble_bottom_is_E4(self):
        """treble bottomY=60, halfStep=5: localY=60 → E4"""
        _assert_node_json(self,
            f"console.log(JSON.stringify(c.localYToPitch(60, 'treble', {self.GEOM})))",
            {"step": "E", "octave": 4})

    def test_treble_top_is_F5(self):
        """treble localY=20 → 8 halfSteps up = F5 (E4 + 8 = E5? 错: stepsFromBottom=(60-20)/5=8, noteIndex=30+8=38, octave=floor(38/7)=5, step=STEP_NAMES[38%7]=STEP_NAMES[3]=F)"""
        _assert_node_json(self,
            f"console.log(JSON.stringify(c.localYToPitch(20, 'treble', {self.GEOM})))",
            {"step": "F", "octave": 5})

    def test_treble_F4(self):
        """localY=55 → 1 halfStep up = F4"""
        _assert_node_json(self,
            f"console.log(JSON.stringify(c.localYToPitch(55, 'treble', {self.GEOM})))",
            {"step": "F", "octave": 4})

    def test_treble_B4(self):
        """localY=40 → 4 halfSteps up = A4? 30+4=34, 34/7=4 r 6, step[6]=B, octave=4 → B4"""
        _assert_node_json(self,
            f"console.log(JSON.stringify(c.localYToPitch(40, 'treble', {self.GEOM})))",
            {"step": "B", "octave": 4})

    def test_bass_bottom_is_G2(self):
        """bass bottomY=60, halfStep=5: localY=60 → G2"""
        _assert_node_json(self,
            f"console.log(JSON.stringify(c.localYToPitch(60, 'bass', {self.GEOM})))",
            {"step": "G", "octave": 2})

    def test_no_geometry_returns_default(self):
        """无 geometry → C4 fallback"""
        _assert_node_json(self,
            "console.log(JSON.stringify(c.localYToPitch(0, 'treble', null)))",
            {"step": "C", "octave": 4})


class TestCSCanvasToStave(unittest.TestCase):
    """canvas (x,y) + geometry → stave (localX, localY)"""

    GEOM = "{staveX:20, staveY:12, noteStartX:50, noteEndX:270, topY:20, bottomY:60, halfStep:5}"

    def test_basic(self):
        _assert_node_json(self,
            f"console.log(JSON.stringify(c.canvasToStave(80, 40, {self.GEOM})))",
            {"localX": 30, "localY": 28})

    def test_origin(self):
        """mouse at noteStartX, staveY → localX=0, localY=0"""
        _assert_node_json(self,
            f"console.log(JSON.stringify(c.canvasToStave(50, 12, {self.GEOM})))",
            {"localX": 0, "localY": 0})

    def test_no_geometry(self):
        _assert_node_json(self,
            "console.log(JSON.stringify(c.canvasToStave(100, 100, null)))",
            {"localX": 0, "localY": 0})


class TestCSIsInRange(unittest.TestCase):
    """isInNoteRange / isInPitchRange"""

    GEOM = "{staveX:20, staveY:12, noteStartX:50, noteEndX:270, topY:20, bottomY:60, halfStep:5}"

    def test_in_note_range_zero(self):
        _assert_node(self, f"console.log(c.isInNoteRange(0, {self.GEOM}))", "true")

    def test_in_note_range_max(self):
        """width=220, max localX=220"""
        _assert_node(self, f"console.log(c.isInNoteRange(220, {self.GEOM}))", "true")

    def test_out_note_range(self):
        _assert_node(self, f"console.log(c.isInNoteRange(250, {self.GEOM}))", "false")

    def test_in_pitch_range(self):
        """topY=20, bottomY=60, padding=42 → [-22, 102]"""
        _assert_node(self, f"console.log(c.isInPitchRange(28, {self.GEOM}))", "true")

    def test_in_pitch_range_at_top_edge(self):
        _assert_node(self, f"console.log(c.isInPitchRange(-22, {self.GEOM}))", "true")

    def test_out_pitch_range(self):
        _assert_node(self, f"console.log(c.isInPitchRange(200, {self.GEOM}))", "false")

    def test_no_geometry(self):
        _assert_node(self, "console.log(c.isInNoteRange(0, null))", "false")


class TestCSCanvasToBeat(unittest.TestCase):
    """canvas x → {beat, beatWidth, targetX}"""

    GEOM = "{staveX:20, staveY:12, noteStartX:50, noteEndX:270, topY:20, bottomY:60, halfStep:5}"
    METER = "cs._internals.meterForTimeSignature('4/4')"

    def test_beat_1(self):
        """canvas x=80, localX=30, beatFromX=floor(30/55)=0, beat=1, targetX=20+0+27.5=47.5"""
        _assert_node_json(self,
            f"console.log(JSON.stringify(c.canvasToBeat(80, {self.GEOM}, {self.METER})))",
            {"beat": 1, "beatWidth": 55, "targetX": 47.5})

    def test_beat_2(self):
        """canvas x=130, localX=80, beatFromX=floor(80/55)=1, beat=2, targetX=20+55+27.5=102.5"""
        _assert_node_json(self,
            f"console.log(JSON.stringify(c.canvasToBeat(130, {self.GEOM}, {self.METER})))",
            {"beat": 2, "beatWidth": 55, "targetX": 102.5})

    def test_beat_clamp_max(self):
        """canvas x=290, localX=240, beatFromX=floor(240/55)=4 → clamp to 4"""
        _assert_node_json(self,
            f"console.log(JSON.stringify(c.canvasToBeat(290, {self.GEOM}, {self.METER})))",
            {"beat": 4, "beatWidth": 55, "targetX": 212.5})

    def test_beat_with_default_meter(self):
        """不传 meter → 用 cs 内部 setMeter 的"""
        _assert_node(self,
            f"c.updateLayout({{timeSignature: '4/4'}}); console.log(c.canvasToBeat(80, {self.GEOM}).beat)",
            1)


class TestCSStaffAtPoint(unittest.TestCase):
    """staffAtPoint: canvas (x,y) → {staveKey, geometry, measureIndex, measureRect}"""

    GEOM = "{staveX:20, staveY:12, noteStartX:50, noteEndX:270, topY:20, bottomY:60, halfStep:5}"

    def test_single_staff_hit(self):
        expr = (
            f"c.updateLayout({{staffGeometry: {self.GEOM}, measureRects: [{{index:0, x:16, y:8, width:260, height:110, isCurrent:true, slot:0, row:0}}]}});"
            f"console.log(JSON.stringify(c.staffAtPoint(100, 40)))"
        )
        out, err, rc = _node_eval(expr)
        self.assertEqual(rc, 0, err)
        result = json.loads(out)
        self.assertEqual(result["staveKey"], "active")
        self.assertEqual(result["measureIndex"], 0)
        self.assertEqual(result["geometry"]["staveX"], 20)

    def test_single_staff_miss(self):
        expr = (
            f"c.updateLayout({{staffGeometry: {self.GEOM}, measureRects: [{{index:0, x:16, y:8, width:260, height:110, isCurrent:true, slot:0, row:0}}]}});"
            f"console.log(c.staffAtPoint(10, 40))"
        )
        _assert_node(self, expr, "null")

    def test_piano_treble_hit(self):
        expr = (
            f"const g = {self.GEOM};"
            f"c.updateLayout({{staffGeometry: g, trebleGeometry: g, bassGeometry: g, measureRects: [{{index:0, x:16, y:8, width:260, height:110, staveKey:'treble', isCurrent:true, slot:0, row:0}}]}});"
            f"console.log(JSON.stringify(c.staffAtPoint(100, 40)))"
        )
        out, err, rc = _node_eval(expr)
        self.assertEqual(rc, 0, err)
        result = json.loads(out)
        self.assertEqual(result["staveKey"], "treble")

    def test_piano_bass_hit(self):
        expr = (
            f"const g = {self.GEOM};"
            f"c.updateLayout({{staffGeometry: g, trebleGeometry: g, bassGeometry: g, measureRects: [{{index:0, x:16, y:140, width:260, height:110, staveKey:'bass', isCurrent:true, slot:0, row:0}}]}});"
            f"console.log(JSON.stringify(c.staffAtPoint(100, 160)))"
        )
        out, err, rc = _node_eval(expr)
        self.assertEqual(rc, 0, err)
        result = json.loads(out)
        self.assertEqual(result["staveKey"], "bass")


class TestCSSumUnits(unittest.TestCase):
    """sumUnits / exceedsUnits / sameUnits / normalizeUnits"""

    def test_sum_quarters(self):
        """4 个 4 分 = 4 * 8 = 32 units"""
        expr = (
            "const entries = [{duration: '4', dotted: 0}, {duration: '4', dotted: 0}, {duration: '4', dotted: 0}, {duration: '4', dotted: 0}];"
            "console.log(c.sumUnits(entries))"
        )
        _assert_node(self, expr, 32)

    def test_sum_with_dotted(self):
        """2 分 + 4 分 + 8 分 = 16 + 8 + 4 = 28 units"""
        expr = (
            "const entries = [{duration: '2', dotted: 0}, {duration: '4', dotted: 0}, {duration: '8', dotted: 0}];"
            "console.log(c.sumUnits(entries))"
        )
        _assert_node(self, expr, 28)

    def test_sum_with_cached_units(self):
        """entry.units 优先 (cache hit)"""
        expr = (
            "const entries = [{duration: '4', dotted: 0, units: 99}];"
            "console.log(c.sumUnits(entries))"
        )
        _assert_node(self, expr, 99)

    def test_sum_empty(self):
        _assert_node(self, "console.log(c.sumUnits([]))", 0)

    def test_exceeds_units_true(self):
        _assert_node(self, "console.log(c.exceedsUnits(17, 16))", "true")

    def test_exceeds_units_false_equal(self):
        _assert_node(self, "console.log(c.exceedsUnits(16, 16))", "false")

    def test_exceeds_units_false_less(self):
        _assert_node(self, "console.log(c.exceedsUnits(15, 16))", "false")

    def test_exceeds_units_epsilon(self):
        """差 0.0005 < 0.001 epsilon → false"""
        _assert_node(self, "console.log(c.exceedsUnits(16.0005, 16))", "false")

    def test_same_units_true(self):
        _assert_node(self, "console.log(c.sameUnits(16, 16))", "true")

    def test_same_units_false(self):
        _assert_node(self, "console.log(c.sameUnits(16, 16.1))", "false")

    def test_normalize_units(self):
        """normalizeUnits 保留 3 位小数"""
        _assert_node(self, "console.log(c.normalizeUnits(1.2345678))", 1.235)


class TestCSViewportToCanvas(unittest.TestCase):
    """viewportToCanvas(event, canvas) — 接受 canvas 作参数, 不绑 this._canvas"""

    def test_basic(self):
        """event.clientX=200, rect.left=50 → 150"""
        expr = (
            "const fakeCanvas = {getBoundingClientRect: () => ({left: 50, top: 30, right: 0, bottom: 0, width: 0, height: 0})};"
            "const ev = {clientX: 200, clientY: 100};"
            "console.log(JSON.stringify(c.viewportToCanvas(ev, fakeCanvas)))"
        )
        _assert_node_json(self, expr, {"x": 150, "y": 70})

    def test_no_canvas_returns_zero(self):
        expr = "console.log(JSON.stringify(c.viewportToCanvas({clientX: 200, clientY: 100}, null)))"
        _assert_node_json(self, expr, {"x": 0, "y": 0})


class TestCSClearLayout(unittest.TestCase):
    """clearLayout 重置所有状态"""

    def test_clear_resets_state(self):
        """clear 后 staffAtPoint 应该返回 null"""
        expr = (
            f"c.updateLayout({{staffGeometry: {self.GEOM}, measureRects: [{{index:0, x:16, y:8, width:260, height:110, isCurrent:true, slot:0, row:0}}], timeSignature: '4/4'}});"
            f"c.clearLayout();"
            f"console.log(JSON.stringify({{hit: c.staffAtPoint(100, 40), cap: c.capacity()}}))"
        )
        out, err, rc = _node_eval(expr)
        self.assertEqual(rc, 0, err)
        result = json.loads(out)
        self.assertIsNone(result["hit"], "staffAtPoint should be null after clear")
        self.assertEqual(result["cap"], 0, "capacity should be 0 after clear")

    GEOM = "{staveX:20, staveY:12, noteStartX:50, noteEndX:270, topY:20, bottomY:60, halfStep:5}"


if __name__ == "__main__":
    unittest.main(verbosity=2)
