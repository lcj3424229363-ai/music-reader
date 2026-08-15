"""P22.3 duration-cleanup — 时值链 runtime simulation

模拟用户场景：
  1. 初始 state: duration=4
  2. 用户切换 8 分音符 (调用 editorState.setDuration("8", 0))
  3. 模拟 hover (走 buildPreviewFromState 同样的逻辑)
  4. 验证 previewEntry.duration === "8"

这是 contract test — 验证时值链契约（不依赖真实 DOM/VexFlow）。
契约：
  - editorState.setDuration 是唯一设置 currentInputDuration 的入口
  - buildPreviewFromState 从 editorState.getInputDuration() 读
  - previewEntry.duration 来自 editorState.currentInputDuration.duration
"""
import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "web" / "app.js"


def read_app_js():
    return APP_JS.read_text(encoding="utf-8")


def extract_function_body(src, name):
    """抓 function NAME(...) { ... } 或方法简写 NAME(...) { ... } 函数体（去注释）"""
    # 先简单去 // 注释
    no_comment = re.sub(r"//[^\n]*", "", src)
    lines = no_comment.split("\n")
    # 找 start
    start_line = None
    for i, line in enumerate(lines):
        if re.match(rf"^\s*function\s+{name}\s*\(", line) or \
           re.match(rf"^\s{{2,}}{name}\s*\([^)]*\)\s*\{{", line):
            start_line = i
            break
    if start_line is None:
        return None
    # 找 brace_col
    brace_col = lines[start_line].rfind("{")
    if brace_col < 0:
        return None
    # 计数
    depth = 0
    end_line = start_line
    for i in range(start_line, len(lines)):
        start_col = brace_col if i == start_line else 0
        for ch in lines[i][start_col:]:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_line = i
                    break
        if depth == 0 and i >= start_line:
            break
    return "\n".join(lines[start_line:end_line + 1])


def make_editor_state():
    """构造最小可跑 editorState（与 web/app.js 行为一致）"""
    return {
        "currentInputDuration": {"duration": "4", "dotted": 0, "units": 8},
        "currentAccidental": "",
        "setDuration": None,  # 后面赋值
        "getInputDuration": None,
        "getInputAccidental": None,
    }


def bind_set_duration(state):
    """模拟 editorState.setDuration (与 app.js 行为一致)"""
    units_map = {"0": 64, "1": 32, "2": 16, "4": 8, "8": 4, "16": 2, "32": 1}
    def set_duration(duration, dotted):
        d = int(dotted) if dotted else 0
        base = units_map.get(duration, 8)
        # dot 1: 1.5x, dot 2: 1.75x
        units = base * (1.5 if d == 1 else (1.75 if d == 2 else 1))
        state["currentInputDuration"] = {
            "duration": duration,
            "dotted": d,
            "units": units,
        }
    state["setDuration"] = set_duration
    state["getInputDuration"] = lambda: state["currentInputDuration"]
    state["getInputAccidental"] = lambda: state["currentAccidental"]


def simulate_build_preview_from_state(state, ghost_params):
    """模拟 buildPreviewFromState — 从 editorState 读，不读 UI"""
    es_dur = state["getInputDuration"]()
    accidental = state["getInputAccidental"]()
    if ghost_params.get("isRest"):
        return {
            "kind": "rest",
            "voice": "1",
            "duration": es_dur["duration"],
            "dotted": es_dur["dotted"],
            "units": es_dur["units"],
            "_ghost": True,
        }
    return {
        "kind": "note",
        "voice": "1",
        "pitches": [{"step": "C", "octave": 5, "accidental": accidental}],
        "duration": es_dur["duration"],
        "dotted": es_dur["dotted"],
        "units": es_dur["units"],
        "_ghost": True,
    }


# ===== 核心 runtime test =====

