# P20.3.7 — Schema Provenance Enhancement

**日期**: 2026-08-11
**状态**: 设计 (未实现)
**目的**: 增强 `data/eval/schema.py` 的 Provenance dataclass, 支持 Gold Adapter 多源数据

---

## 0. 当前状态 (P20.3.7)

`data/eval/schema.py` 现有 `Provenance` dataclass (P20.3.7 添加):

```python
@dataclass
class Provenance:
    source_score: str = ""        # 例 "mozart_k545.mxl"
    source_url: str = ""          # IMSLP URL
    source_format: str = ""       # "musicxml" / "midi" / "kern" / "pdf" / "mscz"
    measure_range: str = ""       # 例 "mm.1-8"
    annotator: str = ""           # "human/<name>" / "music21-auto" / "ai/<model>"
    annotate_date: str = ""       # ISO 8601
    confidence: float = 0.0       # 0-1
    evidence_chain: list[str] = field(default_factory=list)
    acquired_status: str = "needs_imslp"  # "available" / "needs_imslp" / ...
    review_status: str = "raw"    # "raw" / "human_annotated" / "expert_reviewed"
    notes: str = ""
```

**当前限制**:
1. `acquired_status` 缺少"auto_generated" (AI 推断) 状态
2. `review_status` 缺少"auto_generated" 状态
3. 缺 `source_dataset` 字段 (来源 repo / dataset 名)
4. 缺 `source_dataset_url` 字段 (具体到 GitHub URL)
5. 缺 `license` 字段 (商用重要)
6. 缺 `annotation_standard` 字段 (DCML / Sposobin / Schenkerian)
7. 缺 `conversion_method` 字段 (怎么从源转过来的)

---

## 1. 增强版 Provenance (P20.3.7 后)

```python
@dataclass
class Provenance:
    """P20.3.7 增强 — evidence chain + license + 转换方法.

    任何 gold 必须能追溯到原始数据源 + 转换方法 + 标注者 + license.
    """

    # ===== 数据源 (source) =====
    source_dataset: str = ""          # 例 "DCMLab/mozart_piano_sonatas"
    source_dataset_url: str = ""      # 例 "https://github.com/DCMLab/mozart_piano_sonatas"
    source_score: str = ""            # 例 "mozart_k545.mxl" or "K545-1.mscx" or "wtc1p01.krn"
    source_score_local_path: str = "" # 相对 data/eval/scores/ 的路径 (本地缓存)
    source_url: str = ""              # 例 IMSLP URL (兼容旧字段)
    source_format: str = ""           # 见下表

    # ===== 标注 (annotation) =====
    annotator: str = ""               # "human/Uli Kneisel" / "human/DCMLab" / "augmentednet_v1.0.0"
    annotate_date: str = ""           # ISO 8601
    annotation_standard: str = ""     # "dcml_v3.0.0" / "sposobin_v1" / "schenkerian"
    annotation_confidence: float = 0.0  # 标记者自评 (0-1) - **改名 confidence → annotation_confidence 避免与旧的 source_confidence 冲突**
    measure_range: str = ""           # 例 "mm.1-8"

    # ===== 状态 (status) =====
    acquired_status: str = "needs_imslp"
    # 选项:
    #   "needs_imslp"        — 没有谱面, 需要从 IMSLP 获取
    #   "needs_humdrum"      — 没有谱面, 需要从 Humdrum/kern 获取
    #   "needs_pdf_ocr"       — 没有谱面, 需要从 PDF 扫描 + OCR 获取
    #   "available"          — 谱面 + 标注都齐

    review_status: str = "raw"
    # 选项:
    #   "raw"                — 完全没有标 (只有谱面)
    #   "auto_generated"     — AI/算法生成 (e.g. AugmentedNet), 未人工校
    #   "human_annotated"    — 有人类标注, 未 expert 审定
    #   "expert_reviewed"    — expert 审定 (e.g. DCMLab 有 reviewer)

    # ===== 法律 (legal) =====
    license: str = ""                 # "CC BY-NC-SA 4.0" / "CC0" / "Public Domain" / "MIT"
    license_url: str = ""             # 例 "https://creativecommons.org/licenses/by-nc-sa/4.0/"
    commercial_use: bool = True       # 是否允许商用 (license 派生)
    attribution_required: bool = True # 是否需要 attribution

    # ===== 转换 (conversion) =====
    conversion_method: str = ""       # "dcmlab_adapter_v1" / "humdrum_adapter_v1" / "augmentednet_adapter_v1"
    converter_version: str = ""       # 例 "0.1.0"
    conversion_date: str = ""         # ISO 8601

    # ===== 证据链 (evidence chain) =====
    evidence_chain: list[str] = field(default_factory=list)
    # 例 ["DCMLab/mozart_piano_sonatas", "music21 v10.5.0", "ms3 v2.3.0"]

    # ===== 备注 (notes) =====
    notes: str = ""                   # 任何额外说明
```

