"""斯波索宾《和声学教程》体系下的主分析器。

核心做法（不重写 music21 已有的能力）：
  1. 用 `score.analyze("key")` 推测调性
  2. 对每个 chordify 出的和弦，调 `roman.romanNumeralFromChord` 算罗马数字
     —— music21 这一步就能给出副属 (V/V)、转位 (V6, V64, V7, V65, V43, V42)、
        减七 (vii°7)、半减 (viiø43) 等
  3. 用 functions.py 算 T/S/D 主功能 + role
  4. 用 cadence.py 检测终止式
  5. 用 secondary.py 检测副属 / 调式交替 / 临时主
  6. detect_modulation() 扫全曲找转调段落
"""
from __future__ import annotations

import re
from typing import Any, Optional

from music21 import chord, key, roman, stream


# ------------------------------------------------------------------ #
# 1. 单个和弦 → 完整罗马数字解读
# ------------------------------------------------------------------ #

def _safe_roman_from_chord(c: chord.Chord, k: key.Key):
    """包装 music21.roman.romanNumeralFromChord,屏蔽异常。"""
    try:
        return roman.romanNumeralFromChord(c, k)
    except Exception:
        return None


def _inversion_label(rn) -> str:
    """从 music21 figure 字符串提取斯波索宾式转位标记。

    music21 的 figure 末尾已经带转位数字:
      V      根位
      V6     第一转位 (三和弦)
      V64    第二转位 (三和弦)  → 斯波索宾写法 V6/4
      V7     七和弦根位
      V65    七和弦第一转位     → V6/5
      V43    七和弦第二转位     → V4/3
      V42    七和弦第三转位     → V4/2
    返回 "" / "6" / "6/4" / "7" / "6/5" / "4/3" / "4/2"
    """
    if rn is None:
        return ""
    fig = (getattr(rn, "figure", "") or "").strip()
    if not fig:
        return ""
    # 副属不影响转位检测
    main = fig.split("/")[0] if "/" in fig else fig
    # 去掉前置变音 # b
    while main and main[0] in "#b":
        main = main[1:]
    # main 形如 "V64", "V6", "V7", "viio6", "viiø43", "viio7", "V65", "V42", "V43"
    # 检测末尾数字
    import re as _re
    m = _re.search(r"(\d+)$", main)
    if not m:
        return ""
    suffix = m.group(1)
    if suffix == "6":
        return "6"
    if suffix == "64":
        return "6/4"
    if suffix == "65":
        return "6/5"
    if suffix == "43":
        return "4/3"
    if suffix == "42":
        return "4/2"
    if suffix == "7":
        return ""  # 七和弦根位, 转位标记空
    return ""


def _quality_zh(quality: str) -> str:
    return {
        "major": "大三",
        "minor": "小三",
        "diminished": "减三",
        "half-diminished": "半减",
        "augmented": "增三",
        "dominant": "属七",
        "major-seventh": "大七",
        "minor-seventh": "小七",
        "diminished-seventh": "减七",
        "half-diminished-seventh": "半减七",
        "augmented-seventh": "增七",
        "": "未知",
    }.get(quality, quality or "未知")


