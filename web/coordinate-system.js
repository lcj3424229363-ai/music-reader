// P22.4 CoordinateSystem v1
// 统一坐标层 — 把 clientX/Y → canvas 局部 → stave 局部 → 拍位/音高/单位 的转换关进单一类
// 设计原则：
//   1. 不绑 DOM (constructor 无参, viewportToCanvas(event, canvas) 接受 canvas 参数)
//   2. LayoutGeometry = 像素几何层 (canvas ↔ stave ↔ 拍位)
//   3. MusicMapping = 音乐语义层 (duration ↔ units, capacity, localY → pitch)
//   4. CoordinateSystem = 委托层 + lifecycle (updateLayout / clearLayout)
//   5. 兼容浏览器 (window.CoordinateSystem) + Node 测试 (module.exports)

(function (root, factory) {
  'use strict';
  const exported = factory();
  if (typeof root !== 'undefined') {
    root.CoordinateSystem = exported.CoordinateSystem;
    root.LayoutGeometry = exported.LayoutGeometry;
    root.MusicMapping = exported.MusicMapping;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = exported;
  }
}(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function () {
  'use strict';

  // ---------- 常量 (从 app.js line 109-111, 112, 1868, 1944, 1952 复制) ----------
  // P22.3 final — 真实值（app.js:112）: 4/4 1 拍 = 8 units, 1 个 4 分 = 8 units
  const DURATION_UNITS = { '0': 64, '1': 32, '2': 16, '4': 8, '8': 4, '16': 2, '32': 1, '64': 0.5 };
  const CLEF_BOTTOM_LINES = { treble: 'E4', bass: 'G2' };
  const STEP_NAMES = ['C', 'D', 'E', 'F', 'G', 'A', 'B'];
  const STEP_INDEX = { C: 0, D: 1, E: 2, F: 3, G: 4, A: 5, B: 6 };
  const PITCH_RANGE_PADDING = 42;          // app.js:2066, 2695 — 上下 padding
  const UNIT_EPSILON = 0.001;               // app.js:1952 — 容量比较 epsilon

  // ---------- 顶层纯函数 ----------
  function diatonicIndex(token) {
    const match = /^([A-G])(-?\d+)$/.exec(token);
    if (!match) return STEP_INDEX.E + 4 * 7;  // app.js:2169 fallback
    return Number(match[2]) * 7 + STEP_INDEX[match[1]];
  }

  function meterForTimeSignature(timeSignature) {
    const parts = String(timeSignature || '4/4').split('/');
    const numerator = Number(parts[0]) || 4;
    const denominator = Number(parts[1]) || 4;
    return {
      numerator,
      denominator,
      beatUnit: 32 / denominator,            // app.js:1868
      capacity: numerator * (32 / denominator)  // app.js:1867
    };
  }

  function dotCount(value) {
    return value === true ? 1 : Number(value) || 0;
  }

  function normalizeUnitValue(value) {
    return Number(Number(value).toFixed(3));
  }

  // ---------- LayoutGeometry: 像素 ↔ stave ↔ 拍位 ----------
  class LayoutGeometry {
    constructor() {
      this.measureRects = [];
      this.staffGeometry = null;
      this.trebleGeometry = null;
      this.bassGeometry = null;
      this.currentMeasureIndex = 0;
    }

    update(payload) {
      if (!payload) return;
      const {
        staffGeometry = null,
        trebleGeometry = null,
        bassGeometry = null,
        measureRects = [],
        currentMeasureIndex = 0
      } = payload;
      this.staffGeometry = staffGeometry;
      this.trebleGeometry = trebleGeometry;
      this.bassGeometry = bassGeometry;
      this.measureRects = Array.isArray(measureRects) ? measureRects : [];
      this.currentMeasureIndex = currentMeasureIndex;
    }

    clear() {
      this.measureRects = [];
      this.staffGeometry = null;
      this.trebleGeometry = null;
      this.bassGeometry = null;
      this.currentMeasureIndex = 0;
    }

    /**
     * canvas 局部 (x, y) → 命中的 stave 信息.
     * 单谱/双谱统一 — 内部根据 isPianoMode (measureRects 是否有 staveKey 字段) 决定用哪个 geometry.
     * @returns {null|{staveKey, geometry, measureIndex, measureRect}}
     */
    staffAtPoint(x, y) {
      const hit = this.measureRects.find((m) =>
        x >= m.x && x <= m.x + m.width &&
        y >= m.y - 4 && y <= m.y + m.height + 4
      );
      if (!hit) return null;
      // 双谱模式: 命中 rect 带 staveKey, 用对应的 geometry
      // 单谱模式: 命中 rect 不带 staveKey, 用 staffGeometry + activeStaffKey
      const staveKey = hit.staveKey || 'active';
      let geometry;
      if (hit.staveKey === 'treble') {
        geometry = this.trebleGeometry;
      } else if (hit.staveKey === 'bass') {
        geometry = this.bassGeometry;
      } else {
        geometry = this.staffGeometry;
      }
      if (!geometry) return null;
      return { staveKey, geometry, measureIndex: hit.index, measureRect: hit };
    }

    /**
     * canvas 局部 (x, y) + geometry → stave 局部 (localX, localY)
     * localX 相对 noteStartX (VexFlow 允许放音符的位置)
     * localY 相对 staveY (stave 顶部)
     */
    canvasToStave(x, y, geometry) {
      if (!geometry) return { localX: 0, localY: 0 };
      return {
        localX: x - geometry.noteStartX,
        localY: y - geometry.staveY
      };
    }

    isInNoteRange(localX, geometry) {
      if (!geometry) return false;
      const width = geometry.noteEndX - geometry.noteStartX;
      return localX >= 0 && localX <= width;
    }

    isInPitchRange(localY, geometry) {
      if (!geometry) return false;
      return localY >= geometry.topY - PITCH_RANGE_PADDING &&
             localY <= geometry.bottomY + PITCH_RANGE_PADDING;
    }

    /**
     * canvas x → 拍位. clamp 到 [1, numerator].
     * 注意: 需要 meter (从 cs._music.meter 传)
     */
    canvasToBeat(x, geometry, meter) {
      const m = meter || meterForTimeSignature('4/4');
      if (!geometry || !m || !m.numerator) {
        return { beat: 1, beatWidth: 0, targetX: 0 };
      }
      const localX = x - geometry.noteStartX;
      const beatWidth = (geometry.noteEndX - geometry.noteStartX) / m.numerator;
      const beatFromX = Math.floor(localX / beatWidth);
      const beat = Math.max(1, Math.min(m.numerator, beatFromX + 1));
      const targetX = geometry.staveX + (beat - 1) * beatWidth + beatWidth / 2;
      return { beat, beatWidth, targetX };
    }

    /**
     * 拍位 → canvas 中心 x. (渲染网格线用)
     */
    beatToCanvasX(beat, geometry, meter) {
      const m = meter || meterForTimeSignature('4/4');
      if (!geometry || !m || !m.numerator) return 0;
      const beatWidth = (geometry.noteEndX - geometry.noteStartX) / m.numerator;
      return geometry.staveX + (beat - 1) * beatWidth + beatWidth / 2;
    }
  }

  // ---------- MusicMapping: 音乐语义 ----------
  class MusicMapping {
    constructor() {
      this._meter = null;
    }

    setMeter(timeSignature) {
      this._meter = meterForTimeSignature(timeSignature);
    }

    clear() {
      this._meter = null;
    }

    get meter() {
      return this._meter || meterForTimeSignature('4/4');
    }

    capacity() {
      return this._meter ? this._meter.capacity : 0;
    }

    /**
     * stave 局部 y → {step, octave}. 用 geometry.{bottomY, halfStep} + clef.
     * 注意: caller 必须传 localY (相对 staveY), 不能传 canvas 坐标.
     *          geometry.bottomY 也是相对 staveY (单位一致).
     */
    localYToPitch(localY, staveKey, geometry) {
      if (!geometry) return { step: 'C', octave: 4 };
      const clef = staveKey === 'bass' ? 'bass' : (staveKey === 'treble' ? 'treble' : 'treble');
      const bottomIndex = diatonicIndex(CLEF_BOTTOM_LINES[clef]);
      const halfStep = geometry.halfStep || 1;
      const stepsFromBottom = Math.round((geometry.bottomY - localY) / halfStep);
      const noteIndex = bottomIndex + stepsFromBottom;
      const octave = Math.floor(noteIndex / 7);
      const step = STEP_NAMES[((noteIndex % 7) + 7) % 7];
      return { step, octave };
    }

    /**
     * duration + dotted → units.
     *   4 分 = 8 units (4/4)
     *   4 分 + 1 dot = 12 units
     *   4 分 + 2 dot = 14 units
     */
    unitsForDuration(duration, dotted) {
      const base = DURATION_UNITS[duration] || DURATION_UNITS['4'];
      const dots = dotCount(dotted);
      return dots === 2 ? base * 1.75 : dots === 1 ? base * 1.5 : base;
    }

    /**
     * entry → units. (含 tuplet)
     *   entry 必须有 duration, dotted, tupletType 字段
     */
    unitsForEntry(entry) {
      if (!entry) return 0;
      const baseUnits = this.unitsForDuration(entry.duration, entry.dotted);
      // tuplet 不在 v1 范围 — B.3 再加
      return baseUnits;
    }

    /**
     * sumUnits(entries). 累计 + 归一化.
     */
    sumUnits(entries) {
      if (!Array.isArray(entries)) return 0;
      const total = entries.reduce((sum, entry) => {
        if (Number.isFinite(entry.units)) return sum + entry.units;
        return sum + this.unitsForEntry(entry);
      }, 0);
      return normalizeUnitValue(total);
    }

    exceedsUnits(left, right) {
      return (left - right) > UNIT_EPSILON;
    }

    sameUnits(left, right) {
      return Math.abs(left - right) < UNIT_EPSILON;
    }

    normalizeUnits(value) {
      return normalizeUnitValue(value);
    }
  }

  // ---------- CoordinateSystem: 委托层 + lifecycle ----------
  class CoordinateSystem {
    constructor() {
      this._layout = new LayoutGeometry();
      this._music = new MusicMapping();
    }

    /**
     * render 入口调用. 灌入最新 layout + meter.
     * @param {{staffGeometry?, trebleGeometry?, bassGeometry?, measureRects?, currentMeasureIndex?, timeSignature?}} payload
     */
    updateLayout(payload) {
      if (!payload) return;
      const { staffGeometry, trebleGeometry, bassGeometry, measureRects, currentMeasureIndex, timeSignature } = payload;
      this._layout.update({ staffGeometry, trebleGeometry, bassGeometry, measureRects, currentMeasureIndex });
      if (timeSignature !== undefined && timeSignature !== null) {
        this._music.setMeter(timeSignature);
      }
    }

    /**
     * 错误路径重置 (handleRenderError). cs 内部状态清空.
     */
    clearLayout() {
      this._layout.clear();
      this._music.clear();
    }

    // ----- LayoutGeometry 委托 -----

    /**
     * Mouse event + canvas → canvas 局部 (x, y).
     * 替代: const rect = canvas.getBoundingClientRect(); x = event.clientX - rect.left; ...
     */
    viewportToCanvas(event, canvas) {
      if (!canvas || !event) return { x: 0, y: 0 };
      const rect = canvas.getBoundingClientRect();
      return { x: event.clientX - rect.left, y: event.clientY - rect.top };
    }

    staffAtPoint(x, y) { return this._layout.staffAtPoint(x, y); }
    canvasToStave(x, y, geometry) { return this._layout.canvasToStave(x, y, geometry); }
    canvasToBeat(x, geometry, meter) { return this._layout.canvasToBeat(x, geometry, meter || this._music.meter); }
    beatToCanvasX(beat, geometry, meter) { return this._layout.beatToCanvasX(beat, geometry, meter || this._music.meter); }
    isInNoteRange(localX, geometry) { return this._layout.isInNoteRange(localX, geometry); }
    isInPitchRange(localY, geometry) { return this._layout.isInPitchRange(localY, geometry); }

    // ----- MusicMapping 委托 -----

    localYToPitch(localY, staveKey, geometry) { return this._music.localYToPitch(localY, staveKey, geometry); }
    unitsForDuration(duration, dotted) { return this._music.unitsForDuration(duration, dotted); }
    unitsForEntry(entry) { return this._music.unitsForEntry(entry); }
    sumUnits(entries) { return this._music.sumUnits(entries); }
    exceedsUnits(left, right) { return this._music.exceedsUnits(left, right); }
    sameUnits(left, right) { return this._music.sameUnits(left, right); }
    normalizeUnits(value) { return this._music.normalizeUnits(value); }
    capacity() { return this._music.capacity(); }

    // ----- 内部访问 (测试用, 业务不要用) -----
    get _internal() { return { layout: this._layout, music: this._music }; }
  }

  return {
    CoordinateSystem,
    LayoutGeometry,
    MusicMapping,
    // 暴露纯函数 (测试用)
    _internals: {
      DURATION_UNITS,
      CLEF_BOTTOM_LINES,
      STEP_NAMES,
      STEP_INDEX,
      PITCH_RANGE_PADDING,
      UNIT_EPSILON,
      diatonicIndex,
      meterForTimeSignature,
      dotCount,
      normalizeUnitValue
    }
  };
}));
