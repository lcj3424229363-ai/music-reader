# P20.3.8 — Benchmark Manifest Design (3-Tier Architecture)

**日期**: 2026-08-11
**作者**: Mavis (按用户架构审查反馈重设)
**状态**: 设计 (未实施)
**前置**: 推翻 P20.3.7 的"5/8 case 跑 benchmark"推荐
**目的**: 把 benchmark 数据治理从"改 JSON 字段"提升到"架构 + manifest"

---

## 0. 关键架构决策 (来自用户审查)

### 0.1 P20.3.7 推荐错误

❌ **错的**: "V1 = 5/8 case (2 gold + 3 silver) 可直接进 benchmark"

❌ **错的根本原因**: 等级混杂污染评价体系

```
Agent 输出 → 和 gold 比较 → 准确率
                ↑
        错在哪里？
        ├─ Agent 错
        ├─ Gold 错
        └─ Gold 来源模型错
```

**5/8 案例中混入 3 个 silver (AugmentedNet 推断) 意味着 benchmark 跑分反映的不是"Agent 能力"而是"AugmentedNet vs AugmentedNet 衍生数据"**。这是"两个 AI 互相考试"。

### 0.2 正确方向

✅ **MTRE V1 Core Benchmark = Tier A 专家标注 only**
- 现状: 只有 2 个 (Mozart K545-1, Beethoven Op.13-1) — 太少
- 解决: **拓宽 DCML 覆盖** (而不是急着放 silver)
- 目标: 20-30 个 Tier A case

✅ **3-tier 目录结构**:
```
benchmark/
├── gold/expert_verified/   # DCML, 专家论文, 教材
├── silver/machine_generated/  # AugmentedNet 等
└── raw/score_only/         # 只有谱面, 待未来标注
```

✅ **不复制第三方数据** (license 隔离):
```
MTRE (只持 URL + manifest)
 ↓ 运行时下载
Adapter
 ↓
External (DCML/Humdrum/...)
```

✅ **不修改旧 gold 字段**:
```
发现错误 → 写入 old_gold_error_log.json → 不动 gold JSON
保留 "原始假设 → 修正过程" 链路
```

### 0.3 关于 3 个原 "NOT FOUND" case

❌ 标 "NOT FOUND / 不可用" — 错的
✅ 标 "deferred" — 缺公开数据 ≠ 缺分析 (教材 / 论文 / MuseScore 都有)

---

## 1. 3-Tier 数据模型

### 1.1 Tier 定义

| Tier | 定义 | 来源 | 可信度 | 用途 |
|---|---|---|---|---|
| **A — Gold (Expert Verified)** | 人类专家标注, 经同行评议或 DCML 审校 | DCML 完整标注 / 专家论文 / 经典教材 (Riemenschneider) | 0.9-1.0 | **正式 benchmark** |
| **B — Silver (Machine Generated)** | AI 推断 (AugmentedNet) 或自动 chord recognition (Chordino) | AugmentedNet / Chordino 输出 | 0.4-0.6 | 训练 / debug / 快速验证 |
| **C — Raw (Score Only)** | 只有谱面, 无标注 | Humdrum / IMSLP / music21 corpus | N/A (待标注) | 未来人工 / AI 标注 |

### 1.2 Tier 间禁止混用

**关键约束**: benchmark runner **必须** 只对 Tier A 跑最终 accuracy 报告。

Tier B (silver) 可用于:
- 训练 MTRE Agent (但 **不能** 测最终 benchmark)
- 调试 (快速看 Agent 输出是否合理)
- 评估 Agent 的"泛化能力" 报告 (但要明确标 silver)

Tier C (raw) 只用于:
- 评估"谱面解析 + 推断" 能力
- 未来 annotation 入库

### 1.3 Tier A 状态机

```
score only [raw]
    ↓ 人工 / 专家标注
human_annotated [gold]   ← 至少 1 个标记者
    ↓ 同行评议 / expert review
expert_verified [gold]   ← 至少 1 个 reviewer
    ↓
bench_eligible   ← MTRE V1 准入
```

**每一步 transition 必须有 provenance 记录**。

---

## 2. License 隔离架构

### 2.1 当前风险