---

## 2. 字段值约束 (enforced by validators)

### 2.1 source_format 取值

| 值 | 含义 | 典型来源 |
|---|---|---|
| `musicxml` | MusicXML 谱面 | IMSLP, Audiveris OMR |
| `mscx` | MuseScore uncompressed | DCMLab MS3/<name>.mscx |
| `kern` | Humdrum **kern | craigsapp, humdrum-tools |
| `pdf` | PDF (需 OCR 转谱面) | IMSLP PDF |
| `midi` | MIDI (无谱面) | 录音导出 |
| `dcml_tsv` | DCMLab TSV 标注 (注: 不是谱面) | DCMLab harmonies.tsv |
| `augmentednet_csv` | AugmentedNet 输出 (注: 不是谱面) | AugmentedNet inference |

**关键**: 谱面格式 vs 标注格式分离。一个 gold 可同时有 `source_score` (谱面) 和 `source_annotation` (标注)。

**改进**: 拆为 2 个字段

```python
@dataclass
class Provenance:
    # ... 其他字段 ...
    source_score_format: str = ""     # 谱面格式 (musicxml / mscx / kern / pdf / midi)
    source_annotation_format: str = "" # 标注格式 (dcml_tsv / augmentednet_csv / music21_romantext)
```

### 2.2 annotation_standard 取值

| 值 | 含义 | 兼容性 |
|---|---|---|
| `dcml_v3.0.0` | DCML harmony annotation standard | 完整 (含 secondary, altered) |
| `dcml_v2.2.0` | DCML v2.2.0 | 略少字段 |
| `sposobin_v1` | Sposobin V1 体系 (T/S/D only) | 严格, 拒绝 V/V 等 |
| `schenkerian` | Schenker 骨架分析 | 不用 T/S/D |
| `jazz_functional` | Jazz functional (含 9/11/13 extensions) | 允许 altered dominants |
| `modal` | Modal (用 mode 不用 T/S/D) | 不用 T/S/D |
| `none` | 无标注 (只有谱面) | — |

### 2.3 review_status 取值 (重要新值)

| 旧值 | 含义 | P20.3.7 增 | P20.3.7 改 |
|---|---|---|---|
| `raw` | 无标注 | 保留 | — |
| `auto_generated` | AI/算法生成 | **新增** | `review_status="auto_generated"` (AugmentedNet) |
| `human_annotated` | 有人标, 未 expert 审定 | 保留 | — |
| `expert_reviewed` | expert 审定 | 保留 | — |

**约束**:
- `raw` ⇒ `acquired_status` 可以是任何状态 (可以只有谱面无标)
- `auto_generated` ⇒ `annotator` 必须以 "ai/" 或 "augmentednet/" 开头
- `human_annotated` ⇒ `annotator` 必须以 "human/" 开头
- `expert_reviewed` ⇒ `annotator` 必须以 "human/" 开头 + `annotation_confidence` ≥ 0.85

### 2.4 acquired_status 取值

| 值 | 含义 | 期望的 `source_score` |
|---|---|---|
| `needs_imslp` | 谱面缺失, 需 IMSLP | "" (空) |
| `needs_humdrum` | 谱面缺失, 需 Humdrum | "" (空) |
| `needs_pdf_ocr` | 谱面缺失, 需 PDF+OCR | "" (空) |
| `available` | 谱面 + 标注都齐 | 非空 |

---

## 3. 迁移路径 (现有 8 个 gold JSON)

### 3.1 旧 gold JSON (P20.3.7 后) 示例

```json
{
  "metadata": {
    "id": "mozart_k545_m1",
    "composer": "W.A. Mozart",
    "title": "Piano Sonata K.545 1st Movement",
    "opus": "K.545",
    "period": "Classical (1750-1820)",
    "style_profile": "sposobin",
    "analysis_framework": "sposobin",
    "excerpt": "mm.1-8 (1st theme)",
    "difficulty": 1,
    "source_url": "https://imslp.org/wiki/Piano_Sonata_No.16_in_C_major,_K.545_(Mozart,_Wolfgang_Amadeus)"
  },
  ...
  "provenance": {
    "source_score": "",
    "source_url": "https://imslp.org/wiki/Piano_Sonata_No.16_in_C_major,_K.545_(Mozart,_Wolfgang_Amadeus)",
    "source_format": "",
    "measure_range": "mm.1-8",
    "annotator": "",
    "annotate_date": "",
    "confidence": 0.0,
    "evidence_chain": [],
    "acquired_status": "needs_imslp",
    "review_status": "raw",
    "notes": "P20.3.7 — 当前无谱面, gold 是占位文本. 需获取 MusicXML + 人工标注后才能进入 benchmark."
  }
}
```

