# Entry Schema — music-reader 数据契约

**目的**: 把前端编辑器 / 后端 solver / MusicXML 标准三者的数据形状统一，避免
"连接处"格式不对导致 roundtrip 丢东西。

**最后修改**: 2026-08-15 (P2.7+ v1.6 集成)

---

## 1. 整体数据流

```
[用户视角: 4 voice SATB 大谱表]
   ↓
[app.js editor: 2 staff × 2 voice, entry 格式]
   ↓ submitFourPartAnswer → collectScoreMeasuresForAnswer
[/solve-melody: melodyMeasures + bassMeasures (1 voice each)]
   ↓ editor_to_solver.appjs_measures_to_solver_melody/bass
[solver 内部: Note list, 1 voice at a time]
   ↓ solve_melody(key, ts, melody, bass=None)
[solver 输出: 4 voice complete SATB (Voicing + Chord per beat)]
   ↓ _solver_to_four_part_response
[fourPart JSON: voices[soprano/alto/tenor/bass].entries[]]
   ↓ applyFourPartAnswerToEditor
[app.js editor: 4 voice 套回原 staff]
```

```
[/read-score: MusicXML → reader.py events[]]
   ↓ (待加: reader_to_editor)
[app.js editor: entry 格式]
   ↗ 同上
```

---

## 2. 统一 Entry Shape

**所有 layer 共用这一个 entry 形状**：

```json
{
  "kind": "note",                          // "note" | "rest"
  "voice": "soprano",                      // SATB 名: "soprano" | "alto" | "tenor" | "bass"
                                           // editor UI 也接受 "1" | "2" (legacy, 映射见 §4)
  "pitches": [
    {
      "step": "C",                         // C D E F G A B (大写)
      "octave": 4,                         // 0-9
      "accidental": "",                    // "" | "#" | "b" (默认 "")
      "display": "C4"                      // 用于 UI 显示, 跟 step+octave 同步
    }
    // chord 时 pitches 多个, 单音时 1 个
  ],
  "duration": "4",                         // VexFlow code: "1"=whole "2"=half "4"=quarter "8"=eighth "16"=16th
  "dotted": 0,                             // 0|1|2 (number of dots)
  "units": 8                               // 1 unit = 1/16 of whole; quarter=8, half=16, whole=32
}
```

**rest 简化**:
```json
{
  "kind": "rest",
  "voice": "soprano",
  "duration": "4",
  "dotted": 0,
  "units": 8
  // pitches 字段省略
}
```

**约束**:
- `kind: "note"` 时 `pitches` 必须有 ≥1 个
- `pitches[].step` 始终大写
- `pitches[].display` 跟 `step+octave+accidental` 保持一致 (roundtrip 不漂移)
- `duration` 跟 `units` 必须一致 (duration="4" → units=8, duration="2" → units=16, ...)

---

## 3. Voice 命名

**4 声部标准名** (跟 SATB 教科书一致):

| voice | 中文 | 音域 | 谱表 |
|-------|------|------|------|
| `soprano` | 女高音 | C4-G5 | 高谱表 |
| `alto` | 女低音 | G3-D5 | 高谱表 |
| `tenor` | 男高音 | C3-A4 | 低谱表 |
| `bass` | 男低音 | E2-C4 | 低谱表 |

**Editor UI 内部 voice id 映射** (大谱表 2 voice 模式):

| editor voice | staff | SATB 名 |
|--------------|-------|---------|
| `"1"` | treble | soprano |
| `"2"` | treble | alto |
| `"1"` | bass | tenor |
| `"2"` | bass | bass |

**单声部模式** (单 staff 模式) — `voice` 字段忽略，只看 staff：
- treble staff → 默认 soprano
- bass staff → 默认 bass

---

## 4. 各 Layer 转换映射

### 4.1 app.js editor entry (内部, 用 voice="1"|"2")

```js
// UI 实际产生的 entry (legacy)
{
  kind: "note",
  voice: "1",  // 或 "2"
  pitches: [{step:"C", octave:4, accidental:"", display:"C4"}],
  duration: "4", dotted: 0, units: 8
}
```

→ 转换 (`collectScoreMeasuresForAnswer` + `editor_to_solver`):
- treble.voice="1" → 收集到 `melodyMeasures` (solver 当 soprano 处理)
- bass.voice="2" → 收集到 `bassMeasures` (solver 当 bass 处理, P8 模式)
- 其他 voice (treble.2 / bass.1) → 不送 solver (UI 内部声部, 用户在 SATB 模式不用)

### 4.2 /solve-melody 输入 (server 期望 voice="S/A/T/B" 名, 但当前实现是按 list 分)

```json
{
  "key": "C major",
  "timeSignature": "4/4",
  "questionType": "melody",  // 或 "bass"
  "melodyMeasures": [[entry, ...], ...],   // 1 voice (soprano)
  "bassMeasures": [[entry, ...], ...]      // 1 voice (bass), optional
}
```

注：solver 内部不读 `entry.voice` 字段 — 它按"哪个 list 在哪"判断声部。
melodyMeasures 给的全是 soprano，bassMeasures 给的全是 bass。

