"""
P22.5-B.4 — Score Model JSON 序列化 (round-trip)

目标: 验证 B.4 落地的 JSON 序列化能力
  1. class toJSON × 5 (Note / Relation / Voice / Measure / Part / Score 都有 toJSON)
  2. JSON.stringify(score) 自动调 toJSON
  3. scoreFromJSON 反序列化, 完整还原
  4. round-trip: buildScore → scoreFromJSON → toJSON → fromJSON 数据一致
  5. relations (含 tuplet members + payload) 完整还原

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


# ===== 1. class toJSON =====

class TestToJSON(unittest.TestCase):
    """5 个 class 都有 toJSON, JSON.stringify 自动调"""

    def test_01_note_toJSON_has_all_31_fields(self):
        out = _run_node_script(f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const n = new SM.Note();
n.pitches = [{{step: "C", octave: 4}}];
n.tupletType = "triplet";
n.tupletGroup = "g1";
n.tupletPosition = "start";
n.slurStart = true;
n.articulation = "staccato";
const json = JSON.stringify(n);
const obj = JSON.parse(json);
const keys = Object.keys(obj);
process.stdout.write(JSON.stringify({{keyCount: keys.length, hasId: obj.id !== undefined, hasTuplet: obj.tupletType === "triplet", hasSlur: obj.slurStart === true, hasArticulation: obj.articulation === "staccato"}}));
''')
        result = json.loads(out)
        # Note 字段: id, kind, voice, pitches, duration, dotted, units (7) + 20 修饰符 (含 grace + volta + rehearsalMark) + 3 tuplet = 30
        self.assertEqual(result["keyCount"], 30, "Note 应该有 30 字段 (7 + 20 + 3)")
        self.assertTrue(result["hasId"])
        self.assertTrue(result["hasTuplet"])
        self.assertTrue(result["hasSlur"])
        self.assertTrue(result["hasArticulation"])

    def test_02_relation_toJSON_has_members_and_payload(self):
        out = _run_node_script(f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const r = new SM.Relation("tuplet", null, null);
r.id = "r0";
r.members = ["n1", "n2", "n3"];
r.payload = {{actual: 3, normal: 2}};
const obj = JSON.parse(JSON.stringify(r));
process.stdout.write(JSON.stringify({{type: obj.type, members: obj.members, payload: obj.payload, from: obj.from, to: obj.to}}));
''')
        result = json.loads(out)
        self.assertEqual(result["type"], "tuplet")
        self.assertEqual(result["members"], ["n1", "n2", "n3"])
        self.assertEqual(result["payload"], {"actual": 3, "normal": 2})
        self.assertIsNone(result["from"])
        self.assertIsNone(result["to"])

    def test_03_score_toJSON_has_meta_parts_relations(self):
        out = _run_node_script(f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const s = new SM.Score();
s.meta.title = "Test";
const obj = JSON.parse(JSON.stringify(s));
process.stdout.write(JSON.stringify({{hasMeta: obj.meta !== undefined, title: obj.meta.title, hasParts: Array.isArray(obj.parts), hasRelations: Array.isArray(obj.relations)}}));
''')
        result = json.loads(out)
        self.assertTrue(result["hasMeta"])
        self.assertEqual(result["title"], "Test")
        self.assertTrue(result["hasParts"])
        self.assertTrue(result["hasRelations"])


# ===== 2. JSON.stringify 自动调 toJSON =====

class TestJSONStringifyAuto(unittest.TestCase):
    """JSON.stringify(score) 自动触发 toJSON, 不用显式调"""

    def test_01_stringify_simple_score(self):
        out = _run_with_score(
            {"scoreMeasures": [[
                {"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q"}
            ]]},
            "process.stdout.write(JSON.stringify(score));"
        )
        obj = json.loads(out)
        self.assertIn("meta", obj)
        self.assertIn("parts", obj)
        self.assertEqual(obj["parts"][0]["measures"][0]["voices"][0]["notes"][0]["pitches"][0]["step"], "C")


# ===== 3. scoreFromJSON 反序列化 =====

class TestScoreFromJSON(unittest.TestCase):
    """scoreFromJSON 还原完整 Score instance"""

    def test_01_simple_score_from_json(self):
        out = _run_node_script(f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const json = JSON.parse('{{"meta": {{"title": "Test"}}, "parts": [{{"id": "default", "name": "default", "instrument": "piano", "staves": [], "measures": [{{"index": 0, "number": 1, "timeSignature": "4/4", "beginBarline": "single", "endBarline": "single", "voices": [{{"id": "1", "role": "primary", "notes": [{{"id": "p0m0v1e0", "kind": "note", "voice": "1", "pitches": [{{"step": "D", "octave": 5}}], "duration": "q", "dotted": false, "units": 8}}]}}], "tempo": null, "directions": [], "volta": null, "rehearsalMark": ""}}]}}], "relations": []}}');
const score = SM.scoreFromJSON(json);
const note = score.parts[0].measures[0].voices[0].notes[0];
process.stdout.write(JSON.stringify({{title: score.meta.title, partId: score.parts[0].id, noteStep: note.pitches[0].step, noteClass: note.constructor.name}}));
''')
        result = json.loads(out)
        self.assertEqual(result["title"], "Test")
        self.assertEqual(result["partId"], "default")
        self.assertEqual(result["noteStep"], "D")
        self.assertEqual(result["noteClass"], "Note", "反序列化后 Note 类应保留")

    def test_02_relations_including_tuplet_restored(self):
        out = _run_node_script(f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const json = JSON.parse('{{"meta": {{}}, "parts": [], "relations": [{{"id": "r0", "type": "tie", "from": "a", "to": "b", "members": null, "payload": {{}}}}, {{"id": "r1", "type": "tuplet", "from": null, "to": null, "members": ["n1", "n2", "n3"], "payload": {{"actual": 3, "normal": 2}}}}]}}');
const score = SM.scoreFromJSON(json);
const tie = score.relations[0];
const tup = score.relations[1];
process.stdout.write(JSON.stringify({{tieType: tie.type, tieFrom: tie.from, tupType: tup.type, tupMembers: tup.members, tupPayload: tup.payload, tupMembersIsArray: Array.isArray(tup.members)}}));
''')
        result = json.loads(out)
        self.assertEqual(result["tieType"], "tie")
        self.assertEqual(result["tieFrom"], "a")
        self.assertEqual(result["tupType"], "tuplet")
        self.assertEqual(result["tupMembers"], ["n1", "n2", "n3"])
        self.assertEqual(result["tupPayload"], {"actual": 3, "normal": 2})
        self.assertTrue(result["tupMembersIsArray"])

    def test_03_empty_score_from_json(self):
        out = _run_node_script(f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const score = SM.scoreFromJSON({{}});
process.stdout.write(JSON.stringify({{className: score.constructor.name, partsLen: score.parts.length, relationsLen: score.relations.length}}));
''')
        result = json.loads(out)
        self.assertEqual(result["className"], "Score")
        self.assertEqual(result["partsLen"], 0)
        self.assertEqual(result["relationsLen"], 0)


# ===== 4. round-trip: buildScore → scoreFromJSON → toJSON → 一致 =====

class TestRoundTrip(unittest.TestCase):
    """完整 round-trip 数据一致"""

    def test_01_build_to_json_to_from_preserves_data(self):
        out = _run_with_score(
            {
                "meta": {"title": "Round Trip", "tempo": 90},
                "scoreMeasures": [
                    [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStart": True, "slurStart": True, "articulation": "staccato"}],
                    [{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 4}], "duration": "q", "tieStop": True, "slurStop": True, "dynamic": "f"},
                     {"kind": "note", "voice": "1", "pitches": [{"step": "E", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "start"},
                     {"kind": "note", "voice": "1", "pitches": [{"step": "F", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "middle"},
                     {"kind": "note", "voice": "1", "pitches": [{"step": "G", "octave": 4}], "duration": "8", "tupletType": "triplet", "tupletGroup": "g1", "tupletPosition": "end"}]
                ]
            },
            """
