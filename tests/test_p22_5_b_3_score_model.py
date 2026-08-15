"""
P22.5-B.3 — Score Model 跨 measure 关系 (slur / phrase / tuplet)

目标: 验证 B.3 新增 / 修改的能力
  1. Note 类 3 tuplet 字段 (tupletType / tupletGroup / tupletPosition)
  2. legacyToNote 拷贝 tuplet 3 字段 (B.1 漏修)
  3. buildRelations types[] 通用: tie / slur / phrase / tuplet 全扫
  4. validateRelations 区分 errors / warnings
     - slur 跨 voice = warning (不 error)
     - tuplet members count 跟 actual 不一致 = error
  5. syncEntryFromRelation: slur / phrase 分支, tuplet 不接
  6. Relation.members (tuplet) + payload {actual, normal}

纪律: 用 node + subprocess 实际跑 web/score-model.js
"""
import os
import unittest
import json
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOREMODEL_PATH = os.path.join(ROOT, "web", "score-model.js")
SM = SCOREMODEL_PATH.replace(os.sep, "/")


def _run_node_script(js):
    result = subprocess.run(
        ["node", "-e", js], capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        raise RuntimeError(f"node failed: {result.stderr}")
    return result.stdout


def _run_with_score(legacy_state, body):
    js = f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const score = SM.buildScore({json.dumps(legacy_state)});
{body}
'''
    return _run_node_script(js)


# ===== 1. Note 类 3 tuplet 字段 =====

class TestNoteTupletFields(unittest.TestCase):
    """Note 3 tuplet 字段 (B.3 落地, B.1 漏修补全)"""

    def test_01_note_default_has_tuplet_fields(self):
        out = _run_node_script(f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const n = new SM.Note();
process.stdout.write(JSON.stringify({{
  tupletType: n.tupletType,
  tupletGroup: n.tupletGroup,
  tupletPosition: n.tupletPosition
}}));
''')
        result = json.loads(out)
        self.assertEqual(result["tupletType"], "")
        self.assertEqual(result["tupletGroup"], "")
        self.assertEqual(result["tupletPosition"], "")

    def test_02_legacy_to_note_copies_tuplet_fields(self):
        # B.1 漏修根因: legacyToNote 之前没拷 3 tuplet 字段
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1",
                 "pitches": [{"step": "C", "octave": 4}], "duration": "8",
                 "tupletType": "triplet", "tupletGroup": "tg1", "tupletPosition": "start"}
            ]]},
            """
const note = score.parts[0].measures[0].voices[0].notes[0];
process.stdout.write(JSON.stringify({
  tupletType: note.tupletType,
  tupletGroup: note.tupletGroup,
  tupletPosition: note.tupletPosition
}));
"""
        )
        result = json.loads(out)
        self.assertEqual(result["tupletType"], "triplet")
        self.assertEqual(result["tupletGroup"], "tg1")
        self.assertEqual(result["tupletPosition"], "start")

    def test_03_legacy_to_note_without_tuplet_defaults(self):
        # 老 entry 没 tuplet 字段时, Score Model 应该有默认值
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"}
            ]]},
            """
const note = score.parts[0].measures[0].voices[0].notes[0];
process.stdout.write(JSON.stringify({
  tupletType: note.tupletType,
  tupletGroup: note.tupletGroup,
  tupletPosition: note.tupletPosition
}));
"""
        )
        result = json.loads(out)
        self.assertEqual(result["tupletType"], "")
        self.assertEqual(result["tupletGroup"], "")
        self.assertEqual(result["tupletPosition"], "")


# ===== 2. buildRelations: slur =====

class TestBuildRelationsSlur(unittest.TestCase):
    """slur 关系生成 (B.3 新增)"""

    def test_01_same_measure_slur(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "slurStart": True},
                {"kind": "note", "voice": "1", "pitches": [{"step": "D", "octave": 4}], "duration": "q", "slurStop": True}
            ]]},
            "process.stdout.write(JSON.stringify(SM.buildRelations(score)));"
        )
        rels = json.loads(out)
        self.assertEqual(len(rels), 1)
        rel = rels[0]
        self.assertEqual(rel["type"], "slur")
        self.assertTrue(rel["from"].endswith("e0"))
        self.assertTrue(rel["to"].endswith("e1"))

    def test_02_cross_measure_slur(self):
        out = _run_with_score(
            {"scoreMeasures": [
                [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "slurStart": True}],
                [{"kind": "note", "voice": "1", "pitches": [{"step": "D", "octave": 4}], "duration": "q", "slurStop": True}]
            ]},
            "process.stdout.write(JSON.stringify(SM.buildRelations(score)));"
        )
        rels = json.loads(out)
        self.assertEqual(len(rels), 1)
        rel = rels[0]
        from_m = rel["from"].split("m")[1]
        to_m = rel["to"].split("m")[1]
        self.assertTrue(from_m.startswith("0"))
        self.assertTrue(to_m.startswith("1"))

    def test_03_slur_start_without_stop_no_relation(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "slurStart": True}
            ]]},
            "process.stdout.write(JSON.stringify(SM.buildRelations(score)));"
        )
        rels = json.loads(out)
        self.assertEqual(rels, [])


