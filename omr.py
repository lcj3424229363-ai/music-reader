from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


SUPPORTED_OMR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".pdf"}
DEFAULT_AUDIVERIS_PATHS = [
    Path(r"C:\Program Files\Audiveris\Audiveris.exe"),
    Path(r"C:\Program Files (x86)\Audiveris\Audiveris.exe"),
]


class OmrError(RuntimeError):
    pass


def find_audiveris() -> Path | None:
    configured = os.environ.get("AUDIVERIS_EXE")
    if configured:
        configured_path = Path(configured)
        if configured_path.exists():
            return configured_path

    for candidate in DEFAULT_AUDIVERIS_PATHS:
        if candidate.exists():
            return candidate

    return None


def transcribe_with_audiveris(input_path: str | Path, output_dir: str | Path, timeout_seconds: int = 240) -> dict[str, Any]:
    source = Path(input_path).resolve()
    target_dir = Path(output_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    if source.suffix.lower() not in SUPPORTED_OMR_EXTENSIONS:
        raise OmrError(f"Unsupported OMR input type: {source.suffix}")

    audiveris = find_audiveris()
    if not audiveris:
        raise OmrError("Audiveris was not found. Set AUDIVERIS_EXE or install Audiveris.")

    before = _known_musicxml_outputs(target_dir)
    command = [
        str(audiveris),
        "-batch",
        "-transcribe",
        "-export",
        "-output",
        str(target_dir),
        str(source),
    ]

    completed = subprocess.run(
        command,
        cwd=str(target_dir),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )

    after = _known_musicxml_outputs(target_dir)
    new_outputs = [path for path in after if path not in before]
    exported = _pick_best_output(new_outputs or after)

    if completed.returncode != 0:
        raise OmrError(_format_failure(completed))

    if not exported:
        raise OmrError(
            "Audiveris finished but no MusicXML/MXL export was found. "
            "The image may be unreadable or may need manual correction in Audiveris."
        )

    return {
        "engine": "audiveris",
        "enginePath": str(audiveris),
        "inputPath": str(source),
        "outputDir": str(target_dir),
        "exportedPath": str(exported),
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _known_musicxml_outputs(directory: Path) -> set[Path]:
    outputs: set[Path] = set()
    for pattern in ("*.mxl", "*.musicxml", "*.xml"):
        outputs.update(path.resolve() for path in directory.rglob(pattern))
    return outputs


def _pick_best_output(outputs: list[Path] | set[Path]) -> Path | None:
    candidates = [path for path in outputs if path.suffix.lower() in {".mxl", ".musicxml", ".xml"}]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _format_failure(completed: subprocess.CompletedProcess[str]) -> str:
    details = "\n".join(
        item
        for item in [
            f"Audiveris failed with exit code {completed.returncode}.",
            completed.stderr.strip()[-1200:],
            completed.stdout.strip()[-1200:],
        ]
        if item
    )
    return details
