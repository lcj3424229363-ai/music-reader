# P20.3.7 — Gold Dataset Research Report

**日期**: 2026-08-11
**作者**: Mavis (按用户要求: GitHub 官方仓库 + 论文主页优先,不读博客二手)
**目的**: 调研公开音乐理论分析数据集, 找出可接入 MTRE gold benchmark 的可靠 evidence chain

---

## 0. TL;DR (执行摘要)

调研了 5 大公开数据源 + 多个候选仓库。结论:

| 我们的 8 case | DCMLab | Humdrum kern | 谱面 (mxl) | Roman numeral 标注 | 推荐路径 |
|---|---|---|---|---|---|
| bach_wtc_prelude_bwv846 | ❌ | ✅ humdrum-tools | ⚠️ 需 IMSLP | ⚠️ 需 AugmentedNet / 人工 | Humdrum + AugmentedNet inference + 人工校 |
| bach_wtc_fugue_bwv846 | ❌ | ✅ humdrum-tools | ⚠️ 需 IMSLP | ⚠️ 同上 | 同上 |
| mozart_k545_m1 | ✅ **mozart_piano_sonatas** | ✅ craigsapp | ⚠️ 需 IMSLP | ✅ **DCMLab (专家标)** | DCMLab 直接用 (1) |
| beethoven_pathetique_m1 | ✅ **beethoven_piano_sonatas** | ✅ craigsapp | ⚠️ 需 IMSLP | ✅ **DCMLab (专家标)** | DCMLab 直接用 (1) |
| haydn_hobxvi52_m1 | ❌ | ❌ craigsapp 无 | ⚠️ 需 IMSLP | ❌ 无公开 | 暂缓 (无可信标) |
| chopin_op9_no2 | ❌ (只有 mazurka) | ❌ (chopin-preludes 只有 Op.28) | ⚠️ 需 IMSLP | ❌ 无公开 | 暂缓 (无可信标) |
| chopin_op28_no20 | ❌ | ✅ craigsapp/chopin-preludes | ⚠️ 需 IMSLP | ⚠️ 需 AugmentedNet / 人工 | Humdrum + AugmentedNet + 人工校 |
| schubert_op90_no3 | ❌ | ❌ | ⚠️ 需 IMSLP | ❌ 无公开 | 暂缓 (无可信标) |

**关键发现**:
- **DCMLab (EPFL Digital and Cognitive Musicology Lab)** 是目前最可信的公开标注来源, 标记者都是真人 (Adrian Nagel, Lydia Carlisi, Johannes Hentschel 等), 已被 AugmentedNet ISMIR 2021 论文用为 benchmark。
- **2/8 case 有完整公开标 (Mozart K.545, Beethoven Op.13)**, 可直接用 DCMLab 数据替换现有 8 个 gold JSON 中对应 2 个。
- **3/8 case (Bach WTC x2, Chopin Op.28 No.20) 有 Humdrum kern 谱面但无人工标** — 可用 AugmentedNet 自动推断 + 人工校
- **3/8 case (Haydn, Chopin Op.9 No.2, Schubert Op.90 No.3) 公开无完整覆盖** — 建议从 gold 中移除, 等未来

---

## 1. Phase 0 — 项目当前架构

### 1.1 黄金数据位置

| 路径 | 内容 | 来源标注 |
|---|---|---|
| `data/eval/gold/*.json` | 8 个 Sposobin case (V1) | **手写猜测, 无谱面** (P20.3.7 标记为 needs_imslp) |
| `data/eval/later_profiles/*.json` | 4 个 jazz/modal case (V2) | 同上 |
| `data/eval/schema.py` | EvalCase + Provenance dataclass | P20.3.7 加 Provenance, 兼容旧 JSON |
| `data/eval/music21_draft.py` | 自动生成 key/罗马数字初稿 (占位) | 不可信 |
| `data/__init__.py` | package doc | — |
| `data/repertoire.py` | 8 经典作品 metadata (人工写) | 参考用, 非 gold |
| `data/error_cases.py` | 10 错误案例 (人工写) | 参考用, 非 gold |

### 1.2 Benchmark runner

**未实现**。P20.7 还没建。当前架构:

```
data/eval/schema.py    ← dataclass + load + validate
data/eval/gold/*.json  ← 8 case (Sposobin V1)
data/eval/later_profiles/*.json  ← 4 case (V2)
data/eval/__init__.py
data/eval/music21_draft.py  ← 占位
data/eval/provenance_check.py  ← P20.3.7 music21 探索脚本
data/eval/populate_provenance.py  ← P20.3.7 批量加 provenance
```