# ===== 3. buildRelations: phrase =====

class TestBuildRelationsPhrase(unittest.TestCase):
    """phrase 关系生成 (B.3 新增)"""

    def test_01_same_measure_phrase(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "phraseStart": True},
                {"kind": "note", "voice": "1", "pitches": [{"step": "D", "octave": 4}], "duration": "q", "phraseStop": True}
            ]]},
            "process.stdout.write(JSON.stringify(SM.buildRelations(score)));"
        )
        rels = json.loads(out)
        self.assertEqual(len(rels), 1)
        rel = rels[0]
        self.assertEqual(rel["type"], "phrase")

    def test_02_phrase_cross_voice(self):
        # B.3 决策 5: phrase 允许跨 voice
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "phraseStart": True},
                {"kind": "note", "voice": "2", "pitches": [{"step": "E", "octave": 4}], "duration": "q", "phraseStop": True}
            ]]},
            "process.stdout.write(JSON.stringify(SM.buildRelations(score)));"
        )
        rels = json.loads(out)
        self.assertEqual(len(rels), 1, "phrase 跨 voice 应该生成关系")


# ===== 4. buildRelations: tuplet =====

class TestBuildRelationsTuplet(unittest.TestCase):
    """tuplet 关系生成 (B.3 核心新)"""

    def test_01_triplet_generates_one_relation(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "start"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "D", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "middle"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "E", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "end"}
            ]]},
            "process.stdout.write(JSON.stringify(SM.buildRelations(score)));"
        )
        rels = json.loads(out)
        tupletRels = [r for r in rels if r["type"] == "tuplet"]
        self.assertEqual(len(tupletRels), 1, "1 group 应该 1 个 tuplet 关系")
        rel = tupletRels[0]
        self.assertEqual(len(rel["members"]), 3)
        self.assertEqual(rel["payload"]["actual"], 3)
        self.assertEqual(rel["payload"]["normal"], 2)
        # members 不要叫 entryIds
        for k in rel.keys():
            self.assertNotEqual(k, "entryIds", "tuplet 关系不能用 entryIds 字段 (B.3 决策 3)")

    def test_02_quintuplet_payload(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "16", "tupletType": "quintuplet", "tupletGroup": "g1", "tupletPosition": "start"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "D", "octave": 4}], "duration": "16", "tupletType": "quintuplet", "tupletGroup": "g1", "tupletPosition": "middle"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "E", "octave": 4}], "duration": "16", "tupletType": "quintuplet", "tupletGroup": "g1", "tupletPosition": "middle"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "F", "octave": 4}], "duration": "16", "tupletType": "quintuplet", "tupletGroup": "g1", "tupletPosition": "middle"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "G", "octave": 4}], "duration": "16", "tupletType": "quintuplet", "tupletGroup": "g1", "tupletPosition": "end"}
            ]]},
            "process.stdout.write(JSON.stringify(SM.buildRelations(score)));"
        )
        rels = json.loads(out)
        tupletRels = [r for r in rels if r["type"] == "tuplet"]
        self.assertEqual(len(tupletRels), 1)
        rel = tupletRels[0]
        self.assertEqual(len(rel["members"]), 5)
        self.assertEqual(rel["payload"]["actual"], 5)
        self.assertEqual(rel["payload"]["normal"], 4)

    def test_03_two_groups_two_relations(self):
        # 2 个独立 group, 应该 2 个 tuplet 关系
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "start"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "D", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "middle"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "E", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "end"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "F", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g2", "tupletPosition": "start"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "G", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g2", "tupletPosition": "middle"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "A", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g2", "tupletPosition": "end"}
            ]]},
            "process.stdout.write(JSON.stringify(SM.buildRelations(score)));"
        )
        rels = json.loads(out)
        tupletRels = [r for r in rels if r["type"] == "tuplet"]
        self.assertEqual(len(tupletRels), 2)


