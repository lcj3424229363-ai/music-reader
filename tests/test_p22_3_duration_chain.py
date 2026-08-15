"""P22.3 duration-cleanup — 时值链 single source of truth 静态契约测试。

约束（你 P22.3 duration-cleanup 明确要求）：
1. 全局 grep noteDuration.value：业务逻辑（addEntryFromScoreInner / applyDurationToSelected
   / parseBatchInput / parseScoreMeasureText / handleNoteCanvasHover）不再直接读 UI
   唯一允许读 UI 的地方：syncFromUI / refreshPreviewFromUI（UI→editorState 同步入口）
2. setDuration( 调用点：只能从 syncFromUI / refreshPreviewFromUI 进入
3. previewEntry 构造单一入口：buildPreviewFromState — 业务逻辑不再自己拼
4. business 读 input 状态必须走 editorState.getInputDuration() / getInputAccidental()
"""
import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "web" / "app.js"


def read_app_js():
    return APP_JS.read_text(encoding="utf-8")


def strip_js_comments(src):
    """去 // 单行注释 和 /* */ 多行注释。保留字符串字面量。
    简化版：够用即可"""
    # 去掉 // 单行注释（不在字符串内 — 简化：直接删行末 // 后内容）
    out = []
    in_block = False
    for line in src.split("\n"):
        i = 0
        new_line = []
        while i < len(line):
            if in_block:
                end = line.find("*/", i)
                if end < 0:
                    i = len(line)
                    continue
                in_block = False
                i = end + 2
                continue
            # 找 // 或 /* 或字符串开头
            # 简化：只看 // 和 /*
            if line[i:i+2] == "//":
                break  # 后续都是注释
            if line[i:i+2] == "/*":
                in_block = True
                i += 2
                continue
            new_line.append(line[i])
            i += 1
        out.append("".join(new_line))
    return "\n".join(out)


def find_function_ranges(src):
    """找所有 function NAME(...) { ... } 或方法简写 NAME(...) { ... } 的 (start_line, end_line, name)。
    end_line 是匹配的 } 所在行。"""
    lines = src.split("\n")
    # 找所有 `function NAME(` 或  `  NAME(` (方法简写)
    starts = []
    for i, line in enumerate(lines):
        m1 = re.match(r"^\s*function\s+(\w+)\s*\(", line)
        if m1:
            starts.append((i, m1.group(1)))
            continue
        m2 = re.match(r"^\s{2,}(\w+)\s*\([^)]*\)\s*\{", line)
        if m2 and not line.lstrip().startswith("//"):
            starts.append((i, m2.group(1)))
    # 对每个 start，用 brace 计数找 end
    ranges = []
    for start_line_0idx, name in starts:
        # 找函数体 { — 用 rfind 找该行最后一个 {（处理 destructuring 干扰）
        brace_col = lines[start_line_0idx].rfind("{")
        if brace_col < 0:
            continue
        brace_line_0idx = start_line_0idx
        # 计数 — 从 brace 开始
        depth = 0
        end_line_0idx = brace_line_0idx
        for i in range(brace_line_0idx, len(lines)):
            start_col = brace_col if i == brace_line_0idx else 0
            for ch in lines[i][start_col:]:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end_line_0idx = i
                        break
            if depth == 0 and i >= brace_line_0idx:
                break
        ranges.append((start_line_0idx + 1, end_line_0idx + 1, name))
    return ranges


def get_body_lines(src, name, ranges):
    """取函数体的行号范围 (start, end)。"""
    for s, e, n in ranges:
        if n == name:
            return s, e
    return None, None


# ===== rule 1: business 不再直接读 noteDuration.value / noteDotted.value / noteAccidental.value =====

# 这些函数允许读 UI（它们就是 UI→editorState 同步入口本身）
SYNC_FUNCS_ALLOWED_TO_READ_UI = {
    "syncFromUI",         # 显式 UI→editorState
    "refreshPreviewFromUI",  # SELECT change → editorState 同步
}


def test_business_no_direct_ui_read_for_duration():
    """业务函数不能直接读 noteDuration.value / noteDotted.value / noteAccidental.value
    只能通过 editorState.getInputDuration() / getInputAccidental()"""
    raw_src = read_app_js()
    src = strip_js_comments(raw_src)
    ranges = find_function_ranges(src)
    business_funcs = [
        "addEntryFromScoreInner",
        "applyDurationToSelected",
        "parseBatchInput",
        "parseScoreMeasureText",
        "handleNoteCanvasHover",
        "buildPreviewFromState",
    ]
    lines = src.split("\n")
    for fn in business_funcs:
        s, e = get_body_lines(src, fn, ranges)
        assert s is not None, f"找不到函数 {fn}"
        body = "\n".join(lines[s - 1:e])
        for pat in [r"noteDuration\.value", r"noteDotted\.value", r"noteAccidental\.value", r"noteAccidental\?\.value"]:
            assert not re.search(pat, body), \
                f"{fn} (line {s}-{e}) 仍直接读 {pat} — 必须改用 editorState.getInputDuration() / getInputAccidental()"


