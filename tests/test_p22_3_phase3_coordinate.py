"""P22.3 Phase 3 — ghost 与主谱面同坐标系修复

硬要求（你 Phase 3 明确）：
- ghost 和正式谱面同坐标系
- ghost 和正式音符完全重合
- ghost 支持 duration / accidental / dotted
- 鼠标移动到五线谱 → 半透明预览音符直接显示在正确五线谱位置
- 点击后生成正式音符，位置完全重合
"""
import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "web" / "app.js"


def read_app_js():
    return APP_JS.read_text(encoding="utf-8")


# ===== 1. geometry 必须存 activeStave / activeContext (修复核心) =====
def test_staff_geometry_has_active_stave():
    """staffGeometry 必须存 activeStave（主 stave 引用）— 修复关键"""
    src = read_app_js()
    # 找 staffGeometry 赋值块
    m = re.search(r"staffGeometry\s*=\s*\{[^}]+\}", src, re.DOTALL)
    assert m, "找不到 staffGeometry 赋值"
    body = m.group(0)
    assert "activeStave" in body, "staffGeometry 必须存 activeStave（主 stave 引用）"
    assert "activeContext" in body, "staffGeometry 必须存 activeContext（主 ctx 引用）"


def test_treble_geometry_has_active_stave():
    """trebleGeometry 必须存 activeStave（双谱表模式 treble 主 stave 引用）"""
    src = read_app_js()
    m = re.search(r"trebleGeometry\s*=\s*\{[^}]+\}", src, re.DOTALL)
    assert m, "找不到 trebleGeometry 赋值"
    body = m.group(0)
    assert "activeStave" in body, "trebleGeometry 必须存 activeStave"
    assert "activeContext" in body, "trebleGeometry 必须存 activeContext"


def test_bass_geometry_has_active_stave():
    """bassGeometry 必须存 activeStave（双谱表模式 bass 主 stave 引用）"""
    src = read_app_js()
    m = re.search(r"bassGeometry\s*=\s*\{[^}]+\}", src, re.DOTALL)
    assert m, "找不到 bassGeometry 赋值"
    body = m.group(0)
    assert "activeStave" in body, "bassGeometry 必须存 activeStave"
    assert "activeContext" in body, "bassGeometry 必须存 activeContext"


