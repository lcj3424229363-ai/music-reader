/**
 * P22.5-B.3 — Score Model 数据契约 (Note 重命名版)
 *
 * 设计: docs/P22.5-B_schemadef.md
 * 决策: docs/P22.5-B_inventory.md (1A 2A 3A 4B 5B) + B.3 摸底
 *
 * B.3 改动 (2026-08-14):
 *   - Entry class → Note class (Note 更准: 包含 note/rest 抽象)
 *   - 局部变量 entry → note
 *   - Note 加 3 tuplet 字段 (tupletType/tupletGroup/tupletPosition)
 *   - legacyEntryToEntry → legacyToNote, 补 tuplet 3 字段
 *   - buildRelations 通用化: tie/slur/phrase/tuplet 全扫
 *   - validateRelations: slur cross-voice warning, tuplet members count 跟 actual
 *   - syncEntryFromRelation: slur/phrase 分支, tuplet 不接 (避免循环)
 *   - Relation.members 顶层字段 (B.3 决策 3)
 *   - tuplet payload: {actual, normal} (B.3 决策 3)
 *
 * 6 个 class + 1 个 factory:
 *   - Score: 顶层谱面 (parts + relations)
 *   - Part: 谱面部件 (大谱表多 part, 单谱表 1 part)
 *   - Measure: 小节 (per voice 决策)
 *   - Voice: 声部
 *   - Note: 音符/休止符 (18 修饰符 + 3 tuplet 字段, A.4 + B.3 落地)
 *   - Relation: 跨 measure 关系 (tie/slur/phrase/tuplet)
 *
 * 影子模式 (决策 4): 老 `scoreMeasures` 仍真数据, Score Model 是 view/serialization
 * 半隔离 (决策 5): 字段名沿用 VexFlow 习惯, Renderer 翻译留给 P22.6
 */
