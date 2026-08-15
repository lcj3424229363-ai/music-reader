"""
P22.5-Symbol-A.4 — 曲式分析 (volta + rehearsal mark + entry 默认值补全)

目标: 验证 3 件事:
  1. entry 字段全初始化 (18 修饰符默认值, idempotent)
  2. 段标 (rehearsal mark) 渲染 (VF.RehearsalMark)
  3. volta 1./2./3. ending 渲染 (VF.Repetition)
  4. UI: index.html 控件 + app.js findEl + bindEvent + 显示

纪律: 纯静态 grep + Python 字符串分析, 零依赖, 零运行。
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(ROOT, "web", "app.js")
HTML_PATH = os.path.join(ROOT, "web", "index.html")


def _read_app():
    with open(APP_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _read_html():
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _extract_function(content, name):
    """提取指定函数完整 body (paren + brace 配对计数)"""
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


# ===== 1. ENTRY_MODIFIER_DEFAULTS 常量 =====

class TestEntryModifierDefaults(unittest.TestCase):
    """ENTRY_MODIFIER_DEFAULTS: 18 修饰符字段默认值 + Object.freeze"""

    @classmethod
    def setUpClass(cls):
        cls.content = _read_app()

    def test_01_constant_exists(self):
        self.assertIn("const ENTRY_MODIFIER_DEFAULTS", self.content)

    def test_02_frozen(self):
        # 防止运行时意外修改
        match = re.search(r"const\s+ENTRY_MODIFIER_DEFAULTS\s*=\s*Object\.freeze", self.content)
        self.assertIsNotNone(match, "ENTRY_MODIFIER_DEFAULTS 必须 Object.freeze")

    def test_03_contains_18_modifier_fields(self):
        # 期望的 18 个修饰符字段
        expected = [
            # ABOVE slot
            "articulation", "fingering", "textMark", "ornament", "fermata",
            # grace
            "grace",
            # BELOW slot
            "dynamic", "pedal", "breath",
            # 跨音符
            "tieStart", "tieStop", "slurStart", "slurStop",
            "phraseStart", "phraseStop", "hairpin",
            # 文本/演奏法
            "chordSymbol", "arpeggiate",
            # A.4 曲式
            "volta", "rehearsalMark"
        ]
        # 找 ENTRY_MODIFIER_DEFAULTS = Object.freeze({...}) 块
        m = re.search(r"ENTRY_MODIFIER_DEFAULTS\s*=\s*Object\.freeze\(\{(.*?)\}\)", self.content, re.DOTALL)
        self.assertIsNotNone(m)
        block = m.group(1)
        for field in expected:
            self.assertIn(f"{field}:", block, f"ENTRY_MODIFIER_DEFAULTS 必须包含 {field}")


# ===== 2. ensureEntryDefaults helper =====

class TestEnsureEntryDefaults(unittest.TestCase):
    """ensureEntryDefaults: idempotent 补全 18 修饰符字段"""

    @classmethod
    def setUpClass(cls):
        cls.content = _read_app()
        cls.body = _extract_function(cls.content, "ensureEntryDefaults")

    def test_01_function_exists(self):
        self.assertIsNotNone(self.body, "ensureEntryDefaults 必须存在")

    def test_02_signature(self):
        self.assertRegex(self.body, r"function\s+ensureEntryDefaults\s*\(\s*entry\s*\)")

    def test_03_returns_entry(self):
        self.assertRegex(self.body, r"return\s+entry")

    def test_04_uses_for_in_loop(self):
        self.assertIn("for (const key in ENTRY_MODIFIER_DEFAULTS)", self.body)

    def test_05_uses_in_operator(self):
        # 用 'in' 检查字段是否存在, 已有不覆盖
        self.assertRegex(self.body, r"if\s*\(\s*!\(key\s+in\s+entry\)\)")

    def test_06_null_guard(self):
        # entry 不是 object 返原值
        self.assertRegex(self.body, r"if\s*\(\s*!entry\s*\|\|\s*typeof\s+entry\s*!==\s*\"object\"\)")

    def test_07_called_in_drawStaffEntriesOnStave(self):
        # 入口必须调
        body = _extract_function(self.content, "drawStaffEntriesOnStave")
        self.assertIn("entriesSource.forEach(ensureEntryDefaults)", body)


# ===== 3. drawRehearsalMarkAt helper =====

class TestDrawRehearsalMarkAt(unittest.TestCase):
    """drawRehearsalMarkAt: 在 note 上方画段标方框"""

    @classmethod
    def setUpClass(cls):
        cls.content = _read_app()
        cls.body = _extract_function(cls.content, "drawRehearsalMarkAt")

    def test_01_function_exists(self):
        self.assertIsNotNone(self.body)

    def test_02_signature(self):
        self.assertRegex(self.body, r"function\s+drawRehearsalMarkAt\s*\(\s*context,\s*firstNote,\s*mark\s*\)")

    def test_03_uses_VF_RehearsalMark(self):
        self.assertIn("VF.RehearsalMark", self.body)

    def test_04_null_guards(self):
        self.assertIn("!context", self.body)
        self.assertIn("!firstNote", self.body)
        self.assertIn("!mark", self.body)

    def test_05_adds_modifier_to_note(self):
        # addModifier(rm, 0) — index 0 = 第一位
        self.assertIn("firstNote.addModifier(rm, 0)", self.body)


# ===== 4. drawVoltaAt helper =====

class TestDrawVoltaAt(unittest.TestCase):
    """drawVoltaAt: 在 stave 画 volta 括号 1./2./3."""

    @classmethod
    def setUpClass(cls):
        cls.content = _read_app()
        cls.body = _extract_function(cls.content, "drawVoltaAt")

    def test_01_function_exists(self):
        self.assertIsNotNone(self.body)

    def test_02_signature(self):
        self.assertRegex(self.body, r"function\s+drawVoltaAt\s*\(\s*context,\s*stave,\s*voltaSpec\s*\)")

    def test_03_uses_VF_Repetition(self):
        self.assertIn("VF.Repetition", self.body)

    def test_04_accepts_number_and_array(self):
        # 支持 number | number[] | null
        self.assertIn("Array.isArray(voltaSpec)", self.body)
        self.assertIn("Array.isArray(voltaSpec) ? voltaSpec : [voltaSpec]", self.body)

    def test_05_null_guards(self):
        self.assertIn("!context", self.body)
        self.assertIn("!stave", self.body)
        self.assertIn("voltaSpec == null", self.body)


# ===== 5. drawStaffEntriesOnStave 改造 =====

class TestDrawStaffEntriesOnStaveA4(unittest.TestCase):
    """drawStaffEntriesOnStave: 入口补默认值 + 末尾画 rehearsal + volta"""

    @classmethod
    def setUpClass(cls):
        cls.content = _read_app()
        cls.body = _extract_function(cls.content, "drawStaffEntriesOnStave")

    def test_01_calls_ensureEntryDefaults_at_entry(self):
        self.assertIn("entriesSource.forEach(ensureEntryDefaults)", self.body)

    def test_02_calls_drawRehearsalMarkAt(self):
        # 末尾 (在 voice.draw 之后, 收集 notesByMeasure 之前) 调
        self.assertIn("drawRehearsalMarkAt(context, firstNote, firstNoteEntry.rehearsalMark)", self.body)

    def test_03_calls_drawVoltaAt(self):
        # 末尾调, 找 entriesSource 第一个有 volta 的 entry
        self.assertIn("drawVoltaAt(context, stave, voltaSpec)", self.body)
        self.assertIn("e && Number.isInteger(e.volta))?.volta", self.body)


# ===== 6. UI 控件 (index.html) =====

class TestUIElementsA4(unittest.TestCase):
    """index.html 加 2 个新控件"""

    @classmethod
    def setUpClass(cls):
        cls.html = _read_html()

    def test_01_rehearsalMarkInput_exists(self):
        self.assertRegex(self.html, r'id="rehearsalMarkInput"')
        self.assertIn("placeholder=\"A / Intro / Verse 1\"", self.html)

    def test_02_voltaSelect_exists(self):
        self.assertRegex(self.html, r'id="voltaSelect"')
        # 3 个 option: 1, 2, 3
        for value in ["1", "2", "3"]:
            self.assertIn(f'value="{value}"', self.html)


# ===== 7. UI 绑定 (app.js) =====

class TestUIBindingsA4(unittest.TestCase):
    """app.js: findEl + bindEvent + 显示同步"""

    @classmethod
    def setUpClass(cls):
        cls.content = _read_app()

    def test_01_rehearsalMarkInput_findEl(self):
        self.assertIn('const rehearsalMarkInput = findEl("rehearsalMarkInput")', self.content)

    def test_02_voltaSelect_findEl(self):
        self.assertIn('const voltaSelect = findEl("voltaSelect")', self.content)

    def test_03_rehearsalMark_bindEvent(self):
        # bindEvent(rehearsalMarkInput, "change", ...)
        self.assertRegex(self.content, r'bindEvent\(rehearsalMarkInput,\s*"change"')
        # 设 entry.rehearsalMark
        self.assertIn("entry.rehearsalMark = rehearsalMarkInput.value.trim()", self.content)

    def test_04_volta_bindEvent(self):
        self.assertRegex(self.content, r'bindEvent\(voltaSelect,\s*"change"')
        # 设 entry.volta = Number(value) | null
        self.assertIn("entry.volta = value === \"\" ? null : Number(value)", self.content)

    def test_05_show_on_selectEntry(self):
        # selectEntry 时同步显示
        self.assertIn("rehearsalMarkInput.value = entry.rehearsalMark || \"\"", self.content)
        self.assertIn('voltaSelect.value = entry.volta == null ? "" : String(entry.volta)', self.content)


if __name__ == "__main__":
    unittest.main()