# ===== 5. validateRelations: slur warning =====

class TestValidateRelationsSlur(unittest.TestCase):
    """slur cross-voice 是 warning, 不 error (B.3 决策 4)"""

    def test_01_slur_cross_voice_is_warning_not_error(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"},
                {"kind": "note", "voice": "2", "pitches": [{"step": "E", "octave": 4}], "duration": "q"}
            ]]},
            """
const n1 = score.parts[0].measures[0].voices[0].notes[0];
const n2 = score.parts[0].measures[0].voices[1].notes[0];
score.addRelation(new SM.Relation("slur", n1.id, n2.id));
const v = SM.validateRelations(score);
process.stdout.write(JSON.stringify({valid: v.valid, errorCount: v.errors.length, warningCount: v.warnings.length}));
"""
        )
        result = json.loads(out)
        self.assertTrue(result["valid"], "cross-voice slur 应该是 valid (warning 不算 error)")
        self.assertEqual(result["errorCount"], 0)
        self.assertGreaterEqual(result["warningCount"], 1)

    def test_02_slur_does_not_validate_pitch(self):
        # slur 跟 tie 不同, 不要求同音高
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "E", "octave": 4}], "duration": "q"}
            ]]},
            """
const n1 = score.parts[0].measures[0].voices[0].notes[0];
const n2 = score.parts[0].measures[0].voices[0].notes[1];
score.addRelation(new SM.Relation("slur", n1.id, n2.id));
const v = SM.validateRelations(score);
process.stdout.write(JSON.stringify({valid: v.valid, errors: v.errors}));
"""
        )
        result = json.loads(out)
        self.assertTrue(result["valid"], "slur 不同音高应该 valid")


# ===== 6. validateRelations: tuplet errors =====

class TestValidateRelationsTuplet(unittest.TestCase):
    """tuplet 验证: members count 跟 actual 一致"""

    def test_01_triplet_valid(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "start"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "D", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "middle"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "E", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "end"}
            ]]},
            """
SM.buildRelations(score);
const v = SM.validateRelations(score);
process.stdout.write(JSON.stringify({valid: v.valid, errors: v.errors}));
"""
        )
        result = json.loads(out)
        self.assertTrue(result["valid"], "正常 triplet 应该 valid")

    def test_02_triplet_with_missing_member(self):
        # 手动造一个错的 tuplet 关系 (members 数量跟 actual 不一致)
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "8"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "D", "octave": 4}], "duration": "8"}
            ]]},
            """
const n1 = score.parts[0].measures[0].voices[0].notes[0];
const n2 = score.parts[0].measures[0].voices[0].notes[1];
const rel = new SM.Relation("tuplet", null, null);
rel.members = [n1.id, n2.id];  // 只有 2 个, 但 payload.actual = 3
rel.payload = {actual: 3, normal: 2};
score.addRelation(rel);
const v = SM.validateRelations(score);
process.stdout.write(JSON.stringify({valid: v.valid, errors: v.errors}));
"""
        )
        result = json.loads(out)
        self.assertFalse(result["valid"], "members 数量不一致应该 invalid")
        self.assertTrue(any("members.length" in e for e in result["errors"]))


# ===== 7. syncEntryFromRelation: phrase / slur 互不影响 =====

