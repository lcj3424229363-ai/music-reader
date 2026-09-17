# OMR dataset policy

## OLiMPiC 1.0 Scanned

- Source: http://hdl.handle.net/11234/1-5419
- Upstream project: https://github.com/ufal/olimpic-icdar24
- License: CC BY-SA
- Local contents: 2,931 real IMSLP system scans with paired LMX and MusicXML.
- Splits: 1,438 dev systems and 1,493 test systems from 200 documents.
- Project policy: evaluation only. These dev/test systems must not be added to
  HOMR training data or used to select checkpoints against the final test set.

Run `python scripts/audit_olimpic_dataset.py` before benchmarking. The audit
requires every listed sample to contain PNG, LMX, and parseable MusicXML, and
requires document IDs to remain disjoint across dev and test.

Use dev for threshold and pipeline iteration. Use test only for milestone
reports after the implementation and thresholds have been fixed.

## Human review runs

Runtime corrections live in `data/omr-review-runs/<run-id>/`. A run is not a
training label until a human-final MusicXML file has passed structural and
ScoreIR validation. The original image or PDF, HOMR output, VLM crops, content
hashes, final revision history, and semantic comparison remain together for
traceability.

`scripts/build_homr_finetune_dataset.py` accepts verified image and PDF review
sources, but currently converts the human-final MusicXML into synthetic HOMR
staff windows. It must not classify the document-level source as an aligned real
training image. Use `scripts/audit_omr_review_runs.py` to count pending, ready,
and invalid records before building a fine-tuning set.

Current reproducible dev command:

```powershell
python scripts/benchmark_homr_olimpic.py --split dev --limit 100 `
  --predictions-dir data/omr-benchmark/predictions/olimpic-scanned-dev-confidence-v1 `
  --reuse-predictions `
  --output data/omr-benchmark/olimpic-scanned-dev-confidence-v1-100.json
```
