# P20.3.7 — Gold Adapter Design

**日期**: 2026-08-11
**状态**: 设计 (未实现)
**目的**: 把外部数据集 (DCMLab / Humdrum / AugmentedNet) 转换成 MTRE EvalCase 格式

---

## 0. 设计原则

1. **不直接复制外部格式** — 每种源 (DCMLab TSV / Humdrum kern / AugmentedNet JSON) 有自己的 schema, 强耦合会污染 MTRE 内部
2. **统一中间格式 `external_annotation`** — 所有源先转成这个, 再转 EvalCase
3. **每个 case 一个 adapter** — 不写"通用 parser", 因为每个源字段差异太大
4. **adapter 输出必须填 `provenance`** — 保证 evidence chain 不丢
5. **adapter 不可信** — 输出 gold 必须 mark `review_status: "auto_generated"` (P20.3.7 状态机), 等人工校

---

## 1. 目录结构

```
gold_adapter/
├── __init__.py
├── common.py                 # 共享工具 (music21 parse, kern 转 music21 等)
├── external_annotation.py    # 统一中间格式 dataclass
├── dcmlab_adapter.py         # DCMLab TSV → external_annotation
├── humdrum_adapter.py        # Humdrum kern → external_annotation (无标注, 只谱面)
├── augmentednet_adapter.py   # AugmentedNet JSON → external_annotation
├── imslp_adapter.py          # IMSLP mxl → external_annotation (待实现)
├── convert_to_mtre.py        # external_annotation → MTRE EvalCase
└── tests/
    ├── test_dcmlab_adapter.py
    ├── test_humdrum_adapter.py
    └── test_convert_to_mtre.py
```

**核心约束**: adapter 只读 + 转格式, **不写自己的音乐判断**。所有"什么是 T / 什么是 S / 什么是 PAC" 都来自源。

---

## 2. 统一中间格式 `external_annotation.py`

```python
"""P20.3.7 Gold Adapter — 统一外部标注中间格式.

所有外部数据源 (DCMLab / Humdrum / AugmentedNet / IMSLP) 先转成这个 dataclass,
再统一转 MTRE EvalCase.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Literal


@dataclass
class ExternalAnnotation:
    """一个外部源对一首作品 / 一个乐章 / 一个片段的标注.

    字段命名尽量用 music21 罗马数字术语 (避免造新词):
    - roman: "I" / "V7" / "ii6" / "V7/V" (含 secondary)
    - function: "T" / "S" / "D" / "T-sub" (功能分析)
    - key: "C major" / "c minor" (music21 style)
    - cadence: "PAC" / "IAC" / "HC" / "DC" / "deceptive" / "none"

    不强制每个源都填全字段. e.g. Humdrum kern 没标注, key 可留空.
    """
    piece_id: str                              # 例 "mozart_k545_m1"
    source_dataset: str                        # 例 "DCMLab/mozart_piano_sonatas"
    source_dataset_url: str                    # 例 "https://github.com/DCMLab/mozart_piano_sonatas"
    source_format: str                         # 例 "dcml_tsv" / "humdrum_kern" / "augmentednet_json" / "musicxml"
    measure_range: str                         # 例 "mm.1-8" (与 gold JSON 的 metadata.excerpt 对齐)

    # 谱面 (来自 music21 parse)
    score: Optional[object] = None             # music21.stream.Score (parsed)
    score_format: str = "music21_internal"     # "music21_internal" / "mscx" / "musicxml" / "kern"

    # 谱面 + 标注 (从 TSV / augmentednet 提取)
    measures: list[dict] = field(default_factory=list)
    # measures 元素: {
    #   "measure": 1,                          # 1-indexed
    #   "key": "C major",                       # 该小节调性
    #   "time_signature": "4/4",                # 拍号
    #   "chords": [
    #     {
    #       "offset": 0.0,                       # 小节内偏移 (quarter length)
    #       "duration": 4.0,                     # 时值
    #       "roman": "I",                        # 罗马数字 (DCML 格式)
    #       "function": "T",                     # 功能 (如有)
    #       "inversion": "root",                 # root / 6 / 6/4 / 4/2 / 4/3 / 6/5 / 6/4/3 / ...
    #       "figured_bass": "6",                 # 如 "6 4" / "6 4 3"
    #       "secondary_key": "V",                # 如 "V7/V"
    #       "chord_tones": ["C", "E", "G"],     # 实际音
    #       "annotation_source": "dcml_tsv"      # "dcml_tsv" / "augmentednet_inferred" / "human"
    #     }
    #   ]
    #   "cadence": None  # 或 "PAC" / "HC" / "DC" (整小节终止)
    #   "phrase_role": "antecedent"  # "antecedent" / "consequent" / None
    # }

    # 标注的元数据
    annotator: str = "unknown"                  # "human/Uli Kneisel" / "human/DCMLab" / "augmentednet_v1"
    annotate_date: str = ""                     # ISO 8601
    annotation_standard: str = ""               # "dcml_v3.0.0" / "sposobin_v1" / "schenkerian"
    confidence: float = 0.0                     # 标记者自评 (0-1)

    # License / 来源信息
    license: str = ""                           # "CC BY-NC-SA 4.0" / "CC0" / "Public Domain"
    license_url: str = ""                       # 例 "https://creativecommons.org/licenses/by-nc-sa/4.0/"

    # 转换信息
    conversion_method: str = ""                 # "dcml_tsv_to_external_v1" 等
    converter_version: str = ""                 # "0.1.0"
    conversion_date: str = ""                   # ISO 8601

    # 备注
    notes: str = ""                             # 任何额外说明
```