def analyze_chord_in_key(c: chord.Chord, k: key.Key) -> dict:
    """分析单个和弦在指定调下的完整罗马数字解读。

    返回字段：
      figure        罗马数字（含转位、副属、变音）  e.g. "V6", "#ivo6", "V7/IV"
      figureWithInversion  含斯波索宾式转位上标  e.g. "V6", "V64", "V65"
      scaleDegree   音级 1-7
      quality       和弦性质（major/minor/...）
      qualityZh     中文性质
      inversion     斯波索宾转位标记 "" / "6" / "6/4" / "4/3" / "4/2"
      isSeventh     是否带七音
      function      主功能 T / S / D
      role          角色 primary / extension / substitute / cadential / borrowed / applied
      isSecondary   是否副属
      secondaryOf   副属解决到 (V/IV → "IV")
      isBorrowed    是否借用
      key           分析所用的调  e.g. "C major"
      confidence    置信度  high / medium / low
    """
    from .functions import function_from_roman, classify_chord_role
    from .secondary import detect_secondary, detect_borrowed

    rn = _safe_roman_from_chord(c, k)
    if rn is None:
        return {
            "figure": "?",
            "figureWithInversion": "?",
            "scaleDegree": None,
            "quality": None,
            "qualityZh": "未识别",
            "inversion": "",
            "isSeventh": False,
            "function": None,
            "role": None,
            "isSecondary": False,
            "secondaryOf": None,
            "isBorrowed": False,
            "key": _key_label(k),
            "confidence": "low",
        }

    figure = getattr(rn, "figure", "?") or "?"
    inversion = _inversion_label(rn)
    is_seventh = ("7" in figure) or figure.endswith("65") or figure.endswith("43") \
        or figure.endswith("42") or figure.endswith("ø7") or figure.endswith("o7")

    # 拼 figureWithInversion（music21 自带 figure 已是含转位形式，
    # 但有时会写 "V64" 这种"理论"标记，斯波索宾更常用 "V6/4 之于 V64"）
    figure_with_inv = figure

    fn = function_from_roman(rn)
    role_info = classify_chord_role(rn)
    # 副属检测：传入原始 chord + home_key, 走主动扫描路径
    sec = detect_secondary(rn, original_chord=c, home_key=k)
    bor = detect_borrowed(rn)
    quality = getattr(rn, "quality", "") or ""
    scale_degree = getattr(rn, "scaleDegree", None)

    # 副属时改写 figure
    final_figure = figure
    secondary_of = None
    secondary_target_key = None
    if sec:
        # 副属的 figure 用 V/x 形式, 并把 function 强设为 D
        final_figure = sec.get("figure", figure)
        secondary_of = sec.get("target")
        secondary_target_key = sec.get("targetKey")
        fn = "D"  # 副属永远是 D 功能
        role_info = {"function": "D", "role": "applied"}

    # 置信度：转位 + 副属 都能解析 → high；只有 basic roman → medium；连 scaleDegree 都没有 → low
    if scale_degree is not None and fn is not None and not final_figure.startswith("?"):
        confidence = "high"
    elif scale_degree is not None:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "figure": final_figure,
        "figureWithInversion": final_figure,
        "scaleDegree": scale_degree,
        "quality": quality,
        "qualityZh": _quality_zh(quality),
        "inversion": inversion,
        "isSeventh": bool(is_seventh),
        "function": fn,
        "role": role_info.get("role"),
        "isSecondary": bool(sec),
        "secondaryOf": secondary_of,
        "secondaryTargetKey": secondary_target_key,
        "isBorrowed": bool(bor),
        "key": _key_label(k),
        "confidence": confidence,
    }


def _key_label(k: key.Key) -> str:
    if k is None:
        return "unknown"
    try:
        return f"{k.tonic.name} {k.mode}"
    except Exception:
        return "unknown"


# ------------------------------------------------------------------ #
# 2. 整曲分析
# ------------------------------------------------------------------ #

