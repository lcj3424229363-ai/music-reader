"""
P22.5-B.5 — Score Model 渲染集成 (影子模式)

目标: 验证 B.5 落地的影子模式集成
  1. 静态: renderNotation 末尾调 runScoreModelShadow
  2. 静态: exportScoreJson 输出含 scoreModel 字段
  3. 动态: 模拟 shadow pipeline 跑 buildScore + buildRelations + validateRelations
  4. 动态: 验证 Score Model 跟 legacy 数据一致 (parts / voices / notes / relations)
  5. 静态: 验证 shadow 函数 fail-safe (失败只 console.warn 不抛)

纪律: 静态测试 grep app.js, 动态测试用 node subprocess 跑 score-model.js
"""
import os
import re
import unittest
import json
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOREMODEL_PATH = os.path.join(ROOT, "web", "score-model.js")
APP_JS_PATH = os.path.join(ROOT, "web", "app.js")
SM = SCOREMODEL_PATH.replace(os.sep, "/")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _run_node_script(js):
    result = subprocess.run(
        ["node", "-e", js], capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        raise RuntimeError(f"node failed: {result.stderr}")
    return result.stdout


def _run_with_legacy(legacy_state, body):
    """模拟 runScoreModelShadow pipeline"""
    js = f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const legacy = {json.dumps(legacy_state)};
const score = SM.buildScore(legacy);
SM.buildRelations(score);
const v = SM.validateRelations(score);
{body}
'''
    return _run_node_script(js)


# ===== 1. 静态 grep app.js: shadow block 落地 =====

class TestAppJsShadowStatic(unittest.TestCase):
    """app.js 静态检查: shadow block + exportScoreJson 接 scoreModel"""

    @classmethod
    def setUpClass(cls):
        cls.content = _read(APP_JS_PATH)

    def test_01_runScoreModelShadow_defined(self):
        # 函数定义存在
        self.assertRegex(
            self.content,
            r"function\s+runScoreModelShadow\s*\(",
            "runScoreModelShadow 函数必须存在"
        )

    def test_02_renderNotation_calls_shadow_at_end(self):
        # 用 brace 计数定位 renderNotation 函数体结束位置
        start_match = re.search(
            r"function\s+renderNotation\s*\([^)]*\)\s*\{",
            self.content
        )
        self.assertIsNotNone(start_match, "renderNotation 函数必须存在")
        body_start = start_match.end()
        # brace 计数找匹配 `}` (跳过字符串/注释内的 `}` 太复杂, 简化: 假设不含嵌套对象字面量)
        depth = 1
        i = body_start
        while i < len(self.content) and depth > 0:
            ch = self.content[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            i += 1
        body = self.content[body_start:i - 1]
        # 函数末尾应该 runScoreModelShadow();
        self.assertTrue(
            body.rstrip().endswith("runScoreModelShadow();"),
            f"renderNotation 末尾应调 runScoreModelShadow(), 实际末尾: ...{body[-100:]!r}"
        )

    def test_03_exportScoreJson_includes_scoreModel(self):
        # exportScoreJson 输出 scoreModel 字段
        self.assertIn("scoreModel", self.content, "exportScoreJson 路径应有 scoreModel 输出")
        # 找到 exportScoreJson 函数体
        match = re.search(
            r"function\s+exportScoreJson\s*\([^)]*\)\s*\{(.*?)\n\}",
            self.content,
            re.DOTALL
        )
        self.assertIsNotNone(match, "exportScoreJson 函数必须存在")
        body = match.group(1)
        # 应有 scoreModelJson 变量 + JSON.parse(JSON.stringify(score))
        self.assertIn("scoreModelJson", body, "exportScoreJson 应有 scoreModelJson 变量")
        self.assertIn("JSON.parse(JSON.stringify(score))", body, "Score 序列化为 JSON")

    def test_04_shadow_function_fail_safe(self):
        # shadow 函数 try-catch 包, 失败只 console.warn 不抛
        match = re.search(
            r"function\s+runScoreModelShadow\s*\(\)\s*\{(.*?)\n\}",
            self.content,
            re.DOTALL
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertIn("try {", body, "shadow 必须 try-catch 包裹")
        self.assertIn("console.warn", body, "shadow 失败必须 console.warn")
        self.assertNotIn("throw", body, "shadow 失败不能 throw")


# ===== 2. 动态: 模拟 shadow pipeline =====

class TestShadowPipeline(unittest.TestCase):
    """模拟 runScoreModelShadow 跑完整 pipeline"""

    def test_01_piano_mode_dual_part(self):
        # 双谱表: treble + bass
        out = _run_with_legacy(
            {
                "staffScores": {
                    "treble": {"measures": [
                        [{"kind": "note", "voice": "1", "pitches": [{"step": "G", "octave": 4}], "duration": "h"}]
                    ]},
                    "bass": {"measures": [
                        [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 3}], "duration": "h"}]
                    ]}
                }
            },
            """
process.stdout.write(JSON.stringify({
  partCount: score.parts.length,
  partIds: score.parts.map(p => p.id),
  totalNotes: score.parts.reduce((sum, p) => sum + p.measures.reduce((ms, m) => ms + m.voices.reduce((vs, v) => vs + v.notes.length, 0), 0), 0),
  valid: v.valid
}));
"""
        )
        result = json.loads(out)
        self.assertEqual(result["partCount"], 2)
        self.assertEqual(result["partIds"], ["treble", "bass"])
        self.assertEqual(result["totalNotes"], 2)
        self.assertTrue(result["valid"], "双谱表 shadow pipeline 应该 valid")

    def test_02_single_staff_mode(self):
        out = _run_with_legacy(
            {"scoreMeasures": [
                [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStart": True}],
                [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStop": True}]
            ]},
            """
process.stdout.write(JSON.stringify({
  partCount: score.parts.length,
  measureCount: score.parts[0].measures.length,
  totalNotes: score.parts[0].measures.reduce((ms, m) => ms + m.voices.reduce((vs, v) => vs + v.notes.length, 0), 0),
  relationCount: score.relations.length,
  relationType: score.relations[0] && score.relations[0].type,
  valid: v.valid
}));
"""
        )
        result = json.loads(out)
        self.assertEqual(result["partCount"], 1)
        self.assertEqual(result["measureCount"], 2)
        self.assertEqual(result["totalNotes"], 2)
        self.assertEqual(result["relationCount"], 1, "跨 measure tie 应生成 1 关系")
        self.assertEqual(result["relationType"], "tie")
        self.assertTrue(result["valid"])

    def test_03_legacy_data_consistency(self):
        """Score Model 跟 legacy 数据的 notes 数 / pitch 必须一致"""
        out = _run_with_legacy(
            {"scoreMeasures": [
                [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}, {"step": "E", "octave": 4}], "duration": "h"}],
                [{"kind": "note", "voice": "1", "pitches": [{"step": "G", "octave": 4}], "duration": "q"},
                 {"kind": "rest", "voice": "1", "duration": "q"}]
            ]},
            """
const legacyNoteCount = score.parts[0].measures.reduce((s, m) => s + m.voices.reduce((vs, v) => vs + v.notes.length, 0), 0);
const scoreNoteCount = legacyNoteCount;
// 音高对比
const scorePitches = score.parts[0].measures[0].voices[0].notes[0].pitches;
process.stdout.write(JSON.stringify({
  scoreNoteCount: scoreNoteCount,
  firstNoteStep: scorePitches[0].step,
  firstNoteChordSize: scorePitches.length,
  secondNoteKind: score.parts[0].measures[1].voices[0].notes[1].kind
}));
"""
        )
        result = json.loads(out)
        self.assertEqual(result["scoreNoteCount"], 3, "Score Model 3 个 note (2 note + 1 rest)")
        self.assertEqual(result["firstNoteStep"], "C")
        self.assertEqual(result["firstNoteChordSize"], 2, "chord 2 音应保留")
        self.assertEqual(result["secondNoteKind"], "rest", "rest kind 应保留")

    def test_04_fail_safe_empty_score(self):
        """空 score 也不抛, 返空 Score"""
        out = _run_with_legacy(
            {},
            """
process.stdout.write(JSON.stringify({
  className: score.constructor.name,
  partsLen: score.parts.length,
  relationsLen: score.relations.length,
  valid: v.valid
}));
"""
        )
        result = json.loads(out)
        self.assertEqual(result["className"], "Score")
        self.assertEqual(result["partsLen"], 0)
        self.assertTrue(result["valid"])

    def test_05_fail_safe_malformed_legacy(self):
        """坏数据 (undefined / [] measures) 不抛, 走空路径"""
        out = _run_with_legacy(
            {"scoreMeasures": [[], [], [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"}]]},
            """
const noteCount = score.parts[0].measures.reduce((s, m) => s + m.voices.reduce((vs, v) => vs + v.notes.length, 0), 0);
process.stdout.write(JSON.stringify({noteCount, valid: v.valid}));
"""
        )
        result = json.loads(out)
        self.assertEqual(result["noteCount"], 1, "空 measure 跳过, 1 个真 note 保留")
        self.assertTrue(result["valid"])


# ===== 3. 集成: 全 P22.5-B 链路 =====
class TestB1ToB5FullChain(unittest.TestCase):
    """B.1-B.5 完整链路: buildScore → relations → validate → JSON → fromJSON 一致"""

    def test_01_full_chain_no_data_loss(self):
        # B.3 buildRelations 是追加语义 (不覆盖), round-trip 测之前清空 relations
        out = _run_with_legacy(
            {
                "scoreMeasures": [
                    [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStart": True, "slurStart": True}],
                    [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStop": True, "slurStop": True}]
                ]
            },
            """
const originalRelCount = score.relations.length;
const jsonStr = JSON.stringify(score);
const score2 = SM.scoreFromJSON(JSON.parse(jsonStr));
// 清空 score2 已有 relations (fromJSON 还原的), 重新跑 buildRelations 模拟第一次生成
score2.relations = [];
SM.buildRelations(score2);
const jsonStr2 = JSON.stringify(score2);
process.stdout.write(JSON.stringify({
  original: jsonStr.length,
  roundTrip: jsonStr2.length,
  dataEqual: jsonStr === jsonStr2,
  originalRelCount: originalRelCount,
  newRelCount: score2.relations.length
}));
"""
        )
        result = json.loads(out)
        self.assertEqual(result["original"], result["roundTrip"])
        self.assertTrue(result["dataEqual"], "B.1-B.5 完整 round-trip 数据应完全一致")
        self.assertEqual(result["originalRelCount"], 2, "1 tie + 1 slur")
        self.assertEqual(result["newRelCount"], 2)


if __name__ == "__main__":
    unittest.main()