**关键设计点**:
- `score` 字段是 music21 内部对象 (parsed), 其他字段 (key/measure/roman) 来自外部源
- 转换到 EvalCase 时, `roman` 和 `function` 字段可以**保留**或**重命名** — V1 Sposobin 体系下, "T-sub" 等 DCML 标签要改
- **不修改任何 roman / function 字段** — adapter 只搬运, 不判断音乐内容

---

## 3. DCMLab Adapter (`dcmlab_adapter.py`)

### 3.1 DCMLab 数据结构

从 `data/eval/research/provenance_check_report.json` 和 README 调研可知:

**`harmonies/<name>.harmonies.tsv`** 列:
- `mc` (measure count from start)
- `mn` (measure number)
- `timesig` (time signature)
- `mc_onset` (onset within measure, in quarter notes)
- `staff` (1 or 2)
- `voice` (1, 2, 3, 4)
- `cadence` (PAC, IAC, HC, DC, EC, etc. — **this is the cadence type**)
- `numeral` (Roman numeral e.g. "I", "V7", "V7/V", "vii°7")
- `form` (phrase boundary: "{", "}", "}{")
- `figbass` (figured bass, e.g. "6", "6 4 3", "7")
- `changes` (key changes — 改调标注)
- `relativeroot` (root pitch class, e.g. "C#", "Bb")
- `bass` (bass note pitch class)
- `quality` (M, m, m7, °7, +)
- `inversion` (root, 6, 6/4, 4/2, 4/3, 6/5, 6/4/3)
- `pedal` (pedal point)
- `chord` (full chord label)
- `altchord` (alternative label)
- `rn` (alternative Roman numeral)
- `added` (added tones)

**`measures/<name>.measures.tsv`** 列:
- `mc`, `mn`, `timesig`, `length`, `keysig`, `tonic`, `mode`, `nominal`, `actual`, `next` ...

### 3.2 Adapter 流程

```python
def load_dcmlab(
    piece_id: str,
    harmonies_tsv_path: str,
    measures_tsv_path: str,
    notes_tsv_path: str = None,
    mscore_mscx_path: str = None,
) -> ExternalAnnotation:
    """从 DCMLab TSV 加载一个乐章.

    1. 读 harmonies.tsv (TSV 格式, Frictionless)
    2. 读 measures.tsv (调性 / 拍号)
    3. 读 notes.tsv (谱面音符) - 可选
    4. 读 MS3/<name>.mscx - 可选, 作为 score 字段
    5. 按 measure + onset 排序
    6. 返回 ExternalAnnotation
    """
    # 实际实现见 dcmlab_adapter.py
```

### 3.3 DCMLab → MTRE 字段映射