**DCMLab 全部 CC BY-NC-SA 4.0**:
- ✅ 研究 / non-commercial 允许
- ❌ 商业禁止
- ⚠️ 衍生作品必须同 license 共享

**如果把 DCML 数据直接复制进 MTRE repo**:
- MTRE 整个 repo 都被传染为 CC BY-NC-SA
- 商业版本无法发布
- 用户不能选择性剔除 DCML

### 2.2 正确架构: Runtime Adapter

```
MTRE repo
├── data/eval/benchmark/manifest.json    # 只持 URL + license
├── data/eval/gold/*.json                # MTRE 自己生成的 (Sposobin 归一化)
├── data/eval/silver/*.json              # 同上
├── gold_adapter/                         # 运行时下载 + 转换
│   ├── dcmlab_adapter.py
│   ├── humdrum_adapter.py
│   └── ...
└── (无 data/eval/external/)             # ← 不进 repo!
```

**关键设计**:
- `manifest.json` 只指向 DCML 公开 GitHub URL
- Adapter 运行时 git clone / curl 下载到 `~/.cache/mtre/external/`
- 转换 → EvalCase → 存 `data/eval/gold/*.json`
- 用户可配置 `MTRE_EXTERNAL_DIR` 指向其他位置

### 2.3 License Manifest 字段

```python
class LicenseInfo:
    license_id: str          # "CC-BY-NC-SA-4.0" / "CC0" / "Public Domain" / "MIT"
    license_url: str         # 例 "https://creativecommons.org/licenses/by-nc-sa/4.0/"
    commercial_use: bool     # True / False
    attribution_required: bool
    share_alike: bool        # True / False
    notes: str               # 例 "DCMLab: research use only; commercial requires re-licensing"
```

### 2.4 MTRE License 决策

| MTRE 版本 | 是否能包含 DCML 数据 |
|---|---|
| MTRE-Research (MIT) | ❌ 不包含, 运行时下载 |
| MTRE-Commercial (商业) | ❌ 仍不包含, 商业版用其他 source |
| MTRE-Internal (公司内部, 付费给 DCML) | ⚠️ 单独 license, 复制允许 |

**核心**: MTRE 本身永远 MIT, 第三方数据是 "plugin", 不传染。

---

## 3. Manifest Schema (核心)

### 3.1 `data/eval/benchmark/manifest.json` 结构

```json
{
  "manifest_version": "0.1.0",
  "schema_url": "https://github.com/.../benchmark/manifest.schema.json",
  "mtre_benchmark_name": "MTRE V1 Core Benchmark",
  "created": "2026-08-11",
  "tier_definitions": {
    "A": "Expert verified, peer-reviewed or DCML-style. Required for final benchmark.",
    "B": "Machine generated (AugmentedNet, Chordino). For training/debug only.",
    "C": "Score only. No annotation. For future annotation."
  },
  "license_policy": {
    "MTRE_license": "MIT",
    "external_data_license": "Runtime fetch only. No copying into MTRE repo.",
    "commercial_use": "Depends on external data license. See per-case license field."
  },
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
        "specific_file": "harmonies/K545-1.harmonies.tsv",
        "score_file": "MS3/K545-1.mscx"
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
      "provenance": {
        "url": "https://github.com/DCMLab/mozart_piano_sonatas",
        "commit_sha": "v2.3 (2025-04-28)",
        "download_method": "git clone"
      },
      "available": {
        "musicxml_mscx": true,
        "harmonies_tsv": true,
        "measures_tsv": true,
        "kern_humdrum": true,
        "audio": false
      },
      "acquisition_status": "ready",
      "notes": "Full movement annotation (73 measures, 119 labels). Subset mm.1-8 used as excerpt."
    },
    {
      "id": "beethoven_op13_m1",
      "tier": "A",
      ...
    }
  ]
}
```