### 3.2 新 Provenance (替换为 DCMLab 数据后)

```json
{
  "metadata": {
    "id": "mozart_k545_m1",
    "composer": "W.A. Mozart",
    "title": "Piano Sonata K.545 1st Movement (1st theme)",
    "opus": "K.545",
    "period": "Classical (1750-1820)",
    "style_profile": "sposobin",
    "analysis_framework": "functional",
    "excerpt": "mm.1-8 (1st theme, from DCMLab full-movement annotation)",
    "difficulty": 1,
    "source_url": "https://github.com/DCMLab/mozart_piano_sonatas/blob/main/harmonies/K545-1.harmonies.tsv"
  },
  ...
  "provenance": {
    "source_dataset": "DCMLab/mozart_piano_sonatas",
    "source_dataset_url": "https://github.com/DCMLab/mozart_piano_sonatas",
    "source_score": "MS3/K545-1.mscx",
    "source_score_local_path": "mozart_piano_sonatas/MS3/K545-1.mscx",
    "source_url": "https://github.com/DCMLab/mozart_piano_sonatas/blob/main/harmonies/K545-1.harmonies.tsv",
    "source_score_format": "mscx",
    "source_annotation_format": "dcml_tsv",
    "annotator": "human/Uli Kneisel",
    "annotate_date": "2021-04-28",
    "annotation_standard": "dcml_v3.0.0",
    "annotation_confidence": 0.95,
    "measure_range": "mm.1-8",
    "acquired_status": "available",
    "review_status": "expert_reviewed",
    "license": "CC BY-NC-SA 4.0",
    "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "commercial_use": false,
    "attribution_required": true,
    "conversion_method": "dcmlab_adapter_v1",
    "converter_version": "0.1.0",
    "conversion_date": "2026-08-11",
    "evidence_chain": [
      "DCMLab/mozart_piano_sonatas (Hentschel et al. 2021 TISMIR)",
      "music21 v10.5.0 (parse .mscx)",
      "ms3 v2.3.0 (extract harmonies.tsv)",
      "dcmlab_adapter v0.1.0 (convert to MTRE EvalCase)"
    ],
    "notes": "Annotation covers full movement (73 measures, 119 labels). This gold uses mm.1-8 (10 chords, 2 cadences) subset aligned with metadata.excerpt."
  }
}
```

---

## 4. 强制约束 (schema 验证)

新增 `schema.py` 验证函数, 在 `from_dict` 时检查:

```python
def validate_provenance(p: Provenance) -> list[str]:
    """返回 warning / error 列表."""
    issues = []
    if p.acquired_status == "available" and not p.source_score:
        issues.append("ERROR: acquired_status=available but source_score empty")
    if p.review_status == "auto_generated" and not p.annotator.startswith(("ai/", "augmentednet/", "music21-auto/")):
        issues.append(f"ERROR: review_status=auto_generated but annotator={p.annotator!r} not AI-style")
    if p.review_status == "human_annotated" and not p.annotator.startswith("human/"):
        issues.append(f"ERROR: review_status=human_annotated but annotator={p.annotator!r} not human-style")
    if p.review_status == "expert_reviewed" and p.annotation_confidence < 0.85:
        issues.append(f"WARN: review_status=expert_reviewed but confidence={p.annotation_confidence} < 0.85")
    if p.acquired_status == "needs_imslp" and p.source_score:
        issues.append("WARN: acquired_status=needs_imslp but source_score is set (inconsistent)")
    if not p.license and p.acquired_status == "available":
        issues.append("WARN: license empty for available source (legal risk)")
    return issues
```

### 4.1 测试 (test_p20_3_7_provenance_v2.py)

```python
def test_provenance_dcmlab_mozart_validates():
    """验证 DCMLab 替换后的 Mozart K545 gold provenance."""
    case = get_gold("mozart_k545_m1")
    issues = validate_provenance(case.provenance)
    assert all(not i.startswith("ERROR") for i in issues), f"got {issues}"

def test_provenance_status_consistency():
    """status 字段互斥验证."""
    # raw + auto_generated: 应有 source_score
    # available: 必有 source_score + annotator
    ...

def test_provenance_review_status_annotator_format():
    """review_status 决定 annotator 前缀."""
    for case in load_all_gold():
        for review, prefix in [
            ("auto_generated", ("ai/", "augmentednet/", "music21-auto/")),
            ("human_annotated", ("human/",)),
            ("expert_reviewed", ("human/",)),
        ]:
            if case.provenance.review_status == review:
                assert case.provenance.annotator.startswith(prefix)
```

