"""P22.3 Phase 2 — previewEntry 真正预览（VexFlow 真音符）静态测试。

Phase 2 硬约束（你明确要求）：
- 删除 showGhostNote 文字方案
- 不允许生成 C5 这种字符串假预览
- 必须复用 createVexNote / 正式 note rendering
- preview 必须支持 duration / dotted / accidental / rest / voice
"""
import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "web" / "app.js"
APP_CSS = Path(__file__).resolve().parent.parent / "web" / "styles.css"


def read_app_js():
    return APP_JS.read_text(encoding="utf-8")


def read_app_css():
    return APP_CSS.read_text(encoding="utf-8")


def strip_js_comments(src):
    """去 // 单行 和 /* */ 多行 注释"""
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
            if line[i:i+2] == "//":
                break
            if line[i:i+2] == "/*":
                in_block = True
                i += 2
                continue
            new_line.append(line[i])
            i += 1
        out.append("".join(new_line))
    return "\n".join(out)


# ===== 删 showGhostNote =====
def test_show_ghost_note_deleted():
    """showGhostNote 函数必须删除（不再 div+textContent 假预览）"""
    src = read_app_js()
    assert "function showGhostNote(" not in src, \
        "showGhostNote 必须删除（不再 div+textContent 假预览）"


def test_no_ghost_text_string():
    """禁止生成 ghostText 字符串（display + step + octave）"""
    src = read_app_js()
    # 旧版: const ghostText = (display + pitch.step + pitch.octave);
    # 新版必须删这个变量声明
    assert "const ghostText" not in src, \
        "禁止生成 const ghostText 字符串（display + step + octave）"


# ===== appendGhostToMainCanvas 新函数 (P22.3 Phase 3 替换原 renderGhostVexFlow) =====
def test_append_ghost_to_main_canvas_exists():
    """appendGhostToMainCanvas 函数必须存在（Phase 3 替换 renderGhostVexFlow）"""
    src = read_app_js()
    assert "function appendGhostToMainCanvas(" in src, \
        "appendGhostToMainCanvas 函数必须存在（Phase 3）"
    # 旧 renderGhostVexFlow 必须删除（独立 mini VexFlow 已弃用）
    assert "function renderGhostVexFlow(" not in src, \
        "renderGhostVexFlow 必须删除（独立 mini VexFlow 不再使用）"


