# OMR + VLM recognition pipeline

## Runtime flow

1. The project-local `.venv-homr` transcribes an image or renders a PDF page by
   page, then exports merged MusicXML, normalized staff boxes, and per-page
   measure counts. `HOMR_EXE` remains an explicit override.
2. HOMR writes a separate `homr-confidence-v1` JSON sidecar containing only
   aggregate decoder probabilities per branch/system. Full logits are not kept
   and MusicXML is not enlarged with diagnostics.
3. `musicxml_quality.py` checks XML structure, timing cursors, measure capacity,
   pitch bounds, and written-type/duration consistency.
4. `omr_review_pipeline.py` prioritizes structural errors, low-confidence
   systems, and then bounded first/middle/last sentinels. When available, the
   preceding full system is stacked above the target crop and the preceding
   measure candidate is supplied as read-only context.
5. Qwen3.6 Flash reviews each crop. Unresolved results escalate to Qwen3.7 Plus.
6. Python requires every correction to match an existing candidate
   measure/role/onset slot. Unsupported metadata concerns remain warnings. No
   VLM result is applied automatically.
7. `transcriptionReadiness` blocks solver use for structural errors, missing
   confidence diagnostics, failed/unresolved visual reviews, or corrections
   awaiting confirmation. `provisional` means only that no known blocker was
   found; it is never presented as proof of correctness.
8. The user selects proposed event replacements in the review panel. The server
   verifies they came from the same review run, applies them transactionally to
   ScoreIR, validates the result, and regenerates the editor projection.
9. The source document, immutable HOMR output, exact VLM review crops, VLM
   review, confirmed ScoreIR, and later human-final MusicXML are stored under
   `data/omr-review-runs/<run-id>/`.
10. A submitted human final must pass both the conservative MusicXML audit and
    the `music21 -> ScoreIR` validation path. Equal resubmissions are idempotent;
    changed finals increment a revision and archive the previous file. The run
    records semantic HOMR-versus-human metrics and content hashes.

## API

- `POST /api/omr/audit-musicxml`: validate an existing MusicXML document.
- `POST /api/omr/enhanced-parse`: run HOMR, audit, crop, and optional VLM review.
- `POST /api/omr/review-runs/{run_id}/final-musicxml`: attach human-approved gold.
- `POST /api/vision/review-region`: manually review one bounded image crop.
- `GET /api/omr/review-runs/{run_id}/artifacts/{path}`: serve a crop only when
  the path is explicitly listed in that run's review record. The frontend uses
  it to overlay the Qwen target region and compare HOMR events with proposed
  replacements before confirmation.

Audit all persisted runs with:

```powershell
python scripts/audit_omr_review_runs.py --output data/omr-review-runs-audit.json
```

`/api/omr/enhanced-parse` multipart fields:

- `file`: PNG, JPEG, WebP, TIFF, BMP, or PDF score source (maximum 32 MB).
- `useVision`: `true` or `false`.
- `maxRegions`: `0` to `8`; default `3`.

## Baseline

The current real-scan dev baseline uses 100 distinct OLiMPiC documents and the
project-local HOMR executable. All 100 predictions parse successfully. Corpus
micro edit-recognition rates are 62.06% for strict semantic events, 65.40% for
strict note events, 87.82% for ordered pitch content, 93.45% for ordered
accidental content, and 69.31% for measure-normalized rhythm. The report is
`data/omr-benchmark/olimpic-scanned-dev-confidence-v1-100.json`.

Ordered pitch intentionally ignores onset/duration so it diagnoses visual pitch
reading separately from timing alignment. It is not a solver-readiness score.
Some OLiMPiC system crops inherit tuplet or meter context that is not printed in
the isolated image, so strict timing remains the end-to-end safety metric.

The deterministic SHTE test split contains synthetic Verovio renders and is an
upper-bound benchmark, not proof of phone-photo accuracy. On 24 clean test
scores HOMR completed all samples with mean token NED 1.31%, rhythm NED 0.79%,
pitch NED 0.76%, and accidental NED 1.27% (lower is better).

Run clean and degraded baselines with the isolated HOMR environment:

```powershell
.\.venv-homr\Scripts\python.exe .\scripts\benchmark_homr_sposobin.py --limit 24
.\.venv-homr\Scripts\python.exe .\scripts\benchmark_homr_sposobin.py --limit 24 --degradation camera-hard
```

This SHTE split contains 193 records (152 train, 17 validation, 24 test), and all
images are synthetic renders made from the reference MusicXML. Treat its result as
an upper-bound round-trip check, not as real scan/photo accuracy. `tokenNed` covers
the complete HOMR token stream; note, rhythm, pitch, and accidental NEDs exclude
structural tokens such as `chord`, clefs, and barlines. NED is an error rate and
must not be presented as `1 - NED` classification accuracy.

For a real-scan calibration, install the optional benchmark dependency and run:

```powershell
.\scripts\setup_homr_test_env.ps1 -Benchmark
.\.venv-homr\Scripts\python.exe .\scripts\benchmark_homr_polish.py --limit 5
```

The Polish Scores report is intentionally separate from the synthetic SHTE report;
their NED values describe very different image domains and must not be pooled.

## Safety boundary

The canonical HOMR MusicXML is never overwritten. A VLM correction is a review
candidate until a user submits a final MusicXML artifact. Training should use
only runs where `humanFinalAvailable` is true, `labelStatus` is `gold-human`,
and stored hashes still match. Page images and PDFs are retained as real source
evidence, but they are not called staff-aligned HOMR examples. Until explicit
staff-to-token alignment exists, human finals contribute labels through
synthetic token renders and `realImageAligned` remains false.

Decoder probability measures uncertainty, not correctness. On the 100-document
dev calibration, the 0.895 rhythm-mean priority threshold flags 32 systems with
78.1% precision and 44.6% recall for the defined high-risk condition. Sentinel
review remains mandatory because confident errors are common.