| DCMLab 字段 | ExternalAnnotation 字段 | 备注 |
|---|---|---|
| `mc` | `measures[i].measure` | measure count from start |
| `mn` | `measures[i].measure` | measure number (1-indexed) |
| `timesig` | `measures[i].time_signature` | "4/4" |
| `keysig`, `tonic`, `mode` | `measures[i].key` | 拼成 "C major" |
| `mc_onset` | `measures[i].chords[j].offset` | quarter notes |
| (computed from notes) | `measures[i].chords[j].duration` | quarter notes |
| `numeral` | `measures[i].chords[j].roman` | **原样保留 DCML 格式** (e.g. "V7/V") |
| (computed from roman + inversion) | `measures[i].chords[j].function` | **不计算, 留空** — 留给 evaluate phase |
| `inversion` | `measures[i].chords[j].inversion` | "root" / "6" / "6/4" |
| `figbass` | `measures[i].chords[j].figured_bass` | "6" / "6 4 3" |
| `relativeroot` | `measures[i].chords[j].secondary_key` | 仅当 secondary 时填 |
| `chord` (full) | `measures[i].chords[j].chord_tones` | 音名列表 |
| `cadence` | `measures[i].cadence` | "PAC" / "HC" / "DC" |
| `form` | `measures[i].phrase_role` | "{", "}", "}{" |

**关键**: 不修改 `numeral` 字段。DCMLab 的 V/V / V7/V 等 Sposobin V1 体系不接受的标签, 留给 evaluate phase 通过 "needs_expert_review" 标注。

### 3.4 测试 (mo 大调 K545 1-8 小节)

```python
def test_dcmlab_mozart_k545_m1_first_8_measures():
    """验证 Mozart K.545 mvt 1, mm.1-8 的 DCMLab 标注解析正确."""
    ann = load_dcmlab(
        piece_id="mozart_k545_m1",
        harmonies_tsv_path="data/external/dcmlab/mozart_piano_sonatas/harmonies/K545-1.harmonies.tsv",
        measures_tsv_path="data/external/dcmlab/mozart_piano_sonatas/measures/K545-1.measures.tsv",
    )

    # 应该有 73 measures
    assert len(ann.measures) == 73

    # mm.1-8 必须存在
    for m in range(1, 9):
        assert m in [m.measure for m in ann.measures]

    # m.1 第一个和弦应该是 I (C major, T)
    m1 = next(m for m in ann.measures if m["measure"] == 1)
    assert m1["key"] == "C major"
    assert m1["chords"][0]["roman"] == "I"

    # m.4 应该是 HC, m.8 应该是 PAC
    m4 = next(m for m in ann.measures if m["measure"] == 4)
    assert m4["cadence"] == "HC"
    m8 = next(m for m in ann.measures if m["measure"] == 8)
    assert m8["cadence"] == "PAC"
```

---

## 4. Humdrum Adapter (`humdrum_adapter.py`)

### 4.1 Humdrum kern 数据结构

`.krn` 文件: Humdrum spine 格式, 每行一个 token, `**kern` spine 含音符。

例 (Bach WTC Prelude 1 开始):
```
!!!COM: Bach, Johann Sebastian
!!!CDT: 1685/02/21/-1750/07/28
!!!OTL: Prelude
!!!SCT: Das Wohltemperierte Klavier, Book 1
**kern	**kern
*C:	*C:
=1	=1
4c	4g
4e	4g
4g	4c'
=2	=2
...
```

**注意**: 谱面只有**音符 + 时值**, **没有 Roman numeral**。Humdrum `**harm` spine 才是 Roman numeral, 但 Bach WTC 的 .krn 文件**没有 `**harm` spine**。

### 4.2 Adapter 流程

```python
def load_humdrum_kern(
    piece_id: str,
    kern_file_path: str,
) -> ExternalAnnotation:
    """从 Humdrum kern 文件加载谱面 (无 Roman numeral 标注).

    用 music21.converter.parse 加载, 然后提取:
    - 调性 (key)
    - 拍号
    - 音符 (music21 chord/note)
    - 不填 roman / function / cadence
    """
    score = music21.converter.parse(kern_file_path)
    # ... 提取小节、调性、谱面 ...
    return ExternalAnnotation(
        piece_id=piece_id,
        source_dataset="humdrum-tools/bach-wtc",  # or craigsapp/...
        source_format="humdrum_kern",
        score=score,
        annotator="unknown",  # NO annotation
        annotation_standard="none",
        confidence=0.0,
        # measures 字段: 只有 key + time_signature + chord_tones, 无 roman
    )
```