### 4.3 solver 内部 Note

```python
Note(step="C", octave=4, alter=0)  # alter: -1=bb, 0=natural, 1=#
# duration 用 quarter-fraction (1.0 = quarter, 0.5 = eighth, ...)
```

### 4.4 /solve-melody 输出 (fourPart JSON, voice 用 SATB 名)

```json
{
  "fourPart": {
    "voices": [
      {"id": "soprano", "name": "Soprano", "clef": "treble",
       "entries": [entry, ...],
       "measures": [{"number": 1, "entries": [entry, ...]}, ...]},
      {"id": "alto", ...},
      {"id": "tenor", ...},
      {"id": "bass", "clef": "bass", ...}
    ]
  }
}
```

→ 套用 (`applyFourPartAnswerToEditor`):
- soprano → treble.voice="1"
- alto    → treble.voice="2"
- tenor   → bass.voice="1"
- bass    → bass.voice="2"

### 4.5 /read-score 输出 (reader.py events)

```json
{
  "parts": [
    {
      "name": "Piano",
      "measures": [
        {
          "events": [
            {"type": "note", "offset": 0.0, "duration": 1.0, "pitch": "E5", "pitchClass": 4},
            {"type": "note", "offset": 1.0, "duration": 1.0, "pitch": "F5", "pitchClass": 5},
            // 同一拍 (offset 0) 不同 pitch → 实际是 2 voice 同时发声
            {"type": "note", "offset": 0.0, "duration": 1.0, "pitch": "A4", "pitchClass": 9}
          ]
        }
      ]
    }
  ]
}
```

→ 转换 (待加: `reader_to_editor.py`):
- 每 part 视为 1 个 staff
- 每 offset 内的 notes 按音高分 voice:
  - 最高音 → voice 1 (melody 候选)
  - 最低音 → voice 2 (bass 候选)
- 中音 → 暂 drop (不常见, 可后续扩展)
- 转 editor entry shape: `{kind, voice, pitches[], duration, dotted, units}`

---

## 5. 转换层一览 (5 道桥)

| # | 桥 | 入口 | 出口 | 状态 | 备注 |
|---|----|----|------|------|------|
| 1 | MusicXML 文件 → editor | `app.js parseMusicXmlText` (行 5149) | `loadParsedMusicXml` | ✅ 接好 (未测) | 走前端 DOMParser |
| 2 | `/read-score` → editor | server reader.py | `loadParsedMeasuresIntoEditor` | ❌ 缺 | 待加 `reader_to_editor.py` + app.js 调 |
| 3 | editor → `/solve-melody` | `collectScoreMeasuresForAnswer` (行 905+) | `melodyMeasures` + `bassMeasures` | ✅ 接好 | 已测 |
| 3b | editor entry → solver Note | `editor_to_solver.appjs_*` | solver.Note | ⚠️ 部分 | melody+bass 双 voice OK, 4 voice 缺 |
| 4 | fourPart → editor | `applyFourPartAnswerToEditor` (行 1668) | 4 staff × 2 voice | ✅ 接好 (未测 roundtrip) | roleTargets 映射对 |

---

## 6. 不变量 (Invariants)

**编辑 → 求解 → 套用 roundtrip 保持的不变量**:

1. **小节数一致**: 输入 N 小节, 输出也是 N 小节
2. **节拍一致**: 输入每小节总 units == 输出每小节总 units == 4/4 → 32
3. **声部映射唯一**: 输入 voice "X" 必映射到固定 SATB 名 (S/A/T/B 之一)
4. **音域不越界**: 输入音在 voice 音域内 (solver 也会 hard reject 越界)
5. **pitches[].display 跟 step+octave 一致**: roundtrip 不漂移
6. **kind 统一**: 输入输出都是 "note" | "rest" (solver 内部 chord 不暴露给 UI)
7. **duration/units 一致**: 跟 4/4 节拍对齐 (32 units = 1 whole)

---

## 7. 改造清单 (P2.7+ 集成)

按优先级:
- [ ] A. 把 schema 文档同步到 `app.js` 注释 (`collectScoreMeasuresForAnswer` 旁)
- [ ] B. `editor_to_solver` 加 `appjs_measures_to_solver_4voice` (4 voice 模式, 接受 voice S/A/T/B)
- [ ] C. 新增 `reader_to_editor.py` (`/read-score` 输出 → editor entry)
- [ ] D. `server.py` 调 `/read-score` 后自动灌入 editor (前端: 改 renderResult 或加新 callback)
- [ ] E. roundtrip 测试: ch4-01_a minor XML → editor → /solve-melody → 套回 editor → 跟 gold answer 对比

---

**关联文档**:
- `editor_to_solver.py:7-16` (P22 第一刀格式约定)
- `_solver_to_four_part_response` in `server.py:280+` (输出转换)
- `app.js:1668 applyFourPartAnswerToEditor` (套用)
- `app.js:5149 parseMusicXmlText` (MusicXML 文件导入)
- `score-model.js` P22.5 数据契约层 (Score/Part/Measure class, 备用)