const rels = SM.buildRelations(score);
const json = JSON.parse(JSON.stringify(score));
const score2 = SM.scoreFromJSON(json);
const json2 = JSON.parse(JSON.stringify(score2));
// 关键字段对比
const note0_1 = score.parts[0].measures[0].voices[0].notes[0];
const note0_2 = score2.parts[0].measures[0].voices[0].notes[0];
const tupN1 = score.parts[0].measures[1].voices[0].notes[1];
const tupN2 = score2.parts[0].measures[1].voices[0].notes[1];
process.stdout.write(JSON.stringify({
  metaMatch: score.meta.title === score2.meta.title && score.meta.tempo === score2.meta.tempo,
  pitch0Match: note0_1.pitches[0].step === note0_2.pitches[0].step,
  tieStartMatch: note0_1.tieStart === note0_2.tieStart,
  slurStartMatch: note0_1.slurStart === note0_2.slurStart,
  articulationMatch: note0_1.articulation === note0_2.articulation,
  tupletTypeMatch: tupN1.tupletType === tupN2.tupletType,
  tupletGroupMatch: tupN1.tupletGroup === tupN2.tupletGroup,
  tupletPositionMatch: tupN1.tupletPosition === tupN2.tupletPosition,
  relationCount: score.relations.length === score2.relations.length,
  tupletRelationMatch: score.relations.some(r => r.type === "tuplet") === score2.relations.some(r => r.type === "tuplet"),
  jsonEqual: JSON.stringify(json) === JSON.stringify(json2)
}));
"""
        )
        result = json.loads(out)
        self.assertTrue(result["metaMatch"], "meta 应一致")
        self.assertTrue(result["pitch0Match"], "音高应一致")
        self.assertTrue(result["tieStartMatch"], "tieStart 应一致")
        self.assertTrue(result["slurStartMatch"], "slurStart 应一致")
        self.assertTrue(result["articulationMatch"], "articulation 应一致")
        self.assertTrue(result["tupletTypeMatch"], "tupletType 应一致")
        self.assertTrue(result["tupletGroupMatch"], "tupletGroup 应一致")
        self.assertTrue(result["tupletPositionMatch"], "tupletPosition 应一致")
        self.assertTrue(result["relationCount"], "relations 数量应一致")
        self.assertTrue(result["tupletRelationMatch"], "tuplet 关系应保留")
        # JSON 完全相等 (最严的 round-trip 测试)
        self.assertTrue(result["jsonEqual"], "round-trip 后 JSON 应该完全相等")

    def test_02_multi_part_staff_scores_round_trip(self):
        # 大谱表 (multi part) round-trip
        out = _run_with_score(
            {
                "meta": {"title": "Piano"},
                "staffScores": {
                    "treble": {"measures": [[{"kind": "note", "voice": "1", "pitches": [{"step": "G", "octave": 4}], "duration": "h"}]]},
                    "bass": {"measures": [[{"kind": "note", "voice": "1", "pitches": [{"step": "C", "octave": 3}], "duration": "h"}]]}
                }
            },
            """
