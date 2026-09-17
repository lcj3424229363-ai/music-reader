from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOMR_SOURCE = PROJECT_ROOT / "data" / "omr-benchmark" / "homr-source"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "omr-models" / "sposobin-cpu-v1"


def export_checkpoint(checkpoint: Path, homr_source: Path, output: Path) -> dict[str, Any]:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    import onnx
    import torch

    checkpoint = checkpoint.resolve()
    homr_source = homr_source.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(homr_source))
    os.chdir(homr_source)

    from homr.transformer.configs import Config
    from training.onnx import convert
    from training.onnx.split_weights import split_weights

    encoder_path = output / "encoder.onnx"
    decoder_path = output / "decoder.onnx"
    config = Config()
    config.filepaths.encoder_path = str(encoder_path)
    config.filepaths.decoder_path = str(decoder_path)

    with tempfile.TemporaryDirectory(prefix="homr-export-") as temporary:
        original_cwd = Path.cwd()
        os.chdir(temporary)
        try:
            split_weights(str(checkpoint))
            original_config = convert.Config
            convert.Config = lambda: config
            try:
                convert.convert_encoder(overwrite=True)
                convert.convert_decoder(overwrite=True)
            finally:
                convert.Config = original_config
        finally:
            os.chdir(original_cwd)

    for path in (encoder_path, decoder_path):
        model = onnx.load(str(path))
        onnx.checker.check_model(model)
    encoder_external = encoder_path.with_suffix(encoder_path.suffix + ".data")
    report = {
        "checkpoint": str(checkpoint),
        "encoder": str(encoder_path),
        "decoder": str(decoder_path),
        "encoderBytes": encoder_path.stat().st_size,
        "encoderExternalBytes": encoder_external.stat().st_size if encoder_external.exists() else 0,
        "decoderBytes": decoder_path.stat().st_size,
        "opset": 18,
        "validated": True,
        "torchVersion": torch.__version__,
        "onnxVersion": onnx.__version__,
    }
    (output / "export-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a fine-tuned HOMR checkpoint to CPU ONNX")
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--homr-source", type=Path, default=DEFAULT_HOMR_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(export_checkpoint(args.checkpoint, args.homr_source, args.output), indent=2))


if __name__ == "__main__":
    main()
