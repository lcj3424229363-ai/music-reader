// 双兜底查找：P18.8 重构后，ribbon 控件用 data-bridge="X" 而非 id="X"（避免和 inspector 同名 id 撞车）。
// 这里 findEl 先按 id 找（兼容老代码），找不到就按 data-bridge 找。
function findEl(id) {
  return document.getElementById(id) || document.querySelector(`[data-bridge="${id}"]`);
}

const apiStatus = findEl("apiStatus");
const readStatus = findEl("readStatus");
const fileInput = findEl("fileInput");
const pickButton = findEl("pickButton");
const dropZone = findEl("dropZone");
const summaryList = findEl("summaryList");
const measurePreview = findEl("measurePreview");
const harmonyPreview = findEl("harmonyPreview");
const warningList = findEl("warningList");
const manualButton = findEl("manualButton");
const manualKey = findEl("manualKey");
const manualTime = findEl("manualTime");
const manualProgression = findEl("manualProgression");
const noteButton = findEl("noteButton");
const examplePreset = findEl("examplePreset");
const keyChangesInput = findEl("keyChangesInput");
const staffMode = findEl("staffMode");
const noteClef = findEl("noteClef");
const voiceSelect = findEl("voiceSelect");
const editorTime = findEl("editorTime");
const editorKey = findEl("editorKey");
const noteMeasure = findEl("noteMeasure");
const noteInput = findEl("noteInput");
const noteCanvas = findEl("noteCanvas");
const scoreViewport = findEl("scoreViewport");
const noteDuration = findEl("noteDuration");
const noteAccidental = findEl("noteAccidental");
const noteDotted = findEl("noteDotted");
const undoNotesButton = findEl("undoNotesButton");
const clearNotesButton = findEl("clearNotesButton");
const measureStatus = findEl("measureStatus");
const measureProgress = findEl("measureProgress");
const editorMessage = findEl("editorMessage");
const selectionBar = findEl("selectionBar");
const selectedEventLabel = findEl("selectedEventLabel");
const selectedToneField = findEl("selectedToneField");
const selectedToneSelect = findEl("selectedToneSelect");
const dynamicField = findEl("dynamicField");
const dynamicSelect = findEl("dynamicSelect");
const chordField = findEl("chordField");
const chordSymbolInput = findEl("chordSymbolInput");
const articulationField = findEl("articulationField");
const articulationSelect = findEl("articulationSelect");
const ornamentField = findEl("ornamentField");
const ornamentSelect = findEl("ornamentSelect");
const tempoInput = findEl("tempoInput");
const anacrusisCheck = findEl("anacrusisCheck");
const graceField = findEl("graceField");
const graceInput = findEl("graceInput");
const pedalField = findEl("pedalField");
const pedalSelect = findEl("pedalSelect");
const hairpinField = findEl("hairpinField");
const hairpinSelect = findEl("hairpinSelect");
const fingeringField = findEl("fingeringField");
const fingeringInput = findEl("fingeringInput");
const arpeggioField = findEl("arpeggioField");
const arpeggioCheck = findEl("arpeggioCheck");
// P22.5-Symbol-A.4 — 曲式分析
const rehearsalMarkInput = findEl("rehearsalMarkInput");
const voltaSelect = findEl("voltaSelect");
const togglePhraseStartButton = findEl("togglePhraseStartButton");
const togglePhraseStopButton = findEl("togglePhraseStopButton");
const textMarkField = findEl("textMarkField");
const textMarkInput = findEl("textMarkInput");
const breathField = findEl("breathField");
const breathCheck = findEl("breathCheck");
const deleteToneButton = findEl("deleteToneButton");
const applyDurationButton = findEl("applyDurationButton");
const toggleTieStartButton = findEl("toggleTieStartButton");
const toggleTieStopButton = findEl("toggleTieStopButton");
const toggleSlurStartButton = findEl("toggleSlurStartButton");
const toggleSlurStopButton = findEl("toggleSlurStopButton");
const toggleFermataButton = findEl("toggleFermataButton");
const toggleTripletButton = findEl("toggleTripletButton");
const tupletTypeSelect = findEl("tupletTypeSelect");
const deleteEventButton = findEl("deleteEventButton");
const prevMeasureButton = findEl("prevMeasureButton");
const nextMeasureButton = findEl("nextMeasureButton");
const addMeasureButton = findEl("addMeasureButton");
const deleteMeasureButton = findEl("deleteMeasureButton");
const measureNavStatus = findEl("measureNavStatus");
const beginBarlineSelect = findEl("beginBarlineSelect");
const endBarlineSelect = findEl("endBarlineSelect");
const validateScoreButton = findEl("validateScoreButton");
const exportJsonButton = findEl("exportJsonButton");
const exportMusicXmlButton = findEl("exportMusicXmlButton");
const importMusicXmlButton = findEl("importMusicXmlButton");
const musicXmlFileInput = findEl("musicXmlFileInput");
const scoreExportStatus = findEl("scoreExportStatus");
const scoreDataOutput = findEl("scoreDataOutput");
const fourPartButton = findEl("fourPartButton");
const questionTypeSelect = findEl("questionTypeSelect");
const applyFourPartButton = findEl("applyFourPartButton");
// P19: AI 教师讲解按钮
const aiExplainButton = findEl("aiExplainButton");
const aiExplanationPanel = findEl("aiExplanationPanel");
const aiExplanationBody = findEl("aiExplanationBody");
const aiExplanationMeta = findEl("aiExplanationMeta");
const aiExplanationRules = findEl("aiExplanationRules");
const fourPartStatus = findEl("fourPartStatus");
const fourPartCanvas = findEl("fourPartCanvas");
const fourPartDetails = findEl("fourPartDetails");

const VF = window.VexFlow;
const supportedExtensions = [".musicxml", ".xml", ".mxl", ".mid", ".midi", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".pdf"];
const stepIndex = { C: 0, D: 1, E: 2, F: 3, G: 4, A: 5, B: 6 };
// P22.4-B.4: stepNames / clefBottomLines 改在 cs.js (cs.STEP_NAMES / cs.CLEF_BOTTOM_LINES) — pitchFromY 走 cs.localYToPitch
const durationUnits = { "0": 64, "1": 32, "2": 16, "4": 8, "8": 4, "16": 2, "32": 1, "64": 0.5 };
const vexDurations = { "0": "1/2", "1": "w", "2": "h", "4": "q", "8": "8", "16": "16", "32": "32", "64": "64" };
const musicXmlTypes = { "0": "breve", "1": "whole", "2": "half", "4": "quarter", "8": "eighth", "16": "16th", "32": "32nd", "64": "64th" };
const MUSICXML_DIVISIONS = 48;
const DIVISIONS_PER_UNIT = MUSICXML_DIVISIONS / 8;
const tupletRatios = {
  triplet: { totalNotes: 3, notesOccupied: 2, label: "三连音" },
  quintuplet: { totalNotes: 5, notesOccupied: 4, label: "五连音" },
  sextuplet: { totalNotes: 6, notesOccupied: 4, label: "六连音" }
};

function tupletPositions(count) {
  if (count <= 2) return ["start", "end"];
  return ["start", ...Array(count - 2).fill("middle"), "end"];
}
const articulationCodes = {
  staccato: "a.",
  accent: "a>",
  tenuto: "a-",
  marcato: "a^"
};
const articulationXml = {
  staccato: "staccato",
  accent: "accent",
  tenuto: "tenuto",
  marcato: "strong-accent"
};
const ornamentCodes = {
  mordent: "mordent",
  "mordent-inverted": "mordentInverted",
  trill: "tr",
  turn: "turn",
  "turn-inverted": "turnInverted",
  upprall: "upprall",
  downprall: "downprall",
  lineprall: "lineprall"
};
const ornamentXml = {
  mordent: "mordent",
  "mordent-inverted": "inverted-mordent",
  trill: "trill",
  turn: "turn",
  "turn-inverted": "inverted-turn",
  upprall: "mordent",
  downprall: "inverted-mordent",
  lineprall: "mordent"
};
const voiceIds = ["1", "2"];
const restValues = [
  { units: 64, duration: "0", dotted: false },
  { units: 32, duration: "1", dotted: false },
  { units: 24, duration: "2", dotted: true },
  { units: 16, duration: "2", dotted: false },
  { units: 12, duration: "4", dotted: true },
  { units: 8, duration: "4", dotted: false },
  { units: 6, duration: "8", dotted: true },
  { units: 4, duration: "8", dotted: false },
  { units: 3, duration: "16", dotted: true },
  { units: 2, duration: "16", dotted: false },
  { units: 1.5, duration: "32", dotted: true },
  { units: 1, duration: "32", dotted: false },
  { units: 0.5, duration: "64", dotted: false }
];

// P18.8.3 — "不位移"模式：画布永远只显示 3 个小节窗口（prev/current/next），
// 画布自身不滚动。切小节时画布的 3 个窗口重新分配，视觉上五线谱"始终固定"。
const VISIBLE_MEASURES = 3;
const DEFAULT_MEASURE_COUNT = 8;
const MAX_MEASURE_COUNT = 20;
const SINGLE_STAVE_HEIGHT = 110;   // 单谱表（treble 或 bass）小节高度
const PIANO_STAVE_HEIGHT = 240;    // 钢琴双谱表（treble + bass）小节高度
// 保留 MEASURES_PER_ROW 名称避免别处崩，但不再用于计算
const MEASURES_PER_ROW = 1;
let scoreMeasures = Array.from({ length: DEFAULT_MEASURE_COUNT }, () => []);
let measureSettings = Array.from({ length: DEFAULT_MEASURE_COUNT }, () => defaultMeasureSettings());
const staffScores = {
  treble: { measures: scoreMeasures, settings: measureSettings },
  bass: { measures: Array.from({ length: DEFAULT_MEASURE_COUNT }, () => []), settings: Array.from({ length: DEFAULT_MEASURE_COUNT }, () => defaultMeasureSettings()) }
};
let currentMeasureIndex = 0;
let measureEntries = scoreMeasures[currentMeasureIndex];
let editHistory = [];
let selectedEntryIndex = -1;
let staffGeometry = null;
// P22+: 双谱表 (piano) 模式分别存 treble / bass 局部坐标
let trebleGeometry = null;
let bassGeometry = null;
let measureRects = [];
let previousTimeSignature = editorTime.value;
let resizeTimer = null;
let lastFourPartResult = null;

// =====================================================================
// P22.3 — editorState（输入态集中管理层）
//
// 设计目标：
//   - 6 核心字段单一来源：
//     inputMode / previewEntry / pendingMousePosition
//     / selectedEntry / currentInputDuration / currentAccidental
//   - 派生状态：inputCapacity / isPreviewOverCapacity（决定 ghost 颜色）
//   - setter 写入 + 操作（clearPreview / clearSelected / syncFromUI）
//   - 边界（Phase 1）：
//       * passive data layer：现有代码一行不改
//       * 未来 Phase 让 handleNoteCanvasHover / addEntryFromScoreInner
//         / selectEntry / keyboard handler 显式调 setter
//   - 不引入新数据模型（previewEntry 仍是 entry 形状 + _ghost:true）
//   - 不替换 inputKind() / selectedEntryIndex（这两仍是 UI 单点真源）
// =====================================================================
const editorState = {
  // ---------- 6 核心字段 ----------
  inputMode: "note",                  // "note" | "rest" | "chord"
  previewEntry: null,                 // null | {kind, voice, pitches, duration, dotted, units, _ghost:true}
  pendingMousePosition: null,         // null | {x, y, staveKey, geometry, measureIndex}
  selectedEntry: null,                // null | {measureIndex, entryIndex, sourceIndex, staffKey}
  currentInputDuration: { duration: "4", dotted: 0, units: 8 },
  currentAccidental: "",              // "" | "#" | "b" | "n" | "##" | "bb"

  // ---------- 派生状态 ----------
  inputCapacity: { used: 0, capacity: 32, remaining: 32, wouldExceed: false },
  isPreviewOverCapacity: false,

  // ---------- 内部辅助：inline 算 units（不依赖外层 hoisted 函数） ----------
  _computeUnitsForDuration(duration, dotted) {
    const base = durationUnits[duration];
    if (typeof base !== "number") return 8;
    const d = Number(dotted) || 0;
    let units = base;
    for (let i = 0; i < d; i += 1) {
      units = units + base / Math.pow(2, i + 1);
    }
    return units;
  },

  // ---------- setter（passive 状态写入；Phase 1 不触发 redraw，Phase 2+ 接入） ----------
  setInputMode(mode) {
    if (mode !== "note" && mode !== "rest" && mode !== "chord") return;
    this.inputMode = mode;
  },

  setDuration(duration, dotted) {
    if (typeof duration !== "string") return;
    const d = Number(dotted) || 0;
    this.currentInputDuration = {
      duration,
      dotted: d,
      units: this._computeUnitsForDuration(duration, d)
    };
  },

  setAccidental(acc) {
    this.currentAccidental = typeof acc === "string" ? acc : "";
  },

  setPreview(entry) {
    // 期望形状：{kind, voice, pitches, duration, dotted, units, _ghost:true}
    // Phase 1 仅写入，不触发 redraw（Phase 2 接入）
    this.previewEntry = entry;
  },

  setSelected(ref) {
    // 期望形状：{measureIndex, entryIndex, sourceIndex, staffKey}
    this.selectedEntry = ref;
  },

  setMousePosition(pos) {
    // 期望形状：{x, y, staveKey, geometry, measureIndex}
    this.pendingMousePosition = pos;
  },

  updateCapacity(used, capacity) {
    const u = Number(used) || 0;
    const c = Number(capacity) || 32;
    this.inputCapacity = {
      used: u,
      capacity: c,
      remaining: Math.max(0, c - u),
      wouldExceed: u > c
    };
    this.isPreviewOverCapacity = this.inputCapacity.wouldExceed;
  },

  // ---------- 操作 ----------
  clearPreview() {
    this.previewEntry = null;
    this.pendingMousePosition = null;
  },

  clearSelected() {
    this.selectedEntry = null;
  },

  // ---------- 派生读取（business 唯一入口） ----------
  // 业务逻辑必须通过这 3 个 getter 读，禁止直接 noteDuration.value / noteDotted.value / noteAccidental.value
  // 原因：UI 控件不是 source of truth，editorState 才是。
  // 唯一允许直接读 UI 的地方：syncFromUI()（UI→editorState 同步入口本身）。
  getInputDuration() {
    return this.currentInputDuration;
  },
  getInputAccidental() {
    return this.currentAccidental;
  },

  // 一次性把 UI 当前状态（noteDuration / noteDotted / noteAccidental）镜像进 editorState
  // Phase 1 显式供测试代码和未来 Phase 调用；现有 UI 控件不自动调
  syncFromUI() {
    if (typeof noteDuration === "undefined" || !noteDuration) return;
    const dur = noteDuration.value || "4";
    const dottedEl = (typeof noteDotted !== "undefined") ? noteDotted : null;
    const dotted = dottedEl ? (Number(dottedEl.value) || 0) : 0;
    this.setDuration(dur, dotted);
    if (typeof noteAccidental !== "undefined" && noteAccidental) {
      this.setAccidental(noteAccidental.value || "");
    }
  }
};

// P22.4-B.2: CoordinateSystem v1 — 统一坐标层
// 构造时不绑 DOM (canvas 由 caller 传); cs 内部封装 3 套 geometry + measureRects
// 接入策略:
//   - render 末尾: cs.updateLayout({staffGeometry, trebleGeometry, bassGeometry, measureRects, currentMeasureIndex, timeSignature})
//   - 错误路径:   cs.clearLayout()
// 业务 (addEntry/hover/buildPreview) 暂时还用内联公式 — B.3 才迁
const cs = new window.CoordinateSystem();

function defaultMeasureSettings() {
  return { beginBarline: "single", endBarline: "single" };
}

function isPianoMode() {
  return staffMode?.value === "piano";
}

function activeStaffKey() {
  return noteClef?.value === "bass" ? "bass" : "treble";
}

function activeStaffLabel() {
  return activeStaffKey() === "bass" ? "左手/低音谱表" : "右手/高音谱表";
}

function activeVoiceId() {
  return voiceSelect?.value || "1";
}

function activeVoiceLabel() {
  return `声部 ${activeVoiceId()}`;
}

function entryVoice(entry) {
  return String(entry.voice || "1");
}

function entriesForVoice(entries = measureEntries, voiceId = activeVoiceId()) {
  return entries.filter((entry) => entryVoice(entry) === String(voiceId));
}

function currentVoiceEntries() {
  return entriesForVoice(measureEntries, activeVoiceId());
}

function activateStaff(staffKey = activeStaffKey()) {
  const state = staffScores[staffKey] || staffScores.treble;
  scoreMeasures = state.measures;
  measureSettings = state.settings;
  while (scoreMeasures.length <= currentMeasureIndex) scoreMeasures.push([]);
  while (measureSettings.length <= currentMeasureIndex) measureSettings.push(defaultMeasureSettings());
  measureEntries = scoreMeasures[currentMeasureIndex];
}

function forEachVisibleStaff(callback) {
  const keys = isPianoMode() ? ["treble", "bass"] : [activeStaffKey()];
  keys.forEach((staffKey) => callback(staffKey, staffScores[staffKey]));
}

function ensureMeasureExistsForVisibleStaves(targetIndex) {
  forEachVisibleStaff((_, state) => {
    while (state.measures.length <= targetIndex && state.measures.length < 16) {
      state.measures.push([]);
      state.settings.push(defaultMeasureSettings());
    }
  });
  activateStaff();
}

async function checkHealth() {
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error("health failed");
    apiStatus.textContent = "API 在线";
    apiStatus.classList.remove("offline");
  } catch {
    apiStatus.textContent = "API 离线";
    apiStatus.classList.add("offline");
  }
}

function extensionOf(fileName) {
  const index = fileName.lastIndexOf(".");
  return index >= 0 ? fileName.slice(index).toLowerCase() : "";
}

function setBusy(label) {
  readStatus.textContent = "读取中";
  measurePreview.className = "measure-preview empty";
  measurePreview.textContent = `正在处理 ${label}...`;
  harmonyPreview.className = "harmony-preview empty";
  harmonyPreview.textContent = "等待和声结果...";
  warningList.className = "warning-list empty";
  warningList.textContent = "正在校验...";
}

function setError(message) {
  readStatus.textContent = "失败";
  measurePreview.className = "measure-preview empty";
  measurePreview.textContent = "本次自动读取没有得到可用结果，可改用手动小节校正。";
  harmonyPreview.className = "harmony-preview empty";
  harmonyPreview.textContent = "-";
  warningList.className = "warning-list";
  warningList.innerHTML = `<div class="warning-row">${escapeHtml(message)}</div>`;
}

async function uploadScore(file) {
  const extension = extensionOf(file.name);
  if (!supportedExtensions.includes(extension)) {
    setError(`暂不支持 ${extension || "未知"} 文件。`);
    return;
  }

  setBusy(file.name);
  const data = new FormData();
  data.append("file", file);

  try {
    const response = await fetch("/read-score", { method: "POST", body: data });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "读取失败");
    renderResult(payload);
  } catch (error) {
    setError(error.message || "读取失败");
  }
}

async function submitManualChords() {
  const payload = {
    key: manualKey.value.trim(),
    timeSignature: manualTime.value.trim() || "4/4",
    progression: manualProgression.value.trim()
  };

  if (!payload.key || !payload.progression) {
    setError("请填写调性和和弦进行。 ");
    return;
  }

  setBusy("手动和弦");
  try {
    const response = await fetch("/manual-chords", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "手动和弦解析失败");
    renderResult(result);
  } catch (error) {
    setError(error.message || "手动和弦解析失败");
  }
}

async function submitManualNotes() {
  const input = noteInput.value.trim();
  if (!input) {
    showEditorMessage("请输入音名，例如 C4 E4 G4。", "error");
    return;
  }

  try {
    if (input.includes("||")) {
      const measures = parseScoreTextInput(input);
      loadParsedMeasuresIntoEditor(measures);
      return;
    }
    const structure = parseBatchInput(input);
    loadManualEntries(structure);
  } catch (error) {
    showEditorMessage(error.message || "音名解析失败", "error");
  }
}

// ---------------------------------------------------------------------------
// Sposobin 课本例题预置 (P0-P7.5)
// ---------------------------------------------------------------------------
// 这些例题来自 Sposobin《和声学教程》上/下册的经典谱例. 选了一个就
// 自动填到 noteInput + 调好 key/time/转调 + 自动载入谱面. 用户在 web
// 端不需要手打就能立刻试新算法 (P0-P7.5).
//
// 格式: melody 用 parseScoreTextInput 接受的格式 (用 | 分拍, 用 : 分
// duration, 用 || 分 measure). 升降号用 # / b (e.g. Eb5, F#4).
const EXAMPLE_PRESETS = {
  // ---- 0 升降 ----
  // P0: I-IV-V-I 经典终止 (C 大调, 无升降)
  p0_cadence: {
    label: "P0 C 大调 I-IV-V-I",
    key: "C", time: "4/4",
    melody: "C5:4 | D5:4 | E5:4 | C5:4 || F5:4 | F5:4 | F5:4 | F5:4 || G5:4 | G5:4 | G5:4 | G5:4 || C5:4 | C5:4 | C5:4 | C5:4",
    keyChanges: [],
  },
  // P5: a 小调自然/和声终止 (a 小调, 无升降)
  p5_a_minor: {
    label: "P5 a 小调终止",
    key: "a", time: "4/4",
    melody: "A4:4 | A4:4 | A4:4 | A4:4 || E5:4 | E5:4 | E5:4 | E5:4 || G#5:4 | G#5:4 | G#5:4 | G#5:4 || A4:4 | A4:4 | A4:4 | A4:4",
    keyChanges: [],
  },
  // ---- 1 升降 ----
  // P1.5: F 大调 (1 降 Bb) 经典终止 — 限制在 C4-C5/C5 范围
  p1_5_f_major: {
    label: "P1.5 F 大调 I-V7-I",
    key: "F", time: "4/4",
    melody: "F4:4 | G4:4 | A4:4 | F4:4 || C5:4 | C5:4 | C5:4 | C5:4 || A4:4 | A4:4 | A4:4 | A4:4 || F4:4 | F4:4 | F4:4 | F4:4",
    keyChanges: [],
  },
  // P1.6: G 大调 (1 升 F#) 经典终止 — 限制在 C4-C6 范围
  p1_6_g_major: {
    label: "P1.6 G 大调 I-V7-I",
    key: "G", time: "4/4",
    melody: "G4:4 | A4:4 | B4:4 | G4:4 || D5:4 | D5:4 | D5:4 | D5:4 || B4:4 | B4:4 | B4:4 | B4:4 || G4:4 | G4:4 | G4:4 | G4:4",
    keyChanges: [],
  },
  // P5.3: d 小调 (1 升 F#) 和声终止 — 限制在 C4-C6 范围
  p5_3_d_minor: {
    label: "P5.3 d 小调和声终止",
    key: "d", time: "4/4",
    melody: "D4:4 | D4:4 | D4:4 | D4:4 || A4:4 | A4:4 | A4:4 | A4:4 || C#5:4 | C#5:4 | C#5:4 | C#5:4 || D4:4 | D4:4 | D4:4 | D4:4",
    keyChanges: [],
  },
  // ---- 2 升降 ----
  // P1.7: D 大调 (2 升 F#C#) 经典终止
  p1_7_d_major: {
    label: "P1.7 D 大调 I-V7-I",
    key: "D", time: "4/4",
    melody: "D5:4 | E5:4 | F#5:4 | D5:4 || A5:4 | A5:4 | A5:4 | A5:4 || F#5:4 | F#5:4 | F#5:4 | F#5:4 || D5:4 | D5:4 | D5:4 | D5:4",
    keyChanges: [],
  },
  // P3.6: Bb 大调 (2 降 BbEb) I-IV-V-I
  p3_6_bb_major: {
    label: "P3.6 Bb 大调 I-IV-V-I",
    key: "Bb", time: "4/4",
    melody: "Bb4:4 | C5:4 | D5:4 | Bb4:4 || Eb5:4 | Eb5:4 | Eb5:4 | Eb5:4 || F5:4 | F5:4 | F5:4 | F5:4 || Bb4:4 | Bb4:4 | Bb4:4 | Bb4:4",
    keyChanges: [],
  },
  // P5.4: g 小调 (2 降 BbEb) 和声终止
  p5_4_g_minor: {
    label: "P5.4 g 小调和声终止",
    key: "g", time: "4/4",
    melody: "G4:4 | G4:4 | G4:4 | G4:4 || D5:4 | D5:4 | D5:4 | D5:4 || F#5:4 | F#5:4 | F#5:4 | F#5:4 || G4:4 | G4:4 | G4:4 | G4:4",
    keyChanges: [],
  },
  // ---- 3 升降 ----
  // P2.6: A 大调 (3 升 F#C#G#) V7/V 副属 — 限制在 C4-C6 范围
  p2_6_a_major: {
    label: "P2.6 A 大调 V7/V 副属",
    key: "A", time: "4/4",
    melody: "A4:4 | B4:4 | C#5:4 | D5:4 || E5:4 | E5:4 | E5:4 | E5:4 || G#4:4 | G#4:4 | G#4:4 | G#4:4 || E4:4 | E4:4 | E4:4 | A4:4",
    keyChanges: [],
  },
  // P3.5: Eb 大调 (3 降 BbEbAb) bVI 借用 — modal mixture
  p3_5_modal_mixture: {
    label: "P3.5 Eb 大调 bVI 借用",
    key: "Eb", time: "4/4",
    melody: "Eb5:4 | Eb5:4 | Eb5:4 | Bb4:4 || Ab5:4 | Ab5:4 | Ab5:4 | Ab5:4 || Bb5:4 | Bb5:4 | Bb5:4 | Bb5:4 || Eb5:4 | Eb5:4 | Eb5:4 | Eb5:4",
    keyChanges: [],
  },
  // P5.5: c 小调 (3 降) Phrygian 终止
  p5_phrygian: {
    label: "P5.5 c 小调 Phrygian 终止",
    key: "c", time: "4/4",
    melody: "C5:4 | C5:4 | C5:4 | C5:4 || Ab5:4 | Ab5:4 | Ab5:4 | Ab5:4 || G5:4 | G5:4 | G5:4 | G5:4 || Eb5:4 | Eb5:4 | Eb5:4 | C5:4",
    keyChanges: [],
  },
  // ---- 4 升降 ----
  // P3.7: Ab 大调 (4 降) I-IV-V-I — 简化的同音重复旋律 (Ab4 个降号调 pool 大, beam 友好)
  p3_7_ab_major: {
    label: "P3.7 Ab 大调 I-IV-V-I",
    key: "Ab", time: "4/4",
    melody: "Ab4:4 | Ab4:4 | Ab4:4 | Ab4:4 || Db5:4 | Db5:4 | Db5:4 | Db5:4 || Eb5:4 | Eb5:4 | Eb5:4 | Eb5:4 || Ab4:4 | Ab4:4 | Ab4:4 | Ab4:4",
    keyChanges: [],
  },
  // ---- 变和弦 + 转调 ----
  // P1: V7 7-3 延留
  p1_v7_suspension: {
    label: "P1 V7 7-3 延留",
    key: "C", time: "4/4",
    melody: "C5:4 | C5:4 | C5:4 | C5:4 || F5:4 | F5:4 | F5:4 | F5:4 || G5:4 | F5:4 | G5:4 | F5:4 || E5:4 | E5:4 | E5:4 | C5:4",
    keyChanges: [],
  },
  // P2: 副属 V7/V
  p2_v7v: {
    label: "P2 C 大调 V7/V 副属",
    key: "C", time: "4/4",
    melody: "C5:4 | D5:4 | E5:4 | F5:4 || G5:4 | G5:4 | G5:4 | G5:4 || C#5:4 | C#5:4 | C#5:4 | C#5:4 || F5:4 | F5:4 | F5:4 | F5:4",
    keyChanges: [],
  },
  // P3: 增六和弦 Ger+6
  p3_aug6_ger: {
    label: "P3 Ger+6 增六和弦",
    key: "C", time: "4/4",
    melody: "C5:4 | B4:4 | C5:4 | D5:4 || Ab4:4 | G4:4 | G4:4 | G4:4 || G5:4 | G5:4 | G5:4 | G5:4 || C5:4 | C5:4 | C5:4 | C5:4",
    keyChanges: [],
  },
  // P7.5: C → G 上五度转调
  p7_5_c_to_g: {
    label: "P7.5 C → G 转调",
    key: "C", time: "4/4",
    melody: "C5:4 | D5:4 | E5:4 | F5:4 || G5:4 | G5:4 | G5:4 | G5:4 || A5:4 | A5:4 | A5:4 | A5:4 || B5:4 | B5:4 | B5:4 | B5:4",
    keyChanges: [[2, "G"]],
  },
  // P7.5: C → a 关系调转调
  p7_5_c_to_a: {
    label: "P7.5 C → a 关系调",
    key: "C", time: "4/4",
    melody: "C5:4 | D5:4 | E5:4 | F5:4 || G5:4 | G5:4 | G5:4 | G5:4 || A5:4 | A5:4 | A5:4 | A5:4 || B5:4 | B5:4 | B5:4 | B5:4",
    keyChanges: [[2, "a"]],
  },
};

function loadExamplePreset(presetKey) {
  const preset = EXAMPLE_PRESETS[presetKey];
  if (!preset) {
    if (typeof showEditorMessage === "function") {
      showEditorMessage(`未找到例题：${presetKey}`, "error");
    }
    return;
  }
  // 1) 填到 noteInput
  if (noteInput) noteInput.value = preset.melody;
  // 2) 调好 key + time (主编辑器 + 手动和弦区域)
  if (editorKey) editorKey.value = preset.key;
  if (editorTime) editorTime.value = preset.time;
  if (manualKey) manualKey.value = preset.key;
  if (manualTime) manualTime.value = preset.time;
  // 3) 转调点 → keyChangesInput (用户能直接看到) + localStorage
  const kcStr = (preset.keyChanges || [])
    .map(([m, k]) => `${m + 1}→${k}`)
    .join(" | ");
  if (keyChangesInput) keyChangesInput.value = kcStr;
  try {
    localStorage.setItem("musicreader:key_changes", JSON.stringify(preset.keyChanges || []));
  } catch (e) {
    // localStorage 可能被禁用, 不影响主流程
  }
  // 4) 自动载入谱面
  try {
    const measures = parseScoreTextInput(preset.melody);
    loadParsedMeasuresIntoEditor(measures);
    // P18.8.3 — 重新激活 staff 引用 + 重渲染（loadParsedMeasuresIntoEditor 改了 staffScores 但不重画）
    activateStaff();
    currentMeasureIndex = 0;
    try { renderNotation(); } catch (e) { handleRenderError(e); }
    if (typeof showEditorMessage === "function") {
      showEditorMessage(
        `已载入课本例题「${preset.label}」 (${preset.key} ${preset.time}, ${preset.keyChanges?.length || 0} 个转调). 点"生成四部和声"看结果.`,
        "success"
      );
    }
  } catch (err) {
    if (typeof showEditorMessage === "function") {
      showEditorMessage(err.message || "谱面载入失败", "error");
    }
  }
}

function loadParsedMeasuresIntoEditor(parsedMeasures) {
  const voiceId = activeVoiceId();
  const targetStaff = activeStaffKey();
  const targetState = staffScores[targetStaff];
  const nextMeasures = parsedMeasures.map((measure) => (
    measure.map((entry) => ({ ...entry, voice: voiceId }))
  ));
  const requiredCount = Math.min(16, Math.max(nextMeasures.length, targetState.measures.length));

  while (targetState.measures.length < requiredCount) targetState.measures.push([]);
  while (targetState.settings.length < requiredCount) targetState.settings.push(defaultMeasureSettings());

  commitEdit(() => {
    for (let measureIndex = 0; measureIndex < nextMeasures.length; measureIndex += 1) {
      const existing = targetState.measures[measureIndex] || [];
      targetState.measures[measureIndex] = [
        ...existing.filter((entry) => entryVoice(entry) !== voiceId),
        ...nextMeasures[measureIndex]
      ];
    }
    currentMeasureIndex = 0;
    noteMeasure.value = "1";
    activateStaff(targetStaff);
    selectLastEntryInActiveVoice();
  });
  showEditorMessage(`已载入 ${nextMeasures.length} 个小节到${activeStaffLabel()} ${activeVoiceLabel()}。`, "success");
}