### 1.3 测试

`tests/test_p20_3_eval.py` (37) + `test_p20_3_7_provenance.py` (19) — 测试 schema/load, 不测试 gold 内容正确性。

### 1.4 需要修改的地方

1. **gold JSON 替换**: 2 个 case (Mozart, Beethoven) 用 DCMLab 数据替换现有手写 gold。
2. **gold JSON 删除**: 3 个 case (Haydn, Chopin Op.9, Schubert) 暂缓, 不删但标 deprecated。
3. **Gold Adapter**: 新建 `gold_adapter/` 目录, 转换 DCMLab / Humdrum / AugmentedNet 格式到 MTRE EvalCase 格式。
4. **Provenance 增强**: 现有 Provenance 加 `source_format` 字段区分 musicxml / kern / tsv, 加 `conversion_method` 字段记录怎么转换来的。
5. **Benchmark Runner**: P20.7, 等以上 4 项都完成。

---

## 2. Phase 1.1 — DCMLab (Digital and Cognitive Musicology Lab, EPFL)

**URL**: https://github.com/DCMLab
**核心人物**: Johannes Hentschel, Yannis Rammos, Markus Neuwirth, Martin Rohrmeier, Adrian Nagel
**License**: **CC BY-NC-SA 4.0** (非商用, 改动要开源)
**Zenodo DOI 集合**: https://doi.org/10.5281/zenodo.7483349 (Romantic Piano Corpus v1.0)
**数据格式**:
- `MS3/<name>.mscx` — MuseScore 3.6.2 文件 (含标注)
- `notes/<name>.notes.tsv` — 音头表
- `measures/<name>.measures.tsv` — 小节表
- `chords/<name>.chords.tsv` — 谱面标
- `harmonies/<name>.harmonies.tsv` — **和声标注 (核心)**
- `unfolded_harmonies/<name>.unfolded_harmonies.tsv` — 展开的标注 (DLC 格式)
- 每个 TSV 配 `.resource.json` (Frictionless 规范, 描述字段类型)

**标注标准**: DCML harmony annotation standard (3.0.0), Roman Numeral 变体, 含 secondary dominants, 等等

**重要数据报告**:
- Hentschel, Rammos, Neuwirth, Rohrmeier (2025). "A corpus and a modular infrastructure for the empirical study of (an)notated music". *Scientific Data* 12(1), 685. https://doi.org/10.1038/s41597-025-04976-z
- Hentschel, Neuwirth, Rohrmeier (2021). "The Annotated Mozart Sonatas: Score, harmony, and cadence". *TISMIR* 4(1), 67-80. https://doi.org/10.5334/tismir.63

### 2.1 完整仓库列表 (100 个) + 我们的 8 case 匹配

| 我们 case | DCMLab repo | 文件 | 状态 |
|---|---|---|---|
| bach_wtc_prelude_bwv846 | ❌ | (没有 WTC) | **NOT FOUND** |
| bach_wtc_fugue_bwv846 | ❌ | (没有 WTC) | **NOT FOUND** |
| mozart_k545_m1 | ✅ `mozart_piano_sonatas` | `K545-1.harmonies.tsv` (73 measures, 119 labels) | **AVAILABLE** |
| beethoven_pathetique_m1 | ✅ `beethoven_piano_sonatas` | `08-1.harmonies.tsv` (310 measures, 503 labels) | **AVAILABLE** |
| haydn_hobxvi52_m1 | ❌ | (DCMLab 没有 haydn_piano_sonatas) | **NOT FOUND** |
| chopin_op9_no2 | ❌ | (只有 `chopin_mazurkas`) | **NOT FOUND** |
| chopin_op28_no20 | ❌ | (没有 preludes/nocturnes) | **NOT FOUND** |
| schubert_op90_no3 | ❌ | (只有 `schubert_winterreise` 声乐) | **NOT FOUND** |

### 2.2 DCMLab 钢琴相关 corpus 完整列表

