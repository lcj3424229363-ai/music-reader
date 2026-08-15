# P20.3.8 — Benchmark Recommendation (重写版)

**日期**: 2026-08-11
**作者**: Mavis (按用户架构审查反馈, 推翻 P20.3.7 版本)
**状态**: 设计 (待用户审批)
**重要**: **P20.3.7 的"5/8 跑 benchmark"推荐是错的**, 详见 §0

---

## 0. P20.3.7 推荐错误 — 自我审计

### 0.1 我犯的错

在 P20.3.7 的 `benchmark_recommendation.md` 中, 我推荐:

> 🟢 黄金 (2): Mozart K545, Beethoven Op.13
> 🟡 银 (3): Bach WTC x2, Chopin Op.28
> 🔴 不可用 (3): Haydn, Chopin Op.9, Schubert
> **建议**: 5/8 case 跑 benchmark

**用户审查反馈**:
> "不要接受当前 V1 = 5/8 直接进入 benchmark. 原因不是数据不够, 而是 **gold 等级混杂会污染评价体系**."

**我的根本错误**:
- 把不同可信度的"gold" 混到同一个 benchmark
- benchmark 跑分无法区分 "Agent 错" vs "gold 错" vs "来源模型 (AugmentedNet) 错"
- AugmentedNet 推断当 silver, 实际是"模型预测", 不是 gold — "两个 AI 互相考试" 无意义

### 0.2 正确方向 (P20.3.8)

> **MTRE V1 Core Benchmark = Tier A (Gold, 专家标注) only**

| 维度 | P20.3.7 错 | P20.3.8 对 |
|---|---|---|
| V1 准入 | 5 case (2 gold + 3 silver) | 25 case 纯 Tier A |
| 等级定义 | "黄金/银/不可用" 三档但混合 | gold/silver/raw 三层**严格隔离** |
| "NOT FOUND" 处理 | 标"不可用" | 标"deferred" (无公开数据 ≠ 缺分析) |
| 旧 gold 错误 | 修字段 (Eb→Gb) | Log 到 `old_gold_error_log.json` |
| License 处理 | 隐式默认 DCML 可用 | 显式 manifest + Runtime load |
| Benchmark 选取 | "原 8 case 全部" | **能力驱动**, 按 capability balance 选 |
| 字段来源 | 手写 + AugmentedNet | 全部 DCML / Humdrum / 公开源 |

### 0.3 我对 AugmentedNet 误用的承认

P20.3.7 推荐: "用 Humdrum + AugmentedNet 推断 + 人工校" 当 silver.

**实际**: AugmentedNet 是 **预训练模型** (NN, ISMIR 2021), 输出是 **模型预测**, 不是 "gold" 也不是 "silver".

正确的是:
- AugmentedNet 输出标 `source_type: "model_prediction"`, `tier: "raw_with_inference"`, **不** 进 V1 benchmark
- 可用于 MTRE Agent **训练** (监督学习风格), 但不能作为评测 gold
- 用于 debug / 内部验证, 跑分不计入 MTRE V1 正式报告

---

## 1. 重排后的 3-Tier 架构 (来自 `benchmark_manifest_design.md`)

### 1.1 Tier 定义

| Tier | 来源 | 可信度 | 用途 |
|---|---|---|---|
| **A — Gold (Expert Verified)** | DCML 完整标注 / 专家论文 / 经典教材 (Riemenschneider) | 0.9-1.0 | **MTRE V1 Core Benchmark only** |
| **B — Silver (Machine Generated)** | AugmentedNet / Chordino 输出 | 0.4-0.6 | MTRE Agent 训练 / debug / 内部验证 |
| **C — Raw (Score Only)** | Humdrum kern / IMSLP / music21 corpus | N/A | 未来 annotation 入库 |

### 1.2 Tier 间禁止混用 (硬约束)

**Benchmark runner 强制只对 Tier A 跑最终 accuracy 报告.**

实现层面 (P20.3.9 之后):
```python
def run_benchmark(self):
    cases = self.manifest_loader.list_bench_eligible()  # tier == "A" only
    for case in cases:
        result = self.agent.solve(case)
        self.compare(result, case.gold)
    # 不输出 silver / raw
```

### 1.3 Manifest Schema (核心)

完整 schema 见 `benchmark_manifest_design.md §3`. 摘要:

```json
{
  "manifest_version": "0.1.0",
  "mtre_benchmark_name": "MTRE V1 Core Benchmark",
  "cases": [
    {
      "id": "mozart_k545_m1",
      "tier": "A",
      "title": "Mozart Piano Sonata K.545 1st Movement (1st theme)",
      "composer": "W.A. Mozart",
      "period": "Classical",
      "capability_focus": ["I-V-I basic", "PAC/HC cadence", "phrase structure"],
      "source": {
        "dataset": "DCMLab/mozart_piano_sonatas",
        "dataset_url": "https://github.com/DCMLab/mozart_piano_sonatas",
        "specific_file": "harmonies/K545-1.harmonies.tsv"
      },
      "annotators": ["human/Uli Kneisel"],
      "reviewers": ["human/Johannes Hentschel", "human/Markus Neuwirth"],
      "license": {
        "id": "CC-BY-NC-SA-4.0",
        "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        "commercial_use": false,
        "attribution_required": true,
        "share_alike": true
      },
      "acquisition_status": "ready"
    }
  ]
}
```

---

## 2. Tier A 候选 (重写, 从 2 扩到 20-25)

### 2.1 DCML 实际覆盖 (P20.3.8 调研, 详见 `gold_dataset_research.md`)

| DCML repo | 标注 movement 数 | 时期 | capability 重点 |
|---|---|---|---|
| `mozart_piano_sonatas` | ~54 (18 sonatas) | Classical | I-V-I, K6/4, phrase, secondary dominants |
| `beethoven_piano_sonatas` | ~96 (32 sonatas) | Classical→Romantic | Altered, mixture, complex cadences |
| `ABC` (Beethoven Str Qrt) | ~70 (16 quartets) | Classical→Romantic | Sonata form 复杂化, 4 voice texture |
| `chopin_mazurkas` | ~56 (50+ mazurkas) | Romantic | bVI, bIII, mode mixture |
| `schumann_kinderszenen` | 13 (整套) | Romantic | 短小, 借用和弦 |
| `liszt_pelerinage` | 19 (3 年) | Romantic | 转调, 借用, 半音 |
| `grieg_lyric_pieces` | 67 (10 opuses) | Romantic→Late Romantic | 抒情小品 |
| `tchaikovsky_seasons` | 13 (12 月) | Romantic | 情景, 变调 |
| `debussy_suite_bergamasque` | 4 (整套) | Impressionist | Modal, 全音阶 |
| `ravel_piano` | 5 (Jeux d'eau) | Impressionist | Modal + 全音阶 |
| `mendelssohn_quartets` | ~24 (6 quartets) | Romantic | 形式 + Romantic 和声 |
| `wagner_overtures` | 2 | Late Romantic | Augmented 6th, 半音 |
| `mahler_kindertotenlieder` | 5 (整套) | Late Romantic | 复杂和声 |
| `handel_keyboard` | 6 (suites) | Baroque | 数字低音 + Functional |
| `corelli` | 149 (6 opuses) | Baroque | 数字低音 |
| `monteverdi_madrigals` | 19 | Early Baroque | 早期功能 |
| `c_schumann_lieder` | 12 | Romantic | 艺术歌曲 |
| `sweelinck_keyboard` | 1 | Renaissance | 调式 |
| **TOTAL** | **~615 movements** | — | — |

### 2.2 Capability Coverage Matrix

| Capability | 适合作品 (DCML) | 候选数 |
|---|---|---|
| I-V-I 基础 | Mozart K.545, K.279, K.284 | 5+ |
| K6/4 (cadential 6/4) | Mozart K.283, K.332, Beethoven Op.2-1-1 | 5+ |
| 转调 (modulatory sequences) | Mozart K.310, K.457, Beethoven Op.2-3-1 | 5+ |
| Secondary dominants (V/V, V7/V) | Beethoven Op.13, Op.14, late Classical | 5+ |
| Altered dominants / mixture | Beethoven Op.27-2 (Moonlight), Op.106 (Hammerklavier) | 3+ |
| bVI / bIII (mode mixture) | Schumann Kinderszenen, Liszt, Chopin Mazurkas | 10+ |
| Augmented 6th | Wagner Overtures, Liszt | 3+ |
| Modal (Impressionist) | Debussy, Ravel | 5+ |
| Baroque counterpoint | Handel, Corelli | 10+ |
| Phrase structure / form | Sonata exposition movements | 10+ |
| Complex cadences (Phrygian half, Plagal) | Late Beethoven, late Romantic | 3+ |
| Augmented 6th (Fr+6, It+6, Gr+6) | Wagner, Liszt | 3+ |
| Pedal point / ostinato | Chopin Mazurkas, Schumann | 3+ |
| Chromatic harmony | Mahler, Wagner | 3+ |

### 2.3 MTRE V1 Core 25 case 初稿 (待用户审批)

**Classical 入门 (5)**:
1. mozart_k545_m1 (I-V-I, PAC, simple)
2. mozart_k283_1 (K6/4 测试)
3. mozart_k310_1 (modulation, minor key)
4. beethoven_op2_1_1 (Classical period, sonata form)
5. beethoven_op13_1 (Pathétique, 慢引子 + Allegro)

**Classical 中级 (5)**:
6. mozart_k457_1 (c minor, dramatic)
7. beethoven_op10_1_1 (c minor, 小悲怆)
8. beethoven_op14_1_1 (E major, simple)
9. beethoven_op78_1 (F# major, 感恩)
10. ABC Op.18 No.1 mvt 1 (string quartet 起点)

**Classical 高级 (3)**:
11. beethoven_op27_2_1 (Moonlight, c# minor, altered)
12. beethoven_op106_1 (Hammerklavier, Bb major, 复杂)
13. ABC Op.59 No.1 mvt 1 (Rasumovsky, 复杂转调)

**Romantic 早期 (4)**:
14. schumann_kinderszenen_1 (Träumerei, D major)
15. schumann_kinderszenen_7 (Traum eines Kindes, bVI)
16. liszt_pelerinage_s1_1 (Sposalizio, 借用)
17. chopin_mazurka_op17_4 (a minor, mode mixture)

**Romantic 中级 (3)**:
18. grieg_lyric_pieces_op12_1 (Arietta, 简单)
19. tchaikovsky_seasons_october (Autumn Song, 转调)
20. mendelssohn_quartet_op44_1_1 (Eb major, sonata)

**Late Romantic (2)**:
21. wagner_lohengrin_prelude (A major, 半音)
22. mahler_kindertotenlieder_1 (Nun will die Sonn, d minor)

**Impressionist (3)**:
23. debussy_suite_bergamasque_3 (Clair de Lune, modal)
24. debussy_suite_bergamasque_1 (Prélude, modal)
25. ravel_jeux_deau (Bb major, 全音阶)

**总计**: **25 case, 4 时期, 13+ capability**

**注意**:
- 这只是初稿, 用户 / 专家可调
- V1 后扩 V2 加 Jazz / Modal (later_profiles/) 和更难的 case
- 真实 case ID 待 P20.3.8 manifest 阶段确认

### 2.4 旧 8 case 的最终命运

P20.3.8 完成后:

| 旧 case | 处置 |
|---|---|
| mozart_k545_m1 (P20.3 占位) | archive → `_archive/P20.3/` + 新版 (DCMLab) 写到 `benchmark/gold/expert_verified/` |
| beethoven_pathetique_m1 (P20.3 占位) | 同上 |
| bach_wtc_prelude_bwv846 | archive + **不进 V1** (Bach 没 DCML RN, 暂缓) |
| bach_wtc_fugue_bwv846 | archive + 用户原话"暂缓" |
| haydn_hobxvi52_m1 | archive + **标 deferred** (无公开数据) |
| chopin_op9_no2 | archive + **标 deferred** (无 Nocturne 标注) |
| chopin_op28_no20 | archive + P20.3.8 重写到 `silver/machine_generated/` (Humdrum+AugmentedNet) |
| schubert_op90_no3 | archive + **标 deferred** (无公开数据 + key 错) |

---

## 3. Tier B (Silver) 候选 — 不进 V1 benchmark

**关键**: AugmentedNet 输出是 **模型预测**, 不是 gold. 用途限于:
- MTRE Agent 训练 (监督学习, label noise 接受)
- Debug (快速看 Agent 输出是否合理)
- Tier A gold 之外的 "灰色数据"

候选:
- Bach WTC I (Humdrum kern + AugmentedNet)
- Chopin Op.28 preludes (Humdrum kern + AugmentedNet)
- **不** 包含在 `manifest.json` 的 `cases` 列表 (manifest 只 Tier A)
- 单独存 `benchmark/silver/machine_generated/<id>.json`, 不进 runner

---

## 4. Tier C (Raw) 候选 — 缺公开数据

| Case | 状态 | 缺什么 |
|---|---|---|
| haydn_hobxvi52_m1 | **deferred** | 谱面 (IMSLP 有 PDF, 需 OCR 转 mxl) + 标注 (无公开 RN) |
| chopin_op9_no2 | **deferred** | 谱面 (IMSLP 有, 需转 mxl) + 标注 (无 Nocturne 公开) |
| schubert_op90_no3 | **deferred** | 谱面 (IMSLP 有) + 标注 (无 Impromptu 公开) + 修 key 错 (Eb→Gb) |
| Haydn 其他 sonatas | **deferred** | 同上 |
| Schubert 其他 | **deferred** | 同上 |
| Chopin Op.9, 27, 32, 37, 48, 53, 61, 62, 64, 66, 68, 70, 72 | **deferred** | 谱面 + 标注 |
| Mendelssohn Lieder ohne Worte | **deferred** | 谱面 (有) + 标注 (无公开) |
| Late Beethoven quartets (Op.127, 130, 131, 132, 135) | **partial** | ABC 有 (10 movements) |

**重要**: "deferred" ≠ "永远不用". 等 IMSLP mxl + 人工标注 补上后可升级到 Tier A.

---

## 5. License 风险 (强化版)

### 5.1 DCML 全 CC BY-NC-SA 4.0

- 研究 / non-commercial ✅
- 商业 ❌
- 衍生同 license

### 5.2 隔离架构 (Runtime Adapter)

**关键**:
- MTRE 本身永远 MIT
- DCML 数据**不复制**进 MTRE repo
- 运行时 git clone 到 `~/.cache/mtre/external/`
- 用户必须同意 license disclosure 才能下载
- 商业版本用户自己换 source (如用 Humdrum kern + 人工标注)

### 5.3 manifest.json license 字段

每个 case 必须有:
```json
"license": {
  "id": "CC-BY-NC-SA-4.0",
  "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
  "commercial_use": false,
  "attribution_required": true,
  "share_alike": true
}
```

### 5.4 用户首次跑 benchmark 的 license 同意流程

```
User runs: python -m mtre.benchmark
  ↓
ManifestLoader loads manifest.json
  ↓
For each Tier A case, check if external data cached
  ↓
If not cached:
  Show license disclosure
  User must agree
  Then git clone / curl
  Cache to ~/.cache/mtre/external/<dataset>
  ↓
Adapter converts to EvalCase
  ↓
Run benchmark
```

**核心**: license 同意**显式**, 不隐藏在 README.

---

## 6. 不修改旧 gold JSON 的策略

### 6.1 策略

**P20.3.7 之后**:
- 旧 8 个 V1 gold JSON (`data/eval/gold/*.json`) **完全不动**
- 旧 4 个 later_profiles (`data/eval/later_profiles/*.json`) **完全不动**
- 发现的错误写到 `data/eval/benchmark/old_gold_error_log.json`
- P20.3.8 完成后, 把旧 12 个 JSON archive 到 `data/eval/benchmark/_archive/P20.3/`

### 6.2 旧 gold error log 内容 (P20.3.8 已建)

`data/eval/benchmark/old_gold_error_log.json` 含 7 个 entry:
- ERR-2026-08-11-001: Schubert key 错 (Eb→Gb)
- ERR-2026-08-11-002: Haydn 无公开数据
- ERR-2026-08-11-003: Chopin Op.9 无公开数据
- ERR-2026-08-11-004: ALL `analysis_framework` 应是 "functional" 不是 "sposobin"
- ERR-2026-08-11-005: Beethoven Op.13 excerpt+harmonic 缺慢引子
- ERR-2026-08-11-006: Chopin Op.9 VI 标签矛盾
- ERR-2026-08-11-007: Schubert excerpt 范围冲突

### 6.3 保留旧 gold 的好处

- 保留 "原始假设 → 修正过程" 链路
- 训练 MTRE Agent 时, 可对比 "P20.3 占位" vs "P20.3.8 DCML 数据", 测 Agent 鲁棒性
- 历史追溯: 未来可看 "P20.3 阶段我们以为 X, P20.3.8 修正为 Y"

### 6.4 用户审计后的明确决定

> "不要因为发现一个错误, 就让 Agent 修改旧 gold. 正确流程: 记录 old_gold_error_log.json. 保留原始假设 → 修正过程. 这对以后训练和 debug 很有价值."

✅ **接受**. P20.3.7 文档中提的"修 Schubert key (Eb→Gb)" — **撤回**. 改为 log.

---

## 7. 实施步骤 (P20.3.8 全流程)

按用户指示, **不写代码** (除了 manifest + log + 文档). 实施步骤:

1. **Phase 0**: 用户审批 P20.3.8 架构设计 (本文 + benchmark_manifest_design.md)
2. **Phase 1**: 写 `data/eval/benchmark/manifest.json` (25 case Tier A, 3 case Tier B, 3 case Tier C)
3. **Phase 2**: 写 `data/eval/benchmark/old_gold_error_log.json` — **已完成**
4. **Phase 3**: 写 `data/eval/schema.py` 改动 (tier + capability_focus 字段)
5. **Phase 4**: 测试 manifest 解析 + tier 过滤
6. **Phase 5**: Archive 脚本 (旧 12 JSON → `_archive/P20.3/`)

**P20.3.8 范围外**:
- ❌ Adapter 代码 (P20.3.9+)
- ❌ Benchmark Runner (P20.4)
- ❌ 实际下载 DCML 数据 (用户手动)
- ❌ 修改旧 gold JSON
- ❌ 评估 Agent (等 runner)

---

## 8. 时间表

| Phase | 任务 | 工时 |
|---|---|---|
| P20.3.7 (已完成) | 数据源调研 + Adapter 设计 | 报告 |
| P20.3.7 (已完成) | Schema 增强 + Benchmark 旧推荐 | 报告 |
| **P20.3.8 (当前)** | 3-tier manifest 设计 | **报告 (已交付)** |
| **P20.3.8** | manifest.json (25 case) | 4h |
| **P20.3.8** | old_gold_error_log.json | **已完成** |
| **P20.3.8** | schema.py 改动 (tier + capability_focus) | 2h |
| **P20.3.8** | manifest 解析测试 | 2h |
| **P20.3.8** | archive 脚本 | 1h |
| P20.3.9 | Adapter (DCMLab + Humdrum + AugmentedNet) | 24h |
| P20.3.10 | 25 case 端到端生成 | 8h |
| P20.4 | Benchmark Runner | 12h |
| **总计** | | **~53h (~7 工作日)** |

---

## 9. 关键风险

| 风险 | 缓解 |
|---|---|
| Manifest 25 case 选错 (capability 不平衡) | 用户 / 专家审批 Phase 1 |
| DCML 数据更新 (commit_sha 漂移) | 锁 commit_sha, manifest 显式记录 |
| AugmentedNet 误用 (P20.3.7 推荐错) | P20.3.8 严格隔离 Tier, 不进 manifest.cases |
| License 风险 (DCML CC BY-NC-SA) | Runtime adapter 隔离, 不复制 |
| 旧 gold 用户误用 (以为还 active) | README 明确标 DEPRECATED, archive 到 _archive/ |
| 误改旧 gold (像 P20.3.7 那样) | old_gold_error_log.json 记录, P20.3.8 后只 log 不改 |

---

## 10. 总结

### P20.3.7 → P20.3.8 关键升级

| 维度 | P20.3.7 (撤回) | P20.3.8 (当前) |
|---|---|---|
| 数据等级 | 5 case 混 2 gold + 3 silver | 25 case 纯 Tier A |
| "NOT FOUND" 处理 | 标"不可用" | 标"deferred" |
| 旧 gold 错误 | 修字段 | Log + archive |
| AugmentedNet | 标 silver | 标 machine_prediction, 不进 V1 |
| License | 隐式 | 显式 manifest + runtime load |
| 选取标准 | 8 case 默认 | 能力驱动 + 25 case 平衡 |
| 目录结构 | `data/eval/gold/` | `data/eval/benchmark/{gold,silver,raw}/` |

### 下一步

等用户审批 P20.3.8 manifest 设计. 批准后:
1. 写 `data/eval/benchmark/manifest.json`
2. Schema 改动 (tier + capability_focus)
3. Archive 旧 12 JSON

**绝不**:
- 写 Adapter 代码
- 写 Benchmark Runner
- 评估 Agent
- 修改旧 gold JSON
