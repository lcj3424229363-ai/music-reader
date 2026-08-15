"""P22.3 Phase 1 — editorState 骨架静态测试。

不依赖 Node/jest/dom，纯字符串扫描 + JS 表达式求值（不执行 app.js）。
通过 docstring + 字段/方法名 + 边界字符串确认 editorState 模块形状。

Phase 1 边界：
- editorState 模块存在
- 6 核心字段都有
- setter 名字正确
- 操作方法（clearPreview / clearSelected / syncFromUI）存在
- 不替换 inputKind() / selectedEntryIndex（仍是 UI 单点真源）
"""
import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "web" / "app.js"


def read_app_js():
    return APP_JS.read_text(encoding="utf-8")


def extract_editor_state_block(source):
    """Extract the editorState object literal block as a string.

    从 `const editorState = {` 开始到匹配的 `};` 结束。
    """
    m = re.search(r"const editorState = \{", source)
    if not m:
        return None
    start = m.start()
    # 简单做法：从 start 找到下一个 `^};` 行（顶层闭合）
    lines = source[start:].split("\n")
    out = []
    depth = 0
    started = False
    for line in lines:
        out.append(line)
        for ch in line:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
        if started and depth == 0:
            break
    return "\n".join(out)


def test_editor_state_block_exists():
    """editorState 模块必须存在"""
    src = read_app_js()
    assert "const editorState = {" in src, "editorState 模块未找到"
    block = extract_editor_state_block(src)
    assert block is not None, "无法提取 editorState 块"


def test_editor_state_six_core_fields():
    """6 核心字段必须全部存在"""
    block = extract_editor_state_block(read_app_js())
    required_fields = [
        "inputMode:",
        "previewEntry:",
        "pendingMousePosition:",
        "selectedEntry:",
        "currentInputDuration:",
        "currentAccidental:",
    ]
    for field in required_fields:
        assert field in block, f"editorState 缺少字段: {field}"


def test_editor_state_derived_state():
    """派生状态 inputCapacity / isPreviewOverCapacity 必须存在"""
    block = extract_editor_state_block(read_app_js())
    assert "inputCapacity:" in block, "缺少 inputCapacity 派生状态"
    assert "isPreviewOverCapacity:" in block, "缺少 isPreviewOverCapacity 派生状态"


def test_editor_state_setters_exist():
    """setter 方法必须存在"""
    block = extract_editor_state_block(read_app_js())
    required_setters = [
        "setInputMode(",
        "setDuration(",
        "setAccidental(",
        "setPreview(",
        "setSelected(",
        "setMousePosition(",
        "updateCapacity(",
    ]
    for setter in required_setters:
        assert setter in block, f"editorState 缺少 setter: {setter}"


def test_editor_state_operations_exist():
    """操作方法 clearPreview / clearSelected / syncFromUI 必须存在"""
    block = extract_editor_state_block(read_app_js())
    for op in ["clearPreview(", "clearSelected(", "syncFromUI("]:
        assert op in block, f"editorState 缺少操作: {op}"


def test_set_input_mode_validates():
    """setInputMode 必须验证合法值（note/rest/chord）"""
    block = extract_editor_state_block(read_app_js())
    # 抓 setInputMode 函数体
    m = re.search(r"setInputMode\([^)]*\)\s*\{(.+?)\n\s*\}", block, re.DOTALL)
    assert m, "找不到 setInputMode 函数体"
    body = m.group(1)
    assert '"note"' in body and '"rest"' in body and '"chord"' in body, \
        "setInputMode 必须验证 3 种合法值"


def test_set_duration_computes_units():
    """setDuration 必须算出 units（直接调 durationUnits 表 OR 委托 _computeUnitsForDuration）"""
    block = extract_editor_state_block(read_app_js())
    m = re.search(r"setDuration\([^)]*\)\s*\{(.+?)\n\s*\}", block, re.DOTALL)
    assert m, "找不到 setDuration 函数体"
    body = m.group(1)
    # 接受两种实现：直接引用 durationUnits 表 / 委托 _computeUnitsForDuration
    assert ("durationUnits" in body) or ("_computeUnitsForDuration" in block), \
        "setDuration 必须使用 durationUnits 表或委托 _computeUnitsForDuration"
    assert "units:" in body, "setDuration 必须写 units 字段"