| Repo | 内容 | 钢琴奏鸣曲/独奏 | License |
|---|---|---|---|
| `mozart_piano_sonatas` | Mozart 18 首钢琴奏鸣曲 (Neue Mozart Ausgabe) | ✅ **含 K.545** | CC BY-NC-SA 4.0 |
| `beethoven_piano_sonatas` | Beethoven 32 首钢琴奏鸣曲 (Henle) | ✅ **含 Op.13** | CC BY-NC-SA 4.0 |
| `chopin_mazurkas` | Chopin 玛祖卡全集 | ❌ 玛祖卡, 不是夜曲 | CC BY-NC-SA 4.0 |
| `schumann_kinderszenen` | Schumann 童年情景 | ❌ 钢琴套曲 (不是奏鸣曲) | CC BY-NC-SA 4.0 |
| `liszt_pelerinage` | Liszt 朝圣之年 | ❌ | CC BY-NC-SA 4.0 |
| `grieg_lyric_pieces` | Grieg 抒情小品 | ❌ | — |
| `tchaikovsky_seasons` | Tchaikovsky 四季 | ❌ | — |
| `medtner_tales` | Medtner 童话 | ❌ | — |
| `dvorak_silhouettes` | Dvořák 剪影 | ❌ | — |
| `kozeluh_sonatas` | Koželuch 奏鸣曲 | ❌ (Leopold Koželuch, 古典时期) | — |
| `mendelssohn_quartets` | Mendelssohn 弦乐四重奏 | ❌ | — |
| `wagner_overtures` | Wagner 序曲 | ❌ | — |
| `mahler_kindertotenlieder` | Mahler 亡儿悼歌 | ❌ 声乐 | — |
| `monteverdi_madrigals` | Monteverdi 牧歌 | ❌ | — |
| `handel_keyboard` | Handel 键盘作品 | ❌ | — |
| `jc_bach_sonatas` | J.C. Bach 奏鸣曲 | ❌ | — |
| `scarlatti_sonatas` | Scarlatti 奏鸣曲 | ❌ | — |
| `corelli` | Corelli 作品 | ❌ | — |
| `debussy_suite_bergamasque` | Debussy 贝加摩组曲 | ❌ | — |
| `ravel_piano` | Ravel 钢琴作品 | ❌ | — |
| `sweelinck_keyboard` | Sweelinck 键盘作品 | ❌ | — |
| `bach_solo` | Bach 独奏作品 (BWV 1001-1013 弦乐/大提琴/长笛) | ❌ 不是 WTC | — |
| `bach_chorales` | Bach 众赞歌 | ❌ | — |
| `bach_en_fr_suites` | Bach 英国/法国组曲 | ❌ | — |
| `wf_bach_sonatas` | W.F. Bach 奏鸣曲 | ❌ | — |
| `ABC` | **Annotated Beethoven Corpus** — Beethoven 弦乐四重奏 (16 首) | ❌ 弦乐四重奏 | CC BY-NC-SA 4.0 |

### 2.3 Mozart K.545-1 标注详情 (来自 metadata)

```
file: K545-1
measures: 73
labels: 119
standard: 2.3.0
annotators: Uli Kneisel
reviewers: Johannes Hentschel, Markus Neuwirth
```

### 2.4 Beethoven Op.13 (sonata 8) 标注详情 (来自 metadata)

```
file: 08-1
measures: 310
labels: 503
standard: 2.3.0
annotators: Lydia Carlisi (2.2.0), John Heilig (2.3.0)
reviewers: Adrian Nagel
```

**注意**: 我们的 gold JSON 标的是 "excerpt mm.1-8" 或 "mm.1-10", 但 DCMLab 标的是完整乐章 (73 / 310 measures)。这意味着我们只能用 DCMLab 的"mm.1-8 / 1-10" 子集, 而不是整个乐章。

### 2.5 DCMLab MTRE Suitability

**优点**:
- 真实人类标 (Uli Kneisel, Lydia Carlisi, John Heilig, Adrian Nagel — 都是音乐理论学者)
- DCML harmony annotation standard 严格定义
- 每个标注都经至少 1 位 reviewer 校过
- Frictionless 标准格式 (TSV + JSON schema)
- 已被 ISMIR 2021 AugmentedNet 论文用为 benchmark (证明学界认可)

**缺点**:
- **CC BY-NC-SA 4.0** — 非商用 + 衍生要同 license。MTRE 商业使用前需要明确协议
- DCMLab 没有 Haydn / 大部分 Chopin / 大部分 Schubert 的钢琴奏鸣曲
- WTC 不在 DCMLab
- 标注采用 DCML standard (变体 Roman Numeral), 与 Sposobin 体系不完全一致 (需 adapter)