def analyze_score(score: stream.Score) -> dict:
    """对整个 score 做斯波索宾式和声分析。

    返回：
      {
        "key": {name, mode, label, correlation},
        "chordCount": N,
        "measureCount": M,
        "harmony": [
          {
            "measure": int, "beat": float, "duration": float,
            "pitches": [...], "pitchesClass": [...],
            "analysis": {...完整 analyze_chord_in_key 输出...}
          }, ...
        ],
        "cadences":   [ {...}, ... ],
        "tonicizations": [ {...}, ... ],
        "modulations":  [ {...}, ... ],
      }
    """
    from .cadence import detect_cadences
    from .secondary import find_tonicizations

    if score is None:
        return {"key": {"label": "unknown"}, "harmony": [], "cadences": [], "tonicizations": [], "modulations": []}

    # 调性分析
    try:
        analyzed_key = score.analyze("key")
    except Exception:
        analyzed_key = None

    key_info = _key_to_info(analyzed_key)

    # 调性兜底：analyze("key") 失败时用调号
    if not analyzed_key or not isinstance(analyzed_key, key.Key):
        try:
            k_from_sig = score.recurse().getElementsByClass(key.KeySignature).first()
            if k_from_sig is not None:
                analyzed_key = k_from_sig.asKey("major")
                key_info = _key_to_info(analyzed_key)
        except Exception:
            pass

    # chordify
    try:
        chordified = score.chordify()
    except Exception:
        return {
            "key": key_info,
            "chordCount": 0,
            "measureCount": 0,
            "harmony": [],
            "cadences": [],
            "tonicizations": [],
            "modulations": [],
        }

    if analyzed_key is None or not isinstance(analyzed_key, key.Key):
        # 没调就不算罗马数字,只返原始 pitch
        return {
            "key": key_info,
            "chordCount": 0,
            "measureCount": 0,
            "harmony": [],
            "cadences": [],
            "tonicizations": [],
            "modulations": [],
        }

    # 遍历小节
    measure_objs = list(chordified.getElementsByClass(stream.Measure))
    harmony_flat: list[dict] = []
    harmony_by_measure: list[dict] = []

    for m in measure_objs:
        per_measure = {
            "measure": m.measureNumber,
            "ts": _ts_label(m),
            "chords": [],
        }
        for element in m.recurse().notes:
            if isinstance(element, chord.Chord):
                analysis = analyze_chord_in_key(element, analyzed_key)
                beat = _beat_in_measure(m, element)
                entry = {
                    "measure": m.measureNumber,
                    "beat": beat,
                    "duration": float(element.duration.quarterLength),
                    "pitches": [p.nameWithOctave for p in element.pitches],
                    "pitchClasses": sorted(set(p.pitchClass for p in element.pitches)),
                    "analysis": analysis,
                }
                per_measure["chords"].append(entry)
                harmony_flat.append({
                    "measure": m.measureNumber,
                    "beat": beat,
                    "duration": float(element.duration.quarterLength),
                    "roman": _make_rn_proxy(entry),
                })
            elif isinstance(element, chord.Chord) is False and hasattr(element, "pitch"):
                # 单音：用 _safe_roman_from_chord 强造个 chord
                from music21 import chord as _ch
                try:
                    single = _ch.Chord([element.pitch])
                    analysis = analyze_chord_in_key(single, analyzed_key)
                    beat = _beat_in_measure(m, element)
                    entry = {
                        "measure": m.measureNumber,
                        "beat": beat,
                        "duration": float(element.duration.quarterLength),
                        "pitches": [element.pitch.nameWithOctave],
                        "pitchClasses": [element.pitch.pitchClass],
                        "analysis": analysis,
                    }
                    per_measure["chords"].append(entry)
                    harmony_flat.append({
                        "measure": m.measureNumber,
                        "beat": beat,
                        "duration": float(element.duration.quarterLength),
                        "roman": _make_rn_proxy(entry),
                    })
                except Exception:
                    pass

        harmony_by_measure.append(per_measure)

    # 终止式 + 临时主
    cadences = detect_cadences(harmony_flat)
    tonicizations = find_tonicizations(harmony_flat)

    # 转调
    modulations = detect_modulation(score, analyzed_key)

    return {
        "key": key_info,
        "chordCount": len(harmony_flat),
        "measureCount": len(measure_objs),
        "harmonyByMeasure": harmony_by_measure,
        "harmonyFlat": harmony_flat,
        "cadences": cadences,
        "tonicizations": tonicizations,
        "modulations": modulations,
    }


def _key_to_info(k) -> dict:
    if k is None or not isinstance(k, key.Key):
        return {"label": "unknown"}
    try:
        return {
            "name": k.tonic.name,
            "mode": k.mode,
            "label": f"{k.tonic.name} {k.mode}",
            "correlation": round(float(getattr(k, "correlationCoefficient", 0.0)), 4),
        }
    except Exception:
        return {"label": "unknown"}


def _ts_label(measure) -> Optional[str]:
    try:
        ts = measure.timeSignature
        if ts is None:
            return None
        return f"{ts.numerator}/{ts.denominator}"
    except Exception:
        return None