### 3.2 字段定义

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `id` | string | ✓ | 唯一 ID (例 "mozart_k545_m1") |
| `tier` | "A" / "B" / "C" | ✓ | 等级 |
| `title` | string | ✓ | 作品标题 |
| `composer` | string | ✓ | 作曲家 |
| `period` | string | ✓ | 时期 (Baroque/Classical/Romantic/Impressionist/...) |
| `capability_focus` | list[string] | ✓ | 此 case 测试的能力 (例 ["K6/4", "modulation"] ) |
| `source.dataset` | string | ✓ | GitHub repo 或 dataset 名 |
| `source.dataset_url` | string | ✓ | URL |
| `source.specific_file` | string | optional | 标注文件路径 |
| `source.score_file` | string | optional | 谱面文件路径 |
| `annotators` | list[string] | ✓ | 标记者 (`human/...` 或 `ai/...` 或 `music21-auto`) |
| `reviewers` | list[string] | optional | 审核者 |
| `license.*` | LicenseInfo | ✓ | 法律信息 |
| `provenance.url` | string | ✓ | 数据源 URL |
| `provenance.commit_sha` | string | optional | Git commit / version tag |
| `provenance.download_method` | string | ✓ | "git clone" / "curl" / "manual" |
| `available.*` | dict[bool] | ✓ | 各种文件可用性 |
| `acquisition_status` | "ready" / "needs_download" / "needs_imslp" / "deferred" | ✓ | 状态 |
| `notes` | string | optional | 备注 |

### 3.3 `acquisition_status` 状态机

```
deferred                   # 无任何公开数据
    ↓
needs_imslp               # 需要 IMSLP
needs_humdrum             # 需要 Humdrum
needs_pdf_ocr             # 需要 PDF + OCR
    ↓
needs_download            # URL 已知, 未下载
    ↓
ready                     # 已下载 + 标注 ready
```

**约束**: 任何 case 必须能从 `deferred` 状态明确路径到达 `ready`。

---

## 4. Tier A 候选池 (基于 DCML 调研)

### 4.1 DCML 完整标注的实际覆盖 (P20.3.8 调研)