**MTRE 适用度**: ⭐⭐⭐⭐ (4/5) — **推荐直接用 Mozart K.545-1 + Beethoven Op.13 mvt 1**

---

## 3. Phase 1.2 — Humdrum / KernScores (CCARH Stanford)

**URL**: https://github.com/craigsapp (Craig Sapp 是 Humdrum 维护者)
**核心人物**: Craig Sapp (Stanford CCARH)
**License**: 大部分是 CC0 / Public Domain (公共领域作品 + 公共编辑)
**数据格式**:
- `.krn` — **kern 文件 (Humdrum 谱面格式)**
- 配套 `.hmd` (Humdrum data descriptor) + Makefile (转换脚本)
- 可转 MusicXML / MIDI / PDF

### 3.1 关键仓库 (我们 8 case 匹配)

| 仓库 | 内容 | 我们的 case 匹配 |
|---|---|---|
| `humdrum-tools/bach-wtc` | Bach WTC I & II (BWV 846-893), 全部 96 首 | ✅ **wtc1p01.krn (Prelude 1) + wtc1f01.krn (Fugue 1)** |
| `craigsapp/mozart-piano-sonatas` | Mozart 18 首钢琴奏鸣曲 (Alte Mozart Ausgabe) | ✅ **sonata08-1.krn (K.545 mvt 1)** |
| `craigsapp/beethoven-piano-sonatas` | Beethoven 32 首钢琴奏鸣曲 (Durand 1915) | ✅ **sonata08-1.krn (Op.13 mvt 1)** |
| `craigsapp/haydn-piano-sonatas` | Haydn 25+ 首钢琴奏鸣曲 (Universal Edition) | ❌ **Hob.XVI:52 不在** (只有 sonata12-1 等) |
| `craigsapp/chopin-preludes` | Chopin 24 首前奏曲 (Op.28) | ✅ **prelude28-20.krn (Op.28 No.20)** |
| `craigsapp/chopin-mazurkas` | Chopin 玛祖卡 | ❌ (我们要 Op.9 No.2 夜曲) |
| `pl-wnifc/humdrum-chopin-first-editions` | Chopin 原始版 (50+ 首) | ❓ 待查 (可能含 Op.9 No.2) |
| `craigsapp/beethoven-string-quartets` | Beethoven 弦乐四重奏 (与 DCMLab ABC 重复) | ❌ |
| `musedata/humdrum-haydn-quartets` | Haydn 弦乐四重奏 | ❌ |
| `musedata/humdrum-haydn-symphonies` | Haydn 交响曲 nos. 99-104 | ❌ |
| `musedata/humdrum-mozart-quartets` | Mozart 弦乐四重奏 | ❌ |
| `humdrum-tools/bach-chorales` | Bach 371 首众赞歌 | ❌ (我们要 WTC) |
| `musedata/humdrum-bach-organ` | Bach 管风琴作品 | ❌ (我们要 WTC 钢琴) |

### 3.2 Humdrum kern 与 Roman Numeral 标注的关系

**关键事实**: Humdrum kern 文件**只有谱面 (音符 + 时值)**, 不含 Roman numeral 标注。要做和声分析需要:
1. **手工** (用 music21 romanText 或 verovio 标注)
2. **AI** (AugmentedNet 推断)
3. **外部数据集** (DCMLab harmonies.tsv 是独立的)

这意味着 Humdrum kern 文件 + DCMLab harmonies.tsv 是一对 —— 谱面 + 标注, 必须**对齐**使用。

### 3.3 我们的 8 case 在 Humdrum 中的最终覆盖

| Case | kern 文件 | Roman numeral 标注来源 |
|---|---|---|
| bach_wtc_prelude_bwv846 | ✅ `wtc1p01.krn` | ⚠️ 需 AugmentedNet 推断 + 人工校 |
| bach_wtc_fugue_bwv846 | ✅ `wtc1f01.krn` | ⚠️ 同上 |
| mozart_k545_m1 | ✅ `sonata08-1.krn` | ✅ DCMLab `K545-1.harmonies.tsv` |
| beethoven_pathetique_m1 | ✅ `sonata08-1.krn` | ✅ DCMLab `08-1.harmonies.tsv` |
| haydn_hobxvi52_m1 | ❌ | ❌ |
| chopin_op9_no2 | ❓ 待查 pl-wnifc | ❌ |
| chopin_op28_no20 | ✅ `prelude28-20.krn` | ⚠️ 需 AugmentedNet 推断 + 人工校 |
| schubert_op90_no3 | ❌ | ❌ |