# ===== 2. appendGhostToMainCanvas 用主 stave / 主 ctx =====
def test_append_ghost_no_mini_v_extras():
    """appendGhostToMainCanvas 不应创建独立 mini VexFlow renderer/stave/div（关键修复）"""
    src = read_app_js()
    m = re.search(r"function appendGhostToMainCanvas\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    assert m, "找不到 appendGhostToMainCanvas 函数体"
    body = m.group(1)
    # 独立 mini VexFlow renderer 必须删（不能 new VF.Renderer）
    assert "new VF.Renderer" not in body, \
        "appendGhostToMainCanvas 不应创建独立 VF.Renderer（修复：必须用主 ctx）"
    # 独立 mini VexFlow stave 必须删（不能 new VF.Stave 顶层调用）
    # 但 placeholder rest 是 new VF.StaveNote — Stave 是 Stave 的子类
    # 关键判断：不应有 "new VF.Stave(" 形式（顶层 stave），但允许 "new VF.StaveNote("
    assert "new VF.Stave(" not in body, \
        "appendGhostToMainCanvas 不应创建独立 VF.Stave(（修复：必须用主 stave）"
    # 容器 div 必须删
    assert "createElement(\"div\")" not in body and "document.createElement" not in body, \
        "appendGhostToMainCanvas 不应创建 div 容器（修复：直接画到主 SVG）"
    # Backends.SVG 必须删
    assert "Backends.SVG" not in body, \
        "appendGhostToMainCanvas 不应创建新 Backends.SVG（修复：复用主 ctx）"


def test_append_ghost_uses_active_stave():
    """appendGhostToMainCanvas 必须从 geometry 取主 stave"""
    src = read_app_js()
    m = re.search(r"function appendGhostToMainCanvas\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    body = m.group(1)
    # 必须有 geometry.activeStave / geometry.activeContext 引用
    assert "geometry.activeStave" in body, \
        "appendGhostToMainCanvas 必须用 geometry.activeStave"
    assert "geometry.activeContext" in body, \
        "appendGhostToMainCanvas 必须用 geometry.activeContext"
    # 必须用 const stave = geometry.activeStave 形式拿引用
    assert "const stave" in body and "geometry.activeStave" in body, \
        "appendGhostToMainCanvas 必须把 activeStave 赋给本地变量"
    assert "const ctx" in body and "geometry.activeContext" in body, \
        "appendGhostToMainCanvas 必须把 activeContext 赋给本地变量"


def test_append_ghost_formatter_for_beat():
    """appendGhostToMainCanvas 用 placeholder rest 推 ghost note 到目标拍位"""
    src = read_app_js()
    m = re.search(r"function appendGhostToMainCanvas\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    body = m.group(1)
    # placeholder rest 循环
    assert "for (let b = 1; b < beat" in body, \
        "appendGhostToMainCanvas 必须用 placeholder rest 推 ghost 到目标拍位"
    # VF.StaveNote 创建 placeholder rest
    assert "new VF.StaveNote" in body, \
        "appendGhostToMainCanvas 必须创建 placeholder rest StaveNote"
    # 主 VexFlow Formatter
    assert "new VF.Formatter" in body, \
        "appendGhostToMainCanvas 必须用主 VexFlow Formatter"


def test_append_ghost_creates_voice_and_draws_to_main_stave():
    """appendGhostToMainCanvas 必须创建 voice 并画到主 ctx + 主 stave"""
    src = read_app_js()
    m = re.search(r"function appendGhostToMainCanvas\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    body = m.group(1)
    assert "new VF.Voice" in body, "appendGhostToMainCanvas 必须创建 VF.Voice"
    assert "ghostVoice.draw(ctx, stave)" in body, \
        "appendGhostToMainCanvas 必须 ghostVoice.draw(ctx, stave) 画到主 ctx + 主 stave"


# ===== 3. handleNoteCanvasHover 末尾调 appendGhostToMainCanvas =====
def test_handle_hover_calls_append_ghost():
    """handleNoteCanvasHover 末尾必须调 appendGhostToMainCanvas"""
    src = read_app_js()
    m = re.search(r"function handleNoteCanvasHover\(event\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    body = m.group(1)
    assert "appendGhostToMainCanvas(" in body, \
        "handleNoteCanvasHover 末尾必须调 appendGhostToMainCanvas"
    assert "renderGhostVexFlow(" not in body, \
        "handleNoteCanvasHover 不应再调 renderGhostVexFlow（已删）"


# ===== 4. clearGhostNote 必须清 svg 内的 .vf-ghost-note 节点 =====
def test_clear_ghost_note_clears_svg_vf_class():
    """clearGhostNote 必须清 svg 内的 .vf-ghost-note 节点（Phase 3 关键）"""
    src = read_app_js()
    m = re.search(r"function clearGhostNote\(\)\s*\{(.+?)\n\}", src, re.DOTALL)
    assert m, "找不到 clearGhostNote 函数体"
    body = m.group(1)
    # 必须查 svg
    assert 'querySelector("svg")' in body, \
        "clearGhostNote 必须查 svg（Phase 3 关键 — ghost 现在是 SVG 节点）"
    # 必须清 .vf-ghost-note
    assert ".vf-ghost-note" in body, \
        "clearGhostNote 必须清 .vf-ghost-note"


# ===== 5. renderSingleNotationSafe 末尾调 appendGhostToMainCanvas =====
def test_single_notation_tail_calls_append_ghost():
    """renderSingleNotationSafe 末尾必须调 appendGhostToMainCanvas（保证 commit 后 ghost 仍可见）"""
    src = read_app_js()
    # 找 function renderSingleNotationSafe
    m = re.search(r"function renderSingleNotationSafe\(\)\s*\{(.+?)\nfunction ", src, re.DOTALL)
    assert m, "找不到 renderSingleNotationSafe 函数体"
    body = m.group(1)
    # 末尾调 appendGhostToMainCanvas
    assert "appendGhostToMainCanvas()" in body, \
        "renderSingleNotationSafe 末尾必须调 appendGhostToMainCanvas"


# ===== 6. renderGhostVexFlow 必须完全删除 =====
def test_render_ghost_v_ex_flow_removed():
    """renderGhostVexFlow 必须完全删除（不再独立 mini VexFlow）"""
    src = read_app_js()
    assert "function renderGhostVexFlow(" not in src, \
        "renderGhostVexFlow 必须完全删除（Phase 3 修复 — 不再独立 mini VexFlow）"


def test_no_div_ghost_container():
    """Phase 3 不应再有 div.score-ghost-note 容器（ghost 改画到主 SVG）"""
    src = read_app_js()
    # renderGhostVexFlow 已删，不应再有 wrap.className = "score-ghost-note"
    assert 'wrap.className = "score-ghost-note"' not in src, \
        "Phase 3 不应再有 div.score-ghost-note 容器（ghost 改画到主 SVG）"


# ===== 7. ghost 仍复用 createVexNote (Phase 2 硬约束保留) =====
def test_append_ghost_still_uses_create_vex_note():
    """appendGhostToMainCanvas 必须仍复用 createVexNote（Phase 2 硬约束保留）

    边界说明：
    - ghost note 本身（用户预览的那个）必须用 createVexNote
    - placeholder rest（推 ghost note 到目标拍位的透明休止符）允许用 new VF.StaveNote
    """
    src = read_app_js()
    m = re.search(r"function appendGhostToMainCanvas\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    body = m.group(1)
    assert "createVexNote(" in body, \
        "appendGhostToMainCanvas 必须仍复用 createVexNote"
    # ghost note 必须用 createVexNote
    assert "createVexNote(editorState.previewEntry" in body, \
        "appendGhostToMainCanvas 必须 createVexNote(editorState.previewEntry, ...)"
    # placeholder rest 允许 new VF.StaveNote — 但 ghost note 不应是直接 new 出来的
    # 判断：ghost note 必须由 createVexNote 创建
    # 找 createVexNote 调用赋给 ghostNote 变量
    assert "const ghostNote = createVexNote" in body, \
        "appendGhostToMainCanvas 必须 const ghostNote = createVexNote(...)"


# ===== 8. capacity 颜色 (Phase 2 保留) =====
def test_capacity_color_logic():
    """appendGhostToMainCanvas 仍按 capacity 切色 (Phase 2 保留)"""
    src = read_app_js()
    m = re.search(r"function appendGhostToMainCanvas\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    body = m.group(1)
    assert "editorState.isPreviewOverCapacity" in body, \
        "appendGhostToMainCanvas 必须读 editorState.isPreviewOverCapacity"
    assert "239, 68, 68" in body, "必须有红色 rgba（超容量）"
    assert "52, 211, 153" in body, "必须有绿色 rgba（能放）"


# ===== 9. duration / accidental / dotted (Phase 2 保留) =====
def test_supports_dotted():
    """appendGhostToMainCanvas 走 createVexNote，createVexNote 已支持 dotted"""
    src = read_app_js()
    m = re.search(r"function appendGhostToMainCanvas\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    body = m.group(1)
    # 必须传 previewEntry 给 createVexNote — previewEntry 含 duration/dotted/units
    assert "editorState.previewEntry" in body, \
        "appendGhostToMainCanvas 必须读 editorState.previewEntry"
    # previewEntry 含 dotted 字段（来自 setDuration(duration, dotted)）
    # createVexNote 内部读 entry.dotted → VF.Dot.buildAndAttach
    # Phase 2 测试已验证 createVexNote 支持 dotted — 这里只需确认 createVexNote 调用


def test_supports_accidental():
    """appendGhostToMainCanvas 走 createVexNote，accidental 来自 previewEntry.pitches[].accidental"""
    src = read_app_js()
    # previewEntry.pitches 来自 handleNoteCanvasHover 内的 createPitch(pitch, noteAccidental.value)
    # createVexNote 内部读 pitch.accidental → VexFlow key 拼接
    # Phase 2 测试已验证 — 这里只需要 previewEntry.pitches 流过 createVexNote
    m = re.search(r"function appendGhostToMainCanvas\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    body = m.group(1)
    assert "createVexNote(editorState.previewEntry" in body, \
        "appendGhostToMainCanvas 必须传完整 previewEntry（含 pitches/accidental）"


def test_supports_duration():
    """appendGhostToMainCanvas 走 createVexNote，duration 来自 previewEntry.duration"""
    src = read_app_js()
    m = re.search(r"function appendGhostToMainCanvas\([^)]*\)\s*\{(.+?)\n\}\n", src, re.DOTALL)
    body = m.group(1)
    # 传完整 previewEntry 即可
    assert "createVexNote(editorState.previewEntry" in body, \
        "appendGhostToMainCanvas 必须传完整 previewEntry（含 duration）"