---

## 5. 文件结构 (P20.3.7 增强后)

```
data/eval/
├── schema.py             # 增强 Provenance + validate_provenance() 函数
├── gold/                 # 8 gold JSON (mozart/beethoven 用 DCMLab 替换, 其他保留 placeholder)
├── later_profiles/       # 4 V2 JSON (V2 不在 P20.3.7 范围)
├── external/             # 新 — 外部数据集本地缓存
│   ├── DCMLab_mozart_piano_sonatas/
│   │   ├── MS3/K545-1.mscx
│   │   ├── harmonies/K545-1.harmonies.tsv
│   │   ├── measures/K545-1.measures.tsv
│   │   ├── notes/K545-1.notes.tsv
│   │   └── LICENSE
│   ├── DCMLab_beethoven_piano_sonatas/
│   │   ├── MS3/08-1.mscx
│   │   └── harmonies/08-1.harmonies.tsv
│   ├── humdrum-tools_bach-wtc/
│   │   ├── kern/wtc1p01.krn
│   │   └── kern/wtc1f01.krn
│   ├── craigsapp_chopin-preludes/
│   │   └── kern/prelude28-20.krn
│   └── README.md         # 每个 source 的 license + attribution
├── gold_adapter/         # 新 — Phase 2 设计
│   └── (见 gold_adapter_design.md)
└── populate_provenance.py  # 现有 P20.3.7 工具
```

**`external/` 目录**:
- 只放**本地缓存** (git submodule 或单独下载脚本)
- 真实 source 仍在 GitHub / IMSLP
- 每个 source 子目录含 LICENSE 副本
- `data/external/README.md` 列出所有 source + 链接 + license

---

## 6. 实施时间表

| 任务 | 工时 |
|---|---|
| schema.py Provenance 增强 | 2h |
| validate_provenance() 函数 | 1h |
| 测试 (test_p20_3_7_provenance_v2.py) | 2h |
| external/ 目录创建 + 初始 clone | 2h |
| Mozart K545 gold JSON 用 DCMLab 数据替换 | 2h |
| Beethoven Op13 gold JSON 用 DCMLab 数据替换 | 2h |
| Bach WTC x2 + Chopin Op.28 gold JSON 用 AugmentedNet + 人工 | 6h |
| 删 / 标记 deprecated: Haydn, Chopin Op.9, Schubert | 1h |
| **总计** | **~18h (2-3 工作日)** |

---

## 7. 与现有 test_p20_3_7_provenance.py 的兼容性

**约束**: 现有 19 个测试**不能**破坏。P20.3.7 增强后:

- **新增字段** (source_dataset, license, etc.) → 旧 JSON 加载时用默认值 (空字符串)
- **重命名字段** (`confidence` → `annotation_confidence`) → 旧 JSON 有 `confidence`, 需在 from_dict 里兼容读取
- **新增可选字段** → 旧 gold 不影响

**兼容代码示例**:
```python
@classmethod
def from_dict(cls, d: dict) -> "EvalCase":
    # ... 现有代码 ...
    prov_d = d.get("provenance", {})
    # 兼容旧字段名
    if "confidence" in prov_d and "annotation_confidence" not in prov_d:
        prov_d["annotation_confidence"] = prov_d.pop("confidence")
    provenance = Provenance(**prov_d) if prov_d else Provenance()
    # ...
```

---

## 8. 总结

**核心增强**:
1. `source_dataset` + `source_dataset_url` — 精确追溯到 GitHub repo
2. `source_score_format` + `source_annotation_format` — 谱面 / 标注分离
3. `annotator` 前缀强制 (`human/` / `ai/augmentednet/` / `music21-auto/`)
4. `annotation_standard` — DCML / Sposobin / Schenkerian 区分
5. `commercial_use` + `license` + `attribution_required` — 法律字段
6. `conversion_method` + `converter_version` — 转换可追溯
7. `review_status` 新增 `auto_generated` 值 — AI 推断明确区分

**配套新增**:
- `validate_provenance()` 强制约束
- `data/external/` 外部数据本地缓存
- `data/external/README.md` source 索引

**最大变化**:
- Mozart K.545 + Beethoven Op.13 这 2 个 gold 从"手写猜测"变成"DCMLab 专家标"
- 这是**质的提升** — 从可信度 0 到 0.95