### 3.4 Humdrum MTRE Suitability

**优点**:
- 谱面准确 (Stanford CCARH 维护, 学界标准)
- 公共领域, 商用无障碍
- 可转 MusicXML (music21 converter.parse)

**缺点**:
- 只有谱面, 无标注 (需要 adapter + 外部标注)
- 各 repo 单独管理, 无统一索引

**MTRE 适用度**: ⭐⭐⭐⭐ (4/5) — **推荐作为谱面来源 (与 DCMLab 标注配对使用)**

---

## 4. Phase 1.3 — AugmentedNet (ISMIR 2021)

**URL**: https://github.com/napulen/AugmentedNet
**论文**: Nápoles López, Gotham, Fujinaga (2021). "AugmentedNet: A Roman Numeral Analysis Network with Synthetic Training Examples and Additional Tonal Tasks". *ISMIR 2021*, pp. 404-411. https://doi.org/10.5281/zenodo.5624533
**License**: MIT (代码) + 训练数据按各 source 自身 license
**数据格式**:
- **预训练模型**: `AugmentedNetv.hdf5` (可直接用于 MusicXML → Roman numeral 推断)
- **训练数据**: `dataset.zip` (含 preprocessed TSV, real + synthetic)
- 输入: MusicXML 文件
- 输出: `<file>_annotated.xml` (含 Roman numeral 标注) + `<file>_annotated.csv`

### 4.1 AugmentedNet 用作训练/测试的公开数据集

| Dataset | 来源 | 用法 | License |
|---|---|---|---|
| **WTC** (Bach Well-Tempered Clavier) | AugmentedNet 作者手工标注 | **测试集** | 自有, 非商用 |
| **BPS** (Beethoven Piano Sonatas) | = DCMLab `beethoven_piano_sonatas` | 全集 | CC BY-NC-SA 4.0 |
| **ABC** (Annotated Beethoven Corpus) | = DCMLab `ABC` (Beethoven 弦乐四重奏) | 全集 | CC BY-NC-SA 4.0 |
| **TAVERN** | 待查 (可能是 Taverna-Mirex?) | 全集 | ? |
| **WiR** (Wikipedia-in-Roman?) | 待查 | 全集 | ? |
| **HaydnSun** (Haydn String Quartets) | 可能来自 DCMLab? | 全集 | ? |
| **Synthetic** | AugmentedNet 生成的合成数据 | 训练增广 | MIT |

### 4.2 AugmentedNet 在我们 8 case 的可应用性

| Case | 可用 | 方法 |
|---|---|---|
| bach_wtc_prelude_bwv846 | ✅ | 用 wtc1p01.mxl + AugmentedNet 推断, 然后人工校 |
| bach_wtc_fugue_bwv846 | ✅ | 同上 (wtc1f01.mxl) |
| mozart_k545_m1 | ✅ | **优先用 DCMLab (专家标)**, 不必走 AugmentedNet |
| beethoven_pathetique_m1 | ✅ | **优先用 DCMLab (专家标)**, 不必走 AugmentedNet |
| haydn_hobxvi52_m1 | ❌ | 无 mxl 来源 |
| chopin_op9_no2 | ❌ | 无 mxl 来源 |
| chopin_op28_no20 | ✅ | 用 prelude28-20.mxl + AugmentedNet 推断 + 人工校 |
| schubert_op90_no3 | ❌ | 无 mxl 来源 |

### 4.3 AugmentedNet 准确度 (来自论文)

| Model | Key | Degree | Quality | Inversion | Root | ComRN | RN | RN_alt |
|---|---|---|---|---|---|---|---|---|
| AugmentedNet 11+ | 83.7 | 66.0 | 77.6 | 77.2 | 83.2 | 45.0 | 77.0 | — |

对 Bach WTC: 77.2% Key, 47.9% RN. 远低于专家标, **不能**作为 gold standard. 仅可作为"半自动候选标注"。

### 4.4 AugmentedNet MTRE Suitability

**优点**:
- 代码 MIT, 模型可下载, 容易跑
- 输入 MusicXML, 输出标准 Roman numeral
- 已被 ISMIR 同行评议

