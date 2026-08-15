"""
P22.5-B.1 — Score Model 数据契约 (基础数据结构 + factory)

目标: 验证 6 个 class + 1 个 factory 行为
  1. Note (18 修饰符 + 3 tuplet 字段默认值, B.3 重命名)
  2. Voice (id + role)
  3. Measure (per voice 决策, 18 字段)
  4. Part (id + name + instrument)
  5. Relation (跨 measure 关系)
  6. Score (顶层 + addPart + getMeasure + addRelation)
  7. buildScore factory: legacyState → Score Model

纪律: 用 node + subprocess 实际跑 web/score-model.js, 验证运行时行为
"""
import os
import re
import unittest
import json
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOREMODEL_PATH = os.path.join(ROOT, "web", "score-model.js")
APP_PATH = os.path.join(ROOT, "web", "app.js")


def _read_scoremodel():
    with open(SCOREMODEL_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _read_app():
    """extract editorState-like sample data from app.js (single source of truth)"""
    with open(APP_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _run_node(legacy_state_json):
    """用 node 跑 score-model.js, 传 legacyState JSON, 返回 Score Model JSON"""
    js = f'''
global.window = global;
require({json.dumps(SCOREMODEL_PATH.replace(os.sep, "/"))});
const SM = global.ScoreModel;
const state = {legacy_state_json};
const result = SM.buildScore(state);
process.stdout.write(JSON.stringify(result));
'''
    result = subprocess.run(
        ["node", "-e", js],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        raise RuntimeError(f"node failed: {result.stderr}")
    return json.loads(result.stdout)


# ===== 测试 1: 静态文件存在 + 6 个 class 存在 =====

class TestScoreModelStatic(unittest.TestCase):
    """score-model.js 文件存在 + 6 个 class 定义"""

    @classmethod
    def setUpClass(cls):
        cls.content = _read_scoremodel()

    def test_01_file_exists(self):
        self.assertTrue(os.path.exists(SCOREMODEL_PATH), "score-model.js 必须存在")

    def test_02_note_class(self):
        self.assertRegex(self.content, r"class\s+Note\s*\{")
        # 18 修饰符字段
        for field in ["articulation", "fingering", "textMark", "ornament", "fermata",
                      "grace", "dynamic", "pedal", "breath",
                      "tieStart", "tieStop", "slurStart", "slurStop",
                      "phraseStart", "phraseStop", "hairpin",
                      "chordSymbol", "arpeggiate"]:
            self.assertIn(f"this.{field}", self.content, f"Note 必须有 {field} 字段")
        # B.3 新增 3 tuplet 字段
        for field in ["tupletType", "tupletGroup", "tupletPosition"]:
            self.assertIn(f"this.{field}", self.content, f"Note 必须有 {field} 字段 (B.3)")

    def test_03_voice_class(self):
        self.assertRegex(self.content, r"class\s+Voice\s*\{")

    def test_04_measure_class(self):
        self.assertRegex(self.content, r"class\s+Measure\s*\{")
        # per voice 决策: voices 数组
        self.assertIn("this.voices = []", self.content)

    def test_05_part_class(self):
        self.assertRegex(self.content, r"class\s+Part\s*\{")
        self.assertIn("this.measures = []", self.content)

    def test_06_relation_class(self):
        self.assertRegex(self.content, r"class\s+Relation\s*\{")
        self.assertIn("this.type = type", self.content)
        self.assertIn("this.from = fromId", self.content)
        self.assertIn("this.to = toId", self.content)

    def test_07_score_class(self):
        self.assertRegex(self.content, r"class\s+Score\s*\{")
        # meta + parts + relations
        self.assertIn("this.meta =", self.content)
        self.assertIn("this.parts = []", self.content)
        self.assertIn("this.relations = []", self.content)

    def test_08_buildScore_factory(self):
        self.assertRegex(self.content, r"function\s+buildScore\s*\(")
        # 接受 legacyState
        self.assertIn("scoreMeasures", self.content)
        # 大谱表支持
        self.assertIn("staffScores", self.content)

    def test_09_exposes_to_window_or_module(self):
        # IIFE 暴露: window.ScoreModel 或 module.exports
        self.assertIn("ScoreModel", self.content)
        self.assertIn("module.exports", self.content)

    def test_10_no_vexflow_dependency(self):
        # Score Model 不应直接 import VexFlow (决策 5 半隔离)
        # 注释行忽略 (// 或 /* 开头)
        code_lines = []
        for line in self.content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue
            code_lines.append(line)
        code = "\n".join(code_lines)
        # Score Model 数据层不应用 VF. 引用
        self.assertNotIn("VF.", code, "Score Model 代码不应引用 VF. (VexFlow 隔离, P22.6 收口)")
        self.assertNotIn("VexFlow", code, "Score Model 代码不应引用 VexFlow")


# ===== 测试 2: 实际跑 buildScore (用 subprocess + node) =====

class TestBuildScoreFactory(unittest.TestCase):
    """buildScore factory: legacyState → Score Model"""

    def _build(self, legacy_state):
        return _run_node(json.dumps(legacy_state))

    def test_01_empty_state_returns_empty_score(self):
        result = self._build({})
        self.assertEqual(result["meta"]["title"], "")
        self.assertEqual(result["meta"]["tempo"], 120)
        self.assertEqual(result["parts"], [])

    def test_02_meta_overrides(self):
        result = self._build({"meta": {"title": "Test", "composer": "Beethoven", "tempo": 80}})
        self.assertEqual(result["meta"]["title"], "Test")
        self.assertEqual(result["meta"]["composer"], "Beethoven")
        self.assertEqual(result["meta"]["tempo"], 80)

    def test_03_single_staff_scoreMeasures(self):
        legacy = {
            "scoreMeasures": [
                [{"kind": "note", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "dotted": False, "voice": "1"}],
                [{"kind": "rest", "duration": "h", "voice": "1"}]
            ]
        }
        result = self._build(legacy)
        self.assertEqual(len(result["parts"]), 1, "单谱表 1 个 part")
        part = result["parts"][0]
        self.assertEqual(part["id"], "default")
        self.assertEqual(len(part["measures"]), 2)
        # measure 0
        m0 = part["measures"][0]
        self.assertEqual(m0["index"], 0)
        self.assertEqual(m0["number"], 1)
        self.assertEqual(len(m0["voices"]), 1, "单 voice")
        voice = m0["voices"][0]
        self.assertEqual(voice["id"], "1")
        self.assertEqual(voice["role"], "primary")
        self.assertEqual(len(voice["notes"]), 1)
        entry = voice["notes"][0]
        self.assertEqual(entry["kind"], "note")
        self.assertEqual(entry["duration"], "q")
        self.assertEqual(entry["units"], 8)
        # id 格式: p<partId>m<measureIndex>v<voiceId>e<entryIndex>
        self.assertEqual(entry["id"], "pdefaultm0v1e0")
        # 18 修饰符默认值
        self.assertEqual(entry["articulation"], "")
        self.assertEqual(entry["fermata"], False)
        self.assertEqual(entry["tieStart"], False)
        # measure 1: rest
        m1 = part["measures"][1]
        self.assertEqual(m1["voices"][0]["notes"][0]["kind"], "rest")

    def test_04_piano_mode_staffScores(self):
        # 大谱表: 2 part (treble + bass)
        legacy = {
            "staffScores": {
                "treble": {
                    "measures": [
                        [{"kind": "note", "pitches": [{"step": "G", "octave": 4}], "duration": "h", "voice": "1"}]
                    ]
                },
                "bass": {
                    "measures": [
                        [{"kind": "note", "pitches": [{"step": "C", "octave": 3}], "duration": "h", "voice": "1"}]
                    ]
                }
            }
        }
        result = self._build(legacy)
        self.assertEqual(len(result["parts"]), 2, "大谱表 2 个 part")
        self.assertEqual(result["parts"][0]["id"], "treble")
        self.assertEqual(result["parts"][1]["id"], "bass")
        # treble 第 1 音
        t_entry = result["parts"][0]["measures"][0]["voices"][0]["notes"][0]
        self.assertEqual(t_entry["pitches"][0]["step"], "G")
        self.assertEqual(t_entry["id"], "ptreblem0v1e0")
        # bass 第 1 音
        b_entry = result["parts"][1]["measures"][0]["voices"][0]["notes"][0]
        self.assertEqual(b_entry["pitches"][0]["step"], "C")
        self.assertEqual(b_entry["id"], "pbassm0v1e0")

    def test_05_multi_voice_per_measure(self):
        # 1 measure 多 voice
        legacy = {
            "scoreMeasures": [
                [
                    {"kind": "note", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "voice": "1"},
                    {"kind": "note", "pitches": [{"step": "E", "octave": 4}], "duration": "q", "voice": "2"}
                ]
            ]
        }
        result = self._build(legacy)
        m0 = result["parts"][0]["measures"][0]
        self.assertEqual(len(m0["voices"]), 2, "1 measure 2 voice")
        # voice 排序
        voice_ids = sorted([v["id"] for v in m0["voices"]])
        self.assertEqual(voice_ids, ["1", "2"])
        # voice 1: C, voice 2: E
        v1 = next(v for v in m0["voices"] if v["id"] == "1")
        v2 = next(v for v in m0["voices"] if v["id"] == "2")
        self.assertEqual(v1["notes"][0]["pitches"][0]["step"], "C")
        self.assertEqual(v2["notes"][0]["pitches"][0]["step"], "E")

    def test_06_modifier_fields_preserved(self):
        # 验证 18 修饰符字段都从 legacy 复制
        legacy = {
            "scoreMeasures": [
                [{
                    "kind": "note",
                    "pitches": [{"step": "C", "octave": 4}],
                    "duration": "q",
                    "voice": "1",
                    "articulation": "staccato",
                    "fermata": True,
                    "tieStart": True,
                    "dynamic": "f",
                    "volta": 2,
                    "rehearsalMark": "A"
                }]
            ]
        }
        result = self._build(legacy)
        e = result["parts"][0]["measures"][0]["voices"][0]["notes"][0]
        self.assertEqual(e["articulation"], "staccato")
        self.assertEqual(e["fermata"], True)
        self.assertEqual(e["tieStart"], True)
        self.assertEqual(e["dynamic"], "f")
        self.assertEqual(e["volta"], 2)
        self.assertEqual(e["rehearsalMark"], "A")

    def test_07_score_helper_methods(self):
        # addPart / getPart / getMeasure / addRelation / getRelationsByType
        # 用独立 node 脚本跑 Score Model 方法
        js = '''
global.window = global;
require("''' + SCOREMODEL_PATH.replace(os.sep, "/") + '''");
const SM = global.ScoreModel;
const score = new SM.Score();
const part = new SM.Part("test", "Test");
const measure = new SM.Measure(0);
part.measures.push(measure);
score.addPart(part);
const rel = new SM.Relation("tie", "a", "b");
score.addRelation(rel);
process.stdout.write(JSON.stringify({
  partFound: score.getPart("test") !== null,
  measureFound: score.getMeasure("test", 0) !== null,
  relsByType: score.getRelationsByType("tie").length,
  wrongPart: score.getPart("nonexistent") === null
}));
'''
        result = subprocess.run(
            ["node", "-e", js], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            self.fail(f"node failed: {result.stderr}")
        out = json.loads(result.stdout)
        self.assertTrue(out["partFound"])
        self.assertTrue(out["measureFound"])
        self.assertEqual(out["relsByType"], 1)
        self.assertTrue(out["wrongPart"])


# ===== 测试 3: index.html 加载 =====

class TestScoreModelLoading(unittest.TestCase):
    """index.html 加载 score-model.js (在 app.js 前)"""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "web", "index.html"), "r", encoding="utf-8") as f:
            cls.html = f.read()

    def test_01_score_model_script_tag(self):
        self.assertRegex(self.html, r'<script\s+src="score-model\.js[^"]*"')

    def test_02_loaded_before_app_js(self):
        # score-model.js 的 <script> 必须在 app.js 之前
        sm_pos = self.html.find('src="score-model.js')
        app_pos = self.html.find('src="app.js')
        self.assertGreater(sm_pos, 0)
        self.assertGreater(app_pos, 0)
        self.assertLess(sm_pos, app_pos, "score-model.js 必须在 app.js 之前加载")


if __name__ == "__main__":
    unittest.main()