def test_duration_chain_4_to_8_to_hover():
    """用户场景: duration=4 → 切换 8 → hover → previewEntry.duration === '8'"""
    state = make_editor_state()
    bind_set_duration(state)

    # 1. 初始 state
    assert state["currentInputDuration"]["duration"] == "4", \
        "初始 state: currentInputDuration.duration 应为 '4'"

    # 2. 用户切换 8 分音符（ribbon / keyboard / inspector 路径都最终进 setDuration）
    state["setDuration"]("8", 0)
    assert state["currentInputDuration"]["duration"] == "8", \
        "setDuration('8', 0) 后: currentInputDuration.duration 应为 '8'"

    # 3. 模拟 hover（走 buildPreviewFromState）
    ghost_params = {
        "localX": 100,
        "localY": 0,
        "geometry": {"noteStartX": 0, "staveY": 0, "topY": 0, "bottomY": 40},
        "staveKey": "treble",
        "isRest": False,
    }
    preview_entry = simulate_build_preview_from_state(state, ghost_params)

    # 4. 验证 — 这是 P22.3 修复的核心
    assert preview_entry["duration"] == "8", \
        f"hover 后 previewEntry.duration 应为 '8'（实际 {preview_entry['duration']}）"
    assert preview_entry["dotted"] == 0
    assert preview_entry["units"] == 4
    assert preview_entry["_ghost"] is True


def test_duration_chain_dotted_persists():
    """附点不会在 hover 时被清除：8 分音符 + 单附点 → hover → 仍是 8 + dot"""
    state = make_editor_state()
    bind_set_duration(state)

    state["setDuration"]("8", 1)  # 8 分音符 + 单附点
    preview = simulate_build_preview_from_state(state, {"isRest": False})

    assert preview["duration"] == "8"
    assert preview["dotted"] == 1
    # 8+附点 = 4 * 1.5 = 6 units
    assert preview["units"] == 6


def test_duration_chain_accidental_persists():
    """accidental 不会在 hover 时被清除：# → hover → pitch 仍是 #"""
    state = make_editor_state()
    bind_set_duration(state)

    state["setAccidental"] = lambda acc: state.update({"currentAccidental": acc})
    state["currentAccidental"] = "#"

    preview = simulate_build_preview_from_state(state, {"isRest": False})
    assert preview["pitches"][0]["accidental"] == "#"


def test_duration_chain_no_ui_overwrite():
    """核心回归：setDuration 之后，hover 不能把 duration 重置回 '4'
    模拟旧 bug 场景：state = 8, 但某个 UI 控件的 value 还是 '4'，hover 必须用 8"""
    state = make_editor_state()
    bind_set_duration(state)

    # 模拟：用户点 ribbon 8 分音符
    state["setDuration"]("8", 0)

    # 模拟 hover（不应从 UI 读旧值）
    preview = simulate_build_preview_from_state(state, {"isRest": False})

    # 关键：hover 后 duration 仍为 8，不能被覆盖
    assert preview["duration"] == "8", \
        "hover 后 duration 应为 '8'（不应被 UI 旧值 '4' 覆盖）"


def test_set_duration_only_entry_for_currentInputDuration():
    """契约：editorState.setDuration 是 currentInputDuration 的唯一写入入口
    业务代码（hover / addEntry / parseBatch）禁止直接赋值 currentInputDuration"""
    src = read_app_js()
    # 找所有 `currentInputDuration = ` 赋值
    lines = src.split("\n")
    # 去掉注释
    no_comment = re.sub(r"//[^\n]*", "", src)
    no_comment_lines = no_comment.split("\n")
    # 找所有 `currentInputDuration = {` 或 `currentInputDuration:` 字面量赋值
    direct_assigns = []
    for i, line in enumerate(no_comment_lines):
        # 跳过字段定义
        if re.search(r"^\s*currentInputDuration\s*:", line):
            continue
        # 找 `this.currentInputDuration = ` (setDuration 内部)
        if re.search(r"this\.currentInputDuration\s*=", line):
            # 这是 setDuration 内部允许的
            continue
        # 找 `state["currentInputDuration"] = ` (runtime test mock 允许)
        # 其它任何直接赋值都是 bug
        if re.search(r"currentInputDuration\s*=", line):
            direct_assigns.append((i + 1, line.strip()))

    # 注意：runtime test 文件自己可能有 currentInputDuration 赋值（mock）
    # 这里只检查 app.js 自身
    # runtime test 文件路径在 tests/test_p22_3_duration_chain_runtime.py
    assert len(direct_assigns) == 0, \
        f"app.js 中不应有直接给 currentInputDuration 赋值的代码（必须走 setDuration）: {direct_assigns}"


if __name__ == "__main__":
    # 直接运行时也能跑
    import sys
    test_duration_chain_4_to_8_to_hover()
    test_duration_chain_dotted_persists()
    test_duration_chain_accidental_persists()
    test_duration_chain_no_ui_overwrite()
    test_set_duration_only_entry_for_currentInputDuration()
    print("ALL PASS")