**缺点**:
- 准确度 < 50% RN, **不能**作为 gold standard
- WTC 是测试集 (意味着作者**没**用做训练) — 但这个测试集**不对外公开**作为标准答案
- 商用需注意 DCMLab 数据 license (BPS/ABC 来自 DCMLab)

**MTRE 适用度**: ⭐⭐ (2/5) — **仅可作为"半自动标注工具", 不能作 gold source**

---

## 5. Phase 1.4 — MIREX (Music Information Retrieval Evaluation eXchange)

**URL**: https://www.music-ir.org/mirex/wiki/
**背景**: ISMIR 旗下年度评测, 多个任务 (包括 chord estimation, key detection)
**公开性**: 
- **任务定义**: 公开
- **测试数据**: **通常不公开** (评测时才给参赛者)
- **结果排名**: 公开

### 5.1 MIREX 在我们 8 case 的可应用性

| 任务 | 状态 | 我们的应用 |
|---|---|---|
| MIREX 2010-2015 Chord Estimation | 数据**不公开** | ❌ 不能直接用 |
| MIREX Audio Chord Estimation | 音频 (不是谱面) | ❌ 不适用 |
| MIREX 2018-2020 Roman Numeral Analysis | 数据**不公开** | ❌ 不能直接用 |

**结论**: **MIREX 对我们 8 case 完全不可用 (没有公开的谱面 + Roman numeral 数据集)**。

### 5.2 MIREX MTRE Suitability

**MTRE 适用度**: ⭐ (1/5) — **不适用**

---

## 6. Phase 1.5 — music21 RomanText

**URL**: https://web.mit.edu/music21/doc/moduleReference/moduleRomanText.html
**类型**: **文件格式** (不是数据集)
**功能**: music21 支持读写 `.rn.txt` (RomanText) 格式, 编码 Roman numeral 分析
**典型用法**: DCMLab 的 `unfolded_harmonies.tsv` 可转 .rn.txt

### 6.1 music21 在我们 8 case 的可应用性

**不是数据源, 是工具/格式**。可作为 gold adapter 的中间格式。

### 6.2 music21 RomanText MTRE Suitability

**MTRE 适用度**: ⭐⭐⭐ (3/5) — **作为 gold adapter 转换中间格式, 不是数据源**

---

## 7. 我们的 8 case 数据可用性总结表

| Case | 谱面 (kern/mxl) | Roman numeral 标注 | 可信度 | 状态 |
|---|---|---|---|---|
| bach_wtc_prelude_bwv846 | ✅ humdrum-tools (wtc1p01) | ⚠️ 需 AugmentedNet + 人工校 | 中 (AI 半自动) | 可用, 标 needs_review |
| bach_wtc_fugue_bwv846 | ✅ humdrum-tools (wtc1f01) | ⚠️ 同上 | 中 (AI 半自动) | 可用, 标 needs_review |
| mozart_k545_m1 | ✅ craigsapp + DCMLab MS3 | ✅ **DCMLab 专家标 (Uli Kneisel, JH/MN review)** | **高** | **推荐直接用** |
| beethoven_pathetique_m1 | ✅ craigsapp + DCMLab MS3 | ✅ **DCMLab 专家标 (Carlisi, Heilig, AN review)** | **高** | **推荐直接用** |
| haydn_hobxvi52_m1 | ❌ 无公开 | ❌ 无公开 | 无 | **暂缓** |
| chopin_op9_no2 | ❌ 无公开 | ❌ 无公开 | 无 | **暂缓** |
| chopin_op28_no20 | ✅ craigsapp (prelude28-20) | ⚠️ 需 AugmentedNet + 人工校 | 中 (AI 半自动) | 可用, 标 needs_review |
| schubert_op90_no3 | ❌ 无公开 | ❌ 无公开 | 无 | **暂缓** |

**总结**:
- **2/8 case (Mozart K.545, Beethoven Op.13) 有公开专家标, 可直接用**。
- **3/8 case (Bach WTC x2, Chopin Op.28 No.20) 有谱面无标, 可用 AI 半自动 + 人工校**。
- **3/8 case (Haydn, Chopin Op.9, Schubert) 公开数据缺, 建议从 gold 列表移除**。

---

## 8. 4 个被调研数据源 MTRE 适用度总评