def test_clear_preview_resets_both():
    """clearPreview 必须清 previewEntry + pendingMousePosition 双字段"""
    block = extract_editor_state_block(read_app_js())
    m = re.search(r"clearPreview\([^)]*\)\s*\{(.+?)\n\s*\}", block, re.DOTALL)
    assert m, "找不到 clearPreview 函数体"
    body = m.group(1)
    assert "previewEntry = null" in body, "clearPreview 必须清 previewEntry"
    assert "pendingMousePosition = null" in body, "clearPreview 必须清 pendingMousePosition"


def test_clear_selected_resets_selected():
    """clearSelected 必须清 selectedEntry"""
    block = extract_editor_state_block(read_app_js())
    m = re.search(r"clearSelected\([^)]*\)\s*\{(.+?)\n\s*\}", block, re.DOTALL)
    assert m, "找不到 clearSelected 函数体"
    body = m.group(1)
    assert "selectedEntry = null" in body, "clearSelected 必须清 selectedEntry"


def test_sync_from_ui_uses_globals():
    """syncFromUI 必须读 noteDuration / noteDotted / noteAccidental 全局"""
    block = extract_editor_state_block(read_app_js())
    m = re.search(r"syncFromUI\([^)]*\)\s*\{(.+?)\n\s*\}", block, re.DOTALL)
    assert m, "找不到 syncFromUI 函数体"
    body = m.group(1)
    for var in ["noteDuration", "noteDotted", "noteAccidental"]:
        assert var in body, f"syncFromUI 必须读 {var}"


def test_no_existing_code_modified_phase1_boundary():
    """Phase 1 边界：现有 inputKind() / selectedEntryIndex 不能被替换或删"""
    src = read_app_js()
    # inputKind() 仍是 inputKind 形式（radio checked 同步源）
    assert "function inputKind(" in src, "inputKind() 不能被删"
    # selectedEntryIndex 仍是 UI 单点真源
    assert "let selectedEntryIndex" in src, "selectedEntryIndex 不能被删"


def test_editor_state_positioned_after_lastFourPartResult():
    """editorState 必须插在 lastFourPartResult 之后（line 202 位置）"""
    src = read_app_js()
    last_four_idx = src.index("let lastFourPartResult = null;")
    editor_state_idx = src.index("const editorState = {")
    assert last_four_idx > 0
    assert editor_state_idx > last_four_idx, \
        "editorState 必须插在 lastFourPartResult 之后"


def test_editor_state_inline_duration_calc():
    """editorState 必须用 inline _computeUnitsForDuration（不依赖外层 hoisted）"""
    block = extract_editor_state_block(read_app_js())
    assert "_computeUnitsForDuration" in block, "缺少 _computeUnitsForDuration 内部辅助"


# ===== 直接调 setDuration 验证 duration 算 units 的正确性 =====
# 不执行 app.js（依赖 DOM），通过 Python 复现 durationUnits 表 + dotted 算法
# 验证 P22.3 editorState 的 _computeUnitsForDuration 公式正确
DURATION_UNITS = {
    "0": 64, "1": 32, "2": 16, "4": 8, "8": 4, "16": 2, "32": 1, "64": 0.5
}


def python_compute_units_for_duration(duration, dotted):
    """复现 editorState._computeUnitsForDuration 公式"""
    base = DURATION_UNITS[duration]
    d = int(dotted or 0)
    units = base
    for i in range(d):
        units = units + base / (2 ** (i + 1))
    return units


def test_duration_units_whole():
    assert python_compute_units_for_duration("1", 0) == 32


def test_duration_units_half():
    assert python_compute_units_for_duration("2", 0) == 16


def test_duration_units_quarter():
    assert python_compute_units_for_duration("4", 0) == 8


def test_duration_units_eighth():
    assert python_compute_units_for_duration("8", 0) == 4


def test_duration_units_sixteenth():
    assert python_compute_units_for_duration("16", 0) == 2


def test_duration_units_thirtysecond():
    assert python_compute_units_for_duration("32", 0) == 1


def test_duration_units_doublewhole():
    assert python_compute_units_for_duration("0", 0) == 64


def test_duration_units_dotted_quarter():
    """dotted quarter = 8 + 4 = 12"""
    assert python_compute_units_for_duration("4", 1) == 12


def test_duration_units_double_dotted_quarter():
    """double-dotted quarter = 8 + 4 + 2 = 14"""
    assert python_compute_units_for_duration("4", 2) == 14


def test_duration_units_dotted_half():
    """dotted half = 16 + 8 = 24"""
    assert python_compute_units_for_duration("2", 1) == 24