class TestSyncEntryFromRelationPhrase(unittest.TestCase):
    """syncEntryFromRelation 加 phrase / slur 分支"""

    def test_01_phrase_sync_sets_marks(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "D", "octave": 4}], "duration": "q"}
            ]]},
            """
const n1 = score.parts[0].measures[0].voices[0].notes[0];
const n2 = score.parts[0].measures[0].voices[0].notes[1];
const rel = new SM.Relation("phrase", n1.id, n2.id);
SM.syncEntryFromRelation(score, rel);
process.stdout.write(JSON.stringify({start: n1.phraseStart, stop: n2.phraseStop, slurUntouched: n1.slurStart}));
"""
        )
        result = json.loads(out)
        self.assertTrue(result["start"])
        self.assertTrue(result["stop"])
        self.assertFalse(result["slurUntouched"], "phrase sync 不应设置 slur 标记")

    def test_02_slur_sync_does_not_set_phrase(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "D", "octave": 4}], "duration": "q"}
            ]]},
            """
const n1 = score.parts[0].measures[0].voices[0].notes[0];
const n2 = score.parts[0].measures[0].voices[0].notes[1];
const rel = new SM.Relation("slur", n1.id, n2.id);
SM.syncEntryFromRelation(score, rel);
process.stdout.write(JSON.stringify({slurStart: n1.slurStart, slurStop: n2.slurStop, phraseUntouched: n1.phraseStart}));
"""
        )
        result = json.loads(out)
        self.assertTrue(result["slurStart"])
        self.assertTrue(result["slurStop"])
        self.assertFalse(result["phraseUntouched"])

    def test_03_tuplet_sync_returns_false(self):
        # tuplet 不接 sync, 业务侧管
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "start"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "D", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "middle"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "E", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "end"}
            ]]},
            """
const notes = score.parts[0].measures[0].voices[0].notes;
const rel = new SM.Relation("tuplet", null, null);
rel.members = notes.map(n => n.id);
const result = SM.syncEntryFromRelation(score, rel);
process.stdout.write(JSON.stringify({result: result}));
"""
        )
        result = json.loads(out)
        self.assertFalse(result["result"], "tuplet sync 应返回 false (不接)")


# ===== 8. 集成: buildRelations types 参数 =====

class TestBuildRelationsTypesParam(unittest.TestCase):
    """buildRelations 接受 types[] 参数 (B.3 决策 7)"""

    def test_01_types_tie_only(self):
        # 谱面同时有 tie + slur + tuplet, 但只请求 tie
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStart": True, "slurStart": True},
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStop": True, "slurStop": True},
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "start"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "D", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "middle"},
                {"kind": "note", "voice": "1", "pitches": [{"step": "E", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "end"}
            ]]},
            """
const rels = SM.buildRelations(score, ["tie"]);
process.stdout.write(JSON.stringify(rels.map(r => r.type)));
"""
        )
        types = json.loads(out)
        self.assertEqual(types, ["tie"], "types=['tie'] 应只生成 tie 关系")

    def test_02_types_empty_array_no_relations(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStart": True, "slurStart": True},
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStop": True, "slurStop": True}
            ]]},
            "process.stdout.write(JSON.stringify(SM.buildRelations(score, []).length));"
        )
        count = json.loads(out)
        self.assertEqual(count, 0, "空 types 应该不生成关系")


# ===== 9. 集成 round-trip 含 tuplet =====

class TestIntegrationTupletRoundTrip(unittest.TestCase):
    """集成: buildScore → buildRelations (types) → validateRelations → buildLegacyFromScore"""

    def test_01_full_round_trip_with_tuplet(self):
        out = _run_with_score(
            {
                "scoreMeasures": [
                    [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStart": True, "slurStart": True}],
                    [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStop": True, "slurStop": True},
                     {"kind": "note", "voice": "1", "pitches": [{"step": "E", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "start"},
                     {"kind": "note", "voice": "1", "pitches": [{"step": "F", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "middle"},
                     {"kind": "note", "voice": "1", "pitches": [{"step": "G", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "end"}]
                ]
            },
            """
const rels = SM.buildRelations(score);
const v = SM.validateRelations(score);
const legacy = SM.buildLegacyFromScore(score);
const typeCount = {};
rels.forEach(r => { typeCount[r.type] = (typeCount[r.type] || 0) + 1; });
// 验证 legacy 里 tuplet 字段保留
const legacyNotes = legacy.scoreMeasures.flat();
const hasTupletFields = legacyNotes.some(n => n.tupletType);
process.stdout.write(JSON.stringify({
  typeCount: typeCount,
  valid: v.valid,
  errorCount: v.errors.length,
  warningCount: v.warnings.length,
  legacyHasTupletFields: hasTupletFields
}));
"""
        )
        result = json.loads(out)
        # tie + slur + tuplet 都应生成
        self.assertEqual(result["typeCount"].get("tie", 0), 1)
        self.assertEqual(result["typeCount"].get("slur", 0), 1)
        self.assertEqual(result["typeCount"].get("tuplet", 0), 1)
        self.assertTrue(result["valid"], "round-trip 应该 valid")
        self.assertTrue(result["legacyHasTupletFields"], "legacy 应保留 tuplet 字段 (B.3 落地)")


if __name__ == "__main__":
    unittest.main()
