# HOMR fine-tuning workflow

The project does not train HOMR from full-page image/MusicXML pairs directly. HOMR's
TrOMR recognizer expects a cropped one- or two-staff image plus a `.tokens` file. The
dataset builder uses HOMR's own MusicXML parser and vocabulary to create that format.

## 1. Build and audit the dataset

From the project root on Windows:

```powershell
python scripts/build_homr_finetune_dataset.py
python scripts/train_homr_custom.py --check-data
```

Generated files are under `data/omr-training/homr-sposobin-native/`:

- `train-index.txt`, `validation-index.txt`, and `test-index.txt` are HOMR indexes.
- `manifest.jsonl` records source score, content group, window, and label tier.
- `quality-report.json` must show zero `crossSplitLeakage`.
- `rejected.json` explains every excluded source or review run.

Only `human-final.musicxml` review results with `humanFinalAvailable: true` are accepted
as gold transcriptions. Raw HOMR results and unconfirmed VLM suggestions are never used
as ground truth. Until staff-to-token alignment is recorded, these transcriptions are
re-rendered and are not reported as real-image training pairs.

## 2. Fine-tune on a GPU machine

Copy the project dataset and the matching HOMR source revision to the GPU machine.
Install the HOMR training dependencies and initialize its pretrained checkpoint, then
run from the project root:

```bash
python scripts/train_homr_custom.py --check-data
python scripts/train_homr_custom.py --epochs 12 --batch-size 4 --effective-batch 16
```

The custom launcher loads HOMR's pretrained TrOMR checkpoint, trains all decoder
branches, freezes only the vision backbone for the first two epochs, and evaluates on
the explicit validation index. This differs from HOMR's current `--fine` mode, which
only unfreezes the lift decoder and therefore cannot adapt pitch and rhythm recognition.

The launcher selects bf16 on supported GPUs and fp16 otherwise. Use `--fp32` only when
reduced precision is unsuitable. Use `--resume PATH` to resume a Trainer checkpoint.
Do not tune against the test index.

## 3. Acceptance gate

Export or replace a production model only when it beats the current model on the held-
out test split and on a separate set of real scans/photos. Synthetic Verovio renders
measure clean-score adaptation; they do not demonstrate camera or degraded-scan
accuracy. Accumulate human-confirmed review runs before claiming real-image gains.