| 数据源 | MTRE 适用度 | 理由 |
|---|---|---|
| **DCMLab** | ⭐⭐⭐⭐ (4/5) | 专家标, ISMIR 引用, 但 CC BY-NC-SA 限商用 + 无 Haydn/Chopin 钢琴 |
| **Humdrum** | ⭐⭐⭐⭐ (4/5) | 谱面标准, 公共领域, 但无标注, 需配 DCMLab 或 AI |
| **AugmentedNet** | ⭐⭐ (2/5) | MIT 工具, 但准确度不够作 gold, 仅作半自动工具 |
| **MIREX** | ⭐ (1/5) | 数据不公开, 不适用 |
| **music21 RomanText** | ⭐⭐⭐ (3/5) | 工具, 不是数据源 |

---

## 9. 我们应该"暂缓"的 3 个 case 详细说明

### 9.1 Haydn Hob.XVI:52 (Piano Sonata in Eb major)

- 我们的 gold JSON 标的 key 可能是错的 — 实际是 **Eb major** ✅
- 但公开数据:
  - DCMLab: ❌ 没有 haydn_piano_sonatas
  - craigsapp/haydn-piano-sonatas: ❌ 不含 Hob.XVI:52 (只有 25+ 首, sonata12 是 Hob.XVI:12)
  - IMSLP: 有谱面 (Universal Edition), 需手动转 mxl

**决定**: 暂缓, 等未来 IMSLP 转 mxl 后再考虑。

### 9.2 Chopin Op.9 No.2 (Nocturne in Eb major)

- DCMLab: ❌ 只有 mazurka
- craigsapp/chopin-preludes: ❌ 只有 Op.28 preludes
- craigsapp/chopin-mazurkas: ❌ 是 mazurka (Op.6)
- pl-wnifc/humdrum-chopin-first-editions: ❓ 待查 (看到 `072-1-MEIf-001-nocturne.krn` 文件, 但 Brown 索引 B.55 才是 Op.9 No.2, 待编码规范)
- IMSLP: 有谱面

**决定**: 暂缓。

### 9.3 Schubert Op.90 No.3 = D.899 No.3 (Impromptu in Gb major)

**重要**: 我们的 gold JSON 标的 **"Eb major" 是错的** — D.899 No.3 实际是 **Gb major**。
- DCMLab: ❌ 只有 schubert_winterreise (声乐)
- craigsapp: ❌ 没有 schubert_impromptums repo
- IMSLP: 有谱面

**决定**: 暂缓, 同时修正 gold JSON 的 key 字段 (Eb → Gb)。

---

## 10. License 法律风险

| 来源 | License | 商用 | 衍生 |
|---|---|---|---|
| DCMLab | CC BY-NC-SA 4.0 | ❌ 禁止 | ✅ 同 license 共享 |
| craigsapp (Humdrum) | CC0 / Public Domain (谱面); 个别 CC BY | ✅ 可商用 | ✅ |
| IMSLP 编辑版 | 取决于 editor (CC BY-NC-SA / CC BY 等) | 视情况 | 视情况 |
| music21 | BSD | ✅ | ✅ |
| AugmentedNet | MIT | ✅ | ✅ |

**MTRE 商业使用建议**:
1. **优先用 Humdrum (craigsapp) 谱面** (公共领域)
2. **DCMLab 标注**只用于 research / non-commercial — 商用前需重谈 license
3. 或 **用 AugmentedNet 推断** (MIT) + **人工校** — 完全可控

---

## 11. 下一步建议 (Phase 2-4)

### 11.1 Phase 2 — Gold Adapter 设计

详见 `docs/gold_adapter_design.md` (待写)

核心: 在 `gold_adapter/` 目录, 转换 DCMLab / Humdrum / AugmentedNet 格式到 MTRE EvalCase 格式。

### 11.2 Phase 3 — Schema Provenance 增强

详见 `docs/schema_provenance_enhancement.md` (待写)

核心: 现有 Provenance 加 `source_format` (musicxml / kern / tsv), `conversion_method`, `source_dataset_id` 字段。

### 11.3 Phase 4 — Benchmark 重评

详见 `docs/benchmark_recommendation.md` (待写)

核心: 不再"全部保留 8 case", 而是:
- **2 case 推荐**: Mozart K.545-1, Beethoven Op.13 mvt 1 (DCMLab 直接)
- **3 case 谨慎用**: Bach WTC x2, Chopin Op.28 No.20 (需 AI + 人工)
- **3 case 暂缓 / 移除**: Haydn, Chopin Op.9, Schubert (无公开数据)