def _beat_in_measure(measure, element) -> float:
    """把 offset 翻译成小节内拍号。

    4/4 拍时,offset 0.0 = 第 1 拍,1.0 = 第 2 拍。
    """
    try:
        ts = measure.timeSignature
        beat_len = ts.beatDuration.quarterLength if ts else 1.0
    except Exception:
        beat_len = 1.0
    raw = element.getOffsetInHierarchy(measure)
    return round(raw / beat_len + 1.0, 3)


def _make_rn_proxy(entry: dict):
    """为 cadence/secondary 模块造一个"伪 RomanNumeral"对象。

    cadence.py / secondary.py 都基于 music21 RomanNumeral 对象的
    .figure / .scaleDegree / .secondary / .quality 字段,
    并用 figure 末尾判断原位/转位。

    我们存 figure (e.g. "V64", "V/V", "iio") 让 cadence.py 用自己的
    _is_root_position 等函数判断。
    """
    from types import SimpleNamespace

    a = entry["analysis"]
    fig = a["figure"]
    return SimpleNamespace(
        figure=fig,
        scaleDegree=a.get("scaleDegree"),
        quality=a.get("quality"),
        secondaryRomanNumeral=SimpleNamespace(scaleDegree=a.get("secondaryOf"))
        if a.get("isSecondary") and a.get("secondaryOf") is not None
        else None,
    )


# ------------------------------------------------------------------ #
# 3. 转调检测
# ------------------------------------------------------------------ #

# 关系大小调 / 同主音大小调 / 完全转调 的几个特征
_RELATION_KEYS = {
    # 主调 -> [可能的离调目标]
    "C major":  ["a minor", "F major", "G major", "C minor"],
    "G major":  ["e minor", "C major", "D major", "G minor"],
    "D major":  ["b minor", "G major", "A major", "D minor"],
    "A major":  ["f# minor", "D major", "E major", "A minor"],
    "E major":  ["c# minor", "A major", "B major", "E minor"],
    "F major":  ["d minor", "B- major", "C major", "F minor"],
    "B- major": ["g minor", "E- major", "F major", "B- minor"],
}


def detect_modulation(score: stream.Score, home_key: key.Key) -> list[dict]:
    """扫整曲找转调段落。

    简化算法（斯波索宾常用三种转调）：
      1. 离调（Tonicization）: 副属 → 临时主 → 回主调,已经在 secondary.find_tonicizations 里
      2. 关系大小调 / 同主音大小调: 整段持续在新调上
      3. 完全转调: 整段持续在新调且不回来

    实现：对每个小节单独调 `analyze("key")`,跟 home_key 对比,若持续 ≥ 2 小节
    且不是 home_key,就记为转调段落。
    """
    if score is None or home_key is None:
        return []

    try:
        measures = list(score.recurse().getElementsByClass(stream.Measure))
    except Exception:
        return []

    modulations = []
    current_run = None  # {"start": m, "key": str, "keyObj": Key, "count": int}

    for m in measures:
        try:
            # 对单小节取音符做局部 key 分析
            local = m.analyze("key")
        except Exception:
            local = None
        if local is None or not isinstance(local, key.Key):
            if current_run:
                _maybe_emit_modulation(current_run, modulations)
                current_run = None
            continue

        local_label = f"{local.tonic.name} {local.mode}"
        home_label = f"{home_key.tonic.name} {home_key.mode}"

        if local_label == home_label:
            if current_run:
                _maybe_emit_modulation(current_run, modulations)
                current_run = None
            continue

        if current_run and current_run["key"] == local_label:
            current_run["count"] += 1
            current_run["end"] = m.measureNumber
        else:
            if current_run:
                _maybe_emit_modulation(current_run, modulations)
            current_run = {
                "start": m.measureNumber,
                "end": m.measureNumber,
                "key": local_label,
                "keyObj": local,
                "count": 1,
            }

    if current_run:
        _maybe_emit_modulation(current_run, modulations)

    return modulations


def _maybe_emit_modulation(run: dict, out: list) -> None:
    if run["count"] < 2:
        return  # 单小节不构成转调
    start = run["start"]
    end = run["end"]
    label = run["key"]
    out.append({
        "type": "modulation",
        "fromMeasure": start,
        "toMeasure": end,
        "newKey": label,
        "duration": run["count"],
    })