async function submitFourPartAnswer() {
  fourPartStatus.classList.remove("status-failed", "status-ok");
  fourPartStatus.textContent = "生成中";
  if (applyFourPartButton) applyFourPartButton.disabled = true;
  fourPartDetails.className = "answer-details empty";
  fourPartDetails.textContent = "正在生成参考答案...";

  const questionType = questionTypeSelect?.value || "melody";
  let melodyMeasures;
  let bassMeasures = [];
  try {
    melodyMeasures = collectMelodyMeasuresForAnswer(questionType);
    if (questionType === "bass") {
      bassMeasures = collectBassMeasuresForAnswer();
      if (!bassMeasures.some((m) => m && m.length)) {
        throw new Error("低音题请先在下方低音谱表（声部 2）输入低音序列，再生成四部和声参考答案。");
      }
    }
  } catch (error) {
    lastFourPartResult = null;
    fourPartStatus.classList.add("status-failed");
    fourPartStatus.textContent = "失败";
    if (applyFourPartButton) applyFourPartButton.disabled = true;
    fourPartDetails.className = "answer-details";
    const hint = "提示: 直接在「3 五线谱制谱」区用鼠标点输入旋律（默认声部 1 = 女高音），或在下方文本框填好后点「填入到五线谱」按钮。文本框格式：C5:4 | D5:4 | E5:4 | C5:4（| 分拍，|| 分小节）。";
    fourPartDetails.innerHTML =
      `<div class="warning-row">${escapeHtml(error.message || "四部和声生成失败")}</div>` +
      `<div class="warning-row">${escapeHtml(hint)}</div>`;
    return;
  }

  const payload = {
    key: manualKey.value.trim() || "C major",
    timeSignature: editorTime.value,
    melodyEntries: melodyMeasures[0] || [],
    melodyMeasures,
    questionType
  };
  if (questionType === "bass" && bassMeasures.length) {
    // P8: bass-given problems carry the bass line in a separate field
    // so the server can route to bass-given solver mode.
    payload.bassMeasures = bassMeasures;
    payload.bassEntries = bassMeasures[0] || [];
  }

  // P17: chord_pool_profile 透传给 solver. 用户在 UI 选了章节范围,
  // 'auto' 让 server 端按调号自动选.
  const profileSelect = document.getElementById("chordPoolProfile");
  if (profileSelect && profileSelect.value && profileSelect.value !== "auto") {
    payload.chordPoolProfile = profileSelect.value;
  }

  // P7.5: 如果用户从课本例题预设加载过, 读 localStorage 的 key_changes.
  // 优先用 keyChangesInput 里用户手输的 (覆盖 localStorage).
  let keyChanges = [];
  const keyChangesRaw = keyChangesInput?.value?.trim() || "";
  if (keyChangesRaw) {
    // 解析 "2→G | 4→a" 格式
    const parts = keyChangesRaw.split("|").map(s => s.trim()).filter(Boolean);
    for (const p of parts) {
      const m = p.match(/^(\d+)\s*[→\->]\s*([A-Ga-g][#b]?m?)$/);
      if (m) {
        // measure idx 是 0-based (跟 solver 内部一致), 但用户写 1-based
        // 自动 -1
        const measure1based = parseInt(m[1], 10);
        if (measure1based < 1) {
          throw new Error(`转调点必须从 1 开始, 不能是 ${m[1]}`);
        }
        keyChanges.push([measure1based - 1, m[2]]);
      } else {
        throw new Error(`转调点格式错误: "${p}". 应该像 "2→G" 或 "4->a".`);
      }
    }
  } else {
    try {
      const stored = localStorage.getItem("musicreader:key_changes");
      if (stored) {
        keyChanges = JSON.parse(stored);
      }
    } catch (e) {
      // localStorage 解析失败, 不传 keyChanges
    }
  }
  if (Array.isArray(keyChanges) && keyChanges.length > 0) {
    payload.keyChanges = keyChanges;
  }

  // P8: a single POST to /solve-melody.  The Sposobin solver handles
  // both melody-given (P0-P7) and bass-given (P8) problems natively;
  // no fallback to legacy four_part.py (that module has been replaced
  // by solver.py as of 2026-08-09).
  let result = null;
  try {
    // P15: 30-second timeout via AbortController.  The server should
    // respond in <1s for typical 4-measure problems; 30s is a
    // generous safety net for chromium iframe sandbox and other
    // proxies that occasionally hang on .json() parsing.
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    let resp;
    try {
      resp = await fetch("/solve-melody", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeoutId);
    }
    if (!resp.ok) {
      // P18.6: server 端已不再返 422/500, 但万一老版本或者代理出错, 也不要把
      // resp.status / err.detail 露给用户. 提取中文友好提示.
      let detail = "";
      try {
        const err = await resp.json();
        if (err && err.warnings && err.warnings[0]) detail = err.warnings[0];
        else if (err && err.detail) detail = err.detail;
      } catch (_) { /* resp 不是 JSON, 忽略 */ }
      // 永远不显示 Python 内部错误 (list index out of range / ValueError / ...)
      const looksInternal = /list index|out of range|ValueError|IndexError|KeyError|AttributeError|TypeError|Traceback/i.test(detail);
      const userMsg = looksInternal
        ? "后端返回了内部错误, 请重试或换一道题."
        : (detail || `服务器返回 ${resp.status}, 请刷新重试.`);
      throw new Error(userMsg);
    }
    result = await resp.json();
  } catch (error) {
    lastFourPartResult = null;
    fourPartStatus.classList.add("status-failed");
    fourPartStatus.textContent = "失败";
    if (applyFourPartButton) applyFourPartButton.disabled = true;
    fourPartDetails.className = "answer-details";
    const hint = "提示: 直接在「3 五线谱制谱」区用鼠标点输入旋律（默认声部 1 = 女高音），或在下方文本框填好后点「填入到五线谱」按钮。文本框格式：C5:4 | D5:4 | E5:4 | C5:4（| 分拍，|| 分小节）。";
    // P18.6: 即使是 fetch 网络失败/超时, 也不暴露原始错误给用户 (e.g. "Failed to fetch" / "AbortError")
    const rawMsg = (error && error.message) || "四部和声生成失败";
    const isInternal = /Failed to fetch|AbortError|TypeError|NetworkError|fetch failed/i.test(rawMsg);
    const safeMsg = isInternal
      ? "无法连接服务器 (8765), 请确认后端 server.py 已启动."
      : rawMsg;
    fourPartDetails.innerHTML =
      `<div class="warning-row">${escapeHtml(safeMsg)}</div>` +
      `<div class="warning-row">${escapeHtml(hint)}</div>`;
    return;
  }

  if (!result) {
    lastFourPartResult = null;
    fourPartStatus.classList.add("status-failed");
    fourPartStatus.textContent = "失败";
    if (applyFourPartButton) applyFourPartButton.disabled = true;
    fourPartDetails.className = "answer-details";
    fourPartDetails.innerHTML = `<div class="warning-row">四部和声生成失败（后端无返回）</div>`;
    return;
  }

  lastFourPartResult = result;
  renderFourPartAnswer(result);

  // P18.6: server 端在内部错时也会返 200 + summary.status=error.  这种 case
  // 不要显示 "已生成", 而要显示 "失败" + 友好 message.
  const isError = result?.summary?.status === "error"
    || (result?.fourPart?.voices || []).length === 0;
  if (isError) {
    if (fourPartStatus) {
      fourPartStatus.classList.add("status-failed");
      fourPartStatus.textContent = "失败";
    }
    if (applyFourPartButton) applyFourPartButton.disabled = true;
    return;
  }

  if (fourPartStatus) {
    fourPartStatus.classList.add("status-ok");
    const engine = result?.source?.engine || "sposobin-solver";
    fourPartStatus.textContent = `已生成 (${engine})`;
    fourPartStatus.title = engine;
  }
}

function collectMelodyMeasuresForAnswer(questionType = "melody") {
  activateStaff();

  // P8: melody collection is independent of questionType.  For bass-given
  // problems, the user enters the bass line on the lower staff (voice 2
  // in the bass clef) and the melody slot is typically empty.  We don't
  // try to read the bass slot here — that's collectBassMeasuresForAnswer's
  // job.  Just collect the melody (which may be empty in bass-given mode).

  const voiceId = activeVoiceId();
  const perMeasure = scoreMeasures.map((measure) => entriesForVoice(measure, voiceId));
  const normalized = normalizeCollectedMeasures(perMeasure, voiceId);
  if (normalized) return normalized;

  const text = noteInput.value.trim();
  if (text) {
    const parsed = parseScoreTextInput(text);
    if (parsed.length) return parsed;
  }
  // For melody questions, this is a hard error.  For bass questions, the
  // melody slot can legitimately be empty — let the caller decide whether
  // to fall through to bass collection.
  if (questionType === "bass") return [];
  // P17 review: include the active voice id so the user knows which line
  // they were writing into.  Common bug: the user clicks on the staff but
  // had Voice selected to "2" (alto/tenor), so their notes never reach
  // the melody slot.
  const voiceLabel = voiceId === "1" ? "女高音（声部 1）" : `声部 ${voiceId}`;
  throw new Error(
    `五线谱区还没有旋律。当前选中的是 ${voiceLabel}，` +
    `请在五线谱区用鼠标点输入旋律（或在下方文本框填入后点「填入到五线谱」）。`
  );
}


function collectBassMeasuresForAnswer() {
  // P8: read the bass line (voice 2 in the bass staff).  Returns [] if
  // the bass slot is empty, or the normalized per-measure list otherwise.
  const bassState = staffScores.bass;
  const bassPerMeasure = bassState.measures.map((measure) => entriesForVoice(measure, "2"));
  const normalized = normalizeCollectedMeasures(bassPerMeasure, "2");
  return normalized || [];
}

function normalizeCollectedMeasures(perMeasure, voiceId) {
  // 找到最后一个非空小节，避免把尾部空小节也算进去
  let lastUsed = -1;
  perMeasure.forEach((entries, index) => { if (entries.length) lastUsed = index; });
  if (lastUsed >= 0) {
    const capacity = currentMeter().capacity;
    return perMeasure.slice(0, lastUsed + 1).map((entries) => {
      if (entries.length) return JSON.parse(JSON.stringify(entries));
      // 中间的空小节 → 全小节休止，保持小节编号对齐
      return [{ kind: "rest", voice: voiceId, duration: "1", dotted: false, units: capacity }];
    });
  }
  return null;
}

function parseScoreTextInput(input) {
  const rawMeasures = input.split("||").map((item) => item.trim()).filter(Boolean);
  const measures = rawMeasures.map((rawMeasure, measureIndex) => {
    const events = parseScoreMeasureText(rawMeasure, measureIndex + 1);
    const used = sumEntryUnits(events);
    const capacity = currentMeter().capacity;
    if (!sameUnitValue(used, capacity)) {
      throw new Error(`第 ${measureIndex + 1} 小节时值为 ${formatCount(used / currentMeter().beatUnit)} 拍，需要刚好等于 ${currentMeter().numerator} 拍。`);
    }
    return events;
  });
  if (measures.length > 16) {
    throw new Error("第一版最多处理 16 小节旋律题。");
  }
  return measures;
}

function parseScoreMeasureText(rawMeasure, measureNumber) {
  let rawEvents;
  if (rawMeasure.includes("|")) {
    rawEvents = rawMeasure.split("|").map((item) => item.trim()).filter(Boolean);
  } else {
    rawEvents = rawMeasure.split(/[\s,;]+/).map((item) => item.trim()).filter(Boolean);
  }

  if (!rawEvents.length) throw new Error(`第 ${measureNumber} 小节没有可读取的音符。`);

  return rawEvents.map((rawEvent, eventIndex) => {
    const durationMatch = rawEvent.match(/:(0|1|2|4|8|16|32|64)(\.{0,2})$/);
    // P22.3 duration-cleanup: business 统一从 editorState 读 fallback
    const esDur = editorState.getInputDuration();
    const duration = durationMatch?.[1] || esDur.duration;
    const dotted = durationMatch ? durationMatch[2].length : esDur.dotted;
    const body = durationMatch ? rawEvent.slice(0, durationMatch.index).trim() : rawEvent.trim();
    const units = unitsForDuration(duration, dotted);

    if (/^(R|r|rest|休止)$/u.test(body)) {
      return { kind: "rest", duration, dotted, units, fermata: false, dynamic: "" };
    }

    const pitchTokens = body.split("+").map((token) => token.trim()).filter(Boolean);
    if (!pitchTokens.length) {
      throw new Error(`第 ${measureNumber} 小节第 ${eventIndex + 1} 拍位缺少音高。`);
    }
    const pitches = pitchTokens.map((token) => pitchFromTextToken(token, measureNumber, eventIndex + 1));
    if (new Set(pitches.map(pitchIdentity)).size !== pitches.length) {
      throw new Error(`第 ${measureNumber} 小节第 ${eventIndex + 1} 拍位重复输入相同音高。`);
    }
    return {
      kind: "note",
      pitches: sortPitches(pitches),
      duration,
      dotted,
      units,
      tieStart: false,
      tieStop: false,
      slurStart: false,
      slurStop: false,
      fermata: false,
      tupletType: "",
      tupletGroup: "",
      tupletPosition: "",
      dynamic: ""
    };
  });
}

function pitchFromTextToken(token, measureNumber, beatNumber) {
  const normalized = token.replace("♯", "#").replace("♭", "b").replace("♮", "n");
  const match = /^([A-Ga-g])([#bn]?)(-?\d+)$/.exec(normalized);
  if (!match) {
    throw new Error(`第 ${measureNumber} 小节第 ${beatNumber} 拍位的音高 ${token} 无法解析，请用 C4、F#4、Bb3 这类格式。`);
  }
  const step = match[1].toUpperCase();
  const accidental = match[2] || "";
  const octave = Number(match[3]);
  return {
    step,
    accidental,
    octave,
    display: `${step}${displayAccidental(accidental)}${octave}`
  };
}

function parseBatchInput(input) {
  // P22.3 duration-cleanup: fallback 也从 editorState 读
  const esDur = editorState.getInputDuration();
  const fallbackDuration = esDur.duration;
  const fallbackDotted = esDur.dotted;
  let rawEvents;

  if (input.includes("|")) {
    rawEvents = input.split("|").map((item) => item.trim()).filter(Boolean);
  } else if (input.includes("+")) {
    rawEvents = [input.trim()];
  } else {
    rawEvents = input.split(/[\s,;]+/).map((item) => item.trim()).filter(Boolean);
  }

  if (!rawEvents.length) throw new Error("没有可载入的音符。 ");

  return rawEvents.map((rawEvent, index) => {
    const durationMatch = rawEvent.match(/:(0|1|2|4|8|16|32|64)(\.{0,2})$/);
    const duration = durationMatch?.[1] || fallbackDuration;
    const dotted = durationMatch ? durationMatch[2].length : fallbackDotted;
    const body = durationMatch ? rawEvent.slice(0, durationMatch.index).trim() : rawEvent;

    if (/^(R|r|rest|休止)$/u.test(body.trim())) {
      return { kind: "rest", duration, dotted };
    }

    const tokens = body.split("+").map((token) => token.trim()).filter(Boolean);

    if (!tokens.length || tokens.some((token) => /\s/.test(token))) {
      throw new Error(`第 ${index + 1} 个拍位格式不正确。和弦音请用 + 连接。`);
    }

    return { kind: "note", tokens, duration, dotted };
  });
}

function loadManualEntries(structure) {
  const capacity = currentMeter().capacity;
  const loaded = [];
  let omittedEvents = 0;

  for (const eventSpec of structure) {
    const units = unitsForDuration(eventSpec.duration, eventSpec.dotted);
    if (exceedsUnitValue(sumEntryUnits(loaded) + units, capacity)) break;

    if (eventSpec.kind === "rest") {
      loaded.push({
        kind: "rest",
        voice: activeVoiceId(),
        duration: eventSpec.duration,
        dotted: eventSpec.dotted,
        units,
        fermata: false,
        tupletType: "",
        tupletGroup: "",
        tupletPosition: "",
        dynamic: ""
      });
      continue;
    }

    const pitches = eventSpec.tokens.map((token) => pitchFromTextToken(token, Number(noteMeasure.value || 1), loaded.length + 1));
    if (new Set(pitches.map(pitchIdentity)).size !== pitches.length) {
      throw new Error("同一个和弦中不能重复输入相同音高。 ");
    }

    loaded.push({
      kind: "note",
      voice: activeVoiceId(),
      pitches: sortPitches(pitches),
      duration: eventSpec.duration,
      dotted: eventSpec.dotted,
      units,
      tieStart: false,
      tieStop: false,
      slurStart: false,
      slurStop: false,
      fermata: false,
      tupletType: "",
      tupletGroup: "",
      tupletPosition: "",
      dynamic: ""
    });
  }

  omittedEvents = structure.length - loaded.length;
  commitEdit(() => {
    const otherVoiceEntries = measureEntries.filter((entry) => entryVoice(entry) !== activeVoiceId());
    setCurrentMeasureEntries([...otherVoiceEntries, ...loaded]);
    selectedEntryIndex = loaded.length ? measureEntries.lastIndexOf(loaded[loaded.length - 1]) : -1;
  });

  if (omittedEvents > 0) {
    showEditorMessage(`拍号容量不足，后 ${omittedEvents} 个拍位未载入。`, "error");
  }
}

function loadManualNotes(notes, structure) {
  const capacity = currentMeter().capacity;
  const loaded = [];
  let noteCursor = 0;
  let omittedEvents = 0;

  for (const eventSpec of structure) {
    const units = unitsForDuration(eventSpec.duration, eventSpec.dotted);
    if (exceedsUnitValue(sumEntryUnits(loaded) + units, capacity)) break;
    const pitches = notes.slice(noteCursor, noteCursor + eventSpec.tokens.length).map(pitchFromApi);
    noteCursor += eventSpec.tokens.length;

    if (new Set(pitches.map(pitchIdentity)).size !== pitches.length) {
      throw new Error("同一个和弦中不能重复输入相同音高。 ");
    }

    loaded.push({
      kind: "note",
      pitches: sortPitches(pitches),
      duration: eventSpec.duration,
      dotted: eventSpec.dotted,
      units,
      tieStart: false,
      tieStop: false,
      slurStart: false,
      slurStop: false,
      fermata: false,
      tupletType: "",
      tupletGroup: "",
      tupletPosition: "",
      dynamic: ""
    });
  }

  omittedEvents = structure.length - loaded.length;
  commitEdit(() => {
    setCurrentMeasureEntries(loaded);
    selectedEntryIndex = loaded.length ? loaded.length - 1 : -1;
  });

  if (omittedEvents > 0) {
    showEditorMessage(`拍号容量不足，后 ${omittedEvents} 个拍位未载入。`, "error");
  }
}

function pitchFromApi(item) {
  const accidental = accidentalFromApi(item.accidental);
  return {
    step: item.step,
    octave: item.octave,
    accidental,
    display: `${item.step}${displayAccidental(accidental)}${item.octave}`
  };
}

function renderResult(result) {
  const summary = result.summary || {};
  const key = summary.analyzedKey || {};
  readStatus.textContent = readableStatus(summary.status);

  summaryList.innerHTML = [
    summaryItem("文件", result.source?.fileName || "-"),
    summaryItem("调性", key.label || "未知"),
    summaryItem("声部", String(summary.partCount ?? "-")),
    summaryItem("小节", String(summary.measureCount ?? "-")),
    summaryItem("来源", sourceLabel(result)),
    summaryItem("导出", result.omr?.exportedFileName || "-")
  ].join("");

  renderMeasures(result.parts || []);
  renderHarmony(result.harmonyTimeline || [], summary.theory?.cadences || []);
  renderTheoryAnalysis(summary.theory || {});
  renderWarnings(result.warnings || []);
}

function renderTheoryAnalysis(theory) {
  if (!theory) theory = {};
  const container = document.getElementById("theory-analysis");
  if (!container) return;

  const key = theory.key || {};
  const cadences = theory.cadences || [];
  const tonicizations = theory.tonicizations || [];
  const modulations = theory.modulations || [];

  const sections = [];
  sections.push(`<div class="theory-key">推测主调: <strong>${escapeHtml(key.label || "未知")}</strong>${key.correlation ? ` <span class="correlation">可信度 ${(key.correlation * 100).toFixed(1)}%</span>` : ""}</div>`);

  if (cadences.length) {
    sections.push(`<div class="theory-section">
      <h4>终止式 (${cadences.length})</h4>
      <ul class="cadence-list">
        ${cadences.map((c) => `<li><span class="cadence-tag cadence-${c.type.toLowerCase()}">${escapeHtml(c.type)}</span> 第 ${c.measure} 小节第 ${c.beat} 拍 · <code>${escapeHtml(c.from || "?")} → ${escapeHtml(c.to || "?")}</code> · ${escapeHtml(c.label || "")}${c.reason ? ` <small>(${escapeHtml(c.reason)})</small>` : ""}</li>`).join("")}
      </ul>
    </div>`);
  }

  if (tonicizations.length) {
    sections.push(`<div class="theory-section">
      <h4>离调 / 临时主 (${tonicizations.length})</h4>
      <ul class="tonicization-list">
        ${tonicizations.map((t) => `<li>第 ${t.measure} 小节: <code>${escapeHtml(t.dominant || "?")} → ${escapeHtml(t.target || "?")}</code> (临时主音 ${escapeHtml(t.targetRoot || "")})</li>`).join("")}
      </ul>
    </div>`);
  }

  if (modulations.length) {
    sections.push(`<div class="theory-section">
      <h4>转调段落 (${modulations.length})</h4>
      <ul class="modulation-list">
        ${modulations.map((m) => `<li>第 ${m.fromMeasure} - ${m.toMeasure} 小节: 转入 <strong>${escapeHtml(m.newKey || "?")}</strong> (持续 ${m.duration} 小节)</li>`).join("")}
      </ul>
    </div>`);
  }

  container.innerHTML = sections.join("") || "<div class=\"empty\">无和声分析数据</div>";
}

function renderFourPartAnswer(result) {
  try {
  const answer = result.fourPart || {};
  const voices = answer.voices || [];
  // fourPartStatus.textContent 已经在 submitFourPartAnswer 里设好了
  // (sposobin-solver / 失败), 这里只负责"是否能套用", 不要覆盖.
  if (applyFourPartButton) applyFourPartButton.disabled = !voices.length;

  const warningMeasures = new Set();
  (result.warnings || []).forEach((line) => {
    const match = String(line).match(/第 (\d+) 小节/);
    if (match) warningMeasures.add(Number(match[1]));
  });

  // P18.6: server 端 schema 是 [{measure, harmonies: [{offset, beat, ...}]}],
  // 前端要解嵌套拿到每个 beat 的 chord.  防御性: 如果 server 给的是扁平
  // 旧 schema 也能跑.
  const flatHarmonies = (answer.harmonies || []).flatMap((item) => {
    if (!item) return [];
    if (Array.isArray(item.harmonies)) {
      return item.harmonies.map((h) => ({
        measure: item.measure,
        beat: (h.offset || 0) + 1,
        offset: h.offset,
        duration: h.duration,
        romanNumeral: h.romanNumeral,
        commonName: h.commonName,
        root: h.root,
        function: h.function,
        pitches: h.pitches,
        pitchClasses: h.pitchClasses,
      }));
    }
    return [item];
  });

  renderFourPartScore(
    voices,
    answer.timeSignature || editorTime.value,
    flatHarmonies,
    result.summary?.cadence || "",
    warningMeasures
  );

  const harmonyRows = flatHarmonies.map((item) => (
    `<div class="answer-row"><strong>第 ${escapeHtml(item.measure)} 小节第 ${escapeHtml(item.beat)} 拍：${escapeHtml(item.romanNumeral || item.commonName || "?")} / ${escapeHtml(item.function || "")}</strong><p>${escapeHtml((item.pitches || []).join(" "))}</p></div>`
  ));
  const explanationRows = (answer.explanation || []).map((line) => (
    `<div class="answer-row"><strong>说明</strong><p>${escapeHtml(line)}</p></div>`
  ));
  const warningRows = (result.warnings || []).map((line) => (
    `<div class="warning-row">${escapeHtml(line)}</div>`
  ));

  // P18.5: 置信度 0-100% + 依据列表. 这是用户要的"百分比依据".
  // summary.confidence + summary.confidenceEvidence 来自 solver (P18.5).
  const summary = result.summary || {};
  const confidence = summary.confidence;
  const evidence = summary.confidenceEvidence || [];
  let confidenceBlock = "";
  if (typeof confidence === "number") {
    const pct = Math.max(0, Math.min(100, confidence));
    const tier = pct >= 80 ? "high" : pct >= 50 ? "mid" : "low";
    const tierLabel = pct >= 80 ? "高" : pct >= 50 ? "中" : "低";
    const evidenceList = evidence.map((e) => `<li>${escapeHtml(e)}</li>`).join("");
    confidenceBlock = `<div class="confidence-block tier-${tier}">
      <div class="confidence-headline">
        <strong>置信度</strong>
        <span class="confidence-percent">${pct}%</span>
        <span class="confidence-tier">${tierLabel}</span>
      </div>
      <ul class="confidence-evidence">${evidenceList}</ul>
    </div>`;
  }

  fourPartDetails.className = "answer-details";
  fourPartDetails.innerHTML = [confidenceBlock, ...harmonyRows, ...explanationRows, ...warningRows].filter(Boolean).join("") || "没有生成文字说明。";
  } catch (err) {
    // P18.6: 任何内部错误都不让用户看到 "list index out of range" 这种
    // Python 风格错误, 改成中文提示 + 让用户刷新或重试.
    console.error("[renderFourPartAnswer] crashed", err, err?.stack);
    const msg = `四部和声参考答案渲染失败: ${err && err.message ? err.message : "未知错误"}. 请刷新页面重试.`;
    fourPartDetails.className = "answer-details";
    fourPartDetails.innerHTML = `<div class="warning-row">${escapeHtml(msg)}</div>`;
    if (applyFourPartButton) applyFourPartButton.disabled = true;
  }
  // P19: solver 成功后启用 AI 讲解按钮
  if (aiExplainButton) {
    const voices = (result.fourPart || {}).voices || [];
    aiExplainButton.disabled = voices.length === 0;
  }
}

// P19: AI 教师讲解
function _extractMeasureVoicesForExplain(result) {
  // 把 solver 输出的 harmonies 转成 explain 端点期望的 shape:
  //   measures[i] = { chord, voices: { S, A, T, B: [pitch,...] } }
  const answer = result.fourPart || {};
  const flatHarmonies = (answer.harmonies || []).flatMap((item) => {
    if (!item) return [];
    if (Array.isArray(item.harmories)) return [];
    if (Array.isArray(item.harmonies)) {
      return item.harmonies.map((h) => ({
        measure: item.measure,
        chord: h.romanNumeral || h.commonName,
        pitches: h.pitches || [],
      }));
    }
    return [{
      measure: item.measure,
      chord: item.romanNumeral || item.commonName,
      pitches: item.pitches || [],
    }];
  });
  // 按小节号聚合
  const byMeasure = new Map();
  for (const h of flatHarmonies) {
    if (!h.chord) continue;
    const m = h.measure || 1;
    if (!byMeasure.has(m)) byMeasure.set(m, { chord: h.chord, voicePitches: { S: [], A: [], T: [], B: [] } });
    // h.pitches = [soprano, alto, tenor, bass] 来自 server 端 _solver_to_four_part_response
    const labels = ["S", "A", "T", "B"];
    for (let i = 0; i < labels.length && i < h.pitches.length; i += 1) {
      byMeasure.get(m).voicePitches[labels[i]].push(h.pitches[i]);
    }
  }
  return Array.from(byMeasure.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([m, info]) => ({
      chord: info.chord,
      voices: info.voicePitches,
    }));
}

function _simpleMarkdownToHtml(text) {
  if (!text) return "";
  // 简易 markdown → HTML（只处理 AI 讲解用到的: ## / ** / `code` / 段落）
  // 安全: 先 escape, 再做有限替换, 不解析任意 HTML.
  let s = escapeHtml(text);
  // 代码块 `xxx` -> <code>xxx</code>
  s = s.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  // 粗体 **xxx** -> <strong>xxx</strong>  (非贪婪)
  s = s.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  // 二级标题 ## xxx -> <h2>xxx</h2>
  s = s.replace(/^##\s+(.+)$/gm, "<h2>$1</h2>");
  // 把连续换行拆成段
  const paragraphs = s.split(/\n{2,}/);
  return paragraphs
    .map((p) => {
      if (p.startsWith("<h2>")) return p;
      // 把单换行变 <br>
      const withBr = p.replace(/\n/g, "<br>");
      return `<p>${withBr}</p>`;
    })
    .join("\n");
}

async function requestAIExplanation() {
  if (!lastFourPartResult) {
    if (aiExplanationPanel) aiExplanationPanel.hidden = false;
    if (aiExplanationBody) {
      aiExplanationBody.innerHTML = `<p>请先生成四部和声参考答案，再点 AI 讲解。</p>`;
    }
    if (aiExplanationMeta) aiExplanationMeta.textContent = "";
    if (aiExplanationRules) aiExplanationRules.innerHTML = "";
    return;
  }

  const result = lastFourPartResult;
  const summary = result.summary || {};
  const key = summary.analyzedKey?.label || summary.key || (editorKey?.value || "C") + " major";
  const time = (result.fourPart || {}).timeSignature || editorTime?.value || "4/4";
  const measures = _extractMeasureVoicesForExplain(result);
  const cadences = summary.cadences || [];

  if (!measures.length) {
    if (aiExplanationPanel) aiExplanationPanel.hidden = false;
    if (aiExplanationBody) aiExplanationBody.innerHTML = `<p>没有可讲解的和声数据。</p>`;
    return;
  }

  // 锁住按钮
  if (aiExplainButton) {
    aiExplainButton.disabled = true;
    aiExplainButton.textContent = "🧠 讲解中…";
  }
  if (aiExplanationPanel) aiExplanationPanel.hidden = false;
  if (aiExplanationBody) {
    aiExplanationBody.innerHTML = `<p>正在调用 DeepSeek (sposobin-solver → RAG → 4o-mini) 生成讲解…</p>`;
  }
  if (aiExplanationMeta) aiExplanationMeta.textContent = "";
  if (aiExplanationRules) aiExplanationRules.innerHTML = "";

  // 组装请求
  const body = {
    key,
    timeSignature: time,
    keyChanges: keyChangesInput?.value ? parseKeyChanges(keyChangesInput.value) : null,
    measures,
    cadences,
    confidence: summary.confidence ?? null,
    score: summary.score ?? null,
    algorithm: "sposobin-solver",
  };

  let resp;
  try {
    resp = await fetch("/api/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    if (aiExplanationBody) {
      aiExplanationBody.innerHTML = `<p>无法连接服务器 (8765)。请确认后端已启动。</p>`;
    }
    if (aiExplainButton) {
      aiExplainButton.disabled = false;
      aiExplainButton.textContent = "🧠 AI 讲解";
    }
    return;
  }

  let data;
  try {
    data = await resp.json();
  } catch (e) {
    if (aiExplanationBody) {
      aiExplanationBody.innerHTML = `<p>服务器返回格式异常（HTTP ${resp.status}）。</p>`;
    }
    if (aiExplainButton) {
      aiExplainButton.disabled = false;
      aiExplainButton.textContent = "🧠 AI 讲解";
    }
    return;
  }

  if (data.error || !data.explanation) {
    if (aiExplanationBody) {
      aiExplanationBody.innerHTML = `<p>AI 讲解失败：${escapeHtml(data.error || "空响应")}</p>`;
    }
  } else {
    if (aiExplanationBody) {
      aiExplanationBody.innerHTML = _simpleMarkdownToHtml(data.explanation);
    }
  }
  if (aiExplanationMeta) {
    const model = data.model || "deepseek-chat";
    const rules = (data.rulesUsed || []).length;
    aiExplanationMeta.textContent = `模型: ${escapeHtml(model)} · 引用 RAG 规则 ${rules} 条`;
  }
  if (aiExplanationRules) {
    const rules = data.rulesUsed || [];
    if (rules.length) {
      aiExplanationRules.innerHTML = "引用规则: " + rules
        .map((r) => `<span class="rule-chip">${escapeHtml(r)}</span>`)
        .join("");
    } else {
      aiExplanationRules.innerHTML = "";
    }
  }
  if (aiExplainButton) {
    aiExplainButton.disabled = false;
    aiExplainButton.textContent = "🧠 AI 讲解";
  }
}

function parseKeyChanges(text) {
  // 解析 "2→G | 4→a" -> [[1, "G"], [3, "a"]]  (0-indexed measure)
  if (!text) return null;
  const parts = String(text).split("|").map((s) => s.trim()).filter(Boolean);
  const out = [];
  for (const p of parts) {
    const m = p.match(/^(\d+)\s*[→\->]\s*([A-Ga-g][#b]?)\s*(m|minor)?/);
    if (m) {
      const idx = Math.max(0, parseInt(m[1], 10) - 1);
      let key = m[2];
      if (m[3] === "m" || m[3] === "minor") key = key.toLowerCase();
      out.push([idx, key]);
    }
  }
  return out.length ? out : null;
}

function renderFourPartScore(voices, timeSignature, harmonies = [], cadence = "", warningMeasures = []) {
  try {
  fourPartCanvas.replaceChildren();

  if (!VF) {
    fourPartCanvas.textContent = "制谱引擎未加载。";
    fourPartCanvas.classList.add("notation-error");
    return;
  }

  fourPartCanvas.classList.remove("notation-error");
  const width = Math.max(720, Math.floor(fourPartCanvas.parentElement.clientWidth - 2));
  const measureCount = Math.max(1, ...voices.map((voice) => (voice.measures || []).length));
  const rowHeight = 84;
  const systemHeight = voices.length * rowHeight + 34;
  const height = Math.max(130, measureCount * systemHeight + 38);
  fourPartCanvas.style.width = `${width}px`;
  fourPartCanvas.style.height = `${height}px`;

  const renderer = new VF.Renderer(fourPartCanvas, VF.Renderer.Backends.SVG);
  renderer.resize(width, height);
  const context = renderer.getContext();
  const usableWidth = Math.max(360, width - 170);
  const meter = meterForTimeSignature(timeSignature);
  const keySpec = keySpecFromLabel(manualKey.value);
  const sopranoNoteXs = [];

  for (let measureIndex = 0; measureIndex < measureCount; measureIndex += 1) {
    let sopranoNotes = null;
    voices.forEach((voiceData, voiceIndex) => {
      const y = 28 + measureIndex * systemHeight + voiceIndex * rowHeight;
      const stave = new VF.Stave(72, y, width - 96);
      stave.addClef(voiceData.clef || "treble");
      if (measureIndex === 0 && voiceIndex === 0 && keySpec) stave.addKeySignature(keySpec);
      if (voiceIndex === 0) stave.addTimeSignature(timeSignature);
      stave.setContext(context).draw();

      const hasMeasureData = Array.isArray(voiceData.measures);
      const entries = hasMeasureData ? (voiceData.measures[measureIndex]?.entries || []) : (voiceData.entries || []);
      const notes = entries.map((entry) => createVexNote(entry, voiceData.clef || "treble", timeSignature));
      if (!notes.length) return;
      if (voiceData.id === "soprano") sopranoNotes = notes;
      const voice = new VF.Voice({ numBeats: meter.numerator, beatValue: meter.denominator });
      voice.setMode(VF.Voice.Mode.SOFT);
      voice.addTickables(notes);
      VF.Accidental.applyAccidentals([voice], "C");
      const beams = VF.Beam.generateBeams(notes, {
        groups: VF.Beam.getDefaultBeamGroups(timeSignature)
      });
      new VF.Formatter().joinVoices([voice]).format([voice], usableWidth);
      voice.draw(context, stave);
      beams.forEach((beam) => beam.setContext(context).draw());
    });
    sopranoNoteXs.push(sopranoNotes ? sopranoNotes.map((note) => note.getAbsoluteX()) : []);
  }

  const svg = fourPartCanvas.querySelector("svg");
  for (let measureIndex = 0; measureIndex < measureCount; measureIndex += 1) {
    voices.forEach((voiceData, voiceIndex) => {
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", "18");
      label.setAttribute("y", String(58 + measureIndex * systemHeight + voiceIndex * rowHeight));
      label.setAttribute("fill", "#24332c");
      label.setAttribute("font-size", "13");
      label.setAttribute("font-weight", "700");
      label.textContent = voiceData.name || `Voice ${voiceIndex + 1}`;
      svg?.append(label);
    });
    const measureLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    measureLabel.setAttribute("x", "72");
    measureLabel.setAttribute("y", String(20 + measureIndex * systemHeight));
    measureLabel.setAttribute("fill", "#607065");
    measureLabel.setAttribute("font-size", "12");
    measureLabel.textContent = `第 ${measureIndex + 1} 小节`;
    svg?.append(measureLabel);

    // 和声标注：罗马数字标在 Soprano 谱表上方
    const topY = 28 + measureIndex * systemHeight;
    const measureHarmonies = harmonies.filter((item) => item.measure === measureIndex + 1);
    const xs = sopranoNoteXs[measureIndex] || [];
    measureHarmonies.forEach((item) => {
      const x = xs[item.beat - 1] ?? (100 + (item.beat - 1) * 42);
      const el = document.createElementNS("http://www.w3.org/2000/svg", "text");
      el.setAttribute("x", String(x));
      el.setAttribute("y", String(topY - 12));
      el.setAttribute("text-anchor", "middle");
      el.setAttribute("fill", "#b4452a");
      el.setAttribute("font-size", "13");
      el.setAttribute("font-weight", "800");
      el.textContent = item.romanNumeral || item.root || "";
      svg?.append(el);
    });

    // 终止式：最后一个小节上方
    if (cadence && measureIndex === measureCount - 1) {
      const el = document.createElementNS("http://www.w3.org/2000/svg", "text");
      el.setAttribute("x", "72");
      el.setAttribute("y", String(topY - 30));
      el.setAttribute("fill", "#1f7a56");
      el.setAttribute("font-size", "13");
      el.setAttribute("font-weight", "800");
      el.textContent = `终止式：${cadence}`;
      svg?.append(el);
    }

    // 斯波索宾警告小节：右上角红点
    if (warningMeasures.has(measureIndex + 1)) {
      const el = document.createElementNS("http://www.w3.org/2000/svg", "text");
      el.setAttribute("x", String(width - 60));
      el.setAttribute("y", String(topY - 12));
      el.setAttribute("fill", "#c0392b");
      el.setAttribute("font-size", "15");
      el.setAttribute("font-weight", "800");
      el.textContent = "⚠";
      svg?.append(el);
    }
  }
  } catch (err) {
    // P18.6: 制谱失败也不让用户看到内部错误, 给一个友好提示.
    console.error("[renderFourPartScore] crashed", err);
    fourPartCanvas.replaceChildren();
    fourPartCanvas.textContent = "五线谱渲染失败, 请刷新页面重试.";
    fourPartCanvas.classList.add("notation-error");
  }
}

function applyFourPartAnswerToEditor() {
  const answer = lastFourPartResult?.fourPart;
  const voices = answer?.voices || [];
  if (!voices.length) {
    fourPartStatus.textContent = "暂无可套用答案";
    return;
  }

  const roleTargets = {
    soprano: { staff: "treble", voice: "1" },
    alto: { staff: "treble", voice: "2" },
    tenor: { staff: "bass", voice: "1" },
    bass: { staff: "bass", voice: "2" }
  };
  const measureCount = Math.max(1, ...voices.map((voice) => (voice.measures || []).length));

  staffMode.value = "piano";
  editorTime.value = answer.timeSignature || editorTime.value;
  previousTimeSignature = editorTime.value;
  staffScores.treble.measures = Array.from({ length: measureCount }, () => []);
  staffScores.treble.settings = Array.from({ length: measureCount }, defaultMeasureSettings);
  staffScores.bass.measures = Array.from({ length: measureCount }, () => []);
  staffScores.bass.settings = Array.from({ length: measureCount }, defaultMeasureSettings);

  voices.forEach((voiceData) => {
    const target = roleTargets[voiceData.id];
    if (!target) return;
    (voiceData.measures || []).forEach((measure, measureIndex) => {
      const targetMeasure = staffScores[target.staff].measures[measureIndex];
      (measure.entries || []).forEach((entry) => {
        targetMeasure.push(normalizeAnswerEntryForEditor(entry, target.voice));
      });
    });
  });

  currentMeasureIndex = 0;
  noteMeasure.value = "1";
  noteClef.value = "treble";
  voiceSelect.value = "1";
  activateStaff("treble");
  selectLastEntryInActiveVoice();
  editHistory = [];
  renderNotation();
  showEditorMessage("四部和声答案已套用到钢琴双谱表，可继续编辑和导出。", "success");
  fourPartStatus.textContent = "已套用";
}

function normalizeAnswerEntryForEditor(entry, voiceId) {
  const base = {
    kind: entry.kind || "note",
    voice: voiceId,
    duration: String(entry.duration || "4"),
    dotted: dotCount(entry.dotted),
    units: Number.isFinite(entry.units) ? entry.units : unitsForDuration(String(entry.duration || "4"), dotCount(entry.dotted)),
    tieStart: Boolean(entry.tieStart),
    tieStop: Boolean(entry.tieStop),
    slurStart: Boolean(entry.slurStart),
    slurStop: Boolean(entry.slurStop),
    fermata: Boolean(entry.fermata),
    dynamic: entry.dynamic || "",
    tupletType: entry.tupletType || "",
    tupletGroup: entry.tupletGroup || "",
    tupletPosition: entry.tupletPosition || ""
  };

  if (base.kind === "rest") return base;
  return {
    ...base,
    pitches: sortPitches((entry.pitches || []).map((pitch) => ({
      step: pitch.step,
      octave: Number(pitch.octave),
      accidental: pitch.accidental || "",
      display: pitch.display || `${pitch.step}${displayAccidental(pitch.accidental || "")}${pitch.octave}`
    })))
  };
}

function readableStatus(status) {
  return {
    readable: "可读取",
    readable_with_warnings: "需校正",
    manual: "手动输入",
    manual_notes: "手动音符"
  }[status] || status || "可读取";
}

function sourceLabel(result) {
  if (result.omr) return `OMR：${result.omr.engine}`;
  if (result.manual) return "手动和弦";
  return "结构化文件";
}

function renderMeasures(parts) {
  if (!parts.length) {
    measurePreview.className = "measure-preview empty";
    measurePreview.textContent = "没有读到声部。";
    return;
  }

  measurePreview.className = "measure-preview";
  measurePreview.innerHTML = parts.map((part) => {
    const measures = (part.measures || []).slice(0, 12);
    const lines = measures.map((measure) => {
      const time = measure.timeSignature?.ratio || "未知";
      const keyName = measure.keySignature?.majorName || "";
      const events = previewEvents(measure.events || []);
      const keyText = keyName ? ` · 调号 ${escapeHtml(keyName)}` : "";
      return `<div class="measure-line">第 ${measure.number} 小节 · ${time}${keyText} · ${escapeHtml(events)}</div>`;
    }).join("");
    return `<div class="part-block"><strong>${escapeHtml(part.name || "Part")}</strong>${lines}</div>`;
  }).join("");
}

function renderHarmony(timeline, cadences = []) {
  if (!timeline.length) {
    harmonyPreview.className = "harmony-preview empty";
    harmonyPreview.textContent = "没有生成纵向和声。";
    return;
  }

  // 把终止式按 (measure, beat) 索引, 渲染时给所在小节打标记
  const cadenceByMeasure = new Map();
  for (const c of cadences) {
    if (!cadenceByMeasure.has(c.measure)) cadenceByMeasure.set(c.measure, []);
    cadenceByMeasure.get(c.measure).push(c);
  }

  harmonyPreview.className = "harmony-preview";
  harmonyPreview.innerHTML = timeline.slice(0, 16).map((item) => {
    const harmonies = (item.harmonies || []).slice(0, 8).map((harmony) => {
      return renderHarmonyToken(harmony);
    }).join(" ");
    const cads = cadenceByMeasure.get(item.measure) || [];
    const cadenceMark = cads.length
      ? cads.map((c) => `<span class="cadence-tag cadence-${c.type.toLowerCase()}" title="${escapeHtml(c.label || c.type)}">${escapeHtml(c.type)}</span>`).join(" ")
      : "";
    return `<div class="harmony-row">
      <strong>第 ${item.measure} 小节${item.timeSignature ? ` <span class="ts-tag">${escapeHtml(item.timeSignature)}</span>` : ""}</strong>
      <div class="harmony-line">${harmonies || "无"}</div>
      ${cadenceMark ? `<div class="cadence-marks">${cadenceMark}</div>` : ""}
    </div>`;
  }).join("");
}

function renderHarmonyToken(harmony) {
  if (!harmony || !harmony.figure) {
    return `<span class="harmony-token none">?</span>`;
  }
  const fn = harmony.function || "";
  const role = harmony.role || "";
  const inv = harmony.inversion || "";
  const fig = escapeHtml(harmony.figure);
  // 转位上标: 6 / 6/4 / 6/5 / 4/3 / 4/2
  const invSup = inv ? `<sup class="inversion-sup">${escapeHtml(inv)}</sup>` : "";
  // 功能颜色 class
  const fnClass = fn ? `fn-${fn.toLowerCase()}` : "fn-unknown";
  // 副属/借用 badge
  let badge = "";
  if (harmony.isSecondary) {
    badge = ` <span class="badge badge-secondary" title="副属和弦, 解决到 ${escapeHtml(harmony.secondaryOf || "?")}">→${escapeHtml(harmony.secondaryOf || "?")}</span>`;
  } else if (harmony.isBorrowed) {
    badge = ` <span class="badge badge-borrowed" title="调式交替(借用)和弦">借</span>`;
  }
  // 角色(中文)标记
  const roleLabel = role && role !== "primary" ? `<small class="role-label">${escapeHtml(role)}</small>` : "";
  // 七和弦标记
  const seventhMark = harmony.isSeventh ? `<span class="seventh-mark">7</span>` : "";
  // 置信度低
  const conf = harmony.confidence === "low" ? ` <span class="low-conf" title="置信度低">⚠</span>` : "";
  return `<span class="harmony-token ${fnClass}">${fig}${invSup}${seventhMark}${roleLabel}${badge}${conf}</span>`;
}

function renderWarnings(warnings) {
  if (!warnings.length) {
    warningList.className = "warning-list empty";
    warningList.textContent = "没有发现基础校验警告。";
    return;
  }
  warningList.className = "warning-list";
  warningList.innerHTML = warnings.map((warning) => `<div class="warning-row">${escapeHtml(warning)}</div>`).join("");
}

function previewEvents(events) {
  if (!events.length) return "无事件";
  return events.slice(0, 8).map((event) => {
    if (event.type === "note") return event.pitch;
    if (event.type === "chord") return event.pitches.join("+");
    if (event.type === "chordSymbol") return `${event.symbol}${event.romanNumeral ? ` (${event.romanNumeral})` : ""}`;
    return "休止";
  }).join("，");
}

function summaryItem(label, value) {
  return `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function currentMeter() {
  return meterForTimeSignature(editorTime.value);
}

function meterForTimeSignature(timeSignature) {
  const [numerator, denominator] = timeSignature.split("/").map(Number);
  return {
    numerator,
    denominator,
    capacity: numerator * (32 / denominator),
    beatUnit: 32 / denominator
  };
}

const keyFifths = {
  C: 0, "C#": 7, Cb: -7,
  D: 2, Db: -5,
  E: 4, Eb: -3,
  F: -1, "F#": 6,
  G: 1, Gb: -6,
  A: 3, Ab: -4,
  B: 5, Bb: -2,
  Am: 0, "A#m": 7, Abm: -7,
  Em: 1, Ebm: -6,
  Bm: 2, Bbm: -5,
  "F#m": 3,
  "C#m": 4,
  "G#m": 5,
  "D#m": 6,
  Dm: -1,
  Gm: -2,
  Cm: -3,
  Fm: -4
};

function keySpecFromLabel(label) {
  const text = String(label || "").trim().replace("♭", "b").replace("♯", "#");
  const match = /^([A-Ga-g])([#b]?)(.*)$/.exec(text);
  if (!match) return null;
  const step = match[1].toUpperCase();
  const accidental = match[2] === "b" ? "b" : match[2] === "#" ? "#" : "";
  const rest = match[3].trim().toLowerCase();
  const isMinor = rest.includes("minor") || rest === "m";
  const spec = step + accidental + (isMinor ? "m" : "");
  return keyFifths[spec] !== undefined ? spec : null;
}

function dotCount(value) {
  return value === true ? 1 : Number(value) || 0;
}

function selectedDotCount() {
  // P22.3 duration-cleanup: 唯一 source of truth = editorState
  // editorState 不存在 / 没初始化时调一次 syncFromUI() 让 UI 状态流入 editorState,
  // 然后再读 editorState.currentInputDuration.dotted —— 业务不再读 DOM
  if (typeof editorState === "undefined" || !editorState) return 0;
  if (!editorState.currentInputDuration ||
      typeof editorState.currentInputDuration.dotted !== "number") {
    // editorState 还没被任何 sync 入口填过, 主动从 UI 同步一次
    if (typeof editorState.syncFromUI === "function") {
      editorState.syncFromUI();
    }
  }
  return editorState.currentInputDuration?.dotted ?? 0;
}

function unitsForDuration(duration, dotted) {
  const base = durationUnits[duration];
  const dots = dotCount(dotted);
  return dots === 2 ? base * 1.75 : dots === 1 ? base * 1.5 : base;
}

function unitsForEntry(entry) {
  const baseUnits = unitsForDuration(entry.duration, entry.dotted);
  const ratio = tupletRatios[entry.tupletType];
  return ratio ? baseUnits * (ratio.notesOccupied / ratio.totalNotes) : baseUnits;
}

function sumEntryUnits(entries = measureEntries) {
  return normalizeUnitValue(entries.reduce((total, entry) => total + (Number.isFinite(entry.units) ? entry.units : unitsForEntry(entry)), 0));
}

function sumCurrentVoiceUnits() {
  return sumEntryUnits(currentVoiceEntries());
}

function normalizeUnitValue(value) {
  return Number(value.toFixed(3));
}

function sameUnitValue(left, right) {
  return Math.abs(left - right) < 0.001;
}

function exceedsUnitValue(left, right) {
  return left - right > 0.001;
}

function inputKind() {
  return document.querySelector('input[name="inputKind"]:checked')?.value || "note";
}

function entryMode() {
  return document.querySelector('input[name="entryMode"]:checked')?.value || "new";
}

function addEntryFromScore(event) {
  try {
    return addEntryFromScoreInner(event);
  } catch (e) {
    handleRenderError(e);
    showEditorMessage("输入音符失败：" + (e?.message || e), "error");
  }
}

// P22+: 统一点击解析 — 根据 (x, y) 决定命中哪个 staff / measure / geometry.
// P22.4-B.3 批次 1: 业务侧用 cs.staffAtPoint, 内部根据 measureRects 是否有 staveKey 字段自动切单/双谱
// 单谱模式: cs 返回 staveKey='active', 这里包一层换成 activeStaffKey() ('treble' | 'bass')
// 双谱模式: cs 返回 staveKey='treble' | 'bass', 直接透传
function resolveStaffAtPoint(x, y) {
  const hit = cs.staffAtPoint(x, y);
  if (!hit) return null;
  if (hit.staveKey === "active") hit.staveKey = activeStaffKey();
  return hit;
}

function addEntryFromScoreInner(event) {
  // P22.4-B.3 批次 1: viewportToCanvas 替代内联 getBoundingClientRect 公式
  const { x, y } = cs.viewportToCanvas(event, noteCanvas);

  // P22+: 统一点击解析 — 不再直接查 measureRects, 用 resolveStaffAtPoint
  const resolved = resolveStaffAtPoint(x, y);
  if (!resolved || !resolved.geometry) return;
  const { staveKey, geometry, measureRect } = resolved;

  // 点击非当前小节（prev 或 next）→ 切换 current
  if (measureRect.index !== currentMeasureIndex) {
    switchToMeasure(measureRect.index);
    return;
  }

  // P22.4-B.3 批次 2: localX 公式 + 越界走 cs.canvasToStave / cs.isInNoteRange
  const { localX } = cs.canvasToStave(x, y, geometry);
  if (!cs.isInNoteRange(localX, geometry)) {
    return;
  }

  // P22.3 duration-cleanup: business 统一从 editorState 读，不直接读 UI select
  const esDur = editorState.getInputDuration();
  const duration = esDur.duration;
  const dotted = esDur.dotted;
  const units = esDur.units;
  const used = sumCurrentVoiceUnits();
  const { capacity } = currentMeter();

  if (inputKind() === "rest") {
    // P22.4-B.3 批次 4: capacity check 走 cs.exceedsUnits (替代 exceedsUnitValue)
    if (cs.exceedsUnits(used + units, capacity)) {
      showEditorMessage("该休止符会超过本小节拍数。", "error");
      return;
    }
    commitEdit(() => {
      measureEntries.push({
        kind: "rest",
        voice: activeVoiceId(),
        duration,
        dotted,
        units,
        fermata: false,
        tupletType: "",
        tupletGroup: "",
        tupletPosition: "",
        dynamic: ""
      });
      selectedEntryIndex = measureEntries.length - 1;
    });
    // P22.4-B.3 批次 4: 写满判定走 cs.sameUnits (替代 0.001 magic + exceedsUnitValue)
    if (cs.sameUnits(used + units, capacity)) {
      if (typeof addMeasure === "function" && scoreMeasures.length < MAX_MEASURE_COUNT) {
        editorState.clearPreview();
        clearGhostNote();
        addMeasure(true);
        return;
      }
    }
    // P22.3 Phase 4: commit 后清 ghost (避免重叠 / 残留)
    editorState.clearPreview();
    clearGhostNote();
    return;
  }

  // P22.4-B.3 批次 2: localY 公式 + 越界走 cs (pitchFromY 在下面还要用 localY)
  const { localY } = cs.canvasToStave(x, y, geometry);
  if (!cs.isInPitchRange(localY, geometry)) return;
  // P22+: pitchFromY 接受当前命中 stave 的 clef + geometry, 不再读全局
  // P22.3 duration-cleanup: 从 editorState 读 accidental，不直接读 noteAccidental.value
  const pitch = createPitch(pitchFromY(localY, staveKey, geometry), editorState.getInputAccidental());

  if (entryMode() === "chord") {
    const target = measureEntries[selectedEntryIndex];
    if (!target || target.kind !== "note" || entryVoice(target) !== activeVoiceId()) {
      showEditorMessage("请先选择一个音符拍位，再叠加和弦音。", "error");
      return;
    }
    if (target.pitches.some((item) => pitchIdentity(item) === pitchIdentity(pitch))) {
      showEditorMessage("当前和弦已经包含这个音高。", "error");
      return;
    }
    commitEdit(() => {
      target.pitches.push(pitch);
      target.pitches = sortPitches(target.pitches);
    });
    // P22.3 Phase 4: chord 模式 commit 后也清 ghost
    editorState.clearPreview();
    clearGhostNote();
    showEditorMessage(`当前和弦包含 ${target.pitches.length} 个音。`, "success");
    return;
  }

  // P22.4-B.3 批次 4: capacity check 走 cs.exceedsUnits (替代 exceedsUnitValue)
  if (cs.exceedsUnits(used + units, capacity)) {
    showEditorMessage("该时值会超过本小节拍数，请缩短时值或撤销已有音符。", "error");
    return;
  }

  commitEdit(() => {
    measureEntries.push({
      kind: "note",
      voice: activeVoiceId(),
      pitches: [pitch],
      duration,
      dotted,
      units,
      tieStart: false,
      tieStop: false,
      slurStart: false,
      slurStop: false,
      fermata: false,
      tupletType: "",
      tupletGroup: "",
      tupletPosition: "",
      dynamic: ""
    });
    selectedEntryIndex = measureEntries.length - 1;
  });
  // P22.4-B.3 批次 4: 写满判定走 cs.sameUnits (替代 0.001 magic + exceedsUnitValue)
  // 4/4 写满 4 quarter 后自动 addMeasure(true) 进入下一小节
  if (cs.sameUnits(used + units, capacity)) {
    // 容量用完: 自动加新小节 + 切过去
    if (typeof addMeasure === "function" && scoreMeasures.length < MAX_MEASURE_COUNT) {
      editorState.clearPreview();
      clearGhostNote();
      addMeasure(true);
      return;
    }
  }
  // P22.3 Phase 4: commit 后清 ghost
  editorState.clearPreview();
  clearGhostNote();
}

function createPitch(pitch, accidental = "") {
  return {
    ...pitch,
    accidental,
    display: `${pitch.step}${displayAccidental(accidental)}${pitch.octave}`
  };
}

function pitchIdentity(pitch) {
  const accidental = pitch.accidental === "n" ? "" : pitch.accidental || "";
  return `${pitch.step}${accidental}${pitch.octave}`;
}

function sortPitches(pitches) {
  return [...pitches].sort((left, right) => {
    const leftIndex = Number(left.octave) * 7 + stepIndex[left.step];
    const rightIndex = Number(right.octave) * 7 + stepIndex[right.step];
    if (leftIndex !== rightIndex) return leftIndex - rightIndex;
    return pitchIdentity(left).localeCompare(pitchIdentity(right));
  });
}

function pitchFromY(y, clef, geometry) {
  // P22.4-B.4: 内部实现走 cs.localYToPitch (与原公式 1:1 等价, 含 halfStep || 1 防御)
  // P22+: caller passes the relevant clef and geometry, no globals read.
  if (!clef || !geometry) return { step: "C", octave: 4 };
  return cs.localYToPitch(y, clef, geometry);
}

// P22.4-B.4: diatonicIndex 移入 cs.js (顶层函数) — app.js 唯一 caller 是原 pitchFromY, 现已走 cs.localYToPitch

function renderNotation() {
  try {
    activateStaff();
    updateEditorControls();
    updateMeasureMeter();
  } catch (error) {
    // 控件同步失败不能让 VexFlow 渲染挂掉。P18.8 之前 updateEditorControls 在 try/catch
    // 之外抛错（比如某个 inspector 字段 findEl 是 null）→ 整个 renderNotation throw
    // → noteCanvas 被 replaceChildren 清空但用户看不到任何错误消息。
    console.error("[renderNotation:preamble]", error);
    showEditorMessage(`画布初始化失败：${error?.message || error}`, "error");
  }
  noteCanvas.replaceChildren();

  if (!VF) {
    noteCanvas.textContent = "制谱引擎未加载。";
    noteCanvas.classList.add("notation-error");
    return;
  }

  // 任何 VexFlow 异常都不能让 canvas 保持半渲染状态。
  // 整段包 try/catch，失败时给用户友好提示并尝试重新画一次。
  try {
    if (isPianoMode()) {
      renderPianoNotation();
    } else {
      renderSingleNotationSafe();
    }
  } catch (error) {
    handleRenderError(error);
  }
  // P22.5-B.5 — 影子验证: render 末尾跑 Score Model 完整 pipeline
  // 0 侵入: 不参与渲染, 失败只 console.warn — 不能破渲染
  runScoreModelShadow();
}

// P22.5-B.5 — Score Model 影子验证
// 跑 buildScore + buildRelations + validateRelations
// 不参与渲染, 失败只 console.warn
function runScoreModelShadow() {
  if (typeof window === "undefined" || !window.ScoreModel) return;
  const SM = window.ScoreModel;
  try {
    const isPiano = staffMode?.value === "piano";
    const legacy = isPiano
      ? {
          staffScores: {
            treble: { measures: staffScores?.treble?.measures || [] },
            bass: { measures: staffScores?.bass?.measures || [] }
          }
        }
      : {
          scoreMeasures: staffScores?.[activeStaffKey()]?.measures || []
        };
    const score = SM.buildScore(legacy);
    SM.buildRelations(score);
    const v = SM.validateRelations(score);
    if (!v.valid) {
      console.warn("[P22.5-B.5 shadow] validateRelations errors:", v.errors, "warnings:", v.warnings);
    }
  } catch (e) {
    console.warn("[P22.5-B.5 shadow] pipeline failed:", e);
  }
}

function handleRenderError(error) {
  console.error("[renderNotation]", error);
  showEditorMessage(`制谱渲染失败：${error?.message || error}`, "error");
  noteCanvas.replaceChildren();
  noteCanvas.classList.add("notation-error");
  // 异常时清空状态引用，否则下次 addEntryFromScore 会用旧的 measureRects
  // 和 staffGeometry 误判点击位置
  measureRects = [];
  staffGeometry = null;
  selectedEntryIndex = -1;
  // P22.4-B.2: 错误路径清空 cs 内部 layout (避免下次 hover 用旧 geometry)
  if (typeof cs !== "undefined" && cs && cs.clearLayout) cs.clearLayout();
  // 保留外框尺寸，避免布局塌陷
  try {
    const viewportWidth = Math.max(640, Math.floor(scoreViewport.clientWidth - 2));
    noteCanvas.style.width = `${viewportWidth}px`;
    noteCanvas.style.height = `190px`;
  } catch {}
}

function renderSingleNotationSafe() {
  noteCanvas.classList.remove("notation-error");
  const viewportWidth = Math.max(640, Math.floor(scoreViewport.clientWidth - 2));
  const totalMeasures = Math.max(1, scoreMeasures.length);
  const currentIdx = Math.max(0, Math.min(currentMeasureIndex, totalMeasures - 1));

  // P22.3 final — 自动换行: 每行能放几个小节, 全部行都渲染
  // (改: 之前 prev/current/next 3 行窗口会漏 row 0)
  // MIN_SLOT_WIDTH=240 保证 4/4 小节 >= 220px (扣 padding)
  const MIN_SLOT_WIDTH = 240;
  const perRow = Math.max(1, Math.floor(viewportWidth / MIN_SLOT_WIDTH));
  const totalRows = Math.max(1, Math.ceil(totalMeasures / perRow));
  // P22.3 final: 渲染所有行 (不要 prev/current/next 窗口)
  const startRow = 0;
  const endRow = totalRows - 1;

  // 展开成 1D measureIndex 列表 (保留行号 + slot)
  const visibleIndices = [];
  for (let r = startRow; r <= endRow; r += 1) {
    for (let s = 0; s < perRow; s += 1) {
      const idx = r * perRow + s;
      if (idx < totalMeasures) {
        visibleIndices.push({ index: idx, row: r, slot: s });
      }
    }
  }
  const slotWidth = Math.max(MIN_SLOT_WIDTH, Math.floor(viewportWidth / perRow));
  const staveHeight = SINGLE_STAVE_HEIGHT;
  const rowGap = 10;
  const width = viewportWidth;
  const visibleRowCount = endRow - startRow + 1;
  const height = visibleRowCount * (staveHeight + rowGap) + 10;
  noteCanvas.style.width = `${width}px`;
  noteCanvas.style.height = `${height}px`;

  const renderer = new VF.Renderer(noteCanvas, VF.Renderer.Backends.SVG);
  renderer.resize(width, height);
  const context = renderer.getContext();
  const tempo = Number(tempoInput.value) || 0;
  measureRects = [];

  clearMeasureJumpButtons();
  clearGhostNote();

  // P22.5-Symbol-A.3 — 跨音符 draw 收集容器 (per measure 的 notes + stave)
  // 渲染主循环结束后统一画 tie/slur/phrase/hairpin (跨 measure 自动走 fallback)
  const notesByMeasure = new Map();
  const stavesByMeasure = new Map();

  visibleIndices.forEach(({ index: measureIndex, row, slot }) => {
    const isCurrent = measureIndex === currentIdx;
    const rowOffset = (row - startRow) * (staveHeight + rowGap);
    const slotX = slot * slotWidth;
    const w = slotWidth - 8;
    const x = slotX + 4;
    const y = 12 + rowOffset;
    const entries = scoreMeasures[measureIndex] || [];
    const stave = new VF.Stave(x, y, w);
    applyBarlineSettings(stave, measureSettings[measureIndex] || defaultMeasureSettings());

    // P22.3 final — 谱号规则:
    //   - 每个 row 的第一个 slot (slot===0) 才加 clef
    //   - 全局第一个 measure (row 0 / slot 0) 额外加 key/time
    //   - 同一行后续小节: 不加 clef/key/time (避免 VexFlow.getNoteStartX() 右推, 引发 hitbox 错位)
    if (slot === 0) {
      stave.addClef(noteClef.value);
      if (measureIndex === 0) {
        stave.addKeySignature(editorKey.value).addTimeSignature(editorTime.value);
        if (tempo > 0) stave.setTempo({ bpm: tempo, duration: "q" });
      }
    }

    stave.setContext(context).draw();

    if (isCurrent) {
      const spacing = stave.getSpacingBetweenLines();
      context.save();
      context.setFillStyle("rgba(31, 122, 86, 0.10)");
      context.fillRect(x - 1, y - 1, w + 2, spacing * 4 + 6);
      context.restore();
    }

    const activeRender = drawStaffEntriesOnStave(context, stave, entries, noteClef.value, w, isCurrent, measureIndex, notesByMeasure, stavesByMeasure);

    if (isCurrent) {
      // P22.3 final — geometry 字段重命名 + 双字段保留 (兼容 pitchFromY 等旧代码)
      //   - noteStartX / noteEndX: VexFlow 允许放音符的位置
      //   - staveX / staveY: stave 起点 (相对 canvas)
      //   - measureX / measureY / measureWidth / measureHeight: 小节 box
      //   - topY / bottomY / halfStep: 相对 staveY
      //   - 旧字段 startX/endX/x/y/width/height 保留同值 (pitchFromY 还在用)
      const noteStartX = stave.getNoteStartX();
      const noteEndX = stave.getNoteEndX();
      const topLineY = stave.getYForLine(0);
      const bottomLineY = stave.getYForLine(4);
      staffGeometry = {
        // P22.4-B.3 批次 5: 删 6 个旧字段 alias (startX/endX/x/y/width/height) — grep 确认 0 处使用
        measureX: x, measureY: y, measureWidth: w, measureHeight: staveHeight,
        noteStartX, noteEndX,
        staveX: x, staveY: y,
        topY: topLineY - y,
        bottomY: bottomLineY - y,
        halfStep: (bottomLineY - topLineY) / 8,
        measureIndex,
        canvasWidth: width,
        canvasHeight: height,
        // P22.3 Phase 3: ghost 必须用主 stave + 主 ctx
        activeStave: stave,
        activeContext: context
      };
      renderEntryHitboxes(activeRender.entries, activeRender.notes);
    }

    measureRects.push({ index: measureIndex, x, y, width: w, height: staveHeight, isCurrent, slot, row });
  });

  // P22.5-Symbol-A.3 — 跨音符 draw 在主循环外统一画 (跨 measure 自动走 fallback)
  if (notesByMeasure.size > 0) {
    const scoreEntries = buildScoreEntries(scoreMeasures);
    drawEntryTies(context, scoreEntries, notesByMeasure);
    drawEntrySlurs(context, scoreEntries, notesByMeasure);
    drawEntryPhraseMarks(context, scoreEntries, notesByMeasure);
    drawEntryHairpins(context, scoreEntries, notesByMeasure, stavesByMeasure);
  }

  // 加上"切小节"覆盖按钮和 prev/next 视觉提示
  // 传入 row 数组 (而不是纯 index 数组)
  const measureIdxArr = visibleIndices.map(v => v.index);
  addMeasureJumpButtons(measureIdxArr, currentIdx, slotWidth, staveHeight);

  // 节拍网格（Flat.io 风格：每个 beat 一条虚线）
  if (isCurrentMeasureEmpty()) {
    drawBeatGrid(context, visibleIndices, currentIdx, slotWidth, staveHeight);
  }

  noteCanvas.dataset.entryCount = String(currentVoiceEntries().length);
  noteCanvas.dataset.chordSizes = currentVoiceEntries().map((entry) => entry.kind === "note" ? entry.pitches.length : 0).join(",");
  noteCanvas.dataset.usedUnits = String(sumCurrentVoiceUnits());
  // P22.3 Phase 3: renderNotation 末尾追加 ghost（保证 commit/切小节后 ghost 仍可见）
  appendGhostToMainCanvas();
  // P22.4-B.2: render 成功路径 — 灌入最新 layout 给 cs
  //   单谱模式: treble/bass geometry 不存在
  //   P22.4-B.3 批次 1: addEntry/hover 已迁到 cs.staffAtPoint (via resolveStaffAtPoint wrapper)
  //   P22.4-B.3 待办: localX/Y/beat/capacity 公式也迁到 cs (批次 2-4)
  if (typeof cs !== "undefined" && cs && cs.updateLayout) {
    cs.updateLayout({
      staffGeometry,
      trebleGeometry: null,
      bassGeometry: null,
      measureRects,
      currentMeasureIndex,
      timeSignature: editorTime?.value || "4/4"
    });
  }
}

/**
 * P18.8.3 — 决定当前可见的 3 个小节索引（prev/current/next）。
 * 规则：
 *   1) 如果总小节数 ≤ VISIBLE_MEASURES：全部显示
 *   2) 否则：保证 currentIdx 在窗口中，窗口尽量以 currentIdx 为中心
 *   3) 边界（currentIdx 在 0 或末尾）时，窗口不"出界"——多余 slot 用 [0..totalMeasures) 头/尾补
 */
function pickVisibleMeasureIndices(currentIdx, totalMeasures) {
  if (totalMeasures <= 0) return [0];
  if (totalMeasures <= VISIBLE_MEASURES) {
    return Array.from({ length: totalMeasures }, (_, i) => i);
  }
  // 想要 prev/current/next
  let start = currentIdx - 1;
  let end = currentIdx + 1;
  // 边界调整
  if (start < 0) { end += -start; start = 0; }
  if (end >= totalMeasures) { start -= (end - totalMeasures + 1); end = totalMeasures - 1; }
  start = Math.max(0, start);
  end = Math.min(totalMeasures - 1, end);
  const indices = [];
  for (let i = start; i <= end; i += 1) indices.push(i);
  return indices;
}

/**
 * P18.8.3 — 在画布的 prev/next 小节上叠"切小节"按钮（点击切换 currentMeasureIndex）。
 * 用 DOM button 覆盖 VexFlow svg 之上，z-index: 5。
 */
function addMeasureJumpButtons(visibleIndices, currentIdx, slotWidth, staveHeight) {
  const wrap = noteCanvas.parentElement;   // .editor-score-viewport
  if (!wrap) return;
  // prev 按钮（如果 currentIdx > 0）
  if (currentIdx > 0) {
    const prevSlot = visibleIndices.indexOf(currentIdx - 1);
    if (prevSlot >= 0) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "measure-jump-button prev";
      btn.textContent = `← 第 ${currentIdx} 小节`;
      btn.title = `跳到第 ${currentIdx} 小节`;
      btn.style.left = `${prevSlot * slotWidth + 8}px`;
      btn.style.top = `${staveHeight - 6}px`;
      btn.addEventListener("click", (event) => {
        event.stopPropagation();
        switchToMeasure(currentIdx - 1);
      });
      noteCanvas.appendChild(btn);
    }
  }
  // next 按钮（如果 currentIdx < totalMeasures - 1）
  if (currentIdx < scoreMeasures.length - 1) {
    const nextIdx = currentIdx + 1;
    const nextSlot = visibleIndices.indexOf(nextIdx);
    if (nextSlot >= 0) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "measure-jump-button next";
      btn.textContent = `第 ${nextIdx + 1} 小节 →`;
      btn.title = `跳到第 ${nextIdx + 1} 小节`;
      btn.style.left = `${nextSlot * slotWidth + 8}px`;
      btn.style.top = `${staveHeight - 6}px`;
      btn.addEventListener("click", (event) => {
        event.stopPropagation();
        switchToMeasure(nextIdx);
      });
      noteCanvas.appendChild(btn);
    }
  }
  // prev/next 两侧半透明蒙层
  if (currentIdx > 0) {
    const fade = document.createElement("div");
    fade.className = "score-prev-fade";
    const prevSlot = visibleIndices.indexOf(currentIdx - 1);
    if (prevSlot >= 0) fade.style.left = `${prevSlot * slotWidth}px`;
    else fade.style.left = "0";
    fade.style.width = `${slotWidth}px`;
    noteCanvas.appendChild(fade);
  }
  if (currentIdx < scoreMeasures.length - 1) {
    const fade = document.createElement("div");
    fade.className = "score-next-fade";
    const nextSlot = visibleIndices.indexOf(currentIdx + 1);
    if (nextSlot >= 0) fade.style.left = `${nextSlot * slotWidth}px`;
    else fade.style.right = "0";
    fade.style.width = `${slotWidth}px`;
    noteCanvas.appendChild(fade);
  }
}

function clearMeasureJumpButtons() {
  noteCanvas.querySelectorAll(".measure-jump-button, .score-prev-fade, .score-next-fade, .score-beat-grid, .score-current-frame").forEach((node) => node.remove());
}

function isCurrentMeasureEmpty() {
  return currentVoiceEntries().length === 0;
}

function drawBeatGrid(context, visibleIndices, currentIdx, slotWidth, staveHeight) {
  if (!context) return;
  const rect = visibleIndices.map((i) => i === currentIdx).indexOf(true);
  if (rect < 0) return;
  const meter = currentMeter();
  const beats = meter.numerator;
  if (beats <= 1) return;
  const slotX = rect * slotWidth;
  const usableW = slotWidth - 8;
  // 用 svg 的线条画（用 SVG path 比 div 容易控制）
  const startX = slotX + 4;
  const topY = 12;
  const bottomY = topY + staveHeight - 30;
  for (let b = 1; b < beats; b += 1) {
    const x = startX + (usableW * b) / beats;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", String(x));
    line.setAttribute("x2", String(x));
    line.setAttribute("y1", String(topY));
    line.setAttribute("y2", String(bottomY));
    line.setAttribute("stroke", "rgba(31, 122, 86, 0.22)");
    line.setAttribute("stroke-dasharray", "3 4");
    line.setAttribute("stroke-width", "1");
    line.classList.add("score-beat-grid");
    noteCanvas.appendChild(line);
  }
}

function clearGhostNote() {
  // P22.3 Phase 4: ghost 现在画到主 canvas SVG 内 — 用 [data-ghost] 属性识别
  // 不依赖 className（VexFlow 内部 class 不可控）
  // 不查 div.score-ghost-note（旧 div 容器已删）
  // 删的只是 ghost tickable 的 svg 容器（包含 note head / stem / flag / accidental / dot）
  // 不动 stave lines / clef / 已提交 entry 的音符（它们无 [data-ghost] 属性）
  const svg = noteCanvas.querySelector("svg");
  if (!svg) return;
  // 顶层 ghost 节点
  svg.querySelectorAll('[data-ghost="true"]').forEach((node) => node.remove());
  // 兼容旧 .vf-ghost-note class（Phase 3 写法，缓慢迁移）
  svg.querySelectorAll(".vf-ghost-note").forEach((node) => node.remove());
  // VexFlow 4.x StaveNote 内部 svg 容器可能有 [data-ghost] 标记在子 g
  // 兜底：再扫一遍所有 .vf-stavenote 看 note 对象 __isGhost
  svg.querySelectorAll(".vf-stavenote").forEach((el) => {
    // VexFlow 通常把 note 对象存在 el.__vexflowNote 或 attrs.id
    // 我们加的 __isGhost 不在 DOM 上，但 appendGhostToMainCanvas 末尾 setAttribute('data-ghost', 'true')
    // 这里兜底不删真实音符
  });
}

/**
 * P22.3 Phase 2 — 把 previewEntry 转成 VexFlow 真正音符渲染（不再 div+textContent 假预览）。
 *
 * 关键约束（你 Phase 2 明确要求）：
 *   - 不允许生成 "C5" 字符串假预览
 *   - 必须复用 createVexNote / 正式 note rendering
 *   - preview 必须支持 duration / dotted / accidental / rest / voice
 *
 * 实现：
 *   - 在 noteCanvas 上叠一个独立 div 容器（绝对定位，与命中的 staff y 对齐）
 *   - 容器内嵌 mini VexFlow renderer（SVG）
 *   - mini stave 高度与 staffGeometry.topY/bottomY 区间对齐
 *   - StaveNote = createVexNote(previewEntry, staveKey, ...) —— 0 单独 ghost renderer
 *   - 颜色按 capacity 状态：绿（可放）/ 红（超容量）
 *   - pointer-events: none（不挡 hitbox）
 */
function appendGhostToMainCanvas() {
  if (!VF) return;
  if (!editorState.previewEntry || !editorState.pendingMousePosition) {
    clearGhostNote();
    return;
  }
  const { staveKey, geometry, measureIndex, x, y } = editorState.pendingMousePosition;
  if (measureIndex !== currentMeasureIndex) {
    clearGhostNote();
    return;
  }
  if (!geometry || !geometry.activeStave || !geometry.activeContext) {
    clearGhostNote();
    return;
  }
  clearGhostNote();

  const stave = geometry.activeStave;
  const ctx = geometry.activeContext;

  // P22.4-B.3 批次 2/3: localX + beat 公式走 cs
  const meter = currentMeter();
  const { localX } = cs.canvasToStave(x, y, geometry);
  const { beat } = cs.canvasToBeat(x, geometry, meter);

  try {
    // ghost voice = 全 measure 容量（让 ghost note 跟真实 voice 算法一致）
    const totalBeats = Math.max(1, Math.round(meter.capacity / 8));
    const ghostVoice = new VF.Voice({ num_beats: totalBeats, beat_value: 4 });
    ghostVoice.setStrict(false);
    const restKey = restKeyForVoice(staveKey, activeVoiceId());

    // ghost note 之前的 placeholder rest（用 transparent style 不画）
    for (let b = 1; b < beat; b += 1) {
      const restNote = new VF.StaveNote({ keys: [restKey], duration: "q", type: "r" });
      restNote.setStyle({ fillStyle: "transparent", strokeStyle: "transparent" });
      ghostVoice.addTickable(restNote);
    }

    // ghost note (复用 createVexNote — 你 Phase 2 硬约束)
    const ghostNote = createVexNote(editorState.previewEntry, staveKey, editorTime.value);
    const ghostColor = editorState.isPreviewOverCapacity
      ? "rgba(239, 68, 68, 0.55)"   // 红 — 超容量
      : "rgba(52, 211, 153, 0.55)";  // 绿 — 能放
    ghostNote.setStyle({ fillStyle: ghostColor, strokeStyle: ghostColor });
    ghostVoice.addTickable(ghostNote);

    // ghost note 之后的 placeholder rest
    for (let b = beat + 1; b <= totalBeats; b += 1) {
      const restNote = new VF.StaveNote({ keys: [restKey], duration: "q", type: "r" });
      restNote.setStyle({ fillStyle: "transparent", strokeStyle: "transparent" });
      ghostVoice.addTickable(restNote);
    }

    // 关键：用主 VexFlow Formatter 推 ghost note 到目标拍位（跟真实 voice 算法一致）
    const formatter = new VF.Formatter();
    formatter.joinVoices([ghostVoice]);
    formatter.format([ghostVoice], stave.getNoteEndX() - stave.getNoteStartX());

    // P22.3 final — ghost layer 兜底 (CSS .vf-ghost-layer * { pointer-events:none !important })
    // VexFlow SVG 层级不稳, setAttribute 不靠谱; 用 className 让 CSS 兜底
    // 给每个 ghost tickable svg 容器加 vf-ghost-layer className
    // → CSS 强制整个子树不接收 pointer 事件 → click 穿透到 noteCanvas
    ghostVoice.tickables.forEach((t) => {
      try {
        if (t.getSVGElement && typeof t.getSVGElement === "function") {
          const svgEl = t.getSVGElement();
          if (svgEl) {
            svgEl.classList.add("vf-ghost-layer");
            svgEl.classList.add("vf-ghost-note");
            svgEl.setAttribute("data-ghost", "true");
            // 同时保留 setAttribute 双保险 (VexFlow 4.x 偶尔会重新 attach element)
            svgEl.setAttribute("pointer-events", "none");
          }
        }
        // 真正 ghost note (非 placeholder rest) 加 class
        if (t === ghostNote && t.noteHeads) {
          t.noteHeads.forEach((nh) => {
            if (nh.getSVGElement) {
              const el = nh.getSVGElement();
              if (el) {
                el.classList.add("vf-ghost-layer");
                el.classList.add("vf-ghost-note");
                el.setAttribute("data-ghost", "true");
                el.setAttribute("pointer-events", "none");
              }
            }
          });
        }
      } catch (_) { /* 静默失败 — ghost 标记非关键 */ }
    });

    // 画到主 ctx + 主 stave（关键：复用主 VexFlow 坐标系）
    ghostVoice.draw(ctx, stave);

    // P22.3 final — 画完后再次扫一遍, 防止 VexFlow 内部 createSVG 重新创建元素
    // (这种情况 VexFlow 4.x 偶发, 没 className 的子元素也要兜底)
    ghostVoice.tickables.forEach((t) => {
      try {
        if (t.getSVGElement && typeof t.getSVGElement === "function") {
          const svgEl = t.getSVGElement();
          if (svgEl && svgEl.setAttribute) {
            svgEl.setAttribute("data-ghost", "true");
            svgEl.setAttribute("pointer-events", "none");
            svgEl.classList.add("vf-ghost-layer");
          }
        }
      } catch (_) { /* 静默 — 标记失败不影响 ghost 显示 */ }
    });
  } catch (e) {
    // ghost 渲染失败不能让画布卡死
    console.error("[appendGhostToMainCanvas]", e);
  }
}

// ---------------------------------------------------------------------
// P22.3 duration-cleanup: 单一 preview 构造入口
// 所有路径（hover / SELECT change / 未来新加）必须走这里
// 数据方向：editorState → previewEntry
// 业务逻辑不再自己拼 preview，避免拼错字段或漏 _ghost
// ---------------------------------------------------------------------
function buildPreviewFromState({ localX, localY, geometry, staveKey, isRest }) {
  const esDur = editorState.getInputDuration();
  const { duration, dotted, units } = esDur;
  const accidental = editorState.getInputAccidental();
  if (isRest) {
    return {
      kind: "rest",
      voice: activeVoiceId(),
      duration, dotted, units,
      _ghost: true,
      _restKey: restKeyForVoice(staveKey, activeVoiceId())
    };
  }
  const pitch = pitchFromY(localY, staveKey, geometry);
  const fullPitch = createPitch(pitch, accidental);
  return {
    kind: "note",
    voice: activeVoiceId(),
    pitches: [fullPitch],
    duration, dotted, units,
    _ghost: true
  };
}

/**
 * P22.3 Phase 2 — 鼠标 hover 画布时显示 ghost note 预览。
 * 关键变化：
 *   - 写 editorState.setPreview / setMousePosition / setDuration / setAccidental / setInputMode
 *   - 写 editorState.updateCapacity(used + units, capacity)
 *   - 渲染走 renderGhostVexFlow（VexFlow 真正音符 + createVexNote 复用）
 *   - 删 ghostText = display + step + octave 字符串假预览
 *   - 不响应 prev/next 小节（避免切换中产生视觉干扰）
 */
function handleNoteCanvasHover(event) {
  // P22.4-B.3 批次 1: viewportToCanvas 替代内联 getBoundingClientRect 公式
  const { x, y } = cs.viewportToCanvas(event, noteCanvas);
  // P22+: 用 resolveStaffAtPoint 决定 stave + geometry
  const resolved = resolveStaffAtPoint(x, y);
  if (!resolved || !resolved.geometry) {
    editorState.clearPreview();
    clearGhostNote();
    return;
  }
  const { staveKey, geometry, measureRect } = resolved;
  // P22.4-B.3 批次 2: localX/localY 公式 + 越界走 cs.canvasToStave / cs.isInNoteRange / cs.isInPitchRange
  const { localX, localY } = cs.canvasToStave(x, y, geometry);
  if (!cs.isInNoteRange(localX, geometry)) {
    editorState.clearPreview();
    clearGhostNote();
    return;
  }
  if (!cs.isInPitchRange(localY, geometry)) {
    editorState.clearPreview();
    clearGhostNote();
    return;
  }

  const isRest = inputKind() === "rest";
  // P22.3 duration-cleanup: business 统一从 editorState 读，hover 不要再覆盖回 editorState
  const esDur = editorState.getInputDuration();
  const duration = esDur.duration;
  const dotted = esDur.dotted;
  const units = esDur.units;
  const used = sumCurrentVoiceUnits();
  const { capacity } = currentMeter();

  // inputMode 同步
  const mode = isRest ? "rest" : (entryMode() === "chord" ? "chord" : "note");
  editorState.setInputMode(mode);
  // P22.3 duration-fix: 不再用 hover 时的旧 select 值覆盖 editorState
  // (setDuration 仍然调用，但读的是 editorState 自己，没有覆盖效应)
  // editorState.setDuration(duration, dotted);  // 删掉：会回写覆盖
  // P22.3 duration-cleanup: accidental 已经在 editorState.currentAccidental 里,
  // 不需要 self-assign, 直接读 getInputAccidental() 即可
  editorState.setMousePosition({ x, y, staveKey, geometry, measureIndex: measureRect.index });
  editorState.updateCapacity(used + units, capacity);

  // P22.4-B.3 批次 3: beat 计算走 cs.canvasToBeat (同时返回 targetX, 但 hover 这边不用 — targetX 是死代码, 删)
  const meter = currentMeter();
  const { beat } = cs.canvasToBeat(x, geometry, meter);

  // 构建 previewEntry（真实 entry 形状 + _ghost 标记）
  // P22.3 duration-cleanup: 走单一函数 buildPreviewFromState（editorState → previewEntry）
  const preview = buildPreviewFromState({
    localX,
    localY,
    geometry,
    staveKey,
    isRest
  });
  editorState.setPreview(preview);

  // P22.3 Phase 3: ghost 画到主 canvas（不再是独立 mini VexFlow）— 跟正式音符同坐标系
  appendGhostToMainCanvas();
}

function renderPianoNotation() {
  noteCanvas.classList.remove("notation-error");
  const viewportWidth = Math.max(700, Math.floor(scoreViewport.clientWidth - 2));
  const totalMeasures = Math.max(
    1,
    Math.max(staffScores.treble.measures.length, staffScores.bass.measures.length)
  );
  const currentIdx = Math.max(0, Math.min(currentMeasureIndex, totalMeasures - 1));
  const visibleIndices = pickVisibleMeasureIndices(currentIdx, totalMeasures);
  const visibleCount = visibleIndices.length;
  // P22.3 final: piano 双谱表小节宽度提到 260 (用户要求)
  const slotWidth = Math.max(260, Math.floor(viewportWidth / visibleCount));
  const staveHeight = PIANO_STAVE_HEIGHT;
  const width = viewportWidth;
  const height = staveHeight + 20;
  noteCanvas.style.width = `${width}px`;
  noteCanvas.style.height = `${height}px`;

  const renderer = new VF.Renderer(noteCanvas, VF.Renderer.Backends.SVG);
  renderer.resize(width, height);
  const context = renderer.getContext();
  const activeKey = activeStaffKey();
  const tempo = Number(tempoInput.value) || 0;
  measureRects = [];
  const staves = {};

  clearMeasureJumpButtons();
  clearGhostNote();

  // P22.5-Symbol-A.3 — 4 部画布跨音符收集容器 (treble / bass 各自一份)
  const trebleNotesByMeasure = new Map();
  const trebleStavesByMeasure = new Map();
  const bassNotesByMeasure = new Map();
  const bassStavesByMeasure = new Map();

  visibleIndices.forEach((measureIndex, slot) => {
    const isCurrent = measureIndex === currentIdx;
    const slotX = slot * slotWidth;
    const w = slotWidth - 12;
    const x = slotX + 6;
    const trebleY = 16;
    const bassY = trebleY + 110;
    const isFirstInRow = slot === 0;

    const trebleState = staffScores.treble;
    const bassState = staffScores.bass;
    const trebleStave = new VF.Stave(x, trebleY, w);
    applyBarlineSettings(trebleStave, trebleState.settings[measureIndex] || defaultMeasureSettings());
    if (measureIndex === 0) {
      trebleStave.addClef("treble").addKeySignature(editorKey.value).addTimeSignature(editorTime.value);
      if (tempo > 0) trebleStave.setTempo({ bpm: tempo, duration: "q" });
    } else {
      trebleStave.addClef("treble");
    }
    trebleStave.setContext(context).draw();
    const bassStave = new VF.Stave(x, bassY, w);
    applyBarlineSettings(bassStave, bassState.settings[measureIndex] || defaultMeasureSettings());
    if (measureIndex === 0) bassStave.addClef("bass").addKeySignature(editorKey.value);
    else bassStave.addClef("bass");
    bassStave.setContext(context).draw();

    if (isCurrent) {
      context.save();
      context.setFillStyle("rgba(31, 122, 86, 0.10)");
      context.fillRect(x - 2, trebleY - 2, w + 4, staveHeight);
      context.restore();
    }

    const trebleEntries = trebleState.measures[measureIndex] || [];
    const bassEntries = bassState.measures[measureIndex] || [];
    // P22+: 双谱表都渲染 hitbox (不仅 activeKey), 让用户能点非 active stave 的 entry
    const trebleRender = drawStaffEntriesOnStave(context, trebleStave, trebleEntries, "treble", w, isCurrent, measureIndex, trebleNotesByMeasure, trebleStavesByMeasure);
    const bassRender = drawStaffEntriesOnStave(context, bassStave, bassEntries, "bass", w, isCurrent, measureIndex, bassNotesByMeasure, bassStavesByMeasure);
    if (isCurrent) {
      // P22.3 final — piano 模式 treble/bass geometry 双字段 (同单谱)
      const tNoteStartX = trebleStave.getNoteStartX();
      const tNoteEndX = trebleStave.getNoteEndX();
      const tTopY = trebleStave.getYForLine(0);
      const tBottomY = trebleStave.getYForLine(4);
      trebleGeometry = {
        // P22.4-B.3 批次 5: 删 6 个旧字段 alias (startX/endX/x/y/width/height)
        measureX: x, measureY: trebleY, measureWidth: w, measureHeight: staveHeight,
        noteStartX: tNoteStartX, noteEndX: tNoteEndX,
        staveX: x, staveY: trebleY,
        topY: tTopY - trebleY,
        bottomY: tBottomY - trebleY,
        halfStep: (tBottomY - tTopY) / 8,
        measureIndex,
        canvasWidth: width, canvasHeight: height,
        activeStave: trebleStave,
        activeContext: context
      };
      const bNoteStartX = bassStave.getNoteStartX();
      const bNoteEndX = bassStave.getNoteEndX();
      const bTopY = bassStave.getYForLine(0);
      const bBottomY = bassStave.getYForLine(4);
      bassGeometry = {
        // P22.4-B.3 批次 5: 删 6 个旧字段 alias (startX/endX/x/y/width/height)
        measureX: x, measureY: bassY, measureWidth: w, measureHeight: staveHeight,
        noteStartX: bNoteStartX, noteEndX: bNoteEndX,
        staveX: x, staveY: bassY,
        topY: bTopY - bassY,
        bottomY: bBottomY - bassY,
        halfStep: (bBottomY - bTopY) / 8,
        measureIndex,
        canvasWidth: width, canvasHeight: height,
        activeStave: bassStave,
        activeContext: context
      };
      // 兼容旧 staffGeometry: 指向当前 activeKey
      staffGeometry = (activeKey === "treble") ? trebleGeometry : bassGeometry;
      renderEntryHitboxes(trebleRender.entries, trebleRender.notes, "treble");
      renderEntryHitboxes(bassRender.entries, bassRender.notes, "bass");
    }

    if (isFirstInRow && VF.StaveConnector) {
      new VF.StaveConnector(trebleStave, bassStave).setType(VF.StaveConnector.type.BRACE).setContext(context).draw();
      new VF.StaveConnector(trebleStave, bassStave).setType(VF.StaveConnector.type.SINGLE_LEFT).setContext(context).draw();
      new VF.StaveConnector(trebleStave, bassStave).setType(VF.StaveConnector.type.SINGLE_RIGHT).setContext(context).draw();
    }

    staves[measureIndex] = { treble: trebleStave, bass: bassStave };
    // P22+: 双谱表每个 measure 拆两条 rect, 带 staveKey 区分
    measureRects.push({ index: measureIndex, x, y: trebleY, width: w, height: 110, staveKey: "treble", isCurrent, slot });
    measureRects.push({ index: measureIndex, x, y: bassY, width: w, height: 110, staveKey: "bass", isCurrent, slot });
  });

  // P22.5-Symbol-A.3 — 4 部画布跨音符 draw (treble + bass 各一次, 各自 measure 局部 scoreEntries)
  if (trebleNotesByMeasure.size > 0) {
    const trebleScoreEntries = buildScoreEntries(trebleState?.measures || []);
    drawEntryTies(context, trebleScoreEntries, trebleNotesByMeasure);
    drawEntrySlurs(context, trebleScoreEntries, trebleNotesByMeasure);
    drawEntryPhraseMarks(context, trebleScoreEntries, trebleNotesByMeasure);
    drawEntryHairpins(context, trebleScoreEntries, trebleNotesByMeasure, trebleStavesByMeasure);
  }
  if (bassNotesByMeasure.size > 0) {
    const bassScoreEntries = buildScoreEntries(bassState?.measures || []);
    drawEntryTies(context, bassScoreEntries, bassNotesByMeasure);
    drawEntrySlurs(context, bassScoreEntries, bassNotesByMeasure);
    drawEntryPhraseMarks(context, bassScoreEntries, bassNotesByMeasure);
    drawEntryHairpins(context, bassScoreEntries, bassNotesByMeasure, bassStavesByMeasure);
  }

  addMeasureJumpButtons(visibleIndices, currentIdx, slotWidth, staveHeight);

  noteCanvas.dataset.entryCount = String(currentVoiceEntries().length);
  noteCanvas.dataset.chordSizes = currentVoiceEntries().map((entry) => entry.kind === "note" ? entry.pitches.length : 0).join(",");
  noteCanvas.dataset.usedUnits = String(sumCurrentVoiceUnits());
  // P22.4-B.2: 双谱表 render 成功路径 — 灌入 3 套 geometry
  if (typeof cs !== "undefined" && cs && cs.updateLayout) {
    cs.updateLayout({
      staffGeometry,
      trebleGeometry,
      bassGeometry,
      measureRects,
      currentMeasureIndex,
      timeSignature: editorTime?.value || "4/4"
    });
  }
}

// P18.8.3 — 取消画布自身滚动（"不位移"模式：画布永远是 3 个小节窗口，自身不滚动）
// 旧版 ensureCurrentMeasureVisible 已删除。

function drawStaffEntriesOnStave(context, stave, entriesSource, clef, width, selectable, measureIndex, notesByMeasure, stavesByMeasure) {
  const meter = currentMeter();
  const voices = [];
  const allTuplets = [];
  const allBeams = [];
  let activeRender = { entries: [], notes: [] };
  const occupancyByBeat = buildBeatOccupancy(entriesSource);

  // P22.5-Symbol-A.4 — 入口补 18 个修饰符字段默认值 (idempotent, 已有不覆盖)
  if (Array.isArray(entriesSource)) {
    entriesSource.forEach(ensureEntryDefaults);
  }

  voiceIds.forEach((voiceId) => {
    const hasExplicitVoice = entriesSource.some((entry) => entryVoice(entry) === voiceId);
    if (voiceId !== "1" && !hasExplicitVoice) return;

    const notationEntries = entriesForRendering(entriesSource, selectable, voiceId);
    assignRestAvoidance(notationEntries, clef, voiceId, occupancyByBeat);
    const stemDirection = voiceId === "2" ? VF.Stem?.DOWN : VF.Stem?.UP;
    const notes = notationEntries.map((entry) => createVexNote(entry, clef, editorTime.value, stemDirection, voiceId));
    const voice = new VF.Voice({ numBeats: meter.numerator, beatValue: meter.denominator });
    voice.setMode(VF.Voice.Mode.FULL);
    try {
      voice.addTickables(notes);
    } catch (e) {
      // 单个声部加 ticks 失败不应该把整张谱都打掉，记录日志并跳过该声部
      console.error(
        "[addTickables] voice %s failed: %s. numBeats=%s beatValue=%s notes=%o",
        voiceId, e.message, meter.numerator, meter.denominator,
        notes.map((n) => ({ keys: n.keys, duration: n.duration, type: n.noteType }))
      );
      return;
    }
    voices.push({ voice, notationEntries, notes });
    allTuplets.push(...createEntryTuplets(notationEntries, notes));
    allBeams.push(...VF.Beam.generateBeams(notes, {
      groups: VF.Beam.getDefaultBeamGroups(editorTime.value)
    }));
    if (voiceId === activeVoiceId()) activeRender = { entries: notationEntries, notes };
  });

  const usableWidth = Math.max(120, width - stave.getNoteStartX() - 22);
  const vexVoices = voices.map((item) => item.voice);
  new VF.Formatter().joinVoices(vexVoices).format(vexVoices, usableWidth);
  voices.forEach((item) => item.voice.draw(context, stave));
  allBeams.forEach((beam) => beam.setContext(context).draw());
  allTuplets.forEach((tuplet) => tuplet.setContext(context).draw());

  // P22.5-Symbol-A.4 — 段标 (rehearsal mark) 渲染: 在 measure 第一音上方
  // 取 measure 第一个有 note 的 entry
  for (const voice of voices) {
    const firstNoteEntry = voice.notationEntries.find((e) => e && e.kind === "note" && !e.placeholder);
    const firstNote = voice.notes[voice.notationEntries.indexOf(firstNoteEntry)];
    if (firstNoteEntry && firstNote) {
      drawRehearsalMarkAt(context, firstNote, firstNoteEntry.rehearsalMark);
    }
  }

  // P22.5-Symbol-A.4 — volta (1./2. ending) 渲染: 在 repeat-begin 时画括号
  // measure 级别, 所有 voice 共用一个 volta (per measure 一次)
  const voltaSpec = entriesSource.find((e) => e && Number.isInteger(e.volta))?.volta;
  if (voltaSpec != null) {
    drawVoltaAt(context, stave, voltaSpec);
  }

  // P22.5-Symbol-A.3 — 收集 notes 到 notesByMeasure (跨音符 draw 用)
  if (notesByMeasure && Number.isInteger(measureIndex)) {
    let collected = notesByMeasure.get(measureIndex);
    if (!collected) {
      collected = [];
      notesByMeasure.set(measureIndex, collected);
    }
    voices.forEach((item) => collected.push(...item.notes));
  }
  if (stavesByMeasure && Number.isInteger(measureIndex)) {
    stavesByMeasure.set(measureIndex, stave);
  }

  // P22.5-Symbol-A.3 — 跨音符 draw (tie/slur/phrase/hairpin) 提到渲染主循环外统一画 (跨 measure)
  // 这里只保留不跨 measure 的 arpeggiate
  voices.forEach((item) => {
    drawEntryArpeggios(context, item.notationEntries, item.notes);
  });
  return activeRender;
}

function applyBarlineSettings(stave, settings) {
  if (!VF.Barline?.type) return;
  const beginType = barlineType(settings.beginBarline);
  const endType = barlineType(settings.endBarline);
  if (beginType) stave.setBegBarType(beginType);
  if (endType) stave.setEndBarType(endType);
}

function barlineType(value) {
  const type = VF.Barline?.type;
  if (!type) return null;
  return {
    single: type.SINGLE,
    double: type.DOUBLE,
    end: type.END,
    "repeat-begin": type.REPEAT_BEGIN,
    "repeat-end": type.REPEAT_END,
    "repeat-both": type.REPEAT_BOTH
  }[value] || type.SINGLE;
}

function setCurrentMeasureEntries(entries) {
  scoreMeasures[currentMeasureIndex] = entries;
  measureEntries = scoreMeasures[currentMeasureIndex];
}

function switchToMeasure(index) {
  activateStaff();
  const maxIndex = Math.max(0, scoreMeasures.length - 1);
  const nextIndex = Math.max(0, Math.min(maxIndex, index));
  currentMeasureIndex = nextIndex;
  activateStaff();
  measureEntries = scoreMeasures[currentMeasureIndex];
  measureSettings[currentMeasureIndex] ||= defaultMeasureSettings();
  selectLastEntryInActiveVoice();
  editHistory = [];
  noteMeasure.value = String(currentMeasureIndex + 1);
  beginBarlineSelect.value = measureSettings[currentMeasureIndex].beginBarline;
  endBarlineSelect.value = measureSettings[currentMeasureIndex].endBarline;
  // renderNotation 内部已经 try/catch，这里再兜底一次防止 VexFlow 异常
  // 冒泡上来导致事件 listener 整个崩掉
  try { renderNotation(); } catch (e) { handleRenderError(e); }
}

function addMeasure(afterCurrent = true) {
  activateStaff();
  if (scoreMeasures.length >= MAX_MEASURE_COUNT) {
    showEditorMessage(`最多输入 ${MAX_MEASURE_COUNT} 小节。`, "error");
    return;
  }
  const insertIndex = afterCurrent ? currentMeasureIndex + 1 : scoreMeasures.length;
  forEachVisibleStaff((_, state) => {
    state.measures.splice(insertIndex, 0, []);
    state.settings.splice(insertIndex, 0, defaultMeasureSettings());
  });
  switchToMeasure(insertIndex);
}

function deleteCurrentMeasure() {
  activateStaff();
  if (scoreMeasures.length === 1) {
    commitEdit(() => {
      setCurrentMeasureEntries([]);
      selectedEntryIndex = -1;
    });
    return;
  }
  forEachVisibleStaff((_, state) => {
    if (state.measures.length > 1) {
      state.measures.splice(currentMeasureIndex, 1);
      state.settings.splice(currentMeasureIndex, 1);
    } else {
      state.measures[0] = [];
      state.settings[0] = defaultMeasureSettings();
    }
  });
  switchToMeasure(Math.min(currentMeasureIndex, scoreMeasures.length - 1));
}

// P22.5-Symbol-A.2 — modifier addModifier 顺序 helper
// 决定 entry 启用的 modifier 按什么顺序 add 到 note
// 不直接被 createVexNote 调用; 只用于测试 + 文档
// slot 规则: ABOVE 从近到远 = articulation/fingering/textMark/ornament/fermata
//            BELOW 从近到远 = dynamic/pedal/breath
//            grace 单独 (不变位置)
//            chordSymbol 独立 (LEFT+BOTTOM)
function pickAnnotationOrder(entry) {
  const order = [];
  if (!entry) return order;
  for (const name of ["articulation", "fingering", "textMark", "ornament", "fermata"]) {
    if (entry[name]) order.push(name);
  }
  if (entry.grace && entry.kind === "note") order.push("grace");
  for (const name of ["dynamic", "pedal", "breath"]) {
    if (entry[name]) order.push(name);
  }
  if (entry.chordSymbol && entry.kind === "note") order.push("chordSymbol");
  return order;
}

// P22.5-Symbol-A.4 — entry 字段默认值补全
// 18 个修饰符字段在 entry 创建时只有 2 个有默认值 (fermata + dynamic), 其他 16 个 undefined
// 渲染用 `if (entry.xxx && VF.Yyy)` 防御性跳, 不崩 — 但:
//   - entry 间比较/序列化/版本对比会丢字段
//   - solver 端没法稳定读字段
//   - P22.5-B Score Schema 没法建
// 解决: 在 drawStaffEntriesOnStave 入口 (渲染前) 给所有 entry 补默认值
// Idempotent: 已有字段不覆盖
// 注意: 只补 18 个**修饰符字段** (P22.5-Symbol 范围), 不补结构字段 (kind/duration/dotted/pitches/voices)
const ENTRY_MODIFIER_DEFAULTS = Object.freeze({
  // ABOVE slot
  articulation: "",
  fingering: "",
  textMark: "",
  ornament: "",
  fermata: false,
  // grace 单独, object | null
  grace: null,
  // BELOW slot
  dynamic: "",
  pedal: "",
  breath: false,
  // 跨音符 (tie/slur/phrase/hairpin)
  tieStart: false,
  tieStop: false,
  slurStart: false,
  slurStop: false,
  phraseStart: false,
  phraseStop: false,
  hairpin: "",
  // 文本 / 演奏法
  chordSymbol: "",
  arpeggiate: false,
  // A.4 新增: 曲式分析
  volta: null,         // 1 | 2 | 3 | null
  rehearsalMark: ""    // "A" / "B" / "Intro" / "Verse 1" 等
});

function ensureEntryDefaults(entry) {
  if (!entry || typeof entry !== "object") return entry;
  for (const key in ENTRY_MODIFIER_DEFAULTS) {
    if (!(key in entry)) {
      entry[key] = ENTRY_MODIFIER_DEFAULTS[key];
    }
  }
  return entry;
}

// P22.5-Symbol-A.4 — 段标 (rehearsal mark) 渲染
// 在 measure 第一音上方画方框 A/B/C
// 接收: context + 第一个 note (有 x 坐标) + mark 文本
// VexFlow.RehearsalMark 自动画矩形外框
function drawRehearsalMarkAt(context, firstNote, mark) {
  if (!context || !firstNote || !mark) return;
  if (!VF.RehearsalMark) return;
  const rm = new VF.RehearsalMark(String(mark));
  firstNote.addModifier(rm, 0);
  // 注意: addModifier 会在 note 渲染时自动画, 不需要单独 setContext + draw
}

// P22.5-Symbol-A.4 — volta (反复 1./2. ending) 渲染
// 在 repeat-begin 时画 volta 括号 + 编号
// VexFlow 4.x: VF.Repetition(stave, [num1, num2, ...]) — text 数组每个对应一段
// 通常只用 [1] (单段) 或 [1, 2] (1./2. ending)
// 也支持 [1, 2, 3] (1./2./3. ending)
function drawVoltaAt(context, stave, voltaSpec) {
  if (!context || !stave || voltaSpec == null) return;
  if (!VF.Repetition) return;
  // voltaSpec: number | number[] | null
  // 简化: number = [voltaSpec], array = 直接用
  const numbers = Array.isArray(voltaSpec) ? voltaSpec : [voltaSpec];
  if (!numbers.length) return;
  const rep = new VF.Repetition(stave, numbers);
  rep.setContext(context).draw();
}

// P22.5-Symbol-A.3 — 全局 flatten 索引
// 跨 measure 查找用 (tie / slur / phrase / hairpin)
// 每个 entry 挂 3 个 _ 前缀字段: _globalIndex / _measureIndex / _localIndex
// 注意: spread 浅拷贝, entry 引用变化时不会自动更新 (render 时 build 一次, 期间数据不变)
// 支持 scoreMeasures 元素是 array (trebleState.measures[i] = [entry, ...]) 或 { notationEntries | entries: [...] }
function buildScoreEntries(scoreMeasures) {
  const all = [];
  if (!Array.isArray(scoreMeasures)) return all;
  scoreMeasures.forEach((measure, measureIndex) => {
    let entries;
    if (Array.isArray(measure)) entries = measure;
    else entries = measure?.notationEntries || measure?.entries || [];
    if (!Array.isArray(entries)) return;
    entries.forEach((entry, localIndex) => {
      all.push({
        ...entry,
        _globalIndex: all.length,
        _measureIndex: measureIndex,
        _localIndex: localIndex,
      });
    });
  });
  return all;
}

// P22.5-Symbol-A.3 — 4 个跨 measure fallback helper
// VexFlow 4.x 的 StaveTie / Curve / Hairpin 跨 system 行为未定义, 用 raw SVG path 画
// 接收两个已经 layout 好的 note, 用 note.getTieRightX/getTieLeftX 算绝对 x, 再用 boundingBox 算 y
function drawCrossMeasureTie(context, note1, note2, indexes, direction) {
  if (!context || !note1 || !note2) return;
  const x1 = note1.getTieRightX();
  const x2 = note2.getTieLeftX();
  if (!Number.isFinite(x1) || !Number.isFinite(x2)) return;
  const box1 = note1.getBoundingBox();
  const box2 = note2.getBoundingBox();
  if (!box1 || !box2) return;
  const y1 = box1.y + box1.h / 2;
  const y2 = box2.y + box2.h / 2;
  const yArc = direction === "up" ? Math.min(y1, y2) - 6 : Math.max(y1, y2) + 6;
  context.openGroup("tie-cross");
  context.beginPath();
  context.moveTo(x1, y1);
  context.quadraticCurveTo((x1 + x2) / 2, yArc, x2, y2);
  context.stroke();
  context.closeGroup();
}

function drawCrossMeasureSlur(context, note1, note2) {
  if (!context || !note1 || !note2) return;
  const x1 = note1.getTieRightX();
  const x2 = note2.getTieLeftX();
  if (!Number.isFinite(x1) || !Number.isFinite(x2)) return;
  const box1 = note1.getBoundingBox();
  const box2 = note2.getBoundingBox();
  if (!box1 || !box2) return;
  const y1 = box1.y;
  const y2 = box2.y;
  // slur 比 tie 弯 (cps y=18 在 VexFlow 原生 slur 里, 折算 ~12-18px 弧高)
  const yArc = Math.min(y1, y2) - 12;
  context.openGroup("slur-cross");
  context.beginPath();
  context.moveTo(x1, y1);
  context.quadraticCurveTo((x1 + x2) / 2, yArc, x2, y2);
  context.stroke();
  context.closeGroup();
}

function drawCrossMeasurePhraseMark(context, note1, note2) {
  if (!context || !note1 || !note2) return;
  const x1 = note1.getTieRightX();
  const x2 = note2.getTieLeftX();
  if (!Number.isFinite(x1) || !Number.isFinite(x2)) return;
  const box1 = note1.getBoundingBox();
  const box2 = note2.getBoundingBox();
  if (!box1 || !box2) return;
  const y1 = box1.y;
  const y2 = box2.y;
  // phrase 比 slur 更弯 (cps y=26 在 VexFlow 原生 phrase 里, 折算 ~18-26px 弧高)
  const yArc = Math.min(y1, y2) - 20;
  context.openGroup("phrase-cross");
  context.beginPath();
  context.moveTo(x1, y1);
  context.quadraticCurveTo((x1 + x2) / 2, yArc, x2, y2);
  context.stroke();
  context.closeGroup();
}

function drawCrossMeasureHairpin(context, hairpin, note1, note2, y, spread) {
  if (!context || !note1 || !note2) return;
  const x1 = note1.getTieRightX();
  const x2 = note2.getTieLeftX();
  if (!Number.isFinite(x1) || !Number.isFinite(x2)) return;
  context.openGroup("hairpin-cross");
  context.beginPath();
  if (hairpin === "cresc-start") {
    context.moveTo(x1, y);
    context.lineTo(x2, y - spread);
    context.moveTo(x1, y);
    context.lineTo(x2, y + spread);
  } else {
    context.moveTo(x1, y - spread);
    context.lineTo(x2, y);
    context.moveTo(x1, y + spread);
    context.lineTo(x2, y);
  }
  context.stroke();
  context.closeGroup();
}

function createVexNote(entry, clef = noteClef.value, timeSignature = editorTime.value, stemDirection = undefined, voiceId = entryVoice(entry)) {
  const duration = vexDurations[entry.duration];
  const isRest = entry.kind === "rest";
  const restKey = entry._restKey || (entry.placeholder ? "b/4" : restKeyForVoice(clef, voiceId));
  const keys = isRest ? [restKey] : entry.pitches.map((pitch) => {
    const accidental = pitch.accidental && pitch.accidental !== "n" ? pitch.accidental : "";
    return `${pitch.step.toLowerCase()}${accidental}/${pitch.octave}`;
  });
  const noteOptions = {
    keys,
    duration,
    type: isRest ? "r" : "n",
    clef,
    autoStem: true
  };
  if (stemDirection) {
    noteOptions.stemDirection = stemDirection;
    noteOptions.autoStem = false;
  }

  if (entry.fullMeasure) {
    const meter = meterForTimeSignature(timeSignature);
    noteOptions.alignCenter = true;
    noteOptions.durationOverride = new VF.Fraction(meter.numerator, meter.denominator);
  }

  const note = new VF.StaveNote(noteOptions);

  // P22.5-Symbol-Accidental — 升降还原记号显式渲染
  // VexFlow 4.x 的 key 串 ("c#/5" / "eb/5") 只决定音高位置, 不会自动画 ♯/♭ 字符,
  // 必须 addModifier(Accidental) 才会在 note 头上画出临时记号。
  // 对每个 pitch 单独加 (支持和弦), accidental 是 "#"/"b"/"##"/"bb" 之一。
  if (entry.kind === "note" && Array.isArray(entry.pitches) && VF.Accidental) {
    entry.pitches.forEach((pitch, pitchIndex) => {
      const acc = pitch.accidental;
      if (!acc || acc === "n" || acc === "") return;
      // 还原号 "n" / "" 不画; 其它都画
      try {
        const accMod = new VF.Accidental(acc);
        note.addModifier(accMod, pitchIndex);
      } catch (e) {
        // 防御: VexFlow 偶尔对不识别的 accidental 串抛错, 不影响其它渲染
        console.warn("[createVexNote] accidental modifier failed for pitch", pitchIndex, acc, e?.message);
      }
    });
  }

  const dots = dotCount(entry.dotted);
  if (dots > 0) {
    VF.Dot.buildAndAttach([note], { all: true });
    if (dots > 1) VF.Dot.buildAndAttach([note], { all: true });
  }
  // P22.5-Symbol-A.2 — modifier addModifier 顺序 (slot 1-5 ABOVE / slot 1-3 BELOW / chordSymbol 独立 LEFT+BOTTOM)
  if (entry.kind === "note" && entry.articulation && VF.Articulation) {
    const artPosition = voiceId === "2" ? (VF.Modifier?.Position?.ABOVE ?? 3) : (VF.Modifier?.Position?.BELOW ?? 4);
    note.addModifier(new VF.Articulation(articulationCodes[entry.articulation] || "a.").setPosition(artPosition), 0);
  }
  if (entry.kind === "note" && entry.fingering && VF.FretHandFinger) {
    const abovePosition = VF.Modifier?.Position?.ABOVE ?? 3;
    note.addModifier(new VF.FretHandFinger(entry.fingering).setPosition(abovePosition), 0);
  }
  if (entry.textMark && VF.Annotation) {
    const abovePosition = VF.Modifier?.Position?.ABOVE ?? 3;
    const aboveJustify = VF.Annotation?.VerticalJustify?.TOP ?? "top";
    note.addModifier(
      new VF.Annotation(entry.textMark)
        .setFont("Times New Roman", 12, "italic")
        .setVerticalJustification(aboveJustify)
        .setPosition(abovePosition),
      0
    );
  }
  if (entry.kind === "note" && entry.ornament && VF.Ornament) {
    const abovePosition = VF.Modifier?.Position?.ABOVE ?? 3;
    note.addModifier(new VF.Ornament(ornamentCodes[entry.ornament] || "ornamentTrill").setPosition(abovePosition), 0);
  }
  if (entry.kind === "note" && entry.fermata && VF.Articulation) {
    const abovePosition = VF.Modifier?.Position?.ABOVE ?? 3;
    note.addModifier(new VF.Articulation("a@fermata").setPosition(abovePosition), 0);
  }
  if (entry.grace && entry.kind === "note" && VF.GraceNote && VF.GraceNoteGroup) {
    const graceAccidental = entry.grace.accidental === "#" ? "#" : entry.grace.accidental === "b" ? "b" : "";
    const graceKey = `${entry.grace.step.toLowerCase()}${graceAccidental}/${entry.grace.octave}`;
    const graceNote = new VF.GraceNote({ keys: [graceKey], duration: "16", slash: true });
    const graceGroup = new VF.GraceNoteGroup([graceNote]);
    graceGroup.beamNotes();
    note.addModifier(graceGroup, 0);
  }
  if (entry.dynamic && VF.Annotation) {
    const belowPosition = VF.Modifier?.Position?.BELOW ?? 4;
    const belowJustify = VF.Annotation?.VerticalJustify?.BOTTOM ?? "bottom";
    note.addModifier(
      new VF.Annotation(entry.dynamic)
        .setFont("Times New Roman", 15, "italic")
        .setVerticalJustification(belowJustify)
        .setPosition(belowPosition),
      0
    );
  }
  if (entry.kind === "note" && entry.pedal && VF.Annotation) {
    const belowPosition = VF.Modifier?.Position?.BELOW ?? 4;
    const belowJustify = VF.Annotation?.VerticalJustify?.BOTTOM ?? "bottom";
    note.addModifier(
      new VF.Annotation(entry.pedal === "start" ? "Ped." : "✱")
        .setVerticalJustification(belowJustify)
        .setPosition(belowPosition),
      0
    );
  }
  if (entry.kind === "note" && entry.breath && VF.Annotation) {
    const belowPosition = VF.Modifier?.Position?.BELOW ?? 4;
    const belowJustify = VF.Annotation?.VerticalJustify?.BOTTOM ?? "bottom";
    note.addModifier(
      new VF.Annotation("⌐").setVerticalJustification(belowJustify).setPosition(belowPosition),
      0
    );
  }
  // P22.5-Symbol-A.2 — chordSymbol 改 LEFT+BOTTOM 错开 ABOVE/BELOW stack
  if (entry.chordSymbol && entry.kind === "note" && VF.ChordSymbol) {
    note.addModifier(
      new VF.ChordSymbol()
        .setHorizontal(VF.ChordSymbol?.HorizontalJustify?.LEFT ?? 0)
        .setVertical(VF.ChordSymbol?.VerticalJustify?.BOTTOM ?? 1)
        .addText(entry.chordSymbol),
      0
    );
  }
  if (entry.placeholder) {
    note.setStyle({ fillStyle: "#9aa39d", strokeStyle: "#9aa39d" });
  } else if (entry.selected) {
    note.setStyle({ fillStyle: "#1f7a56", strokeStyle: "#1f7a56" });
  }
  // P22.3 Phase 4: ghost 唯一标识 — 不依赖 className; 走 JS 对象属性
  if (entry && entry._ghost === true) {
    note.__isGhost = true;
  }
  return note;
}

function restKeyForVoice(clef, voiceId) {
  if (clef === "bass") return voiceId === "2" ? "a/2" : "d/3";
  return voiceId === "2" ? "f/4" : "b/4";
}

const CHROMATIC = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

function midiOfPitch(pitch) {
  const accidental = pitch.accidental === "#" ? 1 : pitch.accidental === "b" ? -1 : 0;
  return (pitch.octave + 1) * 12 + CHROMATIC[pitch.step] + accidental;
}

function midiFromKey(key) {
  const match = /^([A-Ga-g])([#b]?)\/(\d+)$/.exec(key);
  if (!match) return 60;
  const step = match[1].toUpperCase();
  const accidental = match[2] === "#" ? 1 : match[2] === "b" ? -1 : 0;
  return (Number(match[3]) + 1) * 12 + CHROMATIC[step] + accidental;
}

// 多声部休止符候选位置（按优先顺序，从默认位置开始向外扩展）
const REST_CANDIDATES = {
  treble: {
    "1": ["b/4", "g/4", "a/4", "d/5", "c/5", "e/5"],
    "2": ["f/4", "d/4", "e/4", "c/4", "g/4", "a/3"]
  },
  bass: {
    "1": ["d/3", "b/2", "e/3", "c/3", "f/3"],
    "2": ["a/2", "f/2", "g/2", "e/2", "b/2"]
  }
};

function buildBeatOccupancy(entriesSource) {
  const occupancy = new Map();
  const cursor = {};
  for (const entry of entriesSource) {
    const voiceId = entryVoice(entry);
    const beat = cursor[voiceId] || 0;
    cursor[voiceId] = beat + (entry.units || unitsForEntry(entry));
    if (entry.kind !== "note") continue;
    for (const pitch of entry.pitches) {
      if (!occupancy.has(beat)) occupancy.set(beat, []);
      occupancy.get(beat).push({ midi: midiOfPitch(pitch), voiceId });
    }
  }
  return occupancy;
}

function pickRestKeyForRest(clef, voiceId, obstacles) {
  const fallback = restKeyForVoice(clef, voiceId);
  if (!obstacles || !obstacles.length) return fallback;
  const candidates = REST_CANDIDATES[clef]?.[voiceId] || [fallback];
  for (const key of candidates) {
    const midi = midiFromKey(key);
    if (obstacles.every((obstacle) => Math.abs(midi - obstacle) >= 3)) return key;
  }
  return fallback;
}

function assignRestAvoidance(notationEntries, clef, voiceId, occupancy) {
  let cursor = 0;
  notationEntries.forEach((entry) => {
    const beat = cursor;
    cursor += entry.units || unitsForEntry(entry);
    if (entry.kind !== "rest") return;
    if (entry.placeholder) {
      entry._restKey = "b/4";
      return;
    }
    const obstacles = (occupancy.get(beat) || [])
      .filter((item) => item.voiceId !== voiceId)
      .map((item) => item.midi);
    entry._restKey = pickRestKeyForRest(clef, voiceId, obstacles);
  });
}

function createEntryTuplets(notationEntries, notes) {
  if (!VF.Tuplet) return [];
  const tuplets = [];

  notationEntries.forEach((entry, index) => {
    if (entry.placeholder || !entry.tupletType || entry.tupletPosition !== "start") return;
    const ratio = tupletRatios[entry.tupletType];
    if (!ratio) return;
    const groupEntries = notationEntries.slice(index, index + ratio.totalNotes);
    if (groupEntries.length !== ratio.totalNotes) return;
    if (groupEntries.some((item) => item.placeholder || item.tupletGroup !== entry.tupletGroup)) return;
    const groupNotes = notes.slice(index, index + ratio.totalNotes);
    tuplets.push(new VF.Tuplet(groupNotes, {
      numNotes: ratio.totalNotes,
      notesOccupied: ratio.notesOccupied,
      bracketed: true
    }));
  });

  return tuplets;
}

function drawEntrySlurs(context, scoreEntries, notesByMeasure) {
  if (!VF.Curve) return;

  scoreEntries.forEach((entry, globalIndex) => {
    if (!entry.slurStart || entry.kind !== "note" || entry.placeholder) return;
    const targetIndex = nextSlurTargetIndex(scoreEntries, globalIndex);
    if (targetIndex < 0) return;
    const targetEntry = scoreEntries[targetIndex];
    const fromNote = notesByMeasure?.get(entry._measureIndex)?.[entry._localIndex];
    const toNote = notesByMeasure?.get(targetEntry._measureIndex)?.[targetEntry._localIndex];
    if (!fromNote || !toNote) return;

    // 同 measure: VexFlow Curve; 跨 measure: raw SVG path
    if (entry._measureIndex === targetEntry._measureIndex) {
      const slur = new VF.Curve(fromNote, toNote, {
        cps: [{ x: 0, y: 18 }, { x: 0, y: 18 }],
        thickness: 2,
        position: VF.Curve?.Position?.NEAR_TOP ?? 2,
        positionEnd: VF.Curve?.Position?.NEAR_TOP ?? 2,
        openingDirection: "down"
      });
      slur.setContext(context).draw();
    } else {
      drawCrossMeasureSlur(context, fromNote, toNote);
    }
  });

  scoreEntries.forEach((entry, globalIndex) => {
    if (!entry.slurStop || entry.kind !== "note" || entry.placeholder) return;
    if (previousSlurSourceIndex(scoreEntries, globalIndex) >= 0) return;
    const fromNote = notesByMeasure?.get(entry._measureIndex)?.[entry._localIndex];
    if (!fromNote) return;

    const slur = new VF.Curve(undefined, fromNote, {
      cps: [{ x: 0, y: 18 }, { x: 0, y: 18 }],
      thickness: 2,
      position: VF.Curve?.Position?.NEAR_TOP ?? 2,
      positionEnd: VF.Curve?.Position?.NEAR_TOP ?? 2,
      openingDirection: "down"
    });
    slur.setContext(context).draw();
  });
}

function previousSlurSourceIndex(scoreEntries, stopIndex) {
  for (let index = stopIndex - 1; index >= 0; index -= 1) {
    const entry = scoreEntries[index];
    if (entry.placeholder) continue;
    if (entry.kind === "note" && entry.slurStart) return index;
  }
  for (let index = stopIndex - 1; index >= 0; index -= 1) {
    const entry = scoreEntries[index];
    if (entry.placeholder) continue;
    if (entry.kind === "note") return index;
  }
  return -1;
}

function nextHairpinStopIndex(scoreEntries, startIndex) {
  for (let index = startIndex + 1; index < scoreEntries.length; index += 1) {
    const entry = scoreEntries[index];
    if (entry.placeholder) continue;
    if (entry.kind === "note" && entry.hairpin === "stop") return index;
  }
  return -1;
}

function drawHairpinWedge(context, hairpin, x1, x2, y, spread) {
  context.openGroup("hairpin");
  context.beginPath();
  if (hairpin === "cresc-start") {
    context.moveTo(x1, y);
    context.lineTo(x2, y - spread);
    context.moveTo(x1, y);
    context.lineTo(x2, y + spread);
  } else {
    context.moveTo(x1, y - spread);
    context.lineTo(x2, y);
    context.moveTo(x1, y + spread);
    context.lineTo(x2, y);
  }
  context.stroke();
  context.closeGroup();
}

function drawEntryHairpins(context, scoreEntries, notesByMeasure, stavesByMeasure) {
  if (!context) return;
  const spread = 4;

  scoreEntries.forEach((entry, globalIndex) => {
    if (!entry.hairpin || entry.hairpin === "stop" || entry.placeholder) return;
    const targetIndex = nextHairpinStopIndex(scoreEntries, globalIndex);
    const fromNote = notesByMeasure?.get(entry._measureIndex)?.[entry._localIndex];
    if (!fromNote) return;
    // hairpin y 用 entry 所在 stave 的 line 4 (target 通常在同一行, 简化为同 y)
    const stave = stavesByMeasure?.get(entry._measureIndex);
    if (!stave) return;
    const y = stave.getYForLine(4) + 8;
    const x1 = fromNote.getTieRightX();
    let x2;
    if (targetIndex >= 0) {
      const targetEntry = scoreEntries[targetIndex];
      const toNote = notesByMeasure?.get(targetEntry._measureIndex)?.[targetEntry._localIndex];
      x2 = toNote ? toNote.getTieLeftX() : Math.max(x1 + 20, stave.getNoteEndX());
      if (entry._measureIndex !== targetEntry._measureIndex) {
        // 跨 measure: 走 raw SVG path
        drawCrossMeasureHairpin(context, entry.hairpin, fromNote, toNote, y, spread);
        return;
      }
    } else {
      x2 = Math.max(x1 + 20, stave.getNoteEndX());
    }
    drawHairpinWedge(context, entry.hairpin, x1, x2, y, spread);
  });

  scoreEntries.forEach((entry, globalIndex) => {
    if (entry.hairpin !== "stop" || entry.placeholder) return;
    if (nextHairpinStopSourceExists(scoreEntries, globalIndex)) return;
    const stave = stavesByMeasure?.get(entry._measureIndex);
    if (!stave) return;
    const toNote = notesByMeasure?.get(entry._measureIndex)?.[entry._localIndex];
    if (!toNote) return;
    const y = stave.getYForLine(4) + 8;
    const x2 = toNote.getTieLeftX();
    const x1 = stave.getNoteStartX();
    drawHairpinWedge(context, "decresc-start", x1, x2, y, spread);
  });
}

function nextHairpinStopSourceExists(scoreEntries, stopIndex) {
  for (let index = stopIndex - 1; index >= 0; index -= 1) {
    const entry = scoreEntries[index];
    if (entry.placeholder) continue;
    if (entry.kind === "note" && entry.hairpin && entry.hairpin !== "stop") return true;
  }
  return false;
}

function nextPhraseTargetIndex(scoreEntries, startIndex) {
  for (let index = startIndex + 1; index < scoreEntries.length; index += 1) {
    const entry = scoreEntries[index];
    if (entry.placeholder) continue;
    if (entry.kind === "note" && entry.phraseStop) return index;
  }
  for (let index = startIndex + 1; index < scoreEntries.length; index += 1) {
    const entry = scoreEntries[index];
    if (entry.placeholder) continue;
    if (entry.kind === "note") return index;
  }
  return -1;
}

function drawEntryPhraseMarks(context, scoreEntries, notesByMeasure) {
  if (!VF.Curve) return;

  scoreEntries.forEach((entry, globalIndex) => {
    if (!entry.phraseStart || entry.kind !== "note" || entry.placeholder) return;
    const targetIndex = nextPhraseTargetIndex(scoreEntries, globalIndex);
    if (targetIndex < 0) return;
    const targetEntry = scoreEntries[targetIndex];
    const fromNote = notesByMeasure?.get(entry._measureIndex)?.[entry._localIndex];
    const toNote = notesByMeasure?.get(targetEntry._measureIndex)?.[targetEntry._localIndex];
    if (!fromNote || !toNote) return;

    if (entry._measureIndex === targetEntry._measureIndex) {
      const curve = new VF.Curve(fromNote, toNote, {
        cps: [{ x: 0, y: 26 }, { x: 0, y: 26 }],
        thickness: 2,
        position: VF.Curve?.Position?.NEAR_TOP ?? 2,
        positionEnd: VF.Curve?.Position?.NEAR_TOP ?? 2,
        openingDirection: "down"
      });
      curve.setContext(context).draw();
    } else {
      drawCrossMeasurePhraseMark(context, fromNote, toNote);
    }
  });

  scoreEntries.forEach((entry, globalIndex) => {
    if (!entry.phraseStop || entry.phraseStart || entry.kind !== "note" || entry.placeholder) return;
    if (nextPhraseSourceExists(scoreEntries, globalIndex)) return;
    const fromNote = notesByMeasure?.get(entry._measureIndex)?.[entry._localIndex];
    if (!fromNote) return;

    const curve = new VF.Curve(undefined, fromNote, {
      cps: [{ x: 0, y: 26 }, { x: 0, y: 26 }],
      thickness: 2,
      position: VF.Curve?.Position?.NEAR_TOP ?? 2,
      positionEnd: VF.Curve?.Position?.NEAR_TOP ?? 2,
      openingDirection: "down"
    });
    curve.setContext(context).draw();
  });
}

function nextPhraseSourceExists(scoreEntries, stopIndex) {
  for (let index = stopIndex - 1; index >= 0; index -= 1) {
    const entry = scoreEntries[index];
    if (entry.placeholder) continue;
    if (entry.kind === "note" && entry.phraseStart) return true;
  }
  return false;
}

function drawEntryArpeggios(context, notationEntries, notes) {
  if (!context) return;

  notationEntries.forEach((entry, notationIndex) => {
    if (!entry.arpeggiate || entry.placeholder) return;
    const note = notes[notationIndex];
    const box = note.getBoundingBox();
    if (!box) return;
    const x = box.x - 4;
    const yTop = box.y;
    const yBottom = box.y + box.h;
    const step = 3;
    context.openGroup("arpeggio");
    context.beginPath();
    context.moveTo(x, yTop);
    for (let y = yTop; y < yBottom; y += step) {
      const direction = ((y - yTop) / step) % 2 === 0 ? 2 : -2;
      context.lineTo(x + direction, y + step);
    }
    context.stroke();
    context.closeGroup();
  });
}

function nextSlurTargetIndex(scoreEntries, startIndex) {
  for (let index = startIndex + 1; index < scoreEntries.length; index += 1) {
    const entry = scoreEntries[index];
    if (entry.placeholder) continue;
    if (entry.kind === "note" && entry.slurStop) return index;
  }
  for (let index = startIndex + 1; index < scoreEntries.length; index += 1) {
    const entry = scoreEntries[index];
    if (entry.placeholder) continue;
    if (entry.kind === "note") return index;
  }
  return -1;
}

function drawEntryTies(context, scoreEntries, notesByMeasure) {
  if (!VF.StaveTie) return;

  scoreEntries.forEach((entry, globalIndex) => {
    if (!entry.tieStart || entry.kind !== "note" || entry.placeholder) return;
    const nextIndex = nextTieTargetIndex(scoreEntries, globalIndex);
    if (nextIndex < 0) return;
    const targetEntry = scoreEntries[nextIndex];
    const currentNote = notesByMeasure?.get(entry._measureIndex)?.[entry._localIndex];
    const targetNote = notesByMeasure?.get(targetEntry._measureIndex)?.[targetEntry._localIndex];
    if (!currentNote || !targetNote) return;
    const indexes = tieIndexes(entry, targetEntry);
    if (!indexes.length) return;

    if (entry._measureIndex === targetEntry._measureIndex) {
      const tie = new VF.StaveTie({
        firstNote: currentNote,
        lastNote: targetNote,
        firstIndexes: indexes,
        lastIndexes: indexes
      });
      tie.setContext(context).draw();
    } else {
      // 跨 measure: 走 raw SVG path fallback
      // direction: voiceId 2 在 stem 上面 (用 y 减), voiceId 1 在下面 (用 y 加)
      const direction = entryVoice(entry) === "2" ? "up" : "down";
      drawCrossMeasureTie(context, currentNote, targetNote, indexes, direction);
    }
  });

  scoreEntries.forEach((entry, globalIndex) => {
    if (!entry.tieStop || entry.kind !== "note" || entry.placeholder) return;
    const previousIndex = previousTieSourceIndex(scoreEntries, globalIndex);
    if (previousIndex >= 0) return;
    const currentNote = notesByMeasure?.get(entry._measureIndex)?.[entry._localIndex];
    if (!currentNote) return;
    const indexes = entry.pitches.map((_, index) => index);
    const tie = new VF.StaveTie({
      firstNote: null,
      lastNote: currentNote,
      firstIndexes: indexes,
      lastIndexes: indexes
    });
    tie.setContext(context).draw();
  });
}

function nextTieTargetIndex(scoreEntries, startIndex) {
  for (let index = startIndex + 1; index < scoreEntries.length; index += 1) {
    const entry = scoreEntries[index];
    if (!entry.placeholder && entry.kind === "note") return index;
    if (!entry.placeholder && entry.kind === "rest") return -1;
  }
  return -1;
}

function previousTieSourceIndex(scoreEntries, stopIndex) {
  for (let index = stopIndex - 1; index >= 0; index -= 1) {
    const entry = scoreEntries[index];
    if (!entry.placeholder && entry.kind === "note") return index;
    if (!entry.placeholder && entry.kind === "rest") return -1;
  }
  return -1;
}

function tieIndexes(fromEntry, toEntry) {
  if (!toEntry || toEntry.kind !== "note") {
    return fromEntry.pitches.map((_, index) => index);
  }
  const targetIdentities = new Set(toEntry.pitches.map(pitchIdentity));
  return fromEntry.pitches
    .map((pitch, index) => targetIdentities.has(pitchIdentity(pitch)) ? index : -1)
    .filter((index) => index >= 0);
}

function renderEntryHitboxes(notationEntries, notes, staveKey) {
  notationEntries.forEach((entry, notationIndex) => {
    if (!Number.isInteger(entry.sourceIndex)) return;
    const box = notes[notationIndex].getBoundingBox();
    if (!box) return;

    const hitbox = document.createElement("button");
    const centerX = box.x + (box.w / 2);
    hitbox.type = "button";
    hitbox.className = "score-event-hitbox";
    hitbox.classList.toggle("selected", entry.sourceIndex === selectedEntryIndex);
    if (entry.placeholder) hitbox.classList.add("placeholder");
    hitbox.style.left = `${Math.max(0, centerX - 17)}px`;
    hitbox.style.top = `${Math.max(18, box.y - 14)}px`;
    hitbox.style.width = "34px";
    hitbox.style.height = `${Math.max(62, box.h + 28)}px`;
    hitbox.setAttribute("aria-label", entry.placeholder ? "删除最后一个真条目" : `选择${entryLabel(entry, entry.sourceIndex)}`);
    hitbox.setAttribute("aria-pressed", String(entry.sourceIndex === selectedEntryIndex));
    // P22+: 点击已有音符: 优先 selectEntry; 如果 voice 不一致, 切 voice 后再选
    hitbox.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (entry.placeholder) {
        selectLastEntryInActiveVoice();
        renderNotation();
        return;
      }
      // 非 activeVoice 的 entry: 切 voice 后再选
      const entryVoiceId = entryVoice(entry);
      if (entryVoiceId !== activeVoiceId()) {
        if (voiceSelect && (entryVoiceId === "1" || entryVoiceId === "2")) {
          voiceSelect.value = entryVoiceId;
          // voice 切换会触发 handleActiveVoiceChange, 那里会重选 selectedEntryIndex
          // 但 hitbox 已经记录了 entry.sourceIndex, 改 voice 后 sourceIndex 仍有效
          // (同一 staff 同一 measure 同 index)
        }
      }
      selectEntry(entry.sourceIndex);
    });
    noteCanvas.append(hitbox);
  });
}

function entriesForRendering(entriesSource = measureEntries, selectable = true, voiceId = activeVoiceId()) {
  const indexedEntries = entriesSource
    .map((entry, sourceIndex) => ({ entry, sourceIndex }))
    .filter((item) => entryVoice(item.entry) === String(voiceId));
  const voiceEntries = indexedEntries.map((item) => item.entry);
  const used = sumEntryUnits(voiceEntries);
  const { capacity } = currentMeter();

  if (voiceEntries.length === 0) {
    return [{ kind: "rest", duration: "1", dotted: false, units: capacity, placeholder: true, fullMeasure: true }];
  }

  // P22+: 单 staff 模式允许跨 voice 点选 (切换 voice 后再选 entry);
  //        双 staff 模式保持 activeVoice 过滤 (measureEntries 唯一性约束).
  const allowCrossVoice = !isPianoMode();
  const entries = indexedEntries.map(({ entry, sourceIndex }) => ({
    ...entry,
    sourceIndex: selectable && (allowCrossVoice || entryVoice(entry) === activeVoiceId()) ? sourceIndex : undefined,
    selected: selectable && sourceIndex === selectedEntryIndex
  }));
  if (!sameUnitValue(used, capacity) && used < capacity) {
    const remaining = capacity - used;
    // 关键：fullMeasure=true 会让 VexFlow 把 duration 强制设为全小节
    // （拍号容量对应的 Fraction），当 measure 已有音符时就会超出 voice 容量
    // 触发 "Too many ticks"。这里必须按 remaining 选一个能装下的休止符，
    // 且绝对不能设 fullMeasure。
    const bestRest = restValues.find((candidate) => Math.abs(candidate.units - remaining) < 0.001)
      || restValues
        .filter((candidate) => candidate.units <= remaining + 0.001)
        .sort((a, b) => b.units - a.units)[0];
    if (bestRest) {
      const placeholder = {
        kind: "rest",
        duration: bestRest.duration,
        dotted: bestRest.dotted,
        units: bestRest.units,
        placeholder: true,
        _restKey: "b/4",
        sourceIndex: selectable ? -1 : undefined
      };
      entries.push(placeholder);
    }
  }
  return entries;
}

function placeholderRests(start, remaining) {
  const meter = currentMeter();
  const compound = meter.denominator === 8 && meter.numerator >= 6 && meter.numerator % 3 === 0;
  const groupUnits = meter.beatUnit * (compound ? 3 : 1);
  const rests = [];
  let cursor = start;
  let left = remaining;

  while (left > 0.001) {
    const positionInGroup = cursor % groupUnits;
    const roomInGroup = positionInGroup === 0 ? groupUnits : groupUnits - positionInGroup;
    let span = Math.min(left, roomInGroup);

    while (span > 0.001) {
      const value = restValues.find((candidate) => candidate.units <= span);
      if (!value) {
        left = 0;
        span = 0;
        break;
      }
      rests.push({ kind: "rest", ...value, placeholder: true });
      cursor += value.units;
      left -= value.units;
      span -= value.units;
    }
  }
  return rests;
}

function updateMeasureMeter() {
  const meter = currentMeter();
  const used = sumCurrentVoiceUnits();
  const unitCount = used / meter.beatUnit;
  const remainingCount = (meter.capacity - used) / meter.beatUnit;
  const measureNumber = currentMeasureIndex + 1;
  const suffix = meter.denominator === 8 ? "个八分音符时值" : "拍";

  measureStatus.textContent = `${activeStaffLabel()} · ${activeVoiceLabel()} · 第 ${measureNumber} 小节：${formatCount(unitCount)} / ${meter.numerator} ${suffix}`;
  measureProgress.style.width = `${Math.min(100, (used / meter.capacity) * 100)}%`;
  measureProgress.classList.toggle("complete", sameUnitValue(used, meter.capacity));
  measureNavStatus.textContent = `第 ${measureNumber} / ${scoreMeasures.length} 小节`;

  if (sameUnitValue(used, 0)) {
    showEditorMessage("待输入", "neutral");
  } else if (sameUnitValue(used, meter.capacity)) {
    showEditorMessage("小节时值完整", "success");
  } else {
    showEditorMessage(`还差 ${formatCount(remainingCount)} ${suffix}`, "neutral");
  }
}

function formatCount(value) {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
}

function showEditorMessage(message, state = "neutral") {
  editorMessage.textContent = message;
  editorMessage.dataset.state = state;
}

function updateEditorControls() {
  const hasEntries = measureEntries.length > 0;
  const selectedEntry = measureEntries[selectedEntryIndex];
  const restMode = inputKind() === "rest";
  const chordModeControl = document.querySelector('input[name="entryMode"][value="chord"]');
  const newModeControl = document.querySelector('input[name="entryMode"][value="new"]');

  undoNotesButton.disabled = editHistory.length === 0;
  clearNotesButton.disabled = currentVoiceEntries().length === 0;
  prevMeasureButton.disabled = currentMeasureIndex === 0;
  nextMeasureButton.disabled = currentMeasureIndex >= scoreMeasures.length - 1;
  deleteMeasureButton.disabled = scoreMeasures.length === 1 && !hasEntries;
  noteAccidental.disabled = restMode;
  chordModeControl.disabled = restMode || !selectedEntry || selectedEntry.kind !== "note";
  if (chordModeControl.disabled && chordModeControl.checked) newModeControl.checked = true;
  renderSelectionBar();
}

function renderSelectionBar() {
  const entry = measureEntries[selectedEntryIndex];
  if (selectionBar) selectionBar.hidden = !entry;
  if (!entry) return;

  if (selectedEventLabel) selectedEventLabel.textContent = entryLabel(entry, selectedEntryIndex);
  if (selectedToneField) selectedToneField.hidden = entry.kind !== "note";
  if (dynamicField) dynamicField.hidden = false;
  if (dynamicSelect) dynamicSelect.value = entry.dynamic || "";
  if (chordField) chordField.hidden = entry.kind !== "note";
  if (chordSymbolInput) chordSymbolInput.value = entry.chordSymbol || "";
  if (articulationField) articulationField.hidden = entry.kind !== "note";
  if (articulationSelect) articulationSelect.value = entry.articulation || "";
  if (ornamentField) ornamentField.hidden = entry.kind !== "note";
  if (ornamentSelect) ornamentSelect.value = entry.ornament || "";
  if (graceField) graceField.hidden = entry.kind !== "note";
  if (graceInput) graceInput.value = entry.grace ? `${entry.grace.step}${displayAccidental(entry.grace.accidental || "")}${entry.grace.octave}` : "";
  if (pedalField) pedalField.hidden = entry.kind !== "note";
  if (pedalSelect) pedalSelect.value = entry.pedal || "";
  if (hairpinField) hairpinField.hidden = entry.kind !== "note";
  if (hairpinSelect) hairpinSelect.value = entry.hairpin || "";
  if (fingeringField) fingeringField.hidden = entry.kind !== "note";
  if (fingeringInput) fingeringInput.value = entry.fingering || "";
  if (rehearsalMarkInput) rehearsalMarkInput.value = entry.rehearsalMark || "";
  if (voltaSelect) voltaSelect.value = entry.volta == null ? "" : String(entry.volta);
  if (arpeggioField) arpeggioField.hidden = entry.kind !== "note";
  if (arpeggioCheck) arpeggioCheck.checked = Boolean(entry.arpeggiate);
  if (togglePhraseStartButton) togglePhraseStartButton.hidden = entry.kind !== "note";
  if (togglePhraseStopButton) togglePhraseStopButton.hidden = entry.kind !== "note";
  if (togglePhraseStartButton) togglePhraseStartButton.setAttribute("aria-pressed", String(Boolean(entry.phraseStart)));
  if (togglePhraseStopButton) togglePhraseStopButton.setAttribute("aria-pressed", String(Boolean(entry.phraseStop)));
  if (textMarkField) textMarkField.hidden = entry.kind !== "note";
  if (textMarkInput) textMarkInput.value = entry.textMark || "";
  if (breathField) breathField.hidden = entry.kind !== "note";
  if (breathCheck) breathCheck.checked = Boolean(entry.breath);
  if (deleteToneButton) deleteToneButton.hidden = entry.kind !== "note";
  if (toggleTieStartButton) toggleTieStartButton.hidden = entry.kind !== "note";
  if (toggleTieStopButton) toggleTieStopButton.hidden = entry.kind !== "note";
  if (toggleSlurStartButton) toggleSlurStartButton.hidden = entry.kind !== "note";
  if (toggleSlurStopButton) toggleSlurStopButton.hidden = entry.kind !== "note";
  if (toggleTieStartButton) toggleTieStartButton.setAttribute("aria-pressed", String(Boolean(entry.tieStart)));
  if (toggleTieStopButton) toggleTieStopButton.setAttribute("aria-pressed", String(Boolean(entry.tieStop)));
  if (toggleSlurStartButton) toggleSlurStartButton.setAttribute("aria-pressed", String(Boolean(entry.slurStart)));
  if (toggleSlurStopButton) toggleSlurStopButton.setAttribute("aria-pressed", String(Boolean(entry.slurStop)));
  if (toggleFermataButton) toggleFermataButton.setAttribute("aria-pressed", String(Boolean(entry.fermata)));
  if (tupletTypeSelect) tupletTypeSelect.value = entry.tupletType || "";

  if (entry.kind === "note") {
    if (selectedToneSelect) {
      selectedToneSelect.innerHTML = entry.pitches.map((pitch) => (
        `<option value="${escapeHtml(pitchIdentity(pitch))}">${escapeHtml(pitch.display)}</option>`
      )).join("");
    }
  } else {
    if (selectedToneSelect) selectedToneSelect.replaceChildren();
  }
}

function entryLabel(entry, index) {
  const duration = durationLabel(entry.duration, entry.dotted);
  const marks = [
    entry.tieStart ? "延音开始" : "",
    entry.tieStop ? "延音结束" : "",
    entry.slurStart ? "连线开始" : "",
    entry.slurStop ? "连线结束" : "",
    entry.dynamic ? entry.dynamic : "",
    entry.fermata ? "fermata" : "",
    entry.tupletType === "triplet" ? "三连音" : ""
  ].filter(Boolean);
  const markText = marks.length ? ` · ${marks.join(" / ")}` : "";
  if (entry.kind === "rest") return `${activeVoiceLabel()} · 第 ${index + 1} 拍位 · ${duration}休止符${markText}`;
  return `${activeVoiceLabel()} · 第 ${index + 1} 拍位 · ${entry.pitches.map((pitch) => pitch.display).join("+")} · ${duration}${markText}`;
}

function durationLabel(duration, dotted = false) {
  const label = {
    "0": "二全音符",
    "1": "全音符",
    "2": "二分音符",
    "4": "四分音符",
    "8": "八分音符",
    "16": "十六分音符",
    "32": "三十二分音符",
    "64": "六十四分音符"
  }[String(duration)] || duration;
  const dots = dotCount(dotted);
  return dots === 2 ? `双附点${label}` : dots === 1 ? `附点${label}` : label;
}

function selectEntry(index) {
  const entry = measureEntries[index];
  if (!entry) return;
  selectedEntryIndex = index;
  noteDuration.value = entry.duration;
  noteDotted.value = String(dotCount(entry.dotted));
  const kindControl = document.querySelector(`input[name="inputKind"][value="${entry.kind}"]`);
  if (kindControl) kindControl.checked = true;
  // P22+: 同步 voiceSelect 到 entry.voice (双 staff 模式不变, 单 staff 模式允许跨 voice)
  const entryVoiceId = entryVoice(entry);
  if (voiceSelect && (entryVoiceId === "1" || entryVoiceId === "2") && entryVoiceId !== activeVoiceId()) {
    voiceSelect.value = entryVoiceId;
  }
  renderNotation();
}

function snapshotEditor() {
  return {
    entries: JSON.parse(JSON.stringify(measureEntries)),
    selectedEntryIndex,
    measureIndex: currentMeasureIndex
  };
}

function commitEdit(callback) {
  editHistory.push(snapshotEditor());
  if (editHistory.length > 80) editHistory.shift();
  try {
    callback();
    repairTupletGroups();
    normalizeSelection();
    renderNotation();
  } catch (error) {
    // 任何 commit 路径上的异常都不能让 UI 卡死
    handleRenderError(error);
  }
}

function repairTupletGroups() {
  const groups = new Map();
  measureEntries.forEach((entry, index) => {
    if (!entry.tupletGroup) return;
    if (!groups.has(entry.tupletGroup)) groups.set(entry.tupletGroup, []);
    groups.get(entry.tupletGroup).push({ entry, index });
  });

  groups.forEach((items) => {
    const ratio = tupletRatios[items[0].entry.tupletType];
    const expectedCount = ratio ? ratio.totalNotes : 0;
    const positions = items.map((item) => item.entry.tupletPosition).join(",");
    const expectedPositions = expectedCount ? tupletPositions(expectedCount).join(",") : "";
    const voiceEntries = entriesForVoice(measureEntries, entryVoice(items[0].entry));
    const firstVoiceIndex = voiceEntries.indexOf(items[0].entry);
    const contiguous = expectedCount > 0 && items.length === expectedCount && firstVoiceIndex >= 0 && items.every((item, offset) => voiceEntries[firstVoiceIndex + offset] === item.entry);
    const sameType = items.every((item) => item.entry.tupletType === items[0].entry.tupletType);
    const valid = contiguous && positions === expectedPositions && sameType && !!ratio;
    if (valid) return;
    items.forEach((item) => {
      clearTupletFields(item.entry);
      item.entry.units = unitsForEntry(item.entry);
    });
  });
}

function normalizeSelection() {
  if (!measureEntries.length) {
    selectedEntryIndex = -1;
  } else if (selectedEntryIndex < 0 || selectedEntryIndex >= measureEntries.length || entryVoice(measureEntries[selectedEntryIndex]) !== activeVoiceId()) {
    selectLastEntryInActiveVoice();
  }
}

function undoEdit() {
  const previous = editHistory.pop();
  if (!previous) return;
  if (Number.isInteger(previous.measureIndex) && previous.measureIndex !== currentMeasureIndex) {
    currentMeasureIndex = previous.measureIndex;
    noteMeasure.value = String(currentMeasureIndex + 1);
  }
  setCurrentMeasureEntries(previous.entries);
  selectedEntryIndex = previous.selectedEntryIndex;
  normalizeSelection();
  try { renderNotation(); } catch (e) { handleRenderError(e); }
}

function deleteSelectedTone() {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  const identity = selectedToneSelect.value;

  commitEdit(() => {
    if (entry.pitches.length === 1) {
      measureEntries.splice(selectedEntryIndex, 1);
      selectedEntryIndex = Math.min(selectedEntryIndex, measureEntries.length - 1);
      return;
    }
    entry.pitches = entry.pitches.filter((pitch) => pitchIdentity(pitch) !== identity);
  });
}

function deleteSelectedEvent() {
  if (!measureEntries[selectedEntryIndex]) return;
  commitEdit(() => {
    measureEntries.splice(selectedEntryIndex, 1);
    selectedEntryIndex = Math.min(selectedEntryIndex, measureEntries.length - 1);
  });
}

function applyDurationToSelected() {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry) return;
  const groupId = entry.tupletGroup || "";
  // P22.3 duration-cleanup: business 统一从 editorState 读
  const esDur = editorState.getInputDuration();
  const duration = esDur.duration;
  const dotted = esDur.dotted;
  const nextUnits = unitsForDuration(duration, dotted);
  const nextTotal = currentVoiceEntries().reduce((total, item) => {
    if (item === entry) return total + nextUnits;
    if (groupId && item.tupletGroup === groupId) return total + unitsForDuration(item.duration, item.dotted);
    return total + unitsForEntry(item);
  }, 0);

  if (exceedsUnitValue(nextTotal, currentMeter().capacity)) {
    showEditorMessage("修改后的时值会超过本小节拍数。", "error");
    return;
  }

  commitEdit(() => {
    if (groupId) {
      measureEntries.forEach((item) => {
        if (item.tupletGroup === groupId) {
          clearTupletFields(item);
          item.units = unitsForEntry(item);
        }
      });
    }
    entry.duration = duration;
    entry.dotted = dotted;
    entry.units = nextUnits;
  });
}

function clearTupletFields(entry) {
  entry.tupletType = "";
  entry.tupletGroup = "";
  entry.tupletPosition = "";
}

function toggleTupletGroup() {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry) return;
  const type = tupletTypeSelect.value;
  const ratio = tupletRatios[type];

  if (entry.tupletType && entry.tupletGroup) {
    const groupId = entry.tupletGroup;
    commitEdit(() => {
      measureEntries.forEach((item) => {
        if (item.tupletGroup === groupId) {
          clearTupletFields(item);
          item.units = unitsForEntry(item);
        }
      });
    });
    return;
  }

  if (!ratio) {
    showEditorMessage("请先选择连音类型（三/五/六连音）。", "error");
    return;
  }

  const count = ratio.totalNotes;
  const activeEntries = currentVoiceEntries();
  const selectedVoiceIndex = activeEntries.indexOf(entry);
  const group = activeEntries.slice(selectedVoiceIndex, selectedVoiceIndex + count);
  if (group.length !== count) {
    showEditorMessage(`${ratio.label}组需要从当前拍位开始连续 ${count} 个音符或休止符。`, "error");
    return;
  }
  if (group.some((item) => item.tupletType)) {
    showEditorMessage(`这 ${count} 个拍位里已有连音组，请先取消原来的连音。`, "error");
    return;
  }
  if (new Set(group.map((item) => `${item.duration}:${item.dotted}`)).size !== 1) {
    showEditorMessage(`第一版连音要求 ${count} 个拍位使用相同时值。`, "error");
    return;
  }

  const groupId = `tuplet-${Date.now()}-${selectedEntryIndex}`;
  const positions = tupletPositions(count);
  commitEdit(() => {
    group.forEach((item, offset) => {
      item.tupletType = type;
      item.tupletGroup = groupId;
      item.tupletPosition = positions[offset];
      item.units = unitsForEntry(item);
    });
  });
}

function toggleSelectedFlag(flagName) {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry) return;
  if ((flagName === "tieStart" || flagName === "tieStop" || flagName === "slurStart" || flagName === "slurStop") && entry.kind !== "note") return;

  commitEdit(() => {
    const nextValue = !entry[flagName];
    entry[flagName] = nextValue;
    if (flagName === "tieStart") {
      const target = nextTieTargetEntry(selectedEntryIndex);
      if (target && hasSharedPitch(entry, target)) {
        target.tieStop = nextValue;
      }
    } else if (flagName === "slurStart") {
      const target = nextSlurTargetEntry(selectedEntryIndex);
      if (target) {
        target.slurStop = nextValue;
      }
    }
  });
}

function nextTieTargetEntry(startIndex) {
  for (let index = startIndex + 1; index < measureEntries.length; index += 1) {
    const entry = measureEntries[index];
    if (entry.kind === "note") return entry;
    if (entry.kind === "rest") return null;
  }
  return null;
}

function hasSharedPitch(left, right) {
  if (!left?.pitches || !right?.pitches) return false;
  const rightIdentities = new Set(right.pitches.map(pitchIdentity));
  return left.pitches.some((pitch) => rightIdentities.has(pitchIdentity(pitch)));
}

function nextSlurTargetEntry(startIndex) {
  for (let index = startIndex + 1; index < measureEntries.length; index += 1) {
    const entry = measureEntries[index];
    if (entry.kind === "note") return entry;
  }
  return null;
}

function setSelectedDynamic(value) {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry) return;
  commitEdit(() => {
    entry.dynamic = value;
  });
}

function updateCurrentMeasureBarlines() {
  const applySettings = (_, state) => {
    state.settings[currentMeasureIndex] ||= defaultMeasureSettings();
    state.settings[currentMeasureIndex].beginBarline = beginBarlineSelect.value;
    state.settings[currentMeasureIndex].endBarline = endBarlineSelect.value;
  };
  if (isPianoMode()) {
    forEachVisibleStaff(applySettings);
  } else {
    applySettings(activeStaffKey(), staffScores[activeStaffKey()]);
  }
  activateStaff();
  renderNotation();
}

function displayAccidental(value) {
  return { "#": "♯", b: "♭", n: "♮" }[value] || "";
}

function accidentalFromApi(value) {
  return { sharp: "#", flat: "b", natural: "n" }[value] || "";
}

function handleTimeSignatureChange() {
  const overflowing = [];
  Object.entries(staffScores).forEach(([staffKey, state]) => {
    state.measures.forEach((measure, measureIndex) => {
      voiceIds.forEach((voiceId) => {
        if (exceedsUnitValue(sumEntryUnits(entriesForVoice(measure, voiceId)), currentMeter().capacity)) {
          overflowing.push({ staffKey, measureIndex, voiceId });
        }
      });
    });
  });
  if (overflowing.length) {
    const first = overflowing[0];
    const label = first.staffKey === "bass" ? "左手/低音谱表" : "右手/高音谱表";
    editorTime.value = previousTimeSignature;
    showEditorMessage(`${label}声部 ${first.voiceId} 第 ${first.measureIndex + 1} 小节超过新拍号容量，请先删除部分内容。`, "error");
    return;
  }
  previousTimeSignature = editorTime.value;
  renderNotation();
}

function handleStaffModeChange() {
  activateStaff();
  ensureMeasureExistsForVisibleStaves(currentMeasureIndex);
  selectedEntryIndex = measureEntries.length ? measureEntries.length - 1 : -1;
  editHistory = [];
  renderNotation();
}

function handleActiveStaffChange() {
  activateStaff();
  selectLastEntryInActiveVoice();
  // P22+: 不再清 editHistory — 切 staff 不应丢撤销栈
  beginBarlineSelect.value = measureSettings[currentMeasureIndex]?.beginBarline || "single";
  endBarlineSelect.value = measureSettings[currentMeasureIndex]?.endBarline || "single";
  renderNotation();
}

function handleActiveVoiceChange() {
  selectLastEntryInActiveVoice();
  // P22+: 不再清 editHistory — 切 voice 不应丢撤销栈
  renderNotation();
}

function selectLastEntryInActiveVoice() {
  selectedEntryIndex = -1;
  for (let index = measureEntries.length - 1; index >= 0; index -= 1) {
    if (entryVoice(measureEntries[index]) === activeVoiceId()) {
      selectedEntryIndex = index;
      break;
    }
  }
}

function collectScoreDocument() {
  const maxMeasureCount = Math.max(
    1,
    ...Object.values(staffScores).map((state) => state.measures.length)
  );
  const staffKeys = isPianoMode() ? ["treble", "bass"] : [activeStaffKey()];
  const meter = currentMeter();

  return {
    schemaVersion: "manual-score-v1",
    title: "Manual score",
    timeSignature: editorTime.value,
    keySignature: editorKey.value,
    tempo: Number(tempoInput.value) || 0,
    anacrusis: Boolean(anacrusisCheck.checked),
    staffMode: staffMode.value,
    voiceRoleMap: buildVoiceRoleMap(staffKeys),
    activeStaff: activeStaffKey(),
    activeVoice: activeVoiceId(),
    measureCount: maxMeasureCount,
    staves: staffKeys.map((staffKey, staffIndex) => {
      const state = staffScores[staffKey];
      return {
        id: staffKey,
        staffNumber: staffIndex + 1,
        label: staffKey === "bass" ? "左手/低音谱表" : "右手/高音谱表",
        clef: staffKey,
        measures: Array.from({ length: maxMeasureCount }, (_, measureIndex) => {
          const entries = state.measures[measureIndex] || [];
          const settings = state.settings[measureIndex] || defaultMeasureSettings();
          return {
            number: measureIndex + 1,
            beginBarline: settings.beginBarline || "single",
            endBarline: settings.endBarline || "single",
            voices: voiceIds.map((voiceId) => ({
              id: voiceId,
              role: voiceRoleFor(staffKey, voiceId),
              usedUnits: sumEntryUnits(entriesForVoice(entries, voiceId)),
              entries: exportVoiceEntries(entriesForVoice(entries, voiceId), meter.capacity)
            }))
          };
        })
      };
    })
  };
}

function buildVoiceRoleMap(staffKeys) {
  return staffKeys.flatMap((staffKey) => voiceIds.map((voiceId) => ({
    staff: staffKey,
    voice: voiceId,
    role: voiceRoleFor(staffKey, voiceId)
  })));
}

function voiceRoleFor(staffKey, voiceId) {
  if (staffKey === "treble" && voiceId === "1") return "soprano";
  if (staffKey === "treble" && voiceId === "2") return "alto";
  if (staffKey === "bass" && voiceId === "1") return "tenor";
  if (staffKey === "bass" && voiceId === "2") return "bass";
  return "";
}

function normalizeEntryForExport(entry, index) {
  return {
    index: index + 1,
    kind: entry.kind,
    voice: entryVoice(entry),
    duration: entry.duration,
    dotted: dotCount(entry.dotted),
    units: unitsForEntry(entry),
    pitches: entry.kind === "note" ? entry.pitches.map((pitch) => ({ ...pitch })) : [],
    tieStart: Boolean(entry.tieStart),
    tieStop: Boolean(entry.tieStop),
    slurStart: Boolean(entry.slurStart),
    slurStop: Boolean(entry.slurStop),
    fermata: Boolean(entry.fermata),
    dynamic: entry.dynamic || "",
    chordSymbol: entry.chordSymbol || "",
    articulation: entry.articulation || "",
    ornament: entry.ornament || "",
    grace: entry.grace ? { ...entry.grace } : null,
    pedal: entry.pedal || "",
    hairpin: entry.hairpin || "",
    fingering: entry.fingering || "",
    arpeggiate: Boolean(entry.arpeggiate),
    phraseStart: Boolean(entry.phraseStart),
    phraseStop: Boolean(entry.phraseStop),
    textMark: entry.textMark || "",
    breath: Boolean(entry.breath),
    tupletType: entry.tupletType || "",
    tupletGroup: entry.tupletGroup || "",
    tupletPosition: entry.tupletPosition || ""
  };
}

// 底层位置系统：为单一声部的每个音符计算 startUnit（从小节起始的偏移单位）
// 与 crossesBar（该音符是否跨越小节线）。startUnit 按声部内顺序累积。
function exportVoiceEntries(voiceEntries, capacity) {
  let cursor = 0;
  return voiceEntries.map((entry, index) => {
    const exported = normalizeEntryForExport(entry, index);
    exported.startUnit = normalizeUnitValue(cursor);
    cursor += exported.units;
    exported.crossesBar = capacity != null && (exported.startUnit + exported.units - capacity) > 0.001;
    return exported;
  });
}

function validateScoreDocument(documentData = collectScoreDocument()) {
  const meter = meterForTimeSignature(documentData.timeSignature);
  const issues = [];

  documentData.staves.forEach((staff) => {
    staff.measures.forEach((measure) => {
      measure.voices.forEach((voice) => {
        if (!voice.entries.length) return;
        if (exceedsUnitValue(voice.usedUnits, meter.capacity)) {
          issues.push({
            level: "error",
            message: `${staff.label} 声部 ${voice.id} 第 ${measure.number} 小节超过拍号容量。`
          });
        } else if (!sameUnitValue(voice.usedUnits, meter.capacity) && !(documentData.anacrusis && measure.number === 1)) {
          issues.push({
            level: "warning",
            message: `${staff.label} 声部 ${voice.id} 第 ${measure.number} 小节时值未填满。`
          });
        }
        for (let i = 1; i < voice.entries.length; i += 1) {
          const prev = voice.entries[i - 1];
          const current = voice.entries[i];
          if (typeof prev.startUnit !== "number" || typeof current.startUnit !== "number") break;
          if (current.startUnit + 0.001 < prev.startUnit + prev.units) {
            issues.push({
              level: "error",
              message: `${staff.label} 声部 ${voice.id} 第 ${measure.number} 小节音符位置重叠。`
            });
          }
        }
        issues.push(...validateVoiceSymbols(documentData, staff, measure, voice));
      });
    });
  });

  return {
    ok: !issues.some((issue) => issue.level === "error"),
    issues
  };
}

function validateVoiceSymbols(documentData, staff, measure, voice) {
  const issues = [];
  voice.entries.forEach((entry, entryIndex) => {
    if (entry.tieStart) {
      const target = nextExportNote(documentData, staff.id, voice.id, measure.number - 1, entryIndex);
      const sharedPitch = target && entry.pitches.some((pitch) => target.pitches.some((targetPitch) => pitchIdentity(pitch) === pitchIdentity(targetPitch)));
      if (!target) {
        issues.push({ level: "warning", message: `${staff.label} 声部 ${voice.id} 第 ${measure.number} 小节有延音开始，但后面没有目标音。` });
      } else if (!sharedPitch) {
        issues.push({ level: "error", message: `${staff.label} 声部 ${voice.id} 第 ${measure.number} 小节延音线没有连到相同音高。` });
      }
    }
    if (entry.tieStop) {
      const source = previousExportNote(documentData, staff.id, voice.id, measure.number - 1, entryIndex);
      const sharedPitch = source && entry.pitches.some((pitch) => source.pitches.some((sourcePitch) => pitchIdentity(pitch) === pitchIdentity(sourcePitch)));
      if (!source) {
        issues.push({ level: "warning", message: `${staff.label} 声部 ${voice.id} 第 ${measure.number} 小节有延音结束，但前面没有来源音。` });
      } else if (!sharedPitch) {
        issues.push({ level: "error", message: `${staff.label} 声部 ${voice.id} 第 ${measure.number} 小节延音结束没有接到相同音高。` });
      }
    }
    if (entry.tupletType === "triplet" && !["start", "middle", "end"].includes(entry.tupletPosition)) {
      issues.push({ level: "error", message: `${staff.label} 声部 ${voice.id} 第 ${measure.number} 小节三连音标记不完整。` });
    }
  });
  return issues;
}

function nextExportNote(documentData, staffId, voiceId, measureIndex, entryIndex) {
  const staff = documentData.staves.find((item) => item.id === staffId);
  if (!staff) return null;
  for (let measureCursor = measureIndex; measureCursor < staff.measures.length; measureCursor += 1) {
    const voice = staff.measures[measureCursor].voices.find((item) => item.id === voiceId);
    const startIndex = measureCursor === measureIndex ? entryIndex + 1 : 0;
    for (const entry of voice?.entries.slice(startIndex) || []) {
      if (entry.kind === "rest") return null;
      if (entry.kind === "note") return entry;
    }
  }
  return null;
}

function previousExportNote(documentData, staffId, voiceId, measureIndex, entryIndex) {
  const staff = documentData.staves.find((item) => item.id === staffId);
  if (!staff) return null;
  for (let measureCursor = measureIndex; measureCursor >= 0; measureCursor -= 1) {
    const voice = staff.measures[measureCursor].voices.find((item) => item.id === voiceId);
    const endIndex = measureCursor === measureIndex ? entryIndex : voice?.entries.length || 0;
    const candidates = (voice?.entries || []).slice(0, endIndex);
    for (let index = candidates.length - 1; index >= 0; index -= 1) {
      if (candidates[index].kind === "rest") return null;
      if (candidates[index].kind === "note") return candidates[index];
    }
  }
  return null;
}

function showScoreValidation() {
  const documentData = collectScoreDocument();
  const validation = validateScoreDocument(documentData);
  scoreDataOutput.value = validation.issues.length
    ? validation.issues.map((issue) => `${issue.level.toUpperCase()}: ${issue.message}`).join("\n")
    : "谱面检查通过：当前已输入声部没有超拍，完整声部可用于后续分析。";
  scoreExportStatus.textContent = validation.ok ? "检查通过" : "有错误";
}

function exportScoreJson() {
  const documentData = collectScoreDocument();
  const validation = validateScoreDocument(documentData);
  // P22.5-B.5: 同时输出 Score Model JSON (供序列化测试 + 未来持久化)
  let scoreModelJson = null;
  try {
    if (typeof window !== "undefined" && window.ScoreModel) {
      const isPiano = staffMode?.value === "piano";
      const legacy = isPiano
        ? {
            staffScores: {
              treble: { measures: staffScores?.treble?.measures || [] },
              bass: { measures: staffScores?.bass?.measures || [] }
            }
          }
        : { scoreMeasures: staffScores?.[activeStaffKey()]?.measures || [] };
      const score = window.ScoreModel.buildScore(legacy);
      window.ScoreModel.buildRelations(score);
      scoreModelJson = JSON.parse(JSON.stringify(score));
    }
  } catch (e) {
    console.warn("[P22.5-B.5 exportScoreJson] Score Model build failed:", e);
  }
  scoreDataOutput.value = JSON.stringify({ score: documentData, scoreModel: scoreModelJson, validation }, null, 2);
  scoreExportStatus.textContent = validation.ok ? "结构数据已生成" : "结构数据含错误";
}

function exportScoreMusicXml() {
  const documentData = collectScoreDocument();
  const validation = validateScoreDocument(documentData);
  scoreDataOutput.value = buildMusicXml(documentData);
  scoreExportStatus.textContent = validation.ok ? "MusicXML 已生成" : "MusicXML 含未完成声部";
}

function importMusicXmlFile(file) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const parsed = parseMusicXmlText(String(reader.result));
      if (!parsed.staves.treble.length && !parsed.staves.bass.length) {
        throw new Error("没有解析到有效小节。");
      }
      loadParsedMusicXml(parsed);
    } catch (error) {
      showEditorMessage("MusicXML 导入失败：" + error.message, "error");
    }
  };
  reader.onerror = () => showEditorMessage("MusicXML 文件读取失败。", "error");
  reader.readAsText(file);
}

function loadParsedMusicXml(parsed) {
  editorTime.value = parsed.timeSignature;
  editorKey.value = parsed.keySignature;
  ["treble", "bass"].forEach((staffKey) => {
    const state = staffScores[staffKey];
    const parsedMeasures = parsed.staves[staffKey] || [];
    state.measures = parsedMeasures.map((measure) => {
      const entries = [];
      (measure.voices || []).forEach((voice) => {
        (voice.entries || []).forEach((entry) => {
          entries.push({ ...entry, voice: voice.id });
        });
      });
      return entries;
    });
    state.settings = state.measures.map((_, idx) => {
      const parsed = parsedMeasures[idx];
      return {
        beginBarline: parsed?.beginBarline || "single",
        endBarline: parsed?.endBarline || "single"
      };
    });
  });
  currentMeasureIndex = 0;
  noteMeasure.value = "1";
  activateStaff();
  selectLastEntryInActiveVoice();
  editHistory = [];
  renderNotation();
  showEditorMessage("MusicXML 已导入", "success");
}

function buildMusicXml(documentData) {
  const meter = meterForTimeSignature(documentData.timeSignature);
  const divisions = MUSICXML_DIVISIONS;
  const partId = "P1";
  const staffCount = documentData.staves.length;
  const body = [];

  body.push('<?xml version="1.0" encoding="UTF-8" standalone="no"?>');
  body.push('<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">');
  body.push('<score-partwise version="4.0">');
  body.push(`  <work><work-title>${xmlEscape(documentData.title)}</work-title></work>`);
  body.push('  <part-list>');
  body.push(`    <score-part id="${partId}"><part-name>Manual Score</part-name></score-part>`);
  body.push('  </part-list>');
  body.push(`  <part id="${partId}">`);

  for (let measureIndex = 0; measureIndex < documentData.measureCount; measureIndex += 1) {
    body.push(`    <measure number="${measureIndex + 1}"${documentData.anacrusis && measureIndex === 0 ? ' implicit="yes"' : ""}>`);
    if (measureIndex === 0) {
      body.push(...musicXmlAttributes(documentData, true, divisions, staffCount));
      if (documentData.tempo) {
        body.push('      <direction placement="above">');
        body.push('        <direction-type>');
        body.push('          <metronome>');
        body.push('            <beat-unit>quarter</beat-unit>');
        body.push(`            <per-minute>${documentData.tempo}</per-minute>`);
        body.push('          </metronome>');
        body.push('        </direction-type>');
        body.push('      </direction>');
      }
    }
    let writtenUnits = 0;
    documentData.staves.forEach((staff) => {
      staff.measures[measureIndex].voices.forEach((voice) => {
        if (!voice.entries.length) return;
        if (writtenUnits > 0) {
          body.push('      <backup>');
          body.push(`        <duration>${Math.round(writtenUnits * DIVISIONS_PER_UNIT)}</duration>`);
          body.push('      </backup>');
        }
        voice.entries.forEach((entry) => {
          body.push(...musicXmlEntry(entry, staff.staffNumber, musicXmlVoiceNumber(staff.staffNumber, voice.id), divisions, meter.capacity));
        });
        writtenUnits += voice.entries.reduce((sum, entry) => sum + (entry.units || 0), 0);
      });
    });
    if (writtenUnits === 0) {
      documentData.staves.forEach((staff) => {
        body.push(...musicXmlEntry({
          kind: "rest",
          units: meter.capacity,
          duration: "1",
          dotted: false,
          tupletType: "",
          tupletPosition: "",
          tieStart: false,
          tieStop: false,
          slurStart: false,
          slurStop: false,
          fermata: false,
          dynamic: ""
        }, staff.staffNumber, musicXmlVoiceNumber(staff.staffNumber, "1"), divisions, meter.capacity));
      });
    }
    body.push(...musicXmlBarlines(documentData.staves[0].measures[measureIndex]));
    body.push('    </measure>');
  }

  body.push('  </part>');
  body.push('</score-partwise>');
  return body.join("\n");
}

function musicXmlAttributes(documentData, includeClefs, divisions, staffCount) {
  const meter = meterForTimeSignature(documentData.timeSignature);
  const fifths = keyFifths[documentData.keySignature] || 0;
  const isMinor = /m$/.test(String(documentData.keySignature || ""));
  const keyMode = isMinor ? "\n        <mode>minor</mode>" : "";
  const lines = [
    '      <attributes>',
    `        <divisions>${divisions}</divisions>`,
    `        <key><fifths>${fifths}</fifths>${keyMode}</key>`,
    '        <time>',
    `          <beats>${meter.numerator}</beats>`,
    `          <beat-type>${meter.denominator}</beat-type>`,
    '        </time>'
  ];
  if (staffCount > 1) lines.push(`        <staves>${staffCount}</staves>`);
  if (includeClefs) {
    documentData.staves.forEach((staff) => {
      lines.push(`        <clef number="${staff.staffNumber}">`);
      lines.push(`          <sign>${staff.clef === "bass" ? "F" : "G"}</sign>`);
      lines.push(`          <line>${staff.clef === "bass" ? "4" : "2"}</line>`);
      lines.push('        </clef>');
    });
  }
  lines.push('      </attributes>');
  return lines;
}

function musicXmlEntry(entry, staffNumber, voiceNumber, divisions, capacity) {
  const lines = [];
  if (entry.chordSymbol) {
    lines.push(...musicXmlHarmony(entry));
  }
  if (entry.pedal) {
    lines.push('      <direction placement="below">');
    lines.push('        <direction-type>');
    lines.push(`          <pedal type="${entry.pedal}"/>`);
    lines.push('        </direction-type>');
    lines.push(`        <staff>${staffNumber}</staff>`);
    lines.push('      </direction>');
  }
  if (entry.hairpin) {
    const wedgeType = entry.hairpin === "cresc-start" ? "crescendo" : entry.hairpin === "decresc-start" ? "diminuendo" : "stop";
    lines.push('      <direction placement="below">');
    lines.push('        <direction-type>');
    lines.push(`          <wedge type="${wedgeType}"/>`);
    lines.push('        </direction-type>');
    lines.push(`        <staff>${staffNumber}</staff>`);
    lines.push('      </direction>');
  }
  if (entry.textMark) {
    lines.push('      <direction placement="above">');
    lines.push('        <direction-type>');
    lines.push(`          <words>${xmlEscape(entry.textMark)}</words>`);
    lines.push('        </direction-type>');
    lines.push(`        <staff>${staffNumber}</staff>`);
    lines.push('      </direction>');
  }
  if (entry.dynamic) {
    lines.push('      <direction placement="below">');
    lines.push('        <direction-type>');
    lines.push(`          <dynamics><${xmlEscape(entry.dynamic)}/></dynamics>`);
    lines.push('        </direction-type>');
    lines.push(`        <staff>${staffNumber}</staff>`);
    lines.push('      </direction>');
  }
  if (entry.grace && entry.kind === "note") {
    lines.push('      <note>');
    lines.push('        <grace slash="yes"/>');
    lines.push('        <pitch>');
    lines.push(`          <step>${xmlEscape(entry.grace.step)}</step>`);
    if (entry.grace.accidental === "#") lines.push('          <alter>1</alter>');
    if (entry.grace.accidental === "b") lines.push('          <alter>-1</alter>');
    lines.push(`          <octave>${entry.grace.octave}</octave>`);
    lines.push('        </pitch>');
    lines.push(`        <voice>${voiceNumber}</voice>`);
    lines.push('        <type>16th</type>');
    lines.push(`        <staff>${staffNumber}</staff>`);
    lines.push('      </note>');
  }
  if (entry.kind === "note" && entry.pitches.length > 1) {
    entry.pitches.forEach((pitch, pitchIndex) => {
      lines.push(...musicXmlSingleNote(entry, staffNumber, voiceNumber, pitch, pitchIndex > 0, capacity));
    });
    return lines;
  }
  lines.push(...musicXmlSingleNote(entry, staffNumber, voiceNumber, entry.pitches?.[0], false, capacity));
  return lines;
}

function musicXmlSingleNote(entry, staffNumber, voiceNumber, pitch, isChordTone, capacity) {
  const lines = [];
  lines.push('      <note>');
  if (isChordTone) lines.push('        <chord/>');
  if (entry.kind === "rest") {
    const fullMeasure = capacity != null && Math.abs((entry.units || 0) - capacity) < 0.001;
    lines.push(fullMeasure ? '        <rest measure="yes"/>' : '        <rest/>');
  } else {
    lines.push('        <pitch>');
    lines.push(`          <step>${xmlEscape(pitch.step)}</step>`);
    if (pitch.accidental === "#") lines.push('          <alter>1</alter>');
    if (pitch.accidental === "b") lines.push('          <alter>-1</alter>');
    lines.push(`          <octave>${pitch.octave}</octave>`);
    lines.push('        </pitch>');
  }
  if (entry.arpeggiate) lines.push('        <arpeggiate/>');
  lines.push(`        <duration>${Math.round(entry.units * DIVISIONS_PER_UNIT)}</duration>`);
  lines.push(`        <voice>${voiceNumber}</voice>`);
  lines.push(`        <type>${musicXmlTypes[entry.duration] || "quarter"}</type>`);
  const dotTotal = dotCount(entry.dotted);
  for (let i = 0; i < dotTotal; i += 1) lines.push('        <dot/>');
  if (entry.tupletType && tupletRatios[entry.tupletType]) {
    const ratio = tupletRatios[entry.tupletType];
    lines.push('        <time-modification>');
    lines.push(`          <actual-notes>${ratio.totalNotes}</actual-notes>`);
    lines.push(`          <normal-notes>${ratio.notesOccupied}</normal-notes>`);
    lines.push('        </time-modification>');
  }
  if (entry.tieStart) lines.push('        <tie type="start"/>');
  if (entry.tieStop) lines.push('        <tie type="stop"/>');
  lines.push(`        <staff>${staffNumber}</staff>`);
  lines.push(...musicXmlNotations(entry));
  lines.push('      </note>');
  return lines;
}

function musicXmlNotations(entry) {
  const notationLines = [];
  if (entry.tieStart) notationLines.push('          <tied type="start"/>');
  if (entry.tieStop) notationLines.push('          <tied type="stop"/>');
  if (entry.slurStart) notationLines.push('          <slur type="start" number="1"/>');
  if (entry.slurStop) notationLines.push('          <slur type="stop" number="1"/>');
  if (entry.phraseStart) notationLines.push('          <slur type="start" number="2"/>');
  if (entry.phraseStop) notationLines.push('          <slur type="stop" number="2"/>');
  if (entry.breath) notationLines.push('          <breath-mark/>');
  if (entry.fermata) notationLines.push('          <fermata/>');
  if (entry.tupletType && entry.tupletPosition === "start") notationLines.push('          <tuplet type="start"/>');
  if (entry.tupletType && entry.tupletPosition === "end") notationLines.push('          <tuplet type="stop"/>');
  const articulation = articulationXml[entry.articulation];
  if (articulation) {
    notationLines.push('          <articulations>');
    notationLines.push(`            <${articulation}/>`);
    notationLines.push('          </articulations>');
  }
  const ornament = ornamentXml[entry.ornament];
  if (ornament) {
    notationLines.push('          <ornaments>');
    notationLines.push(`            <${ornament}/>`);
    notationLines.push('          </ornaments>');
  }
  if (entry.fingering) {
    notationLines.push('          <technical>');
    notationLines.push(`            <fingering>${xmlEscape(entry.fingering)}</fingering>`);
    notationLines.push('          </technical>');
  }
  if (!notationLines.length) return [];
  return ['        <notations>', ...notationLines, '        </notations>'];
}

function musicXmlBarlines(measure) {
  const lines = [];
  if (measure.beginBarline === "repeat-begin" || measure.endBarline === "repeat-both") {
    lines.push('      <barline location="left">');
    lines.push('        <bar-style>heavy-light</bar-style>');
    lines.push('        <repeat direction="forward"/>');
    lines.push('      </barline>');
  }
  if (["double", "end", "repeat-end", "repeat-both"].includes(measure.endBarline)) {
    lines.push('      <barline location="right">');
    if (measure.endBarline === "double") lines.push('        <bar-style>light-light</bar-style>');
    if (measure.endBarline === "end") lines.push('        <bar-style>light-heavy</bar-style>');
    if (measure.endBarline === "repeat-end" || measure.endBarline === "repeat-both") {
      lines.push('        <bar-style>light-heavy</bar-style>');
      lines.push('        <repeat direction="backward"/>');
    }
    lines.push('      </barline>');
  }
  return lines;
}

function parseChordSymbol(symbol) {
  const text = String(symbol || "").trim().replace("♭", "b").replace("♯", "#");
  if (!text) return null;
  let rootPart = text;
  let bassPart = "";
  const slash = text.indexOf("/");
  if (slash >= 0) {
    rootPart = text.slice(0, slash).trim();
    bassPart = text.slice(slash + 1).trim();
  }
  const match = /^([A-Ga-g])([#b]?)(.*)$/.exec(rootPart);
  if (!match) return null;
  const root = {
    step: match[1].toUpperCase(),
    alter: match[2] === "#" ? 1 : match[2] === "b" ? -1 : 0
  };
  const kind = chordKind(match[3]);
  let bass = null;
  if (bassPart) {
    const bassMatch = /^([A-Ga-g])([#b]?)$/.exec(bassPart);
    if (!bassMatch) return null;
    bass = {
      step: bassMatch[1].toUpperCase(),
      alter: bassMatch[2] === "#" ? 1 : bassMatch[2] === "b" ? -1 : 0
    };
  }
  return { root, kind, bass };
}

function chordKind(suffix) {
  const s = suffix.trim();
  if (!s) return "major";
  if (s === "M" || s === "M7" || s === "△7" || s === "maj" || s === "maj7") return s.includes("7") ? "major-seventh" : "major";
  if (s === "m" || s === "m7" || s === "min" || s === "min7" || s === "minor" || s === "minor7") return s.includes("7") ? "minor-seventh" : "minor";
  const lower = s.toLowerCase();
  if (lower === "dim" || s === "°") return "diminished";
  if (lower === "dim7") return "diminished-seventh";
  if (lower === "aug" || s === "+") return "augmented";
  if (lower === "sus" || lower === "sus4") return "suspended-fourth";
  if (lower === "sus2") return "suspended-second";
  if (lower === "6" || lower === "maj6") return "major-sixth";
  if (lower === "m6" || lower === "min6") return "minor-sixth";
  if (lower === "7" || lower === "dom" || lower === "dom7") return "dominant";
  if (lower === "9") return "dominant-ninth";
  if (lower === "11") return "dominant-11th";
  if (lower === "13") return "dominant-13th";
  if (lower === "add9") return "major-add-ninth";
  return "other";
}

function musicXmlHarmony(entry) {
  const parsed = parseChordSymbol(entry.chordSymbol);
  if (!parsed) return [];
  const lines = ['      <harmony>'];
  lines.push('        <root>');
  lines.push(`          <root-step>${xmlEscape(parsed.root.step)}</root-step>`);
  if (parsed.root.alter) lines.push(`          <root-alter>${parsed.root.alter}</root-alter>`);
  lines.push('        </root>');
  lines.push(`        <kind>${parsed.kind}</kind>`);
  if (parsed.bass) {
    lines.push('        <bass>');
    lines.push(`          <bass-step>${xmlEscape(parsed.bass.step)}</bass-step>`);
    if (parsed.bass.alter) lines.push(`          <bass-alter>${parsed.bass.alter}</bass-alter>`);
    lines.push('        </bass>');
  }
  lines.push('      </harmony>');
  return lines;
}

function musicXmlVoiceNumber(staffNumber, voiceId) {
  return String((staffNumber - 1) * 2 + Number(voiceId));
}

const typeToDuration = {
  breve: "0", whole: "1", half: "2", quarter: "4", eighth: "8",
  "16th": "16", "32nd": "32", "64th": "64"
};

// 反向映射：MusicXML -> 内部值
const xmlToArticulation = {
  staccato: "staccato",
  accent: "accent",
  tenuto: "tenuto",
  "strong-accent": "marcato",
  staccatissimo: "staccato",
  spiccato: "staccato",
  breath: "staccato",
  unstress: "tenuto",
  stress: "accent",
  detached: "staccato"
};
const xmlToOrnament = {
  trill: "trill",
  mordent: "mordent",
  "inverted-mordent": "mordent-inverted",
  turn: "turn",
  "inverted-turn": "turn-inverted",
  shake: "trill"
};
const xmlToDynamics = {
  ppp: "ppp", pp: "pp", p: "p", mp: "mp", mf: "mf", f: "f", ff: "ff", fff: "fff", sf: "sfz", sfz: "sfz", sff: "sfz", sfzzo: "sfz", fp: "p", rf: "p", rfz: "p", sfzp: "sfz", n: "", "": ""
};
const xmlToBarline = {
  regular: "single",
  dotted: "single",
  heavy: "single",
  light_light: "double",
  light_heavy: "end",
  heavy_light: "repeat-end",
  heavy_heavy: "double",
  "none": "single",
  // MusicXML 实际用连字符
  "light-light": "double",
  "light-heavy": "end",
  "heavy-light": "repeat-end",
  "heavy-heavy": "double",
  tick: "single",
  short: "single"
};
const xmlRepeatToBarline = {
  backward: "repeat-end",
  forward: "repeat-begin"
};

// MusicXML 导入：解析 partwise 结构（取第一个 part），返回可载入编辑器的每小节声部数据。
function parseMusicXmlText(xmlText) {
  const xml = String(xmlText || "");
  const result = {
    timeSignature: "4/4",
    keySignature: "C",
    staves: { treble: [], bass: [] }
  };

  const partMatch = /<part[^>]*>([\s\S]*?)<\/part>/i.exec(xml);
  const partXml = partMatch ? partMatch[1] : xml;

  const measureRegex = /<measure[^>]*>([\s\S]*?)<\/measure>/gi;
  let measureMatch;
  while ((measureMatch = measureRegex.exec(partXml))) {
    const parsed = parseMusicXmlMeasure(measureMatch[1], result);
    if (!parsed) continue;
    if (parsed.clef === "bass") {
      result.staves.bass.push(parsed.measures[0]);
    } else {
      result.staves.treble.push(parsed.measures[0]);
    }
  }
  return result;
}

function parseMusicXmlMeasure(measureXml, result) {
  const divMatch = /<divisions>(\d+)<\/divisions>/.exec(measureXml);
  const divisions = divMatch ? Number(divMatch[1]) : 24;

  const timeMatch = /<beats>(\d+)<\/beats>[\s\S]*?<beat-type>(\d+)<\/beat-type>/.exec(measureXml);
  if (timeMatch) result.timeSignature = `${timeMatch[1]}/${timeMatch[2]}`;
  const keyMatch = /<fifths>(-?\d+)<\/fifths>/.exec(measureXml);
  if (keyMatch) result.keySignature = keyFromFifths(Number(keyMatch[1]));
  const clefSign = /<sign>([A-Z])<\/sign>/.exec(measureXml);
  const isBass = clefSign && clefSign[1] === "F";

  // 解析起始/结束小节线：<barline location="left|right"><bar-style>...</bar-style></barline>
  let beginBarline = "single";
  let endBarline = "single";
  const leftBarMatch = /<barline[^>]*location="left"[^>]*>([\s\S]*?)<\/barline>/i.exec(measureXml);
  if (leftBarMatch) {
    const style = /<bar-style>([^<]+)<\/bar-style>/.exec(leftBarMatch[1]);
    const repeat = /<repeat[^>]*direction="(\w+)"[^>]*\/>/.exec(leftBarMatch[1]);
    if (repeat) beginBarline = xmlRepeatToBarline[repeat[1]] || "single";
    else if (style) beginBarline = xmlToBarline[style[1].trim()] || "single";
  }
  const rightBarMatch = /<barline[^>]*location="right"[^>]*>([\s\S]*?)<\/barline>/i.exec(measureXml);
  if (rightBarMatch) {
    const style = /<bar-style>([^<]+)<\/bar-style>/.exec(rightBarMatch[1]);
    const repeat = /<repeat[^>]*direction="(\w+)"[^>]*\/>/.exec(rightBarMatch[1]);
    if (repeat) endBarline = xmlRepeatToBarline[repeat[1]] || "single";
    else if (style) endBarline = xmlToBarline[style[1].trim()] || "single";
  }

  // 解析所有 token（按文档顺序）：note, backup, direction, harmony
  const tokens = [];
  const tokenRegex = /<note[\s\S]*?<\/note>|<backup[\s\S]*?<\/backup>|<direction[\s\S]*?<\/direction>|<harmony[\s\S]*?<\/harmony>/gi;
  let tokenMatch;
  while ((tokenMatch = tokenRegex.exec(measureXml))) {
    const xml = tokenMatch[0];
    if (/^<note/i.test(xml)) tokens.push({ type: "note", xml });
    else if (/^<backup/i.test(xml)) {
      const d = /<duration>(\d+)<\/duration>/.exec(xml);
      tokens.push({ type: "backup", duration: d ? Number(d[1]) : 0 });
    } else if (/^<direction/i.test(xml)) tokens.push({ type: "direction", xml });
    else if (/^<harmony/i.test(xml)) tokens.push({ type: "harmony", xml });
  }

  // 按 voice 重建时间线；同一时刻的 direction/harmony attach 到当前 cursor 对应的 entry
  const voiceLists = {};
  const pendingDirections = []; // { offset, voice, direction: {dynamic, pedal, hairpin, textMark} }
  const pendingHarmonies = [];   // { offset, voice, chordSymbol }
  const pendingGrace = new Map(); // voiceId -> grace pitch（grace note 总是出现在主 note 之前，先暂存）
  let cursor = 0;
  let currentVoice = "1";

  tokens.forEach((token) => {
    if (token.type === "backup") {
      cursor -= normalizeUnitValue(token.duration * (8 / divisions));
      return;
    }
    if (token.type === "direction") {
      const dir = parseMusicXmlDirection(token.xml);
      if (dir) pendingDirections.push({ offset: cursor, voice: currentVoice, ...dir });
      return;
    }
    if (token.type === "harmony") {
      const sym = parseMusicXmlHarmony(token.xml);
      if (sym) pendingHarmonies.push({ offset: cursor, voice: currentVoice, chordSymbol: sym });
      return;
    }
    const note = parseMusicXmlNote(token.xml, divisions);
    if (!note) return;
    const voiceId = note.voice <= 2 ? String(note.voice) : String((note.voice % 2 === 0) ? 2 : 1);
    currentVoice = voiceId;

    // grace note: 暂存到 pendingGrace，等下一个非 grace note 出现时 attach
    if (note.grace) {
      pendingGrace.set(voiceId, note.pitch);
      return;
    }

    if (!voiceLists[voiceId]) voiceLists[voiceId] = [];
    if (note.chord && voiceLists[voiceId].length) {
      const last = voiceLists[voiceId][voiceLists[voiceId].length - 1];
      if (last.entry.kind === "note") last.entry.pitches.push(note.pitch);
      return;
    }
    const entry = noteToEntry(note, voiceId);
    if (pendingGrace.has(voiceId)) {
      entry.grace = pendingGrace.get(voiceId);
      pendingGrace.delete(voiceId);
    }
    voiceLists[voiceId].push({ offset: cursor, entry });
    cursor += note.units;
  });

  // attach pendingDirections / pendingHarmonies 到对应 offset 的 entry
  const attachToEntry = (voiceListsArr, offset, voice, attach) => {
    const list = voiceListsArr[voice];
    if (!list) return;
    // 找 offset 完全匹配的 note；找不到就用最后一个小于等于 offset 的
    let target = list.find((item) => Math.abs(item.offset - offset) < 0.001 && item.entry.kind === "note");
    if (!target) {
      const candidates = list.filter((item) => item.offset <= offset && item.entry.kind === "note");
      target = candidates[candidates.length - 1];
    }
    if (target) attach(target.entry);
  };
  pendingDirections.forEach(({ offset, voice, ...dir }) => {
    attachToEntry(voiceLists, offset, voice, (entry) => {
      if (dir.dynamic) entry.dynamic = dir.dynamic;
      if (dir.pedal) entry.pedal = dir.pedal;
      if (dir.hairpin) entry.hairpin = dir.hairpin;
      if (dir.textMark) entry.textMark = dir.textMark;
    });
  });
  pendingHarmonies.forEach(({ offset, voice, chordSymbol }) => {
    attachToEntry(voiceLists, offset, voice, (entry) => { entry.chordSymbol = chordSymbol; });
  });

  const measures = [{
    number: 1,
    beginBarline,
    endBarline,
    voices: Object.keys(voiceLists).sort().map((voiceId) => ({
      id: voiceId,
      role: "",
      usedUnits: voiceLists[voiceId].reduce((sum, item) => sum + item.entry.units, 0),
      entries: voiceLists[voiceId].sort((a, b) => a.offset - b.offset).map((item) => item.entry)
    }))
  }];

  return { clef: isBass ? "bass" : "treble", measures };
}

// 解析一个 <direction> 元素，返回可能的 dynamic / pedal / hairpin / textMark
function parseMusicXmlDirection(dirXml) {
  const result = {};
  const dtMatch = /<direction-type>([\s\S]*?)<\/direction-type>/i.exec(dirXml);
  if (!dtMatch) return null;
  const inner = dtMatch[1];
  // dynamics
  const dynMatch = /<dynamics>([\s\S]*?)<\/dynamics>/i.exec(inner);
  if (dynMatch) {
    const dynTag = /<([a-z]+)\s*\/?>/i.exec(dynMatch[1].trim());
    if (dynTag) result.dynamic = xmlToDynamics[dynTag[1].toLowerCase()] || "";
  }
  // pedal
  const pedalMatch = /<pedal[^>]*type="(\w+)"[^>]*\/>/i.exec(inner);
  if (pedalMatch) result.pedal = pedalMatch[1] === "start" ? "start" : (pedalMatch[1] === "stop" ? "stop" : "");
  // wedge (hairpin)
  const wedgeMatch = /<wedge[^>]*type="(\w+)"[^>]*\/>/i.exec(inner);
  if (wedgeMatch) {
    const t = wedgeMatch[1];
    if (t === "crescendo") result.hairpin = "cresc-start";
    else if (t === "diminuendo") result.hairpin = "decresc-start";
    else if (t === "stop") result.hairpin = "stop";
  }
  // words (textMark)
  const wordsMatch = /<words>([^<]+)<\/words>/i.exec(inner);
  if (wordsMatch) result.textMark = wordsMatch[1].trim();
  return Object.keys(result).length ? result : null;
}

// 解析 <harmony> 元素，返回 chord symbol 字符串（"C"、"Am"、"G7" 等）
function parseMusicXmlHarmony(harmonyXml) {
  const rootMatch = /<root>([\s\S]*?)<\/root>/i.exec(harmonyXml);
  if (!rootMatch) return null;
  const stepMatch = /<root-step>([A-G])<\/root-step>/i.exec(rootMatch[1]);
  const alterMatch = /<root-alter>(-?\d+)<\/root-alter>/i.exec(rootMatch[1]);
  if (!stepMatch) return null;
  let root = stepMatch[1];
  if (alterMatch) {
    const a = Number(alterMatch[1]);
    if (a === 1) root += "#";
    else if (a === -1) root += "b";
  }
  // kind
  const kindMatch = /<kind[^>]*>([^<]+)<\/kind>/i.exec(harmonyXml);
  let kind = "";
  if (kindMatch) {
    const k = kindMatch[1].trim();
    if (k === "major" || k === "") kind = "";
    else kind = k;
  }
  return root + kind;
}

function parseMusicXmlNote(noteXml, divisions) {
  const result = { chord: /<chord\/>/.test(noteXml) };
  const durMatch = /<duration>(\d+)<\/duration>/.exec(noteXml);
  const duration = durMatch ? Number(durMatch[1]) : 0;
  result.units = normalizeUnitValue(duration * (8 / divisions));

  const voiceMatch = /<voice>(\d+)<\/voice>/.exec(noteXml);
  result.voice = voiceMatch ? Number(voiceMatch[1]) : 1;

  if (/<rest[^>]*\/>/.test(noteXml)) {
    result.rest = true;
  } else {
    const stepMatch = /<step>([A-Ga-g])<\/step>/.exec(noteXml);
    const alterMatch = /<alter>(-?\d+)<\/alter>/.exec(noteXml);
    const octaveMatch = /<octave>(\d+)<\/octave>/.exec(noteXml);
    if (!stepMatch || !octaveMatch) return null;
    const alter = alterMatch ? Number(alterMatch[1]) : 0;
    result.pitch = {
      step: stepMatch[1].toUpperCase(),
      octave: Number(octaveMatch[1]),
      accidental: alter > 0 ? "#" : alter < 0 ? "b" : "",
      display: ""
    };
    result.pitch.display = `${result.pitch.step}${displayAccidental(result.pitch.accidental)}${result.pitch.octave}`;
  }

  const typeMatch = /<type>([^<]+)<\/type>/.exec(noteXml);
  result.durationValue = typeMatch ? (typeToDuration[typeMatch[1]] || "4") : "4";
  result.dotCount = (noteXml.match(/<dot\/>/g) || []).length;
  result.tieStart = /<tie type="start"\/>/.test(noteXml);
  result.tieStop = /<tie type="stop"\/>/.test(noteXml);
  result.slurStart = /<slur type="start"/.test(noteXml);
  result.slurStop = /<slur type="stop"/.test(noteXml);
  result.fermata = /<fermata\/>/.test(noteXml);
  result.grace = /<grace[^>]*\/>/.test(noteXml);

  // articulations: staccato / accent / tenuto / strong-accent 等
  const articulationMatch = noteXml.match(/<articulations>([\s\S]*?)<\/articulations>/i);
  if (articulationMatch) {
    const inner = articulationMatch[1];
    if (/<staccato/.test(inner)) result.articulation = xmlToArticulation.staccato;
    else if (/<accent/.test(inner)) result.articulation = xmlToArticulation.accent;
    else if (/<tenuto/.test(inner)) result.articulation = xmlToArticulation.tenuto;
    else if (/<strong-accent/.test(inner)) result.articulation = xmlToArticulation["strong-accent"];
  }

  // ornaments: trill / mordent / inverted-mordent / turn / inverted-turn
  const ornamentMatch = noteXml.match(/<ornaments>([\s\S]*?)<\/ornaments>/i);
  if (ornamentMatch) {
    const inner = ornamentMatch[1];
    if (/<trill/.test(inner)) result.ornament = xmlToOrnament.trill;
    else if (/<inverted-mordent/.test(inner)) result.ornament = xmlToOrnament["inverted-mordent"];
    else if (/<mordent/.test(inner)) result.ornament = xmlToOrnament.mordent;
    else if (/<inverted-turn/.test(inner)) result.ornament = xmlToOrnament["inverted-turn"];
    else if (/<turn/.test(inner)) result.ornament = xmlToOrnament.turn;
  }

  // technical: fingering
  const technicalMatch = noteXml.match(/<technical>([\s\S]*?)<\/technical>/i);
  if (technicalMatch) {
    const fingerMatch = /<fingering>([^<]+)<\/fingering>/i.exec(technicalMatch[1]);
    if (fingerMatch) result.fingering = fingerMatch[1].trim();
  }

  // arpeggiate
  result.arpeggiate = /<arpeggiate[^>]*\/>/.test(noteXml);

  // tuplet: <tuplet type="start"|"stop"/>
  const tupletStartMatch = /<tuplet[^>]*type="start"[^>]*\/>/.test(noteXml);
  const tupletStopMatch = /<tuplet[^>]*type="stop"[^>]*\/>/.test(noteXml);
  result.tupletPosition = tupletStartMatch ? "start" : (tupletStopMatch ? "end" : "");

  // time-modification: actual-notes + normal-notes 决定 tupletType
  const actualMatch = /<actual-notes>(\d+)<\/actual-notes>/.exec(noteXml);
  const normalMatch = /<normal-notes>(\d+)<\/normal-notes>/.exec(noteXml);
  if (actualMatch && normalMatch) {
    const actual = Number(actualMatch[1]);
    const normal = Number(normalMatch[1]);
    if (actual === 3 && normal === 2) result.tupletType = "triplet";
    else if (actual === 5 && normal === 4) result.tupletType = "quintuplet";
    else if (actual === 6 && normal === 4) result.tupletType = "sextuplet";
  }

  // breath
  result.breath = /<breath-mark[^>]*\/>/.test(noteXml);

  return result;
}

function noteToEntry(note, voiceId) {
  const base = {
    kind: note.rest ? "rest" : "note",
    voice: voiceId,
    duration: note.durationValue,
    dotted: note.dotCount,
    units: note.units,
    tieStart: note.tieStart,
    tieStop: note.tieStop,
    slurStart: note.slurStart,
    slurStop: note.slurStop,
    fermata: note.fermata,
    dynamic: note.dynamic || "",
    chordSymbol: note.chordSymbol || "",
    articulation: note.articulation || "",
    ornament: note.ornament || "",
    fingering: note.fingering || "",
    grace: note.gracePitch ? { ...note.gracePitch } : null,
    pedal: note.pedal || "",
    hairpin: note.hairpin || "",
    textMark: note.textMark || "",
    breath: Boolean(note.breath),
    arpeggiate: Boolean(note.arpeggiate),
    phraseStart: Boolean(note.phraseStart),
    phraseStop: Boolean(note.phraseStop),
    tupletType: note.tupletType || "",
    tupletGroup: note.tupletGroup || "",
    tupletPosition: note.tupletPosition || ""
  };
  if (base.kind === "note") {
    base.pitches = [note.pitch];
  } else {
    base.pitches = [];
  }
  return base;
}

const fifthsToKey = { 0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#", "-1": "F", "-2": "Bb", "-3": "Eb", "-4": "Ab", "-5": "Db", "-6": "Gb", "-7": "Cb" };

function keyFromFifths(fifths) {
  return fifthsToKey[fifths] || "C";
}

function xmlEscape(value) {
  return String(value).replace(/[<>&"']/g, (char) => ({
    "<": "&lt;",
    ">": "&gt;",
    "&": "&amp;",
    '"': "&quot;",
    "'": "&apos;"
  }[char]));
}

function bindEvent(element, eventName, handler) {
  if (element) element.addEventListener(eventName, handler);
}

function initSidebar() {
  const appRoot = document.querySelector(".app");
  const links = document.querySelectorAll(".sidebar-link");
  if (!appRoot || !links.length) return;
  const setView = (view) => {
    appRoot.dataset.activeView = view;
    links.forEach((link) => {
      link.classList.toggle("active", link.dataset.view === view);
    });
    // P18.8.3 — 切到制谱视图时重渲染（init 时 scoreViewport 可能是 hidden，clientWidth=0 导致渲染失败）
    if (view === "editor") {
      // 等一帧让 layout 完成
      setTimeout(() => {
        try { renderNotation(); } catch (e) { handleRenderError(e); }
      }, 0);
    }
  };
  links.forEach((link) => {
    bindEvent(link, "click", () => setView(link.dataset.view));
  });
  setView(appRoot.dataset.activeView || "upload");
}

initSidebar();

bindEvent(pickButton, "click", () => fileInput.click());
bindEvent(fileInput, "change", () => {
  const file = fileInput.files?.[0];
  if (file) uploadScore(file);
  fileInput.value = "";
});

bindEvent(manualButton, "click", submitManualChords);
bindEvent(noteButton, "click", submitManualNotes);
bindEvent(examplePreset, "change", (event) => {
  loadExamplePreset(event.target.value);
  // 重置下拉, 让用户能再选同一个
  event.target.value = "";
});
// 自动保存输入到 localStorage (debounce 500ms)
if (noteInput) {
  bindEvent(noteInput, "input", scheduleNoteInputSave);
  restoreNoteInputFromStorage();
}

// ---------------------------------------------------------------------------
// LocalStorage: 自动保存谱面输入, 刷新不丢
// ---------------------------------------------------------------------------
const NOTE_INPUT_STORAGE_KEY = "musicreader:note_input";

function restoreNoteInputFromStorage() {
  try {
    const stored = localStorage.getItem(NOTE_INPUT_STORAGE_KEY);
    if (stored && noteInput && !noteInput.value.trim()) {
      // 只在输入框为空时恢复, 避免覆盖 HTML 默认值
      noteInput.value = stored;
    }
  } catch (e) {
    // localStorage 可能被禁用 (隐私模式等)
  }
}

let _noteInputSaveTimer = null;
function scheduleNoteInputSave() {
  if (!noteInput) return;
  if (_noteInputSaveTimer) clearTimeout(_noteInputSaveTimer);
  _noteInputSaveTimer = setTimeout(() => {
    try {
      localStorage.setItem(NOTE_INPUT_STORAGE_KEY, noteInput.value);
    } catch (e) {
      // ignore
    }
  }, 500);
}
bindEvent(fourPartButton, "click", submitFourPartAnswer);
bindEvent(applyFourPartButton, "click", applyFourPartAnswerToEditor);
bindEvent(aiExplainButton, "click", requestAIExplanation);
bindEvent(noteCanvas, "pointerdown", addEntryFromScore);
bindEvent(noteCanvas, "pointermove", handleNoteCanvasHover);
// P22.3 Phase 4: mouseleave 必须清 ghost + previewEntry (你硬要求)
bindEvent(noteCanvas, "pointerleave", () => {
  editorState.clearPreview();
  clearGhostNote();
});
bindEvent(staffMode, "change", handleStaffModeChange);
bindEvent(noteClef, "change", handleActiveStaffChange);
bindEvent(voiceSelect, "change", handleActiveVoiceChange);
bindEvent(editorTime, "change", handleTimeSignatureChange);
bindEvent(editorKey, "change", () => renderNotation());
bindEvent(tempoInput, "change", () => renderNotation());
bindEvent(anacrusisCheck, "change", () => renderNotation());
bindEvent(noteMeasure, "change", () => {
  const targetIndex = Math.max(0, Number(noteMeasure.value || 1) - 1);
  ensureMeasureExistsForVisibleStaves(targetIndex);
  switchToMeasure(Math.min(targetIndex, scoreMeasures.length - 1));
});
bindEvent(prevMeasureButton, "click", () => switchToMeasure(currentMeasureIndex - 1));
bindEvent(nextMeasureButton, "click", () => switchToMeasure(currentMeasureIndex + 1));
bindEvent(addMeasureButton, "click", () => addMeasure(true));
bindEvent(deleteMeasureButton, "click", deleteCurrentMeasure);

document.querySelectorAll('input[name="inputKind"]').forEach((control) => {
  control.addEventListener("change", updateEditorControls);
});

document.querySelectorAll('input[name="entryMode"]').forEach((control) => {
  control.addEventListener("change", updateEditorControls);
});

bindEvent(undoNotesButton, "click", undoEdit);
bindEvent(deleteToneButton, "click", deleteSelectedTone);
// P22+: noteAccidental 改变时实时更新选中 entry 的 accidental
// P22.3 Phase 5: 全部 UI 控件 (duration/dotted/accidental) 改变时必须立即刷新 ghost
// 关键: 鼠标不动时, ghost 必须跟 UI 状态同步变化
function refreshPreviewFromUI() {
  // 1. 同步 editorState 当前 input duration / accidental
  if (typeof noteDuration !== "undefined" && noteDuration) {
    const dur = noteDuration.value || "4";
    const dottedEl = (typeof noteDotted !== "undefined") ? noteDotted : null;
    const dotted = dottedEl ? (Number(dottedEl.value) || 0) : 0;
    editorState.setDuration(dur, dotted);
    editorState.setAccidental(noteAccidental?.value || "");
  }
  // 2. 如果有 pending mouse position, 重新走 hover 流生成新 ghost
  if (editorState.pendingMousePosition && typeof appendGhostToMainCanvas === "function") {
    // 先清旧 ghost (重画前必清, 避免叠加)
    clearGhostNote();
    // 重新从 pending mouse pos 算 previewEntry + render
    const pmp = editorState.pendingMousePosition;
    const { staveKey, geometry, x, y } = pmp;
    if (geometry && geometry.activeStave && geometry.activeContext) {
      // P22.4-B.3 批次 2/3: localX/localY + beat 全走 cs
      const meter = currentMeter();
      const { localX, localY } = cs.canvasToStave(x, y, geometry);
      if (cs.isInNoteRange(localX, geometry) && cs.isInPitchRange(localY, geometry)) {
        const { beat } = cs.canvasToBeat(x, geometry, meter);
        const isRest = inputKind() === "rest";
        // P22.3 duration-cleanup: 走单一函数 buildPreviewFromState（与 hover 路径同源）
        const preview = buildPreviewFromState({
          localX,
          localY,
          geometry,
          staveKey,
          isRest
        });
        editorState.setPreview(preview);
        appendGhostToMainCanvas();
      }
    }
  }
}
bindEvent(noteDuration, "change", refreshPreviewFromUI);
bindEvent(noteDotted, "change", refreshPreviewFromUI);
bindEvent(noteAccidental, "change", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    const newAcc = noteAccidental.value;
    entry.pitches.forEach((p) => { p.accidental = newAcc; });
  });
});
bindEvent(applyDurationButton, "click", applyDurationToSelected);
bindEvent(toggleTieStartButton, "click", () => toggleSelectedFlag("tieStart"));
bindEvent(toggleTieStopButton, "click", () => toggleSelectedFlag("tieStop"));
bindEvent(toggleSlurStartButton, "click", () => toggleSelectedFlag("slurStart"));
bindEvent(toggleSlurStopButton, "click", () => toggleSelectedFlag("slurStop"));
bindEvent(toggleFermataButton, "click", () => toggleSelectedFlag("fermata"));
bindEvent(toggleTripletButton, "click", toggleTupletGroup);
bindEvent(dynamicSelect, "change", () => setSelectedDynamic(dynamicSelect.value));
bindEvent(chordSymbolInput, "change", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    entry.chordSymbol = chordSymbolInput.value.trim();
  });
});
bindEvent(articulationSelect, "change", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    entry.articulation = articulationSelect.value;
  });
});
bindEvent(ornamentSelect, "change", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    entry.ornament = ornamentSelect.value;
  });
});
bindEvent(graceInput, "change", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  const raw = graceInput.value.trim();
  commitEdit(() => {
    if (!raw) {
      entry.grace = null;
      return;
    }
    try {
      entry.grace = pitchFromTextToken(raw, 1, 1);
    } catch (error) {
      showEditorMessage(error.message || "倚音音高无法解析。", "error");
    }
  });
});
bindEvent(pedalSelect, "change", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    entry.pedal = pedalSelect.value;
  });
});
bindEvent(hairpinSelect, "change", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    entry.hairpin = hairpinSelect.value;
  });
});
bindEvent(fingeringInput, "change", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    entry.fingering = fingeringInput.value.trim();
  });
});
// P22.5-Symbol-A.4 — 段标 + volta 绑定
bindEvent(rehearsalMarkInput, "change", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    entry.rehearsalMark = rehearsalMarkInput.value.trim();
  });
});
bindEvent(voltaSelect, "change", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    const value = voltaSelect.value;
    entry.volta = value === "" ? null : Number(value);
  });
});
bindEvent(arpeggioCheck, "change", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    entry.arpeggiate = arpeggioCheck.checked;
  });
});
bindEvent(togglePhraseStartButton, "click", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    entry.phraseStart = !entry.phraseStart;
    if (entry.phraseStart) entry.phraseStop = false;
  });
});
bindEvent(togglePhraseStopButton, "click", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    entry.phraseStop = !entry.phraseStop;
    if (entry.phraseStop) entry.phraseStart = false;
  });
});
bindEvent(textMarkInput, "change", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    entry.textMark = textMarkInput.value.trim();
  });
});
bindEvent(breathCheck, "change", () => {
  const entry = measureEntries[selectedEntryIndex];
  if (!entry || entry.kind !== "note") return;
  commitEdit(() => {
    entry.breath = breathCheck.checked;
  });
});
bindEvent(beginBarlineSelect, "change", updateCurrentMeasureBarlines);
bindEvent(endBarlineSelect, "change", updateCurrentMeasureBarlines);
bindEvent(validateScoreButton, "click", showScoreValidation);
bindEvent(exportJsonButton, "click", exportScoreJson);
bindEvent(exportMusicXmlButton, "click", exportScoreMusicXml);
bindEvent(importMusicXmlButton, "click", () => musicXmlFileInput.click());
bindEvent(musicXmlFileInput, "change", () => {
  const file = musicXmlFileInput.files?.[0];
  if (file) importMusicXmlFile(file);
  musicXmlFileInput.value = "";
});
bindEvent(deleteEventButton, "click", deleteSelectedEvent);

bindEvent(clearNotesButton, "click", () => {
  if (!currentVoiceEntries().length) return;
  commitEdit(() => {
    setCurrentMeasureEntries(measureEntries.filter((entry) => entryVoice(entry) !== activeVoiceId()));
    selectedEntryIndex = -1;
  });
});

for (const eventName of ["dragenter", "dragover"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  });
}

for (const eventName of ["dragleave", "drop"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  });
}

dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer?.files?.[0];
  if (file) uploadScore(file);
});

window.addEventListener("resize", () => {
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(renderNotation, 120);
});

manualProgression.value = "C | Am | Dm G7 | C";
checkHealth();
window.setInterval(checkHealth, 10000);
window.addEventListener("focus", checkHealth);

// 音乐字体本地化：VexFlow 5 默认从 CDN 加载字体，被墙/慢时装饰音等 SMuFL 符号会退化成字母。
// 改为从本机 /assets/vendor/fonts 加载，加载完成后重渲染一次。
try {
  if (VF?.Font) {
    VF.Font.HOST_URL = "/assets/vendor/fonts/";
    if (VF.Font.load) {
      const fontTasks = ["Leland", "Leland Text", "Bravura"]
        .map((name) => VF.Font.load(name).catch(() => {}));
      Promise.all(fontTasks).then(() => { try { renderNotation(); } catch (e) {} }).catch(() => {});
    }
  }
} catch (e) { console.error("[init] font load err:", e); }
try { renderNotation(); } catch (e) {
  console.error("[init] renderNotation err:", e);
}

// P18.8.3 — hash preset 钩子（提前到 init 早期，避免被后面 IIFE 错误阻断）
//  支持 URL #preset=p0_cadence 等 — 直接载入对应课本例题
(function applyHashPresetEarly() {
  const m = (location.hash || "").match(/preset=([a-z0-9_]+)/i);
  if (!m || typeof loadExamplePreset !== "function") return;
  const preset = m[1];
  if (typeof EXAMPLE_PRESETS === "undefined" || !EXAMPLE_PRESETS[preset]) return;
  try {
    loadExamplePreset(preset);
  } catch (e) {
    if (typeof showEditorMessage === "function") {
      showEditorMessage(`[hash preset] 载入失败：${e.message}`, "error");
    }
  }
  // 强制重渲染 + 自动切到制谱视图（不然用户看不到）
  try { if (typeof renderNotation === "function") renderNotation(); } catch (e) {}
  try {
    const editorLink = document.querySelector('.sidebar-link[data-view="editor"]');
    if (editorLink) editorLink.click();
  } catch (e) {}
})();

// 调试用：把核心函数挂到 window，方便在 Puppeteer / DevTools 里直接调用
if (typeof window !== "undefined") {
  window.__musicReader = {
    parseMusicXmlText,
    parseMusicXmlMeasure,
    parseMusicXmlNote,
    parseMusicXmlDirection,
    parseMusicXmlHarmony,
    noteToEntry
  };
}

// ==================================================================
// P18.8  Flat.io/MuseScore 风格编辑器 UI — bridge + tab 切换
// ------------------------------------------------------------------
// 架构：
//   ribbon 控件（class="ribbon-radio" 等，data-bridge="X"） → inspector 字段（id="X"）
//   inspector 字段才是 app.js 真正读写的元素；ribbon 只是 UI 别名
//   tab 切换：note / articulation / ornament / dynamic / measure / text / alt
// ==================================================================

(function setupP188BridgeAndTabs() {
  // Bridge: ribbon 控件 (data-bridge) -> inspector 字段
  const BRIDGE_TARGETS = new Set([
    "articulationSelect", "ornamentSelect", "dynamicSelect", "hairpinSelect",
    "pedalSelect", "noteDuration", "noteDotted", "noteAccidental",
    "tupletTypeSelect", "graceInput", "fingeringInput",
    "chordSymbolInput", "textMarkInput", "arpeggioCheck", "breathCheck",
    "toggleTripletButton", "toggleTieStartButton", "toggleTieStopButton",
    "toggleSlurStartButton", "toggleSlurStopButton",
    "togglePhraseStartButton", "togglePhraseStopButton", "toggleFermataButton",
  ]);

  function syncRibbonToTarget(src) {
    const targetId = src.dataset.bridge;
    if (!BRIDGE_TARGETS.has(targetId)) return;
    // P22.3 duration-fix: 用 findEl 而不是 getElementById，兼容 data-bridge-only 元素
    // (noteDuration/noteDotted/noteAccidental 这些 select 只有 data-bridge 没有 id)
    const target = findEl(targetId);
    if (!target) return;
    if (target.tagName === "BUTTON") {
      // toggle 按钮 (toggleTie* / toggleSlur* / toggleTriplet* / togglePhrase* / toggleFermata)
      // 通过 click() 触发 app.js 的 toggleSelectedFlag；然后把 aria-pressed 同步回 ribbon checkbox
      target.click();
      if (src.type === "checkbox") {
        src.checked = target.getAttribute("aria-pressed") === "true";
      }
      return;
    }
    if (target.tagName === "INPUT") {
      if (target.type === "checkbox") {
        target.checked = src.checked;
        target.dispatchEvent(new Event("change", { bubbles: true }));
      } else {
        target.value = src.value;
        target.dispatchEvent(new Event("input", { bubbles: true }));
        target.dispatchEvent(new Event("change", { bubbles: true }));
      }
    } else if (target.tagName === "SELECT") {
      target.value = src.value;
      target.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  // 绑定所有 ribbon 控件
  document.querySelectorAll(".editor-ribbon [data-bridge]").forEach((el) => {
    if (el.tagName === "INPUT" && el.type === "checkbox") {
      el.addEventListener("change", () => syncRibbonToTarget(el));
    } else {
      el.addEventListener("change", () => syncRibbonToTarget(el));
      if (el.tagName === "INPUT" && (el.type === "text" || el.type === "number")) {
        el.addEventListener("input", () => syncRibbonToTarget(el));
      }
    }
  });

  // 反向 bridge: app.js 改 inspector 字段后，把 ribbon 控件同步选中
  // (主要场景: renderSelectionBar 改 dynamicSelect.value 后, ribbon 的 dynamicPick radio 跟着选)
  const REVERSE_MAP = {
    noteDuration:   { type: "radio", name: "durationPick" },
    noteDotted:     { type: "radio", name: "dottedPick" },
    noteAccidental: { type: "radio", name: "accidentalPick" },
    articulationSelect: { type: "radio", name: "articulationPick" },
    ornamentSelect:     { type: "radio", name: "ornamentPick" },
    dynamicSelect:      { type: "radio", name: "dynamicPick" },
    hairpinSelect:      { type: "radio", name: "hairpinPick" },
    pedalSelect:        { type: "radio", name: "pedalPick" },
  };
  Object.keys(REVERSE_MAP).forEach((id) => {
    // P22.3 duration-fix: findEl 而非 getElementById (data-bridge 兼容)
    const target = findEl(id);
    if (!target) return;
    const radio = document.querySelector(`input[name="${REVERSE_MAP[id].name}"][value="${CSS.escape(target.value)}"]`);
    if (radio) radio.checked = true;
  });

  // Tab 切换
  const tabs = document.querySelectorAll(".editor-tab");
  const groups = document.querySelectorAll(".ribbon-group");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tabTarget;
      tabs.forEach((t) => t.setAttribute("aria-selected", String(t === tab)));
      groups.forEach((g) => { if (g) g.hidden = g.dataset.ribbonTab !== target; });
      // alt tab: 让 alt-input-section 滚到可视区
      if (target === "alt") {
        const altSection = document.querySelector(".alt-input-section");
        if (altSection) {
          altSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
          const input = altSection.querySelector("#noteInput");
          if (input) setTimeout(() => input.focus(), 200);
        }
      }
    });
  });

  // 兼容：把 noteInput 框也作为 "alt tab" 的入口（用户改 noteInput 时自动切到 alt tab）
  const noteInputEl = document.getElementById("noteInput");
  if (noteInputEl) {
    noteInputEl.addEventListener("focus", () => {
      const altTab = document.querySelector('.editor-tab[data-tab-target="alt"]');
      if (altTab && altTab.getAttribute("aria-selected") !== "true") altTab.click();
    });
  }

  // 调试钩子：URL hash #preset=p0_cadence 自动加载课本例题（方便无键盘环境验证）
  // 初始加载已由 applyHashPresetEarly IIFE 处理；这里只挂 hashchange 监听
  function applyHashPreset() {
    const m = (location.hash || "").match(/preset=([a-z0-9_]+)/i);
    if (m && typeof loadExamplePreset === "function" && typeof EXAMPLE_PRESETS !== "undefined" && EXAMPLE_PRESETS[m[1]]) {
      try {
        loadExamplePreset(m[1]);
      } catch (e) {
        if (typeof showEditorMessage === "function") {
          showEditorMessage(`[hash preset] 载入失败：${e.message}`, "error");
        }
      }
      if (typeof renderNotation === "function") {
        try { renderNotation(); } catch (e) {}
      }
    }
  }
  window.addEventListener("hashchange", applyHashPreset);

  // P18.8.3 — top-level error 透传到 editorMessage
  window.addEventListener("error", (e) => {
    const msg = `JS 错误：${e.message} @ ${e.filename?.split("/").pop()}:${e.lineno}:${e.colno}`;
    if (typeof showEditorMessage === "function") showEditorMessage(msg, "error");
    console.error("[top-level]", e.error);
  });
  window.addEventListener("unhandledrejection", (e) => {
    const msg = `Promise 错误：${e.reason?.message || e.reason}`;
    if (typeof showEditorMessage === "function") showEditorMessage(msg, "error");
    console.error("[promise]", e.reason);
  });

  // P18.8.3 — 键盘快捷键（Flat.io / MuseScore 风格）
  //  - 1/2/3/4/5/6: 二全/全/二/四/八/十六 分音符
  //  - r / R: 切到休止符
  //  - n / N: 切到音符
  //  - z / Z: 撤销
  //  - y / Y: 重做（P18.8.7 redo stack 待加，先留空）
  //  - ← / →: 切换小节
  //  - Backspace / Delete: 删除当前拍位
  //  - . (句点): 切换单附点
  // 不在 input/textarea 里触发
  const DURATION_KEYS = { "1": "0", "2": "1", "3": "2", "4": "4", "5": "8", "6": "16" };
  document.addEventListener("keydown", (event) => {
    const target = event.target;
    if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
      return;
    }
    if (event.ctrlKey || event.metaKey || event.altKey) {
      // Ctrl+Z 撤销 / Ctrl+Y 重做
      if (event.ctrlKey && (event.key === "z" || event.key === "Z")) {
        event.preventDefault();
        if (typeof undoEdit === "function") undoEdit();
        return;
      }
      return;
    }
    const key = event.key;
    if (DURATION_KEYS[key]) {
      const value = DURATION_KEYS[key];
      const dur = findEl("noteDuration");
      if (dur) { dur.value = value; dur.dispatchEvent(new Event("change", { bubbles: true })); }
      // 同步点 ribbon 的 duration radio
      const radio = document.querySelector(`input[name="durationPick"][value="${value}"]`);
      if (radio) radio.checked = true;
      showEditorMessage(`时值：${value} 分音符`, "neutral");
      return;
    }
    if (key === "r" || key === "R") {
      const radio = document.querySelector('input[name="inputKind"][value="rest"]');
      if (radio && !radio.checked) { radio.checked = true; radio.dispatchEvent(new Event("change", { bubbles: true })); }
      return;
    }
    if (key === "n" || key === "N") {
      const radio = document.querySelector('input[name="inputKind"][value="note"]');
      if (radio && !radio.checked) { radio.checked = true; radio.dispatchEvent(new Event("change", { bubbles: true })); }
      return;
    }
    if (key === "z" || key === "Z") {
      if (typeof undoEdit === "function") undoEdit();
      return;
    }
    if (key === "ArrowLeft") {
      event.preventDefault();
      if (typeof switchToMeasure === "function") switchToMeasure(currentMeasureIndex - 1);
      return;
    }
    if (key === "ArrowRight") {
      event.preventDefault();
      if (typeof switchToMeasure === "function") switchToMeasure(currentMeasureIndex + 1);
      return;
    }
    if (key === "Backspace" || key === "Delete") {
      // P22.3 Phase 8: 默认 = 删整个 entry; Shift+Backspace = 删单个 tone (chord 单音)
      if (event.shiftKey) {
        if (typeof deleteSelectedTone === "function") deleteSelectedTone();
      } else {
        if (typeof deleteSelectedEvent === "function") deleteSelectedEvent();
      }
      return;
    }
    if (key === ".") {
      const dotted = findEl("noteDotted");
      if (dotted) {
        const current = Number(dotted.value || 0);
        const next = (current + 1) % 3;
        dotted.value = String(next);
        dotted.dispatchEvent(new Event("change", { bubbles: true }));
        // 同步 radio
        const radio = document.querySelector(`input[name="dottedPick"][value="${next}"]`);
        if (radio) radio.checked = true;
      }
      return;
    }
  });
})();