def test_sync_funcs_can_read_ui():
    """syncFromUI / refreshPreviewFromUI 允许直接读 UI（它们就是同步入口）"""
    raw_src = read_app_js()
    src = strip_js_comments(raw_src)
    ranges = find_function_ranges(src)
    for fn in SYNC_FUNCS_ALLOWED_TO_READ_UI:
        s, e = get_body_lines(src, fn, ranges)
        assert s is not None, f"找不到 {fn}"
        lines = src.split("\n")
        body = "\n".join(lines[s - 1:e])
        assert "noteDuration" in body, f"{fn} 必须是 UI→editorState 同步入口（含 noteDuration 引用）"


# ===== rule 2: setDuration() 调用只允许在 sync 入口 =====

def test_setDuration_only_called_in_sync_entries():
    """setDuration( 调用点：只能从 syncFromUI / refreshPreviewFromUI 进入
    业务逻辑（hover / addEntry / applyDuration / parseBatch / buildPreview）禁止 setDuration"""
    raw_src = read_app_js()
    src = strip_js_comments(raw_src)
    ranges = find_function_ranges(src)
    lines = src.split("\n")
    call_sites = []
    for i, line in enumerate(lines, 1):
        if re.search(r"^\s*setDuration\([^)]*\)\s*\{", line):
            continue
        if "setDuration(" in line:
            call_sites.append((i, line.strip()))

    for line_no, call_line in call_sites:
        enclosing_fn = None
        for s, e, n in ranges:
            if s <= line_no <= e:
                enclosing_fn = n
                break
        assert enclosing_fn in SYNC_FUNCS_ALLOWED_TO_READ_UI, \
            f"line {line_no}: setDuration() 调用必须在 sync 入口 (syncFromUI / refreshPreviewFromUI), " \
            f"但在 {enclosing_fn} 里: {call_line}"


# ===== rule 3: previewEntry 构造单一入口 =====

def test_preview_entry_construction_only_in_build_preview():
    """previewEntry ({...}) 构造只允许在 buildPreviewFromState
    业务逻辑（handleNoteCanvasHover / refreshPreviewFromUI）必须调它，不能自己拼"""
    raw_src = read_app_js()
    src = strip_js_comments(raw_src)
    ranges = find_function_ranges(src)
    lines = src.split("\n")
    s, e = get_body_lines(src, "handleNoteCanvasHover", ranges)
    assert s is not None
    hover_body = "\n".join(lines[s - 1:e])
    assert "buildPreviewFromState(" in hover_body, \
        "handleNoteCanvasHover 必须调 buildPreviewFromState（single source 入口）"
    assert '_ghost: true' not in hover_body, \
        "handleNoteCanvasHover 不应自己拼 _ghost: true（必须走 buildPreviewFromState）"

    s, e = get_body_lines(src, "refreshPreviewFromUI", ranges)
    assert s is not None
    refresh_body = "\n".join(lines[s - 1:e])
    assert "buildPreviewFromState(" in refresh_body, \
        "refreshPreviewFromUI 必须调 buildPreviewFromState（single source 入口）"
    assert '_ghost: true' not in refresh_body, \
        "refreshPreviewFromUI 不应自己拼 _ghost: true（必须走 buildPreviewFromState）"


def test_build_preview_from_state_exists():
    """buildPreviewFromState 必须存在 — 单一 preview 构造入口"""
    raw_src = read_app_js()
    src = strip_js_comments(raw_src)
    assert "function buildPreviewFromState(" in src, \
        "buildPreviewFromState 单一入口必须存在（duration-cleanup 抽出）"
    ranges = find_function_ranges(src)
    lines = src.split("\n")
    s, e = get_body_lines(src, "buildPreviewFromState", ranges)
    assert s is not None
    body = "\n".join(lines[s - 1:e])
    assert "editorState.getInputDuration()" in body, \
        "buildPreviewFromState 必须从 editorState.getInputDuration() 读"
    assert "editorState.getInputAccidental()" in body, \
        "buildPreviewFromState 必须从 editorState.getInputAccidental() 读"


# ===== rule 4: business 读 input 走 editorState =====

