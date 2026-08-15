"""test_p22_mouse_fix_static.py — P22 鼠标输入链修复静态验证

P22 修复了 5 类鼠标输入 bug (双谱表 / 跨 voice 选 / 撤销栈 / accidental
实时更新 / pitchFromY 接受参数)。本文件用字符串扫描验证这些修复
**没被回滚** — 跑不通, 但跑得过能 catch 关键代码丢失.

不是行为级测试 — 真行为验证需要浏览器 (jsdom / playwright).
"""
import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "web" / "app.js"


def _read_app_js() -> str:
    return APP_JS.read_text(encoding="utf-8")


def test_pitchFromY_signature_accepts_clef_and_geometry():
    """pitchFromY 必须接受 (y, clef, geometry) — 不再读 noteClef.value 全局."""
    src = _read_app_js()
    # 匹配 `function pitchFromY(y, clef, geometry)` 或带默认参数
    m = re.search(r"function\s+pitchFromY\s*\(([^)]*)\)", src)
    assert m, "pitchFromY function not found"
    params = [p.strip().split("=")[0].strip() for p in m.group(1).split(",")]
    assert "y" in params
    assert "clef" in params, f"pitchFromY must accept 'clef' param, got: {params}"
    assert "geometry" in params, f"pitchFromY must accept 'geometry' param, got: {params}"


def test_pitchFromY_no_longer_reads_noteClef_value():
    """pitchFromY 函数体内不应再读 noteClef.value — 用 caller 传参."""
    src = _read_app_js()
    # 抓 pitchFromY 函数体
    m = re.search(r"function\s+pitchFromY\s*\([^)]*\)\s*\{(.*?)\n\}", src, re.DOTALL)
    assert m, "pitchFromY function body not found"
    body = m.group(1)
    assert "noteClef.value" not in body, \
        "pitchFromY still reads global noteClef.value — caller must pass clef"
    assert "staffGeometry" not in body, \
        "pitchFromY still reads global staffGeometry — caller must pass geometry"


def test_resolveStaffAtPoint_helper_exists():
    """P22+ 新增 helper resolveStaffAtPoint 必须存在."""
    src = _read_app_js()
    assert "function resolveStaffAtPoint" in src, \
        "resolveStaffAtPoint helper not found"


def test_treble_and_bass_geometry_globals_exist():
    """P22+ 双谱表分别存 treble / bass 局部坐标."""
    src = _read_app_js()
    assert "let trebleGeometry" in src, "trebleGeometry global not declared"
    assert "let bassGeometry" in src, "bassGeometry global not declared"


def test_handleActiveStaffChange_no_longer_clears_editHistory():
    """P22+ 切 staff 不再清空 editHistory (撤销栈)."""
    src = _read_app_js()
    m = re.search(r"function\s+handleActiveStaffChange\s*\(\)\s*\{(.*?)\n\}", src, re.DOTALL)
    assert m
    body = m.group(1)
    assert "editHistory = []" not in body, \
        "handleActiveStaffChange still clears editHistory — undo stack will be lost on staff switch"


def test_handleActiveVoiceChange_no_longer_clears_editHistory():
    """P22+ 切 voice 不再清空 editHistory (撤销栈)."""
    src = _read_app_js()
    m = re.search(r"function\s+handleActiveVoiceChange\s*\(\)\s*\{(.*?)\n\}", src, re.DOTALL)
    assert m
    body = m.group(1)
    assert "editHistory = []" not in body, \
        "handleActiveVoiceChange still clears editHistory — undo stack will be lost on voice switch"


def test_noteAccidental_change_listener_exists():
    """P22+ accidental 改选下拉时实时更新选中 entry."""
    src = _read_app_js()
    # 找 noteAccidental 的 change 监听 (绑在 init 区域)
    assert re.search(
        r"bindEvent\(\s*noteAccidental\s*,\s*[\"']change[\"']",
        src
    ), "noteAccidental change listener not found — accidental dropdown won't update selected entry"


def test_addEntryFromScoreInner_uses_resolveStaffAtPoint():
    """P22+ addEntryFromScoreInner 必须用 resolveStaffAtPoint (不再 measureRects.find 直接查)."""
    src = _read_app_js()
    m = re.search(r"function\s+addEntryFromScoreInner\s*\([^)]*\)\s*\{(.*?)\n  commitEdit\(\(\) => \{\s*measureEntries\.push\(\{", src, re.DOTALL)
    # 简化: 找函数体前 50 行
    m = re.search(r"function\s+addEntryFromScoreInner\s*\([^)]*\)\s*\{(.*?)\n\}", src, re.DOTALL)
    assert m
    body = m.group(1)
    assert "resolveStaffAtPoint" in body, \
        "addEntryFromScoreInner does not call resolveStaffAtPoint"


def test_renderPianoNotation_writes_treble_and_bass_geometry():
    """P22+ 双谱表模式分别赋值 trebleGeometry 和 bassGeometry."""
    src = _read_app_js()
    m = re.search(r"function\s+renderPianoNotation\s*\([^)]*\)\s*\{(.*?)\n\}", src, re.DOTALL)
    assert m
    body = m.group(1)
    assert "trebleGeometry =" in body, "renderPianoNotation does not assign trebleGeometry"
    assert "bassGeometry =" in body, "renderPianoNotation does not assign bassGeometry"


def test_measureRects_in_piano_mode_has_staveKey_field():
    """P22+ 双谱表 measureRects 每条带 staveKey 字段."""
    src = _read_app_js()
    # 找 renderPianoNotation 内 measureRects.push
    m = re.search(r"function\s+renderPianoNotation\s*\([^)]*\)\s*\{(.*?)\n\}", src, re.DOTALL)
    assert m
    body = m.group(1)
    # 双 staff 拆 2 条 push, 都带 staveKey
    push_calls = re.findall(r"measureRects\.push\(([^)]+)\)", body, re.DOTALL)
    assert len(push_calls) >= 2, f"expected >=2 measureRects.push in piano mode, got {len(push_calls)}"
    for call in push_calls:
        assert "staveKey" in call, f"measureRects.push missing staveKey: {call[:80]}"


def test_selectEntry_syncs_voiceSelect():
    """P22+ selectEntry 同步 voiceSelect 到 entry.voice."""
    src = _read_app_js()
    m = re.search(r"function\s+selectEntry\s*\([^)]*\)\s*\{(.*?)\n\}", src, re.DOTALL)
    assert m
    body = m.group(1)
    assert "voiceSelect.value" in body, \
        "selectEntry does not sync voiceSelect — clicking other-voice entry won't switch voice"


def test_pitchFromY_keeps_backward_compatible_default_fallback():
    """pitchFromY 接受参数后, 无参调用应兜底不 crash (defensive)."""
    src = _read_app_js()
    m = re.search(r"function\s+pitchFromY\s*\(([^)]*)\)", src)
    assert m
    params = m.group(1)
    # 允许 clef / geometry 没默认 (caller 必须传), 但函数体必须有 defensive return
    func_match = re.search(r"function\s+pitchFromY\s*\([^)]*\)\s*\{(.*?)\n\}", src, re.DOTALL)
    assert func_match
    body = func_match.group(1)
    assert "return { step: \"C\", octave: 4 }" in body, \
        "pitchFromY must return safe fallback when clef/geometry missing"