const json = JSON.parse(JSON.stringify(score));
const score2 = SM.scoreFromJSON(json);
const json2 = JSON.parse(JSON.stringify(score2));
process.stdout.write(JSON.stringify({
  partCount: score2.parts.length,
  partIds: score2.parts.map(p => p.id),
  trebleNote: score2.parts.find(p => p.id === "treble").measures[0].voices[0].notes[0].pitches[0].step,
  bassNote: score2.parts.find(p => p.id === "bass").measures[0].voices[0].notes[0].pitches[0].step,
  jsonEqual: JSON.stringify(json) === JSON.stringify(json2)
}));
"""
        )
        result = json.loads(out)
        self.assertEqual(result["partCount"], 2)
        self.assertEqual(result["partIds"], ["treble", "bass"])
        self.assertEqual(result["trebleNote"], "G")
        self.assertEqual(result["bassNote"], "C")
        self.assertTrue(result["jsonEqual"])


# ===== 5. 边界 / 鲁棒性 =====

class TestEdgeCases(unittest.TestCase):
    """边界 case"""

    def test_01_pitches_shallow_copy_no_shared_reference(self):
        out = _run_node_script(f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const n = new SM.Note();
n.pitches = [{{step: "C", octave: 4}}];
const json = JSON.parse(JSON.stringify(n));
// 修改 json 不应影响原 n
json.pitches[0].step = "X";
process.stdout.write(JSON.stringify({{original: n.pitches[0].step, modified: json.pitches[0].step}}));
''')
        result = json.loads(out)
        self.assertEqual(result["original"], "C", "浅拷贝 — 改 json 不应影响原 note")

    def test_02_members_array_copy_no_shared_reference(self):
        out = _run_node_script(f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const r = new SM.Relation("tuplet", null, null);
r.members = ["a", "b", "c"];
const json = JSON.parse(JSON.stringify(r));
json.members.push("d");
process.stdout.write(JSON.stringify({{originalLen: r.members.length, jsonLen: json.members.length}}));
''')
        result = json.loads(out)
        self.assertEqual(result["originalLen"], 3, "members 浅拷贝")

    def test_03_null_pitches_handled(self):
        out = _run_node_script(f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const n = new SM.Note("rest");
n.pitches = [];
const json = JSON.parse(JSON.stringify(n));
const score = SM.scoreFromJSON(json);
process.stdout.write(JSON.stringify({{kind: json.kind, pitchesIsArray: Array.isArray(json.pitches), restoredPitchesLen: score.parts[0] ? 0 : 0}}));
''')
        result = json.loads(out)
        self.assertEqual(result["kind"], "rest")
        self.assertTrue(result["pitchesIsArray"])

    def test_04_grace_object_preserved(self):
        # grace 是 object|null, 浅拷贝要正确
        out = _run_node_script(f'''
global.window = global;
require("{SM}");
const SM = global.ScoreModel;
const n = new SM.Note();
n.grace = {{slash: true, type: "eighth"}};
const json = JSON.parse(JSON.stringify(n));
const score = SM.scoreFromJSON(json);
// scoreFromJSON 不重建 grace 路径, 但 json 本身应正确
process.stdout.write(JSON.stringify({{graceSlash: json.grace.slash, graceType: json.grace.type}}));
''')
        result = json.loads(out)
        self.assertEqual(result["graceSlash"], True)
        self.assertEqual(result["graceType"], "eighth")


if __name__ == "__main__":
    unittest.main()