def test_business_uses_getInputDuration():
    """业务函数必须用 editorState.getInputDuration() 而不是直接读 UI"""
    raw_src = read_app_js()
    src = strip_js_comments(raw_src)
    ranges = find_function_ranges(src)
    lines = src.split("\n")
    business_funcs = [
        "addEntryFromScoreInner",
        "applyDurationToSelected",
        "parseBatchInput",
        "parseScoreMeasureText",
        "handleNoteCanvasHover",
        "buildPreviewFromState",
    ]
    for fn in business_funcs:
        s, e = get_body_lines(src, fn, ranges)
        assert s is not None, f"找不到 {fn}"
        body = "\n".join(lines[s - 1:e])
        assert "editorState.getInputDuration()" in body, \
            f"{fn} 必须用 editorState.getInputDuration() 读 input duration"


# ===== rule 5: editorState 提供 single-source getter =====

def test_editor_state_has_input_getters():
    """editorState 必须有 getInputDuration() / getInputAccidental() — 业务唯一入口"""
    src = read_app_js()
    m = re.search(r"const editorState\s*=\s*\{(.+?)\n\};", src, re.DOTALL)
    assert m, "找不到 editorState 对象"
    body = m.group(1)
    assert "getInputDuration()" in body, \
        "editorState 必须有 getInputDuration() getter"
    assert "getInputAccidental()" in body, \
        "editorState 必须有 getInputAccidental() getter"


# ===== rule 6: editorState 不存 _ghost previewEntry 自身 — previewEntry 是另一个字段 =====
# (P22.3 duration-cleanup: 业务只能 setPreview，不混 duration)


def test_preview_entry_set_only_in_sync_or_hover_or_build():
    """editorState.setPreview() 调用点：buildPreviewFromState + hover/refresh（业务不直接拼）"""
    raw_src = read_app_js()
    src = strip_js_comments(raw_src)
    ranges = find_function_ranges(src)
    lines = src.split("\n")
    business_funcs = [
        "addEntryFromScoreInner",
        "applyDurationToSelected",
        "parseBatchInput",
        "parseScoreMeasureText",
        "handleNoteCanvasHover",
        "refreshPreviewFromUI",
    ]
    for fn in business_funcs:
        s, e = get_body_lines(src, fn, ranges)
        if s is None:
            continue
        body = "\n".join(lines[s - 1:e])
        # 业务函数只能 setPreview（已构造好的对象），不能字面量拼 _ghost
        # 检查不出现 "_ghost: true" 字面量
        if fn != "buildPreviewFromState":  # buildPreview 本身允许
            assert "_ghost: true" not in body, \
                f"{fn} 不应直接拼 _ghost: true（必须走 buildPreviewFromState）"


# ===== rule 7: selectedDotCount 不 fallback UI（时值多源零容忍） =====

def test_selectedDotCount_no_ui_fallback():
    """selectedDotCount 业务函数不再直接读 noteDotted.value
    只从 editorState.currentInputDuration.dotted 读 — 时值多源零容忍
    """
    raw_src = read_app_js()
    src = strip_js_comments(raw_src)
    ranges = find_function_ranges(src)
    lines = src.split("\n")
    s, e = get_body_lines(src, "selectedDotCount", ranges)
    assert s is not None, "找不到 selectedDotCount 函数"
    body = "\n".join(lines[s - 1:e])
    # 业务函数禁止读 noteDotted.value (之前是 fallback: Number(noteDotted.value || "0") || 0)
    for pat in [r"noteDotted\.value", r"noteAccidental\.value", r"noteDuration\.value"]:
        assert not re.search(pat, body), \
            f"selectedDotCount (line {s}-{e}) 仍直接读 {pat} — 必须只走 editorState"
    # 必须用 editorState
    assert "editorState" in body, \
        "selectedDotCount 必须用 editorState 读 dotted 状态"


# ===== rule 8: handleNoteCanvasHover 不做 setAccidental self-assign =====

def test_handleNoteCanvasHover_no_self_assign():
    """handleNoteCanvasHover 不应 setAccidental(getInputAccidental())
    (那是 self-cover no-op, 真正的 source-of-truth 在 setAccidental 已被 sync 入口写过)
    """
    raw_src = read_app_js()
    src = strip_js_comments(raw_src)
    ranges = find_function_ranges(src)
    lines = src.split("\n")
    s, e = get_body_lines(src, "handleNoteCanvasHover", ranges)
    assert s is not None, "找不到 handleNoteCanvasHover 函数"
    body = "\n".join(lines[s - 1:e])
    # 找 setAccidental(getInputAccidental()) 这种 no-op 调用
    assert not re.search(r"setAccidental\s*\(\s*getInputAccidental\s*\(\s*\)\s*\)", body), \
        f"handleNoteCanvasHover (line {s}-{e}) 仍在 setAccidental(getInputAccidental()) " \
        f"—— 这是 no-op self-cover, 应删除"


