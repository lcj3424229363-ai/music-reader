from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOMR_SOURCE = PROJECT_ROOT / "data" / "omr-benchmark" / "homr-source"
DEFAULT_DATASET = PROJECT_ROOT / "data" / "omr-training" / "homr-sposobin-native"


def _activate_homr_source(path: Path) -> None:
    source = str(path.resolve())
    if source not in sys.path:
        sys.path.insert(0, source)
    os.chdir(source)


def read_index(path: Path, homr_source: Path) -> list[str]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    validated: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        fields = line.split(",")
        if len(fields) != 2:
            raise ValueError(f"{path}:{line_number} must contain image,tokens")
        image, tokens = (Path(field) for field in fields)
        if not image.is_absolute():
            image = homr_source / image
        if not tokens.is_absolute():
            tokens = homr_source / tokens
        if not image.is_file() or not tokens.is_file():
            raise FileNotFoundError(f"Missing indexed pair at {path}:{line_number}")
        with Image.open(image) as opened:
            opened.verify()
        validated.append(f"{image.resolve()},{tokens.resolve()}\n")
    return validated


def check_dataset(dataset: Path, homr_source: Path) -> dict[str, Any]:
    _activate_homr_source(homr_source)
    from training.transformer.training_vocabulary import check_token_lines, read_tokens

    counts: dict[str, int] = {}
    for split in ("train", "validation", "test"):
        lines = read_index(dataset / f"{split}-index.txt", homr_source)
        for line in lines:
            token_path = line.strip().split(",")[1]
            check_token_lines(read_tokens(token_path))
        counts[split] = len(lines)
    groups: dict[str, set[str]] = {}
    manifest = dataset / "manifest.jsonl"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        groups.setdefault(row["group"], set()).add(row["split"])
    leaks = [group for group, splits in groups.items() if len(splits) > 1]
    if leaks:
        raise ValueError(f"Cross-split content leakage detected in {len(leaks)} groups")
    if counts["train"] == 0 or counts["validation"] == 0:
        raise ValueError("Training and validation indexes must both be non-empty")
    return {"samples": counts, "groups": len(groups), "crossSplitLeakage": 0}


def train(args: argparse.Namespace) -> Path:
    _activate_homr_source(args.homr_source)
    import torch
    from transformers import EarlyStoppingCallback, TrainingArguments

    from homr.transformer.configs import Config
    from training.architecture.transformer.tromr_arch import load_model
    from training.run_id import get_run_id
    from training.transformer.data_loader import DataLoader, _filter_valid_samples, label_names
    from training.transformer.distribute import Distribute
    from training.transformer.metrics import HomrTrainer
    from training.transformer.train import FreezeCallback

    train_lines = _filter_valid_samples(read_index(args.dataset / "train-index.txt", args.homr_source))
    validation_lines = _filter_valid_samples(read_index(args.dataset / "validation-index.txt", args.homr_source))
    if args.max_train_samples and len(train_lines) > args.max_train_samples:
        step = len(train_lines) / args.max_train_samples
        train_lines = [train_lines[int(index * step)] for index in range(args.max_train_samples)]
    config = Config()
    model = load_model(config)
    if args.freeze_encoder:
        model.freeze_encoder()
    distribute = Distribute()
    run_id = get_run_id()
    output = args.output or args.homr_source / "current_finetuning"
    use_cuda = torch.cuda.is_available()
    use_bf16 = use_cuda and not args.fp32 and torch.cuda.is_bf16_supported()
    use_fp16 = use_cuda and not args.fp32 and not use_bf16
    training_args = TrainingArguments(
        str(output),
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=3,
        learning_rate=args.learning_rate,
        optim="adamw_torch_fused" if use_cuda else "adamw_torch",
        gradient_accumulation_steps=max(1, args.effective_batch // args.batch_size),
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=max(1, args.batch_size // 2),
        num_train_epochs=args.epochs,
        weight_decay=0.05,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        load_best_model_at_end=True,
        metric_for_best_model="eval_accuracy",
        greater_is_better=True,
        report_to=["tensorboard"],
        logging_dir=str(args.homr_source / "logs" / f"custom-{run_id}"),
        label_names=label_names,
        bf16=use_bf16,
        fp16=use_fp16,
        dataloader_pin_memory=use_cuda,
        dataloader_num_workers=args.workers,
        use_cpu=not use_cuda,
    )
    callbacks = [EarlyStoppingCallback(early_stopping_patience=3)]
    if not args.freeze_encoder:
        callbacks.append(FreezeCallback(epochs_to_freeze=2))
    trainer = HomrTrainer(
        model,
        training_args,
        train_dataset=DataLoader(train_lines, config, is_validation=False),
        eval_dataset=DataLoader(validation_lines, config, is_validation=True),
        callbacks=callbacks,
        distribute=distribute,
    )
    try:
        trainer.train(resume_from_checkpoint=args.resume)
        destination = args.homr_source / "training" / "architecture" / "transformer" / f"pytorch_model_custom_{run_id}.pth"
        if distribute.is_rank0():
            torch.save(model.state_dict(), destination)
        distribute.barrier()
        return destination
    finally:
        distribute.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune all HOMR TrOMR branches on explicit split indexes")
    parser.add_argument("--homr-source", type=Path, default=DEFAULT_HOMR_SOURCE)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--effective-batch", type=int, default=16)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-train-samples", type=int)
    parser.add_argument("--freeze-encoder", action="store_true")
    parser.add_argument("--resume")
    parser.add_argument("--fp32", action="store_true")
    parser.add_argument("--check-data", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1 or args.effective_batch < args.batch_size:
        parser.error("effective batch must be greater than or equal to batch size")
    cwd = Path.cwd()
    args.homr_source = (cwd / args.homr_source).resolve() if not args.homr_source.is_absolute() else args.homr_source.resolve()
    args.dataset = (cwd / args.dataset).resolve() if not args.dataset.is_absolute() else args.dataset.resolve()
    if args.output is not None:
        args.output = (cwd / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    report = check_dataset(args.dataset, args.homr_source)
    print(json.dumps(report, indent=2))
    if not args.check_data:
        print(f"Saved model: {train(args)}")


if __name__ == "__main__":
    main()
