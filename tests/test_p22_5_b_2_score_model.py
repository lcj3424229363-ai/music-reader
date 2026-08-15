"""
P22.5-B.2 — Score Model 转换层 (双向 + 关系生成 + 验证)

目标: 验证 4 个新 helper 行为
  1. buildLegacyFromScore: Score → legacy (反向)
  2. buildRelations: 扫描 entry 标记 → Relation 对象
  3. validateRelations: 关系一致性验证
  4. syncEntryFromRelation: 关系反向更新 entry 标记

纪律: 用 node + subprocess 实际跑 web/score-model.js
        Score Model 是 class instance, 不能用 Python JSON 序列化 (会丢 class type),
        所以每个测试用单次 subprocess, 在 node 内部全程持有 Score instance。
"""
import os
import unittest
import json
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOREMODEL_PATH = os.path.join(ROOT, "web", "score-model.js")
SM = SCOREMODEL_PATH.replace(os.sep, "/")


def _run_node_script(js):
    """node 跑独立 JS 脚本, 返 stdout"""
    result = subprocess.run(
        ["node", "-e", js], capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        raise RuntimeError(f"node failed: {result.stderr}")
    return result.stdout


def _run_with_score(legacy_state, body):
    """
    在 node 里:
      1. buildScore(legacy_state) → score
      2. 跑 body(score, SM)
      3. 输出 body 的 process.stdout.write(...) 结果
    """
    js = f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const score = SM.buildScore({json.dumps(legacy_state)});
{body}
'''
    return _run_node_script(js)


# ===== 1. buildLegacyFromScore: 反向转换 =====

class TestBuildLegacyFromScore(unittest.TestCase):
    """Score → legacy 反向转换 (B.2 决策 1: 自动检测)"""

    def test_01_single_part_returns_scoreMeasures(self):
        out = _run_with_score(
            {"scoreMeasures": [[{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"}]]},
            "process.stdout.write(JSON.stringify(SM.buildLegacyFromScore(score)));"
        )
        legacy = json.loads(out)
        self.assertIn("scoreMeasures", legacy)
        self.assertNotIn("staffScores", legacy)
        self.assertEqual(len(legacy["scoreMeasures"]), 1)
        self.assertEqual(legacy["scoreMeasures"][0][0]["pitches"][0]["step"], "C")

    def test_02_multi_part_returns_staffScores(self):
        out = _run_with_score(
            {
                "staffScores": {
                    "treble": {"measures": [[{"kind": "note", "voice": "1", "pitches": [{"step": "G", "octave": 4}], "duration": "h"}]]},
                    "bass": {"measures": [[{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 3}], "duration": "h"}]]}
                }
            },
            "process.stdout.write(JSON.stringify(SM.buildLegacyFromScore(score)));"
        )
        legacy = json.loads(out)
        self.assertIn("staffScores", legacy)
        self.assertNotIn("scoreMeasures", legacy)
        self.assertEqual(len(legacy["staffScores"]["treble"]["measures"]), 1)
        self.assertEqual(legacy["staffScores"]["bass"]["measures"][0][0]["pitches"][0]["step"], "C")

    def test_03_meta_preserved(self):
        out = _run_with_score(
            {"meta": {"title": "Test", "tempo": 80}, "scoreMeasures": []},
            "process.stdout.write(JSON.stringify(SM.buildLegacyFromScore(score)));"
        )
        legacy = json.loads(out)
        self.assertEqual(legacy["meta"]["title"], "Test")
        self.assertEqual(legacy["meta"]["tempo"], 80)

    def test_04_strips_underscore_fields(self):
        out = _run_with_score(
            {"scoreMeasures": [[{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"}]]},
            "process.stdout.write(JSON.stringify(SM.buildLegacyFromScore(score)));"
        )
        legacy = json.loads(out)
        entry = legacy["scoreMeasures"][0][0]
        # _ 前缀字段 (Score Model 内部) 不应泄漏
        for k in ["_globalIndex", "_measureIndex", "_localIndex", "_voiceId", "_staffId"]:
            self.assertNotIn(k, entry, f"legacy entry 不应有内部字段 {k}")
        # 但基础字段 + id 保留
        self.assertIn("kind", entry)
        self.assertIn("pitches", entry)
        self.assertIn("id", entry)

    def test_05_empty_score_returns_meta_only(self):
        out = _run_with_score(
            {},
            "process.stdout.write(JSON.stringify(SM.buildLegacyFromScore(score)));"
        )
        legacy = json.loads(out)
        # 空 score: meta 仍存在, 没有 scoreMeasures/staffScores
        self.assertIn("meta", legacy)


# ===== 2. buildRelations: 关系生成 =====

class TestBuildRelations(unittest.TestCase):
    """扫描 entry 标记 → tie Relation 对象 (B.2 决策 2: 只做 tie)"""

    def test_01_empty_score_no_relations(self):
        out = _run_with_score(
            {},
            "process.stdout.write(JSON.stringify(SM.buildRelations(score)));"
        )
        rels = json.loads(out)
        self.assertEqual(rels, [])

    def test_02_same_measure_tie(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStart": True},
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStop": True}
            ]]},
            "process.stdout.write(JSON.stringify(SM.buildRelations(score)));"
        )
        rels = json.loads(out)
        self.assertEqual(len(rels), 1, "应该生成 1 个 tie 关系")
        rel = rels[0]
        self.assertEqual(rel["type"], "tie")
        self.assertEqual(rel["id"], "r0")
        # from/to id: p<partId>m<measureIdx>v<voiceId>e<entryIdx>
        self.assertTrue(rel["from"].endswith("e0"))
        self.assertTrue(rel["to"].endswith("e1"))

    def test_03_cross_measure_tie(self):
        out = _run_with_score(
            {"scoreMeasures": [
                [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStart": True}],
                [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStop": True}]
            ]},
            "process.stdout.write(JSON.stringify(SM.buildRelations(score)));"
        )
        rels = json.loads(out)
        self.assertEqual(len(rels), 1, "跨 measure tie 应该生成 1 个关系")
        rel = rels[0]
        # from 在 measure 0, to 在 measure 1
        # id 格式: p<partId>m<measureIdx>v<voiceId>e<entryIdx>
        from_m = rel["from"].split("m")[1]  # "0v1e0"
        to_m = rel["to"].split("m")[1]
        self.assertTrue(from_m.startswith("0"), f"from 应在 measure 0, got {from_m}")
        self.assertTrue(to_m.startswith("1"), f"to 应在 measure 1, got {to_m}")

    def test_04_tie_start_without_stop_no_relation(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStart": True}
            ]]},
            "process.stdout.write(JSON.stringify(SM.buildRelations(score)));"
        )
        rels = json.loads(out)
        self.assertEqual(rels, [], "找不到 tieStop 时不生成关系")


# ===== 3. validateRelations: 关系验证 =====

class TestValidateRelations(unittest.TestCase):
    """关系一致性验证 (B.2)"""

    def test_01_valid_relation(self):
        # from/to 同音高 — valid
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStart": True},
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStop": True}
            ]]},
            """
const rels = SM.buildRelations(score);
const v = SM.validateRelations(score);
process.stdout.write(JSON.stringify({rels: rels.length, valid: v.valid, errors: v.errors}));
"""
        )
        result = json.loads(out)
        self.assertEqual(result["rels"], 1)
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])

    def test_02_missing_from_entry(self):
        # 手动加一个错关系 (from id 不存在)
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"}
            ]]},
            """
score.addRelation(new SM.Relation("tie", "nonexistent", "pdefaultm0v1e0"));
const v = SM.validateRelations(score);
process.stdout.write(JSON.stringify({valid: v.valid, errors: v.errors}));
"""
        )
        result = json.loads(out)
        self.assertFalse(result["valid"])
        self.assertTrue(any("from note" in e and "not found" in e for e in result["errors"]))

    def test_03_pitches_dont_share(self):
        # tie from C/to D — 不同音高
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "D", "octave": 4}], "duration": "q"}
            ]]},
            """
const from = score.parts[0].measures[0].voices[0].notes[0];
const to = score.parts[0].measures[0].voices[0].notes[1];
score.addRelation(new SM.Relation("tie", from.id, to.id));
const v = SM.validateRelations(score);
process.stdout.write(JSON.stringify({valid: v.valid, errors: v.errors}));
"""
        )
        result = json.loads(out)
        self.assertFalse(result["valid"])
        self.assertTrue(any("pitches don't share" in e for e in result["errors"]))


# ===== 4. syncEntryFromRelation: 双向同步 =====

class TestSyncEntryFromRelation(unittest.TestCase):
    """关系 → entry 标记 双向同步 (B.2)"""

    def test_01_tie_sync_sets_tieStart_and_tieStop(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"}
            ]]},
            """
const from = score.parts[0].measures[0].voices[0].notes[0];
const to = score.parts[0].measures[0].voices[0].notes[1];
const rel = new SM.Relation("tie", from.id, to.id);
SM.syncEntryFromRelation(score, rel);
process.stdout.write(JSON.stringify({fromTieStart: from.tieStart, toTieStop: to.tieStop}));
"""
        )
        result = json.loads(out)
        self.assertTrue(result["fromTieStart"])
        self.assertTrue(result["toTieStop"])

    def test_02_slur_sync_sets_slurStart_and_slurStop(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"}
            ]]},
            """
const from = score.parts[0].measures[0].voices[0].notes[0];
const to = score.parts[0].measures[0].voices[0].notes[1];
const rel = new SM.Relation("slur", from.id, to.id);
SM.syncEntryFromRelation(score, rel);
process.stdout.write(JSON.stringify({fromSlurStart: from.slurStart, toSlurStop: to.slurStop, tieStartUntouched: from.tieStart}));
"""
        )
        result = json.loads(out)
        self.assertTrue(result["fromSlurStart"])
        self.assertTrue(result["toSlurStop"])
        # tieStart 不应被 slur 影响
        self.assertFalse(result["tieStartUntouched"])


# ===== 5. 集成 round-trip =====

class TestIntegrationRoundTrip(unittest.TestCase):
    """集成: buildScore → buildRelations → validateRelations → buildLegacyFromScore"""

    def test_01_full_round_trip(self):
        # 复杂乐谱: 跨 measure tie
        out = _run_with_score(
            {
                "scoreMeasures": [
                    [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "h", "tieStart": True}],
                    [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStop": True}]
                ]
            },
            """
const rels = SM.buildRelations(score);
const v = SM.validateRelations(score);
const legacy = SM.buildLegacyFromScore(score);
process.stdout.write(JSON.stringify({
  relsCount: rels.length,
  valid: v.valid,
  errors: v.errors,
  legacyMeasures: legacy.scoreMeasures ? legacy.scoreMeasures.length : 0
}));
"""
        )
        result = json.loads(out)
        self.assertEqual(result["relsCount"], 1)
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["legacyMeasures"], 2)


if __name__ == "__main__":
    unittest.main()