### 4.3 Humdrum Adapter 限制

**关键事实**: Humdrum kern 文件**只有谱面, 无 Roman numeral 标注**。所以:
- `measures[i].chords[j].roman` = None
- `measures[i].chords[j].function` = None
- `measures[i].cadence` = None
- `confidence` = 0.0
- `annotator` = "unknown"

后续步骤 (人工或 AugmentedNet) 才能填这些字段。

### 4.4 测试 (Bach WTC Prelude 1)

```python
def test_humdrum_bach_wtc_prelude_bwv846():
    """验证 Bach WTC Prelude 1 的 Humdrum kern 谱面加载."""
    ann = load_humdrum_kern(
        piece_id="bach_wtc_prelude_bwv846",
        kern_file_path="data/external/humdrum-tools/bach-wtc/kern/wtc1p01.krn",
    )
    assert ann.source_format == "humdrum_kern"
    assert ann.source_dataset == "humdrum-tools/bach-wtc"
    assert ann.score is not None
    assert len(ann.measures) >= 35  # Prelude 1 大约 35 小节
    # 无 Roman numeral
    for m in ann.measures:
        for c in m["chords"]:
            assert c["roman"] is None
    # 必须从 IMSLP / 人工 / AugmentedNet 获取标注
```

---

## 5. AugmentedNet Adapter (`augmentednet_adapter.py`)

### 5.1 AugmentedNet 输出

```python
# AugmentedNet inference 输出 <input_file>_annotated.csv 格式:
# onset,key,degree,quality,inversion,roman,RN
# 0.0,C,1,M,0,I,I
# 0.5,C,2,m,0,ii,ii
# 1.0,C,5,M,0,V,V
# 1.5,C,1,M,0,I,I
```

### 5.2 Adapter 流程

```python
def load_augmentednet_csv(
    piece_id: str,
    augmentednet_csv_path: str,
    musicxml_input_path: str = None,
) -> ExternalAnnotation:
    """从 AugmentedNet 推断输出加载标注.

    1. 读 <input>_annotated.csv
    2. (可选) 读 <input>.musicxml 作为谱面
    3. 构造 ExternalAnnotation
    """
```

### 5.3 AugmentedNet → MTRE 字段映射

| AugmentedNet 列 | ExternalAnnotation 字段 |
|---|---|
| `onset` (in beats) | `measures[i].chords[j].offset` |
| `key` | `measures[i].key` (拼成 "C major" / "c minor") |
| `degree` (scale degree 1-7) | (不直接存, 需 degree + quality → Roman) |
| `quality` (M, m, m7, °7, +) | (不直接存) |
| `inversion` (0/1/2/3) | `measures[i].chords[j].inversion` (0→root, 1→6, 2→6/4) |
| `roman` | `measures[i].chords[j].roman` |
| `RN` | `measures[i].chords[j].function` (T/S/D) |

### 5.4 AugmentedNet Adapter 限制

**关键事实**: AugmentedNet 准确度 < 50% RN. 所以:
- `annotator` = "augmentednet_v1"
- `annotate_date` = (run date)
- `annotation_standard` = "augmentednet_inferred"
- `confidence` = 0.5 (经验值, 实际约 0.4-0.5)
- 标注**必须** mark `needs_expert_review=true` 在最终 EvalCase

### 5.5 测试

```python
def test_augmentednet_bach_wtc_prelude():
    """验证 AugmentedNet 输出格式转换正确."""
    ann = load_augmentednet_csv(
        piece_id="bach_wtc_prelude_bwv846",
        augmentednet_csv_path="data/external/augmentednet/wtc1p01_annotated.csv",
        musicxml_input_path="data/external/humdrum/wtc1p01.musicxml",
    )
    assert ann.annotator == "augmentednet_v1"
    assert ann.confidence < 0.6  # 永远 < 0.6 (准确度限制)
    # 标注必须 mark needs_expert_review
    # (在 convert_to_mtre.py 里强制)
```

---

## 6. IMSLP Adapter (`imslp_adapter.py`)