(function (root) {
  "use strict";

  // ===== 1. Note (B.3: 原 Entry 重命名) =====
  class Note {
    constructor(kind = "note") {
      this.id = "";
      this.kind = kind;               // "note" | "rest" | "placeholder" | "chord" | "grace"
      this.voice = "1";               // 冗余 (Voice.id 已存), 兼容老代码
      this.pitches = [];              // Pitch[] (kind=note) | [] (kind=rest)
      this.duration = "q";
      this.dotted = false;
      this.units = 8;                 // 1 quarter = 8 (决策 3)

      // 18 修饰符字段 (P22.5-Symbol A.4 落地)
      this.articulation = "";
      this.fingering = "";
      this.textMark = "";
      this.ornament = "";
      this.fermata = false;
      this.grace = null;
      this.dynamic = "";
      this.pedal = "";
      this.breath = false;
      this.tieStart = false;
      this.tieStop = false;
      this.slurStart = false;
      this.slurStop = false;
      this.phraseStart = false;
      this.phraseStop = false;
      this.hairpin = "";
      this.chordSymbol = "";
      this.arpeggiate = false;
      this.volta = null;
      this.rehearsalMark = "";

      // 3 tuplet 字段 (B.3 落地, 之前 B.1 漏)
      // tuplet 是 group-based: groupId 串接多 entry, position 决定 start/middle/end
      this.tupletType = "";           // "" | "triplet" | "quintuplet" | "sextuplet"
      this.tupletGroup = "";          // groupId, 串接同组
      this.tupletPosition = "";       // "" | "start" | "middle" | "end"
    }

    // B.4: toJSON — JSON.stringify(note) 自动调
    // 返回 plain object, 包含 18 修饰符 + 3 tuplet 字段 + 基础字段
    toJSON() {
      return {
        id: this.id,
        kind: this.kind,
        voice: this.voice,
        pitches: Array.isArray(this.pitches) ? this.pitches.map((p) => Object.assign({}, p)) : [],
        duration: this.duration,
        dotted: this.dotted,
        units: this.units,
        articulation: this.articulation,
        fingering: this.fingering,
        textMark: this.textMark,
        ornament: this.ornament,
        fermata: this.fermata,
        grace: this.grace ? Object.assign({}, this.grace) : null,
        dynamic: this.dynamic,
        pedal: this.pedal,
        breath: this.breath,
        tieStart: this.tieStart,
        tieStop: this.tieStop,
        slurStart: this.slurStart,
        slurStop: this.slurStop,
        phraseStart: this.phraseStart,
        phraseStop: this.phraseStop,
        hairpin: this.hairpin,
        chordSymbol: this.chordSymbol,
        arpeggiate: this.arpeggiate,
        volta: this.volta,
        rehearsalMark: this.rehearsalMark,
        tupletType: this.tupletType,
        tupletGroup: this.tupletGroup,
        tupletPosition: this.tupletPosition
      };
    }
  }

  // ===== 2. Voice =====
  class Voice {
    constructor(id, role = "primary") {
      this.id = id;                   // "1" | "2"
      this.role = role;               // "primary" | "secondary" | "bass"
      this.notes = [];                // B.3: notes (原 entries, 重命名)
    }

    // B.4: toJSON
    toJSON() {
      return {
        id: this.id,
        role: this.role,
        notes: this.notes.map((n) => n ? n.toJSON() : null)
      };
    }
  }

  // ===== 3. Measure =====
  class Measure {
    constructor(index, timeSignature = "4/4") {
      this.index = index;
      this.number = index + 1;
      this.timeSignature = timeSignature;
      this.beginBarline = "single";
      this.endBarline = "single";
      this.voices = [];
      this.tempo = null;
      this.directions = [];
      this.volta = null;              // A.4 字段
      this.rehearsalMark = "";        // A.4 字段
    }

    // B.4: toJSON
    toJSON() {
      return {
        index: this.index,
        number: this.number,
        timeSignature: this.timeSignature,
        beginBarline: this.beginBarline,
        endBarline: this.endBarline,
        voices: this.voices.map((v) => v.toJSON()),
        tempo: this.tempo,
        directions: Array.isArray(this.directions) ? this.directions.slice() : [],
        volta: this.volta,
        rehearsalMark: this.rehearsalMark
      };
    }
  }

  // ===== 4. Part =====
  class Part {
    constructor(id, name, instrument = "piano") {
      this.id = id;                   // "treble" | "bass" | "soprano"
      this.name = name;
      this.instrument = instrument;
      this.staves = [];               // 通常 1 个 (P22.7 大谱表扩展)
      this.measures = [];             // Measure[]
    }

    // B.4: toJSON
    toJSON() {
      return {
        id: this.id,
        name: this.name,
        instrument: this.instrument,
        staves: this.staves.slice(),
        measures: this.measures.map((m) => m.toJSON())
      };
    }
  }

  // ===== 5. Relation (跨 measure 关系) =====
  // B.3 扩展: 加 members 顶层字段 (tuplet 用)
  // tie/slur/phrase 用 from/to, tuplet 用 members (3/5/6 个 noteId)
  // payload 通用: type-specific 元数据 (tuplet 的 actual/normal)
  class Relation {
    constructor(type, fromId, toId) {
      this.id = "";
      this.type = type;               // "tie" | "slur" | "phrase" | "tuplet"
      this.from = fromId || null;     // tie/slur/phrase 用
      this.to = toId || null;         // tie/slur/phrase 用
      this.members = null;            // tuplet 用 (noteId[])
      this.payload = {};              // tuplet: {actual, normal}; 其他类型 {}
    }

    // B.4: toJSON
    toJSON() {
      return {
        id: this.id,
        type: this.type,
        from: this.from,
        to: this.to,
        members: Array.isArray(this.members) ? this.members.slice() : null,
        payload: this.payload ? Object.assign({}, this.payload) : {}
      };
    }
  }

  // ===== 6. Score =====
  class Score {
    constructor() {
      this.meta = {
        title: "",
        composer: "",
        tempo: 120,
        anacrusis: false
      };
      this.parts = [];
      this.relations = [];
    }

    addPart(part) {
      if (!(part instanceof Part)) {
        throw new TypeError("addPart requires a Part instance");
      }
      this.parts.push(part);
      return this;
    }

    getPart(partId) {
      return this.parts.find((p) => p.id === partId) || null;
    }

    getMeasure(partId, measureIndex) {
      const part = this.getPart(partId);
      if (!part) return null;
      return part.measures[measureIndex] || null;
    }

    addRelation(relation) {
      if (!(relation instanceof Relation)) {
        throw new TypeError("addRelation requires a Relation instance");
      }
      this.relations.push(relation);
      return this;
    }

    getRelationsByType(type) {
      return this.relations.filter((r) => r.type === type);
    }

    // B.4: toJSON
    toJSON() {
      return {
        meta: Object.assign({}, this.meta),
        parts: this.parts.map((p) => p.toJSON()),
        relations: this.relations.map((r) => r.toJSON())
      };
    }
  }

  // ===== 7. Factory: buildScore(legacyState) =====
  /**
   * 把老 {scoreMeasures, staffScores, ...} 转成 Score Model
   * @param {Object} legacyState - 老数据结构
   *   - scoreMeasures: Array<Array<note>>  单谱表
   *   - staffScores: { treble: { measures: Array<Array<note>> }, bass: ... }  大谱表
   *   - meta: { title, composer, tempo, anacrusis }  可选
   * @returns {Score}
   */
  function buildScore(legacyState) {
    const score = new Score();
    if (legacyState.meta) {
      Object.assign(score.meta, legacyState.meta);
    }

    // 1) 优先用 staffScores (大谱表模式) — 多 part
    if (legacyState.staffScores && typeof legacyState.staffScores === "object") {
      const staffNames = Object.keys(legacyState.staffScores);
      staffNames.forEach((staffName) => {
        const staffState = legacyState.staffScores[staffName];
        if (!staffState || !Array.isArray(staffState.measures)) return;
        const part = new Part(staffName, staffName, "piano");
        const measureCount = staffState.measures.length;
        for (let i = 0; i < measureCount; i += 1) {
          const legacyNotes = staffState.measures[i] || [];
          const measure = new Measure(i, "4/4");
          const voiceMap = new Map();
          legacyNotes.forEach((legacyNote) => {
            if (!legacyNote || !legacyNote.kind) return;
            const vid = String(legacyNote.voice || "1");
            let voice = voiceMap.get(vid);
            if (!voice) {
              voice = new Voice(vid, vid === "1" ? "primary" : "secondary");
              voiceMap.set(vid, voice);
            }
            const note = legacyToNote(legacyNote, vid, part.id, i, voiceMap.get(vid).notes.length);
            voice.notes.push(note);
          });
          measure.voices = Array.from(voiceMap.values());
          if (staffState.settings && staffState.settings[i]) {
            const s = staffState.settings[i];
            if (s.beginBarline) measure.beginBarline = s.beginBarline;
            if (s.endBarline) measure.endBarline = s.endBarline;
          }
          part.measures.push(measure);
        }
        score.addPart(part);
      });
    }

    // 2) 否则用 scoreMeasures (单谱表模式) — 1 part
    if (score.parts.length === 0 && Array.isArray(legacyState.scoreMeasures)) {
      const part = new Part("default", "default", "piano");
      legacyState.scoreMeasures.forEach((legacyNotes, i) => {
        const measure = new Measure(i, "4/4");
        if (!Array.isArray(legacyNotes)) {
          part.measures.push(measure);
          return;
        }
        const voiceMap = new Map();
        legacyNotes.forEach((legacyNote) => {
          if (!legacyNote || !legacyNote.kind) return;
          const vid = String(legacyNote.voice || "1");
          let voice = voiceMap.get(vid);
          if (!voice) {
            voice = new Voice(vid, vid === "1" ? "primary" : "secondary");
            voiceMap.set(vid, voice);
          }
          const note = legacyToNote(legacyNote, vid, part.id, i, voiceMap.get(vid).notes.length);
          voice.notes.push(note);
        });
        measure.voices = Array.from(voiceMap.values());
        part.measures.push(measure);
      });
      score.addPart(part);
    }

    return score;
  }

  // ===== helper: legacy entry → Note (B.3: 加 tuplet 3 字段) =====
  function legacyToNote(legacy, voiceId, partId, measureIndex, noteIndex) {
    const note = new Note(legacy.kind || "note");
    note.id = `p${partId}m${measureIndex}v${voiceId}e${noteIndex}`;
    note.voice = voiceId;
    if (Array.isArray(legacy.pitches)) {
      note.pitches = legacy.pitches.map((p) => Object.assign({}, p));
    }
    note.duration = legacy.duration || "q";
    note.dotted = Boolean(legacy.dotted);
    note.units = Number.isFinite(legacy.units) ? legacy.units : 8;

    // 18 修饰符字段
    const fields = [
      "articulation", "fingering", "textMark", "ornament", "fermata",
      "grace", "dynamic", "pedal", "breath",
      "tieStart", "tieStop", "slurStart", "slurStop",
      "phraseStart", "phraseStop", "hairpin",
      "chordSymbol", "arpeggiate", "volta", "rehearsalMark"
    ];
    fields.forEach((k) => {
      if (k in legacy) note[k] = legacy[k];
    });

    // 3 tuplet 字段 (B.3 补 — 之前 B.1 漏)
    if ("tupletType" in legacy) note.tupletType = legacy.tupletType;
    if ("tupletGroup" in legacy) note.tupletGroup = legacy.tupletGroup;
    if ("tupletPosition" in legacy) note.tupletPosition = legacy.tupletPosition;

    return note;
  }

  // ===== 8. buildLegacyFromScore (B.2) =====
  // 反向: Score → {scoreMeasures, staffScores, meta}
  function buildLegacyFromScore(score) {
    if (!(score instanceof Score)) {
      throw new TypeError("buildLegacyFromScore requires a Score instance");
    }
    const legacy = { meta: Object.assign({}, score.meta) };
    if (score.parts.length === 0) return legacy;

    if (score.parts.length === 1) {
      const part = score.parts[0];
      legacy.scoreMeasures = part.measures.map(measureToLegacyNotes);
    } else {
      legacy.staffScores = {};
      score.parts.forEach((part) => {
        legacy.staffScores[part.id] = {
          measures: part.measures.map(measureToLegacyNotes)
        };
      });
    }
    return legacy;
  }

  // measure → 合并所有 voice 的 notes
  function measureToLegacyNotes(measure) {
    const notes = [];
    measure.voices.forEach((voice) => {
      voice.notes.forEach((note) => {
        if (note) notes.push(noteToLegacyNote(note));
      });
    });
    return notes;
  }

  // note → legacy: 剥 _ 前缀字段
  function noteToLegacyNote(note) {
    const legacy = {};
    const skipKeys = new Set(["_globalIndex", "_measureIndex", "_localIndex", "_voiceId", "_staffId"]);
    for (const k in note) {
      if (!skipKeys.has(k) && note[k] !== undefined) {
        legacy[k] = note[k];
      }
    }
    return legacy;
  }

  // ===== 9. buildRelations (B.3 通用化) =====
  // 扫描 Score 里所有 entry 标记, 生成 Relation 对象
  // types: ["tie", "slur", "phrase", "tuplet"] — 默认全做
  // B.3 改动:
  //   - tie: tieStart → tieStop (B.2 有)
  //   - slur: slurStart → slurStop (新)
  //   - phrase: phraseStart → phraseStop (新)
  //   - tuplet: 按 tupletGroup 聚合 → 1 个 Relation (members + payload{actual, normal})
  function buildRelations(score, types) {
    if (!(score instanceof Score)) {
      throw new TypeError("buildRelations requires a Score instance");
    }
    // types=undefined → 默认全扫; types=[] → 空扫 (啥都不生); types=['tie'] → 只 tie
    const wantedTypes = Array.isArray(types)
      ? types
      : ["tie", "slur", "phrase", "tuplet"];

    // 1) 建 note 索引
    const noteIndex = new Map();
    score.parts.forEach((part) => {
      part.measures.forEach((measure) => {
        measure.voices.forEach((voice) => {
          voice.notes.forEach((note) => {
            if (note && note.id) noteIndex.set(note.id, note);
          });
        });
      });
    });

    const newRelations = [];
    let relIndex = score.relations ? score.relations.length : 0;

    // 2) tie: 跟 B.2 一致, 跨 measure 找 tieStop
    if (wantedTypes.indexOf("tie") !== -1) {
      const tieStarts = collectMarkerStarts(score, "tieStart");
      tieStarts.forEach((start) => {
        const stop = findNextMarkerStop(score, start, "tieStop");
        if (stop) {
          const rel = new Relation("tie", start.note.id, stop.note.id);
          rel.id = `r${relIndex++}`;
          newRelations.push(rel);
        }
      });
    }

    // 3) slur: 跟 tie 同, 但允许跨 voice (B.3 决策 4)
    if (wantedTypes.indexOf("slur") !== -1) {
      const slurStarts = collectMarkerStarts(score, "slurStart");
      slurStarts.forEach((start) => {
        const stop = findNextMarkerStop(score, start, "slurStop", { crossVoice: true });
        if (stop) {
          const rel = new Relation("slur", start.note.id, stop.note.id);
          rel.id = `r${relIndex++}`;
          newRelations.push(rel);
        }
      });
    }

    // 4) phrase: 跟 slur 同, 允许跨 voice (B.3 决策 5)
    if (wantedTypes.indexOf("phrase") !== -1) {
      const phraseStarts = collectMarkerStarts(score, "phraseStart");
      phraseStarts.forEach((start) => {
        const stop = findNextMarkerStop(score, start, "phraseStop", { crossVoice: true });
        if (stop) {
          const rel = new Relation("phrase", start.note.id, stop.note.id);
          rel.id = `r${relIndex++}`;
          newRelations.push(rel);
        }
      });
    }

    // 5) tuplet: 按 groupId 聚合, 1 group 1 Relation (B.3 决策 3)
    //    payload: {actual, normal} — 跟 MusicXML time-modification 对齐
    //    members: 顶层数组 (B.3 决策 3: 不要叫 entryIds, 不要放 payload)
    if (wantedTypes.indexOf("tuplet") !== -1) {
      const tupletGroups = collectTupletGroups(score);
      tupletGroups.forEach((groupNotes) => {
        if (groupNotes.length < 2) return;
        const rel = new Relation("tuplet", null, null);
        rel.id = `r${relIndex++}`;
        rel.members = groupNotes.map((n) => n.id);
        const firstType = groupNotes[0].tupletType;
        const ratio = tupletRatioMap[firstType];
        if (ratio) {
          rel.payload = { actual: ratio.totalNotes, normal: ratio.notesOccupied };
        } else {
          rel.payload = { actual: groupNotes.length, normal: groupNotes.length };
        }
        newRelations.push(rel);
      });
    }

    score.relations = newRelations;
    return newRelations;
  }

  // 收集某个 marker (tieStart/slurStart/phraseStart) 的所有 note
  // 返回 [{note, voiceId, partId, partIndex, measureIndex, entryIndex}, ...]
  function collectMarkerStarts(score, markerField) {
    const starts = [];
    score.parts.forEach((part, partIndex) => {
      part.measures.forEach((measure, mIndex) => {
        measure.voices.forEach((voice, vIndex) => {
          voice.notes.forEach((note, nIndex) => {
            if (note && note[markerField]) {
              starts.push({
                note, voiceId: voice.id, partId: part.id,
                partIndex, measureIndex: mIndex, voiceIndex: vIndex, entryIndex: nIndex
              });
            }
          });
        });
      });
    });
    return starts;
  }

  // 找后续同 part 后续 measure/voice 第一个 marker stop
  // options.crossVoice: 允许跨 voice (slur/phrase 用)
  function findNextMarkerStop(score, start, stopField, options) {
    options = options || {};
    const part = score.parts[start.partIndex];
    if (!part) return null;
    for (let m = start.measureIndex; m < part.measures.length; m += 1) {
      const measure = part.measures[m];
      for (let v = 0; v < measure.voices.length; v += 1) {
        if (!options.crossVoice && measure.voices[v].id !== start.voiceId) continue;
        // crossVoice 模式: 也扫同 voice 之外 (从 voice 0 开始重置)
        const voice = measure.voices[v];
        const startE = (m === start.measureIndex && (!options.crossVoice || voice.id === start.voiceId))
          ? start.entryIndex + 1
          : 0;
        for (let e = startE; e < voice.notes.length; e += 1) {
          const note = voice.notes[e];
          if (!note) continue;
          if (note[stopField]) {
            return {
              note, partIndex: start.partIndex, measureIndex: m,
              voiceId: voice.id, entryIndex: e
            };
          }
        }
      }
    }
    return null;
  }

  // 收集所有 tuplet group, 按 tupletGroup 串接
  // 返回 [[note1, note2, ...], ...] — 每个内部数组是 1 个 group, 按 part/measure/voice 顺序排
  // B.3 决策 6: builder 暂只扫同 measure (跨 measure 留 B.4)
  function collectTupletGroups(score) {
    const groupMap = new Map();
    score.parts.forEach((part, partIndex) => {
      part.measures.forEach((measure, mIndex) => {
        measure.voices.forEach((voice) => {
          voice.notes.forEach((note) => {
            if (!note || !note.tupletGroup) return;
            if (!groupMap.has(note.tupletGroup)) {
              groupMap.set(note.tupletGroup, {
                groupId: note.tupletGroup,
                partIndex, measureIndex: mIndex,
                voiceId: voice.id,
                notes: []
              });
            }
            groupMap.get(note.tupletGroup).notes.push(note);
          });
        });
      });
    });
    // 转数组, 按 group 的 measureIndex 排
    const groups = Array.from(groupMap.values());
    groups.sort((a, b) => {
      if (a.partIndex !== b.partIndex) return a.partIndex - b.partIndex;
      return a.measureIndex - b.measureIndex;
    });
    return groups.map((g) => g.notes);
  }

  // tuplet type → {actual, normal}
  // 跟 app.js L119 tupletRatios 对齐
  const tupletRatioMap = Object.freeze({
    triplet: { totalNotes: 3, notesOccupied: 2 },
    quintuplet: { totalNotes: 5, notesOccupied: 4 },
    sextuplet: { totalNotes: 6, notesOccupied: 4 }
  });

  // ===== 10. validateRelations (B.3 扩) =====
  // 验证 Score Model 关系一致性
  // 返回 {valid: bool, errors: [], warnings: []}
  // B.3 改动:
  //   - errors: 硬错 (from/to 找不到, tie 不同 pitch, tuplet members.length 跟 actual 不一致)
  //   - warnings: 软提示 (slur 跨 voice — 不禁止, 但提示)
  function validateRelations(score) {
    if (!(score instanceof Score)) {
      throw new TypeError("validateRelations requires a Score instance");
    }
    const errors = [];
    const warnings = [];
    const noteIndex = new Map();
    const noteLocation = new Map();
    score.parts.forEach((part, partIndex) => {
      part.measures.forEach((measure, mIndex) => {
        measure.voices.forEach((voice) => {
          voice.notes.forEach((note) => {
            if (note && note.id) {
              noteIndex.set(note.id, note);
              noteLocation.set(note.id, { partId: part.id, voiceId: voice.id });
            }
          });
        });
      });
    });
    score.relations.forEach((rel) => {
      if (rel.type === "tie" || rel.type === "slur" || rel.type === "phrase") {
        const fromNote = noteIndex.get(rel.from);
        const toNote = noteIndex.get(rel.to);
        if (!fromNote) errors.push(`Relation ${rel.id}: from note ${rel.from} not found`);
        if (!toNote) errors.push(`Relation ${rel.id}: to note ${rel.to} not found`);
        if (!fromNote || !toNote) return;

        if (rel.type === "tie") {
          // tie 必须同音高
          const fromPitches = new Set((fromNote.pitches || []).map(pitchIdentity));
          const shared = (toNote.pitches || []).some((p) => fromPitches.has(pitchIdentity(p)));
          if (!shared) {
            errors.push(`Relation ${rel.id}: tie from/to pitches don't share`);
          }
          // tie 不允许跨 voice
          const fromLoc = noteLocation.get(rel.from);
          const toLoc = noteLocation.get(rel.to);
          if (fromLoc && toLoc && fromLoc.voiceId !== toLoc.voiceId) {
            errors.push(`Relation ${rel.id}: tie cannot cross voice`);
          }
        } else if (rel.type === "slur") {
          // slur 跨 voice 是 warning, 不 error
          const fromLoc = noteLocation.get(rel.from);
          const toLoc = noteLocation.get(rel.to);
          if (fromLoc && toLoc && fromLoc.voiceId !== toLoc.voiceId) {
            warnings.push(`Relation ${rel.id}: slur cross-voice (${fromLoc.voiceId} -> ${toLoc.voiceId})`);
          }
        }
        // phrase: 不校验音高不校验 voice
      } else if (rel.type === "tuplet") {
        // tuplet 用 members
        if (!Array.isArray(rel.members) || rel.members.length < 2) {
          errors.push(`Relation ${rel.id}: tuplet must have at least 2 members`);
          return;
        }
        const actual = rel.payload && Number.isFinite(rel.payload.actual) ? rel.payload.actual : null;
        if (actual && rel.members.length !== actual) {
          errors.push(`Relation ${rel.id}: tuplet members.length (${rel.members.length}) != actual (${actual})`);
        }
        // 所有 members 必须存在
        rel.members.forEach((mid) => {
          if (!noteIndex.has(mid)) {
            errors.push(`Relation ${rel.id}: tuplet member ${mid} not found`);
          }
        });
        // 同 part 同 voice (跨 voice tuplet 不允许)
        const memberLocs = rel.members.map((mid) => noteLocation.get(mid)).filter(Boolean);
        if (memberLocs.length > 1) {
          const firstLoc = memberLocs[0];
          const allSameVoice = memberLocs.every((loc) => loc.voiceId === firstLoc.voiceId);
          if (!allSameVoice) {
            errors.push(`Relation ${rel.id}: tuplet cannot cross voice`);
          }
        }
      }
    });
    return { valid: errors.length === 0, errors, warnings };
  }

  // pitch 唯一标识: step+accidental+octave
  function pitchIdentity(p) {
    if (!p) return "";
    return `${p.step || ""}${p.accidental || ""}/${p.octave || ""}`;
  }

  // ===== 11. syncEntryFromRelation (B.3 扩) =====
  // 根据 Relation 对象, 反向更新 note 标记
  // B.3 改动: 加 slur/phrase 分支, tuplet 不接 (避免循环)
  function syncEntryFromRelation(score, rel) {
    if (!(rel instanceof Relation)) {
      throw new TypeError("syncEntryFromRelation requires a Relation instance");
    }
    const noteIndex = new Map();
    score.parts.forEach((part) => {
      part.measures.forEach((measure) => {
        measure.voices.forEach((voice) => {
          voice.notes.forEach((note) => {
            if (note && note.id) noteIndex.set(note.id, note);
          });
        });
      });
    });
    if (rel.type === "tuplet") {
      // tuplet 不接 sync, 业务侧管 (group 复杂, 容易循环)
      return false;
    }
    const fromNote = noteIndex.get(rel.from);
    const toNote = noteIndex.get(rel.to);
    if (!fromNote || !toNote) return false;
    if (rel.type === "tie") {
      fromNote.tieStart = true;
      toNote.tieStop = true;
    } else if (rel.type === "slur") {
      fromNote.slurStart = true;
      toNote.slurStop = true;
    } else if (rel.type === "phrase") {
      fromNote.phraseStart = true;
      toNote.phraseStop = true;
    }
    return true;
  }

  // ===== 12. scoreFromJSON (B.4 反序列化 helper) =====
  // 接受 {meta, parts, relations} 形状, 还原成 Score instance
  // 不接受 schemaVersion 包装 (B.4 范围: 裸对象, 留给 P22.6 持久化)
  // 不接 (B.4 不做): {schema: "score-v1", version, data} — 留给 schema 阶段
  function scoreFromJSON(json) {
    if (!json || typeof json !== "object") {
      throw new TypeError("scoreFromJSON requires a plain object");
    }
    const score = new Score();
    if (json.meta && typeof json.meta === "object") {
      Object.assign(score.meta, json.meta);
    }
    if (Array.isArray(json.parts)) {
      json.parts.forEach((pJson) => {
        if (!pJson || typeof pJson !== "object") return;
        const part = new Part(pJson.id || "default", pJson.name || pJson.id || "default", pJson.instrument || "piano");
        if (Array.isArray(pJson.measures)) {
          pJson.measures.forEach((mJson) => {
            const measure = new Measure(
              Number.isFinite(mJson.index) ? mJson.index : part.measures.length,
              mJson.timeSignature || "4/4"
            );
            if (Number.isFinite(mJson.number)) measure.number = mJson.number;
            if (mJson.beginBarline) measure.beginBarline = mJson.beginBarline;
            if (mJson.endBarline) measure.endBarline = mJson.endBarline;
            if (mJson.tempo != null) measure.tempo = mJson.tempo;
            if (Array.isArray(mJson.directions)) measure.directions = mJson.directions.slice();
            if (mJson.volta != null) measure.volta = mJson.volta;
            if (mJson.rehearsalMark) measure.rehearsalMark = mJson.rehearsalMark;
            if (Array.isArray(mJson.voices)) {
              mJson.voices.forEach((vJson) => {
                if (!vJson || typeof vJson !== "object") return;
                const voice = new Voice(vJson.id || "1", vJson.role || "primary");
                if (Array.isArray(vJson.notes)) {
                  vJson.notes.forEach((nJson) => {
                    if (!nJson || typeof nJson !== "object") return;
                    voice.notes.push(noteFromJSON(nJson));
                  });
                }
                measure.voices.push(voice);
              });
            }
            part.measures.push(measure);
          });
        }
        score.addPart(part);
      });
    }
    if (Array.isArray(json.relations)) {
      json.relations.forEach((rJson) => {
        if (!rJson || typeof rJson !== "object") return;
        const rel = new Relation(rJson.type, rJson.from || null, rJson.to || null);
        rel.id = rJson.id || "";
        if (Array.isArray(rJson.members)) rel.members = rJson.members.slice();
        else rel.members = null;
        rel.payload = (rJson.payload && typeof rJson.payload === "object") ? Object.assign({}, rJson.payload) : {};
        score.addRelation(rel);
      });
    }
    return score;
  }

  // ===== helper: note plain → Note instance (B.4 private) =====
  function noteFromJSON(nJson) {
    const note = new Note(nJson.kind || "note");
    note.id = nJson.id || "";
    note.voice = nJson.voice || "1";
    if (Array.isArray(nJson.pitches)) {
      note.pitches = nJson.pitches.map((p) => Object.assign({}, p));
    }
    note.duration = nJson.duration || "q";
    note.dotted = Boolean(nJson.dotted);
    note.units = Number.isFinite(nJson.units) ? nJson.units : 8;

    // 18 修饰符字段
    const fields = [
      "articulation", "fingering", "textMark", "ornament", "fermata",
      "grace", "dynamic", "pedal", "breath",
      "tieStart", "tieStop", "slurStart", "slurStop",
      "phraseStart", "phraseStop", "hairpin",
      "chordSymbol", "arpeggiate", "volta", "rehearsalMark"
    ];
    fields.forEach((k) => {
      if (k in nJson) note[k] = nJson[k];
    });

    // 3 tuplet 字段
    if ("tupletType" in nJson) note.tupletType = nJson.tupletType;
    if ("tupletGroup" in nJson) note.tupletGroup = nJson.tupletGroup;
    if ("tupletPosition" in nJson) note.tupletPosition = nJson.tupletPosition;

    return note;
  }

  // ===== 暴露到全局 =====
  // B.3: Entry → Note 重命名
  // B.4: 加 scoreFromJSON
  const api = {
    Score,
    Part,
    Measure,
    Voice,
    Note,           // B.3: 原 Entry
    Relation,
    buildScore,
    buildLegacyFromScore,
    buildRelations,
    validateRelations,
    syncEntryFromRelation,
    scoreFromJSON   // B.4
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.ScoreModel = api;
  }
})(typeof window !== "undefined" ? window : (typeof globalThis !== "undefined" ? globalThis : null));