def test_append_ghost_uses_create_vex_note():
    """appendGhostToMainCanvas 必须复用 createVexNote（你 Phase 2 硬约束）"""
    src = read_app_js()
    # 抓 appendGhostToMainCanvas 函数体
    m = re.search(r"function appendGhostToMainCanvas\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    assert m, "找不到 appendGhostToMainCanvas 函数体"
    body = m.group(1)
    assert "createVexNote(" in body, \
        "appendGhostToMainCanvas 必须调用 createVexNote 复用（你 Phase 2 硬约束）"
    # 不再 new 独立 VF.Renderer / VF.Stave — 必须用主 stave / 主 ctx
    assert "new VF.Renderer" not in body, \
        "appendGhostToMainCanvas 不应创建独立 renderer（必须复用主 ctx）"
    # 不应创建顶层 VF.Stave — 但 placeholder rest 是 VF.StaveNote（StaveNote 是 Stave 子类，substring 匹配）
    # 关键判断：不应有 "new VF.Stave(" 形式（顶层 Stave）
    assert "new VF.Stave(" not in body, \
        "appendGhostToMainCanvas 不应创建独立 VF.Stave(（必须用主 stave；placeholder rest 是 VF.StaveNote）"
    # ghost note 本身必须 createVexNote 复用 — 但 placeholder rest 允许 new VF.StaveNote
    # 关键判断：body 里 createVexNote(editorState.previewEntry 必出现
    assert "createVexNote(editorState.previewEntry" in body, \
        "appendGhostToMainCanvas 必须 createVexNote(editorState.previewEntry, ...) 复用"
    # 必须用主 ctx + 主 stave
    assert "geometry.activeStave" in body, \
        "appendGhostToMainCanvas 必须用 geometry.activeStave（主 stave）"
    assert "geometry.activeContext" in body, \
        "appendGhostToMainCanvas 必须用 geometry.activeContext（主 ctx）"
    # 必须用主 VexFlow Formatter
    assert "new VF.Formatter" in body, "appendGhostToMainCanvas 必须用 VexFlow Formatter"
    assert "ghostVoice.draw(ctx, stave)" in body, \
        "appendGhostToMainCanvas 必须把 ghost voice 画到主 ctx + 主 stave"


def test_append_ghost_capacity_color():
    """appendGhostToMainCanvas 必须按 capacity 切换颜色（绿/红）"""
    src = read_app_js()
    m = re.search(r"function appendGhostToMainCanvas\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    body = m.group(1)
    # fillStyle 颜色按 isPreviewOverCapacity 切换
    assert "editorState.isPreviewOverCapacity" in body, \
        "appendGhostToMainCanvas 必须读 editorState.isPreviewOverCapacity 切色"
    # 绿/红 rgba
    assert "239, 68, 68" in body, "appendGhostToMainCanvas 必须有红色 rgba（超容量）"
    assert "52, 211, 153" in body, "appendGhostToMainCanvas 必须有绿色 rgba（能放）"


def test_append_ghost_uses_main_stave_not_mini():
    """appendGhostToMainCanvas 必须用主 stave，不用独立 mini stave（关键修复）"""
    src = read_app_js()
    m = re.search(r"function appendGhostToMainCanvas\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    body = m.group(1)
    # 关键：appendGhostToMainCanvas 跟 ghost 同坐标系（用主 stave）
    # 不应有独立 mini stave 创建
    assert "containerW" not in body, \
        "appendGhostToMainCanvas 不应有 containerW（独立 mini VexFlow 容器已弃）"
    assert "containerH" not in body, \
        "appendGhostToMainCanvas 不应有 containerH（独立 mini VexFlow 容器已弃）"
    # 关键：用 placeholder rest 占满 ghost note 之前拍位
    assert "placeholder rest" in body or "transparent" in body, \
        "appendGhostToMainCanvas 必须用 placeholder rest 推 ghost note 到目标拍位"


# ===== handleNoteCanvasHover 重写 =====
def _handle_hover_body_no_comments():
    """抓 handleNoteCanvasHover 函数体 (去注释) — 避免误判注释里的 setDuration"""
    raw_src = read_app_js()
    src = strip_js_comments(raw_src)
    m = re.search(r"function handleNoteCanvasHover\(event\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    assert m, "找不到 handleNoteCanvasHover 函数体"
    return m.group(1)


def test_handle_hover_writes_editor_state():
    """handleNoteCanvasHover 必须写 editorState — 派生状态写入

    P22.3 duration-cleanup: hover 不再回写 setDuration / setAccidental
    (那会从 UI 旧值覆盖 editorState, 违反 single source of truth)
    只写派生状态: setPreview / setMousePosition / setInputMode / updateCapacity
    """
    body = _handle_hover_body_no_comments()
    # 必须写派生状态 setter (P22.3 duration-cleanup 后)
    for setter in ["editorState.setPreview", "editorState.setMousePosition",
                   "editorState.setInputMode", "editorState.updateCapacity"]:
        assert setter in body, f"handleNoteCanvasHover 必须调 {setter}"
    # 关键约束: hover 不应回写 setDuration / setAccidental
    # (那是旧契约, 会用 UI 旧值覆盖 editorState, 破坏切 8 → hover → 仍是 8)
    assert "editorState.setDuration(" not in body, \
        "handleNoteCanvasHover 不应调 setDuration (会从 UI 旧值覆盖 editorState, 时值多源)"
    assert "editorState.setAccidental(" not in body, \
        "handleNoteCanvasHover 不应调 setAccidental (会从 UI 旧值覆盖 editorState, 时值多源)"


def test_handle_hover_no_rest_skip():
    """handleNoteCanvasHover 不应跳过 rest 模式（旧版有 `if (inputKind() === "rest") return`）"""
    body = _handle_hover_body_no_comments()
    # 旧版: if (inputKind() === "rest") return;
    # 新版: rest 也展示 ghost
    # 检查没有无条件 return 跳过 rest
    has_rest_skip = 'inputKind() === "rest") return' in body
    assert not has_rest_skip, \
        "handleNoteCanvasHover 不应跳过 rest（rest 也展示 ghost 预览）"


def test_handle_hover_supports_rest_and_note():
    """handleNoteCanvasHover 必须支持 rest + note 两种 previewEntry
    (P22.3 duration-cleanup: 实际构造已抽到 buildPreviewFromState 单一函数)"""
    src = read_app_js()
    # hover 现在调 buildPreviewFromState — 真正逻辑在 buildPreviewFromState 里
    m = re.search(r"function buildPreviewFromState\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    assert m, "找不到 buildPreviewFromState（duration-cleanup 抽出的单一 preview 构造入口）"
    body = m.group(1)
    # rest 路径：kind: "rest"
    assert 'kind: "rest"' in body, "buildPreviewFromState 必须有 rest previewEntry 路径"
    # note 路径：pitches: [fullPitch]
    assert "pitches: [fullPitch]" in body, "buildPreviewFromState 必须有 note previewEntry 路径"
    # 两条路径都带 _ghost: true
    rest_path = body[body.find('kind: "rest"'):body.find('kind: "note"')] if 'kind: "rest"' in body else ""
    note_path = body[body.find('kind: "note"'):] if 'kind: "note"' in body else ""
    assert "_ghost: true" in rest_path, "rest previewEntry 必须有 _ghost: true"
    assert "_ghost: true" in note_path, "note previewEntry 必须有 _ghost: true"
    # hover 必须调它
    hover_body = re.search(r"function handleNoteCanvasHover\(event\)\s*\{(.+?)\n\}\n", src, re.DOTALL).group(1)
    assert "buildPreviewFromState(" in hover_body, \
        "handleNoteCanvasHover 必须调 buildPreviewFromState（duration-cleanup 单一入口）"


def test_handle_hover_passes_voice_to_preview():
    """previewEntry 必须带 voice (P22.3 duration-cleanup: 逻辑在 buildPreviewFromState)"""
    src = read_app_js()
    m = re.search(r"function buildPreviewFromState\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    assert m, "找不到 buildPreviewFromState"
    body = m.group(1)
    # voice 字段
    assert "voice: activeVoiceId()" in body, \
        "buildPreviewFromState previewEntry 必须带 voice 字段"


def test_handle_hover_capacity_check():
    """handleNoteCanvasHover 必须调 updateCapacity(used + units, capacity)"""
    src = read_app_js()
    m = re.search(r"function handleNoteCanvasHover\(event\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    body = m.group(1)
    assert "used + units" in body, "必须传 used + units 给 updateCapacity"
    assert "currentMeter().capacity" in body or "capacity" in body, \
        "必须传 current meter capacity"


def test_handle_hover_uses_append_ghost():
    """handleNoteCanvasHover 必须调 appendGhostToMainCanvas（Phase 3 替换 renderGhostVexFlow）"""
    src = read_app_js()
    m = re.search(r"function handleNoteCanvasHover\(event\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    body = m.group(1)
    assert "appendGhostToMainCanvas(" in body, \
        "handleNoteCanvasHover 必须调 appendGhostToMainCanvas（Phase 3 修复）"
    # 旧的 renderGhostVexFlow 不能还在 hover 里调
    assert "renderGhostVexFlow(" not in body, \
        "handleNoteCanvasHover 不应再调 renderGhostVexFlow（已被 appendGhostToMainCanvas 替换）"


def test_handle_hover_accidental_applied():
    """previewEntry 必须应用 current accidental (P22.3 duration-cleanup: 在 buildPreviewFromState)"""
    src = read_app_js()
    m = re.search(r"function buildPreviewFromState\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    assert m, "找不到 buildPreviewFromState"
    body = m.group(1)
    # createPitch 必须收到 accidental 字段
    # (P22.3 duration-cleanup: 从 editorState.getInputAccidental() 读，不再直接读 noteAccidental.value)
    assert "createPitch(pitch, accidental)" in body or \
           "createPitch(pitch, editorState.getInputAccidental" in body, \
        "buildPreviewFromState 必须用 createPitch 应用 accidental (source = editorState)"


# ===== CSS =====
def test_css_ghost_note_container():
    """.score-ghost-note CSS 必须是容器（不再是 textContent 字体设置）"""
    css = read_app_css()
    # 容器应保留 position: absolute / pointer-events: none / z-index
    m = re.search(r"\.score-ghost-note\s*\{([^}]*)\}", css)
    assert m, ".score-ghost-note CSS 必须存在"
    body = m.group(1)
    assert "position: absolute" in body, "容器必须 absolute"
    assert "pointer-events: none" in body, "容器必须 pointer-events: none（不挡 hitbox）"
    # 不应有 font-size（不再是 textContent）
    assert "font-size" not in body, "容器不再需要 font-size（textContent 已删）"
    assert "color:" not in body, "容器不再需要 color（VexFlow 内部 setStyle 控）"


def test_css_ghost_capacity_classes():
    """.score-ghost-note.ghost-ok / .ghost-over 必须存在（capacity 颜色 class）"""
    css = read_app_css()
    assert ".score-ghost-note.ghost-over" in css, ".ghost-over class 必须存在"
    assert ".score-ghost-note.ghost-ok" in css, ".ghost-ok class 必须存在"