### 6.1 IMSLP 数据

IMSLP 上有 mxl (MusicXML compressed) 编辑版:
- 公共领域 (PD-EU / PD-World) → 商用 OK
- CC BY-NC-SA → 商用禁止
- CC BY → 商用 OK (要 attribution)
- 取决于 editor (Fingers, BSB, Petrucci, etc.)

### 6.2 Adapter 流程

```python
def load_imslp_musicxml(
    piece_id: str,
    mxl_path: str,
    imslp_url: str,
    editor: str = "",
    license: str = "",
) -> ExternalAnnotation:
    """从 IMSLP MusicXML 加载谱面 (无 Roman numeral 标注).

    与 Humdrum adapter 类似, 但 source_dataset="imslp_<editor>".
    """
```

### 6.3 IMSLP 限制

**关键事实**: IMSLP 上**没有**免费的 Roman numeral 标注。所以 IMSLP adapter 只产谱面, 不产标注。

标注来源 (人工 or AI) 必须分开。

---

## 7. 转换到 MTRE (`convert_to_mtre.py`)

### 7.1 转换流程

```python
def external_to_evalcase(ann: ExternalAnnotation, mtre_style: str = "sposobin") -> EvalCase:
    """从 ExternalAnnotation 转 MTRE EvalCase.

    Steps:
    1. 验证 ann.provenance 完整
    2. 根据 mtre_style 决定 function 标签:
       - "sposobin" (V1): 纯 T/S/D, no T-sub (reject T-sub and convert to T)
       - "functional_classical": 允许 T-sub
       - "schenkerian": 不用 T/S/D
       - "jazz_functional": 允许 extended/altered
    3. 构造 Metadata
    4. 构造 Analysis
    5. 构造 Provenance (从 ann 复制)
    6. needs_expert_review = (ann.confidence < 0.95) OR (mtre_style == "sposobin" AND DCML-style roman exists)
    """
```

### 7.2 V1 Sposobin 处理逻辑

**特别重要**: V1 体系只接受 T/S/D, 不接受 T-sub / D-sub / "inverted" / 等。

```python
def normalize_function_sposobin(roman: str, quality: str) -> str:
    """把 DCML roman 标签归一化到 V1 Sposobin 体系.

    Examples:
        "I" / "Imaj7" / "I6" / "I64" → "T"
        "ii" / "ii6" / "ii7" → "T" (V1: ii 是 pre-dominant 不是 S)
        "iii" / "iii6" → "T" (V1: iii 是 T)
        "IV" / "IV6" / "IV64" → "S"
        "V" / "V7" / "V6" → "D"
        "V7/V" / "vii°7" / "vii°7/V" → "D" (secondary dominants 归 D)
        "vi" / "vi6" / "vi7" → "T" (V1: vi 是 T 不是 S)
        "vii°" / "vii°7" → "D" (导音是 D, 解决到 T)
    """
    # 详细映射表见 convert_to_mtre.py
```

**注意**: 这只是**字段名**归一化 (function 字段), **不改** roman 字段。roman 字段保留 DCML 原始值。

### 7.3 V1 冲突检测

```python
def detect_sposobin_v1_conflict(ann: ExternalAnnotation) -> list[str]:
    """检测 DCML 标注中 V1 体系不能直接用的标签.

    Returns: list of conflict notes (e.g. "m.5: DCML vi 标 T, V1 应为 T (already T, OK)")
    """
```

### 7.4 EvalCase 输出

```python
def external_to_evalcase(ann, mtre_style="sposobin") -> EvalCase:
    """完整转换."""
    return EvalCase(
        metadata=Metadata(
            id=ann.piece_id,
            composer=...,
            title=...,
            ...
        ),
        analysis=Analysis(
            key=ann.measures[0]["key"],
            cadences=[Cadence(type=...) for m in ann.measures if m.get("cadence")],
            harmony=Harmony(
                roman_progression=[c["roman"] for m in ann.measures for c in m["chords"]],
                functional_analysis=[c["function"] for m in ann.measures for c in m["chords"]],
            ),
            ...
        ),
        needs_expert_review=(
            ann.confidence < 0.95
            or ann.source_format != "dcml_tsv"  # DCMLab 是唯一可信直接源
        ),
        review_notes=...,
        provenance=Provenance(
            source_score=ann.score,
            source_url=ann.source_dataset_url,
            source_format=ann.source_format,
            measure_range=ann.measure_range,
            annotator=ann.annotator,
            annotate_date=ann.annotate_date,
            confidence=ann.confidence,
            evidence_chain=[ann.source_dataset],
            acquired_status="available",  # 因为有谱面
            review_status=(
                "expert_reviewed" if ann.source_format == "dcml_tsv"
                else "raw" if ann.source_format == "humdrum_kern"
                else "auto_generated" if ann.source_format == "augmentednet_json"
                else "raw"
            ),
            notes=ann.notes,
        ),
    )
```