# ===== rule 9: setAccidental( 也只允许在 sync 入口调用 =====

def test_setAccidental_only_called_in_sync_entries():
    """setAccidental( 调用点: 跟 setDuration 一样, 只允许在 syncFromUI / refreshPreviewFromUI
    业务函数 (handleNoteCanvasHover / addEntry / applyDuration / parseBatch / buildPreview) 禁止
    """
    raw_src = read_app_js()
    src = strip_js_comments(raw_src)
    ranges = find_function_ranges(src)
    lines = src.split("\n")
    call_sites = []
    for i, line in enumerate(lines, 1):
        if re.search(r"^\s*setAccidental\s*\([^)]*\)\s*\{", line):
            continue  # 函数定义本身
        if "setAccidental(" in line and "function setAccidental" not in line:
            # 排除 const setAccidental = " 之类 (我们用方法简写不会有)
            call_sites.append((i, line.strip()))

    for line_no, call_line in call_sites:
        enclosing_fn = None
        for s, e, n in ranges:
            if s <= line_no <= e:
                enclosing_fn = n
                break
        assert enclosing_fn in SYNC_FUNCS_ALLOWED_TO_READ_UI, \
            f"line {line_no}: setAccidental() 调用必须在 sync 入口 " \
            f"(syncFromUI / refreshPreviewFromUI), 但在 {enclosing_fn} 里: {call_line}"


# ===== rule 10: 显式用户输入路径收口到 editorState.setDuration =====

def test_user_input_paths_reach_setDuration():
    """所有用户输入路径 (ribbon / keyboard / inspector) 最终必须触发 editorState.setDuration
    验证 3 条路径:
      1. ribbon 控件 (input[type=radio][data-bridge=noteDuration]) change 事件 → 走 syncRibbonToTarget
      2. keyboard DURATION_KEYS (1/2/3/4/5/6) 改 inspector.value 然后 dispatch change
      3. noteDuration select 直接 change → refreshPreviewFromUI 监听器
    关键: 这些路径最终必须触发 editorState.setDuration (或 setDuration via syncFromUI)
    """
    raw_src = read_app_js()
    src = strip_js_comments(raw_src)
    # 检查 refreshPreviewFromUI 监听 noteDuration 的 change 事件
    assert 'bindEvent(noteDuration, "change", refreshPreviewFromUI)' in src, \
        "noteDuration 控件必须绑 refreshPreviewFromUI 监听器 (sync 入口)"
    # 检查 keyboard handler 改完 dur.value 后 dispatch change
    keyboard_match = re.search(
        r'DURATION_KEYS\s*=\s*\{[^}]+\}',
        src
    )
    assert keyboard_match, "找不到 DURATION_KEYS 字典"
    # keyboard 必须 dispatch change (这样会触发 refreshPreviewFromUI → editorState.setDuration)
    # 用 line range 抓 keyboard handler block: 找 addEventListener("keydown" 那一行, 抓到下一个 }) 结束
    lines = src.split("\n")
    kb_start = None
    for i, line in enumerate(lines, 1):
        if 'addEventListener("keydown"' in line:
            kb_start = i  # 1-indexed
            break
    assert kb_start is not None, "找不到 keydown 监听器"
    # 从 kb_start 开始, 数 brace depth, 找结束
    depth = 0
    kb_end = None
    for j in range(kb_start - 1, len(lines)):
        for ch in lines[j]:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    kb_end = j + 1
                    break
        if kb_end is not None:
            break
    assert kb_end is not None, "keyboard handler 没找到匹配的 }"
    kb_body = "\n".join(lines[kb_start - 1:kb_end])
    # keyboard 必须 dispatch change (路径: dur.value=value; dispatchEvent(change) → refreshPreviewFromUI → setDuration)
    assert "dispatchEvent" in kb_body and "change" in kb_body, \
        "keyboard handler 必须 dispatch change 事件以触发 refreshPreviewFromUI → editorState.setDuration"
    # ribbon → syncRibbonToTarget → 改 inspector.value + dispatch change
    assert "syncRibbonToTarget" in src, \
        "ribbon 必须通过 syncRibbonToTarget 把变更路由到 inspector"
    # syncRibbonToTarget 内部要 dispatch change
    ranges = find_function_ranges(src)
    s, e = get_body_lines(src, "syncRibbonToTarget", ranges)
    assert s is not None, "找不到 syncRibbonToTarget 函数"
    lines = src.split("\n")
    sync_body = "\n".join(lines[s - 1:e])
    assert "dispatchEvent" in sync_body and "change" in sync_body, \
        "syncRibbonToTarget 必须 dispatch change 事件"
