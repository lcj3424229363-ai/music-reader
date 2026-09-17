from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOMR_SOURCE = PROJECT_ROOT / "data" / "omr-benchmark" / "homr-source"
DEFAULT_DATASET = PROJECT_ROOT / "data" / "omr-training" / "homr-sposobin-native"


def evaluate(
    homr_source: Path,
    dataset: Path,
    split: str,
    checkpoint: Path | None,
    batch_size: int,
    limit: int | None,
) -> dict[str, Any]:
    import torch

    original_cwd = Path.cwd()
    if checkpoint is not None and not checkpoint.is_absolute():
        checkpoint = (original_cwd / checkpoint).resolve()
    homr_source = homr_source.resolve()
    dataset = dataset.resolve()
    os.chdir(homr_source)
    sys.path.insert(0, str(homr_source))

    from homr.transformer.configs import Config
    from training.architecture.transformer.tromr_arch import TrOMR
    from training.transformer.data_loader import DataLoader

    config = Config()
    checkpoint = checkpoint or Path(config.filepaths.checkpoint).resolve()
    model = TrOMR(config)
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing or unexpected:
        raise ValueError(f"Checkpoint mismatch: missing={missing}, unexpected={unexpected}")
    model.eval()
    torch.set_num_threads(max(1, min(6, os.cpu_count() or 1)))

    index = dataset / f"{split}-index.txt"
    lines = [line for line in index.read_text(encoding="utf-8").splitlines() if line.strip()]
    if limit is not None:
        lines = lines[:limit]
    loader = DataLoader(lines, config, is_validation=True)
    branch_names = ("rhythm", "pitch", "lift", "position", "articulations", "slurs")
    correct: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    loss_sum = 0.0
    batches = 0
    started = time.perf_counter()
    with torch.no_grad():
        for start in range(0, len(loader), batch_size):
            items = [loader[index] for index in range(start, min(start + batch_size, len(loader)))]
            batch = {key: torch.stack([item[key] for item in items]) for key in items[0]}
            output = model(**batch)
            loss_sum += float(output["loss"])
            batches += 1
            mask = batch["mask"][:, 1:].bool()
            labels = (
                batch["rhythms"], batch["pitchs"], batch["lifts"], batch["positions"],
                batch["articulations"], batch["slurs"],
            )
            for name, logits, values in zip(branch_names, output["logits"], labels):
                expected = values[:, 1:]
                usable = mask & (expected != -100)
                predicted = logits.argmax(dim=-1)
                correct[name] += int(((predicted == expected) & usable).sum())
                total[name] += int(usable.sum())
    branch_accuracy = {name: correct[name] / total[name] for name in branch_names}
    return {
        "checkpoint": str(checkpoint),
        "split": split,
        "samples": len(lines),
        "loss": loss_sum / max(1, batches),
        "accuracy": sum(correct.values()) / max(1, sum(total.values())),
        "branchAccuracy": branch_accuracy,
        "elapsedSeconds": round(time.perf_counter() - started, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a HOMR checkpoint with its teacher-forced token metric")
    parser.add_argument("--homr-source", type=Path, default=DEFAULT_HOMR_SOURCE)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--split", choices=("train", "validation", "test"), default="validation")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve() if args.output else None
    report = evaluate(args.homr_source, args.dataset, args.split, args.checkpoint, args.batch_size, args.limit)
    text = json.dumps(report, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