### 7.5 测试 (Mozart K.545-1 DCMLab → MTRE)

```python
def test_convert_mozart_k545_dcmlab_to_mtre():
    """端到端测试: DCMLab → External → EvalCase."""
    ann = load_dcmlab(
        piece_id="mozart_k545_m1",
        harmonies_tsv_path="data/external/dcmlab/mozart_piano_sonatas/harmonies/K545-1.harmonies.tsv",
        measures_tsv_path="data/external/dcmlab/mozart_piano_sonatas/measures/K545-1.measures.tsv",
    )
    case = external_to_evalcase(ann, mtre_style="sposobin")

    # 验证 metadata
    assert case.metadata.id == "mozart_k545_m1"
    assert case.analysis.key == "C major"

    # 验证 cadences (DCMLab 标 HC@4 + PAC@8)
    cadence_types = {c.measure: c.type for c in case.analysis.cadences}
    assert cadence_types[4] == "HC"
    assert cadence_types[8] == "PAC"

    # 验证 provenance
    assert case.provenance.source_dataset_url == "https://github.com/DCMLab/mozart_piano_sonatas"
    assert case.provenance.acquired_status == "available"
    assert case.provenance.review_status == "expert_reviewed"  # DCMLab 有 expert review
    assert "DCMLab" in case.provenance.evidence_chain[0]

    # 验证 functional_analysis (V1 Sposobin T/S/D 纯标签)
    for f in case.analysis.harmony.functional_analysis:
        assert f in ("T", "S", "D"), f"Got {f}"
```

---

## 8. 错误处理与降级

| 场景 | 处理 |
|---|---|
| DCMLab TSV 列缺失 | 用 column 名校验, 缺失 raise ValueError |
| Humdrum kern 解析失败 | music21 抛异常, propagate |
| AugmentedNet CSV 空 | 返回空 `measures=[]`, `confidence=0.0` |
| IMSLP 谱面无 license 信息 | `license="unknown"`, 警告用户手动确认 |
| `roman` 含 V1 体系外字符 (e.g. "/") | 保留原值, 标 `needs_expert_review=true`, 写 review_notes |

---

## 9. 实施时间表 (预估)

| Phase | 任务 | 工时 |
|---|---|---|
| 2.1 | common.py (music21 工具) | 2h |
| 2.2 | external_annotation.py (dataclass) | 1h |
| 2.3 | dcmlab_adapter.py (含测试) | 6h |
| 2.4 | humdrum_adapter.py (含测试) | 3h |
| 2.5 | augmentednet_adapter.py (含测试) | 4h |
| 2.6 | imslp_adapter.py (含测试) | 2h |
| 2.7 | convert_to_mtre.py (含 Sposobin V1 归一化) | 4h |
| 2.8 | 集成测试 (8 case 端到端) | 3h |
| 2.9 | P20.7 Benchmark Runner (依赖以上) | 8h |

**总计**: ~33h (4 工作日)

---

## 10. 关键约束 (不能违反)

1. **不修改 gold JSON 音乐内容** — adapter 只搬运, 不判断
2. **每条标注必填 provenance** — 至少 `source_dataset`, `source_format`, `annotator`, `confidence`
3. **自动生成的标注 mark `review_status: "auto_generated"`** — 不允许 mark "expert_reviewed"
4. **V1 Sposobin 归一化只改 `function` 字段, 不改 `roman` 字段** — 原始 DCML 标签必须保留
5. **失败时抛 ValueError, 不吞异常** — adapter 必须显式