| DCML repo | 标注 movement 数 | 时期 | 风格 |
|---|---|---|---|
| `mozart_piano_sonatas` | ~54 (18 sonatas × ~3 mvt) | Classical | Functional |
| `beethoven_piano_sonatas` | ~96 (32 sonatas × ~3 mvt) | Classical→Romantic | Functional + Altered |
| `ABC` (Beethoven Str Qrt) | ~70 (16 quartets × ~4 mvt) | Classical→Romantic | Functional + Altered |
| `chopin_mazurkas` | ~56 (50+ mazurkas) | Romantic | Mode mixture |
| `schumann_kinderszenen` | 13 (整套) | Romantic | 短小, 简单功能 |
| `liszt_pelerinage` | 19 (3 年) | Romantic | 复杂和声 / 转调 |
| `grieg_lyric_pieces` | 67 (10 opuses) | Romantic→Late Romantic | 抒情小品 |
| `tchaikovsky_seasons` | 13 (12 月 + 副) | Romantic | 情景性 |
| `debussy_suite_bergamasque` | 4 (整套) | Impressionist | Modal |
| `ravel_piano` | 5 (Jeux d'eau, etc.) | Impressionist | Modal + 全音阶 |
| `mendelssohn_quartets` | ~24 (6 quartets × ~4 mvt) | Romantic | Classical form + Romantic harmony |
| `wagner_overtures` | 2 (Tannhäuser, Lohengrin) | Late Romantic | 半音 + Augmented 6th |
| `mahler_kindertotenlieder` | 5 (整套) | Late Romantic | 复杂和声 |
| `handel_keyboard` | 6 (suites) | Baroque | 数字低音 + Functional |
| `corelli` | 149 (6 opuses × 12 sonatas × 2 mvt) | Baroque | 数字低音 |
| `monteverdi_madrigals` | 19 | Early Baroque | 早期功能 |
| `c_schumann_lieder` | 12 | Romantic | 艺术歌曲 |
| `sweelinck_keyboard` | 1 | Renaissance | 调式 |
| **TOTAL** | **~615 movements** | — | — |

### 4.2 Capability Coverage Matrix (Tier A 选择指南)

| Capability | 适合作品 (DCML) | 候选数 |
|---|---|---|
| **I-V-I 基础功能 (Sposobin 入门)** | Mozart K.545-1, K.279-1, K.284-1 | 5+ |
| **变格终止 / 阻碍终止** | Mozart K.310-1, Beethoven Op.13-1, Op.10-1 | 5+ |
| **Cadential 6/4 (K6/4)** | Mozart K.283-1, K.332-1, Beethoven Op.2-1-1 | 5+ |
| **转调 (modulation, sonata exposition)** | Mozart K.310-1, K.457-1, Beethoven Op.2-3-1, Op.78-1 | 5+ |
| **Secondary dominants (V/V, V7/V)** | Beethoven Op.13-1, Op.14-1, late Classical | 5+ |
| **Altered dominants / mixture** | Beethoven Op.27-2-1 (Moonlight), Op.106-1 (Hammerklavier) | 3+ |
| **bVI / bIII (mode mixture)** | Schumann Kinderszenen, Liszt, Chopin Mazurkas | 10+ |
| **Augmented 6th chords** | Wagner Overtures, Liszt | 3+ |
| **Modal harmony (Impressionist)** | Debussy, Ravel | 5+ |
| **Baroque counterpoint** | Handel, Corelli (但**不是** Bach 复调, 那是 Fugue) | 10+ |
| **Phrase structure / form** | Sonata exposition movements (Mozart, Beethoven) | 10+ |
| **Complex cadences (Phrygian half, Plagal)** | Late Beethoven, Romantic | 3+ |

### 4.3 推荐的 MTRE V1 Core (20-25 case) 初稿

按 capability balance 选:

**Classical 入门 (5)**:
- mozart_k545_m1 (I-V-I, PAC, simple)
- mozart_k283_1 (K6/4 测试)
- mozart_k310_1 (modulation, minor key)
- beethoven_op2_1_1 (Classical period, sonata form)
- beethoven_op13_1 (Pathétique, 慢引子 + Allegro)

**Classical 中级 (5)**:
- mozart_k457_1 (c minor, dramatic)
- beethoven_op10_1_1 (c minor, 小悲怆)
- beethoven_op14_1_1 (E major, simple)
- beethoven_op78_1 (F# major, 感恩)
- ABC Op.18 No.1 mvt 1 (string quartet 起点)

**Classical 高级 (3)**:
- beethoven_op27_2_1 (Moonlight, c# minor, altered)
- beethoven_op106_1 (Hammerklavier, Bb major, 复杂)
- ABC Op.59 No.1 mvt 1 (Rasumovsky, 复杂转调)

**Romantic 早期 (4)**:
- schumann_kinderszenen_1 (Träumerei, 简单 D major)
- schumann_kinderszenen_7 (Traum eines Kindes, bVI 测试)
- liszt_pelerinage_s1_1 (Sposalizio, 借用和弦)
- chopin_mazurka_op17_4 (a minor, mode mixture)

**Romantic 中级 (3)**:
- grieg_lyric_pieces_op12_1 (Arietta, 简单)
- tchaikovsky_seasons_october (Autumn Song, 转调)
- mendelssohn_quartet_op44_1_1 (Eb major, sonata)

**Late Romantic (2)**:
- wagner_lohengrin_prelude (A major, 半音)
- mahler_kindertotenlieder_1 (Nun will die Sonn so hell, d minor)

**Impressionist (3)**:
- debussy_suite_bergamasque_3 (Clair de Lune, 全音阶 / 五声音阶)
- debussy_suite_bergamasque_1 (Prélude, modal)
- ravel_jeux_deau (Bb major, 全音阶)

**总计**: **25 case, 跨 4 时期, 12+ capability**

**注意**: 这只是初稿。具体选 case 需用户 / 专家审定。

### 4.4 Tier B (Silver) 候选

仅用于训练 / debug, **不进 V1 benchmark**:
- Bach WTC (Humdrum + AugmentedNet)
- Chopin Op.28 preludes (Humdrum + AugmentedNet)

### 4.5 Tier C (Raw) 候选

只有谱面, 待未来标注:
- Haydn Hob.XVI:52 (Humdrum kern 无, IMSLP 待下载)
- Chopin Op.9 No.2 (无 Nocturne 公开标注)
- Schubert Op.90 No.3 (无 Impromptu 公开标注, key 错误待修)

---

## 5. Benchmark Runner 接口 (建议)

```python
# gold_adapter/manifest_loader.py

class ManifestLoader:
    """从 manifest.json 加载 case, 运行时下载 external 数据."""

    def __init__(self, manifest_path: str, cache_dir: str = "~/.cache/mtre/external"):
        self.manifest = load_manifest(manifest_path)
        self.cache_dir = Path(cache_dir).expanduser()

    def get_case(self, case_id: str) -> EvalCase:
        entry = self.manifest.find(case_id)
        if entry.tier != "A":
            raise ValueError(f"{case_id} is tier {entry.tier}, only tier A in MTRE V1 Core")
        # 运行时下载 (if not cached)
        local_path = self._ensure_downloaded(entry)
        # adapter 转换
        return self.adapter.convert(entry, local_path)

    def _ensure_downloaded(self, entry) -> Path:
        """git clone / curl, 检查 cache."""
        cache_path = self.cache_dir / entry.source.dataset
        if not cache_path.exists():
            clone_repo(entry.source.dataset_url, cache_path)
        # 检查 commit_sha
        if entry.provenance.commit_sha:
            checkout_commit(cache_path, entry.provenance.commit_sha)
        return cache_path

    def list_bench_eligible(self) -> list[str]:
        """返回 V1 可跑 case 列表 (Tier A + ready)."""
        return [c.id for c in self.manifest.cases
                if c.tier == "A" and c.acquisition_status == "ready"]
```

**关键**:
- **MTRE 本身不下载任何数据** — 用户首次跑时自动下载
- **License 显示在 manifest**, 用户确认后再下载
- **Tier B/C 不进 benchmark runner**, 需 `tier == "A"` 强制

---

## 6. 旧 gold JSON 处理

### 6.1 不修改旧文件

`data/eval/gold/*.json` 8 个文件**完全不动**。它们是 P20.3 阶段的"placeholder", 不是 P20.3.7 实际可用的 gold。

P20.3.7 实际可用的 gold 是**新建**的:
- `data/eval/benchmark/gold/expert_verified/mozart_k545_m1.json` (DCMLab 转换)
- `data/eval/benchmark/gold/expert_verified/beethoven_op13_m1.json` (DCMLab 转换)
- 等 23 个 (P20.3.8 选择后)

### 6.2 Old Gold Error Log

发现的所有问题写到 `data/eval/benchmark/old_gold_error_log.json`:

```json
{
  "log_version": "0.1.0",
  "created": "2026-08-11",
  "entries": [
    {
      "error_id": "ERR-2026-08-11-001",
      "case_id": "schubert_op90_no3",
      "field": "analysis.key",
      "old_value": "Eb major",
      "correct_value": "Gb major",
      "evidence": "D.899 No.3 是降 G 大调, 不是降 E 大调. 现有 gold 标错.",
      "source": "Schubert D.899 Impromptu No.3 (Op.90 No.3), 全名: 4 Impromptu D.899, 第三首: G♭ major.",
      "discovered_by": "Mavis (P20.3.7 Phase 1.5 schema 增强检查)",
      "discovered_date": "2026-08-11",
      "action_taken": "LOGGED. old gold JSON NOT modified. future gold (P20.3.8) will use Gb major.",
      "status": "open"
    }
  ]
}
```

**不修改旧 gold JSON 的好处**:
- 保留 "原始假设 → 修正过程" 链路
- 旧 gold 的"误" 本身是 gold 历史的真实部分 (P20.3 阶段就是这样)
- 训练 / debug 时可对比 "原始 vs 修正"

### 6.3 旧 gold 的最终命运

P20.3.7 完成后:
- `data/eval/gold/*.json` (8 个 V1 placeholder) → **archive** 到 `data/eval/benchmark/_archive/P20.3/`
- 不删除 (历史)
- `data/eval/later_profiles/*.json` (4 个 V2 placeholder) → 同上
- `data/eval/benchmark/gold/expert_verified/*.json` (新建, 25 个 P20.3.8 选 case) → **active**

---

## 7. Schema 改动清单 (P20.3.8)

### 7.1 `data/eval/benchmark/manifest.json` (新)

- 顶层结构: 见 §3.1
- 字段: 见 §3.2

### 7.2 `data/eval/schema.py` 改动 (vs P20.3.7)

P20.3.7 已加 `Provenance` dataclass。P20.3.8 改动:

```python
@dataclass
class EvalCase:
    # ... 现有字段 ...
    deprecated: bool = False
    tier: str = ""        # P20.3.8 新增: "A" / "B" / "C" / "" (legacy)
    capability_focus: list[str] = field(default_factory=list)  # P20.3.8 新增
```

### 7.3 `data/eval/benchmark/old_gold_error_log.json` (新)

- 见 §6.2

### 7.4 `data/eval/benchmark/_archive/P20.3/` (新目录)

- 把 8 + 4 个旧 gold JSON archive 进去

---

## 8. 实施步骤 (建议, 全部 P20.3.8 范围)

**先不写代码**。下一步是用户审批这个 manifest 设计。

1. **Phase 0**: 用户审批 P20.3.8 架构设计
2. **Phase 1**: 写 `data/eval/benchmark/manifest.json` (25 case Tier A, 3-4 case Tier B, 3 case Tier C)
3. **Phase 2**: 写 `data/eval/benchmark/old_gold_error_log.json`
4. **Phase 3**: 写 `data/eval/schema.py` 改动 (tier + capability_focus)
5. **Phase 4**: 测试 (manifest 解析 + tier 过滤)
6. **Phase 5**: 写 `data/eval/benchmark/_archive/P20.3/` 脚本 (archive 旧 gold)

**不实施**: Adapter 代码, benchmark runner — 这些是 P20.3.9 之后的事

---

## 9. 关键风险

### 9.1 Manifest 不准

- DCML 数据可能更新 (commit_sha 需锁)
- 标记者可能修改 label
- 解决: 锁 commit_sha, manifest 显式记录, 更新时 manifest 也要更新

### 9.2 Tier A 实际"专家程度"被高估

- DCML 标记者是 musicology PhD, 不是 Sposobin 教材委员会
- DCML 标注用 DCML standard, 不是 Sposobin 体系
- 解决: 标"DCML standard"在 provenance, V1 归一化到 Sposobin 时记录此 conflict

### 9.3 License 风险

- DCML CC BY-NC-SA 限商用, 但 MTRE 如果不复制数据只 runtime load, 风险降低
- 用户用 MTRE 时要同意 license disclosure

### 9.4 旧 gold 处理争议

- 旧 8 个 V1 gold JSON "占位文本" 是 P20.3 阶段历史
- P20.3.8 不动它们, 但用户可能误以为"MTRE V1 还在用"
- 解决: `data/eval/gold/README.md` 明确标 "DEPRECATED, use data/eval/benchmark/gold/"

---

## 10. 总结

### P20.3.7 → P20.3.8 关键升级

| 维度 | P20.3.7 (错) | P20.3.8 (对) |
|---|---|---|
| 数据等级 | 5 case 混 2 gold + 3 silver | 25 case 纯 Tier A |
| 目录结构 | 旧 `data/eval/gold/` | 新 `data/eval/benchmark/{gold,silver,raw}/` |
| License 隔离 | 复制数据进 repo | Runtime 加载, MTRE 永远 MIT |
| 旧 gold 错误 | 修字段 | Log + archive, 保留历史 |
| "NOT FOUND" 处理 | 标不可用 | 标 deferred, 区分"无数据" vs "无分析" |
| 选取标准 | 默认 8 case 全部 | 能力覆盖 + 平衡选取 |
| 数据源 | DCML only | DCML + Humdrum + (Riemenschneider 未来) |
| Tier A 数量 | 2 (Mozart, Beethoven) | **~615 movements 可选, 选 20-30** |

### 不做的事 (out of scope)

- ❌ 写 Adapter 代码 (等 P20.3.9)
- ❌ 写 Benchmark Runner (等 P20.4)
- ❌ 修改现有 8 个 gold JSON (只 archive)
- ❌ 处理 Schubert key 错误 (只 log, 等 P20.3.9 重写时用 Gb major)
- ❌ 评估 Agent (benchmark runner 不在 P20.3.8)
