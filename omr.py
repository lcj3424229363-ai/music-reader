"""OMR wrapper: score images/PDF -> MusicXML using homr."""
from __future__ import annotations

import copy
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_OMR_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS
MUSICXML_EXTENSIONS = {".musicxml", ".xml", ".mxl"}
SUPPORTED_TRANSCRIPTION_EXTENSIONS = SUPPORTED_OMR_EXTENSIONS | MUSICXML_EXTENSIONS


class OmrError(RuntimeError):
    pass


def find_homr() -> Path | None:
    """Locate homr from HOMR_EXE, PATH, or common per-user installs."""
    configured = os.environ.get("HOMR_EXE")
    candidates = [
        Path(configured).expanduser() if configured else None,
        Path.home() / ".local" / "bin" / "homr.exe",
        Path.home() / "AppData" / "Roaming" / "uv" / "tools" / "homr" / "Scripts" / "homr.exe",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate.resolve()
    for command in ("homr", "homr.exe"):
        found = shutil.which(command)
        if found:
            return Path(found).resolve()
    return None


def _run_homr(
    homr: Path,
    source_image: Path,
    target_dir: Path,
    timeout_seconds: int,
) -> tuple[Path, str, str]:
    """Run homr with a unique work name so repeated calls remain detectable."""
    work_name = f"{source_image.stem}_{uuid.uuid4().hex[:10]}{source_image.suffix.lower()}"
    work_input = target_dir / work_name
    shutil.copy2(source_image, work_input)
    expected = work_input.with_suffix(".musicxml")
    started_ns = time.time_ns()

    try:
        completed = subprocess.run(
            [str(homr), work_input.name],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise OmrError(
            f"homr timed out after {timeout_seconds}s on {source_image.name}."
        ) from exc
    except OSError as exc:
        raise OmrError(f"homr executable could not be started: {exc}") from exc

    exported: Path | None = expected if expected.is_file() else None
    if exported is None:
        changed = [
            path for path in target_dir.glob(f"{work_input.stem}*.musicxml")
            if path.stat().st_mtime_ns >= started_ns
        ]
        if changed:
            exported = max(changed, key=lambda path: path.stat().st_mtime_ns)

    if completed.returncode != 0 or exported is None:
        tail = (completed.stderr or completed.stdout or "").strip()[-1500:]
        raise OmrError(f"homr failed (exit {completed.returncode}). Tail:\n{tail}")
    return exported.resolve(), completed.stdout[-4000:], completed.stderr[-4000:]


def _render_pdf_pages(
    source: Path,
    target_dir: Path,
    timeout_seconds: int,
) -> tuple[list[Path], str]:
    """Render every PDF page to PNG, preferring Poppler with a PyMuPDF fallback."""
    render_dir = target_dir / f"pdf-pages-{uuid.uuid4().hex[:10]}"
    render_dir.mkdir(parents=True, exist_ok=False)
    prefix = render_dir / "page"
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        try:
            completed = subprocess.run(
                [pdftoppm, "-png", "-r", "300", str(source), str(prefix)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OmrError(f"PDF rendering timed out after {timeout_seconds}s.") from exc
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip()[-1500:]
            raise OmrError(f"pdftoppm failed (exit {completed.returncode}). Tail:\n{tail}")
        pages = sorted(render_dir.glob("page-*.png"))
        engine = "pdftoppm"
    else:
        try:
            import fitz  # type: ignore
        except ImportError as exc:
            raise OmrError(
                "PDF OMR requires Poppler (pdftoppm) or PyMuPDF (fitz)."
            ) from exc
        try:
            document = fitz.open(source)
            matrix = fitz.Matrix(300 / 72, 300 / 72)
            pages = []
            for index, page in enumerate(document):
                output = render_dir / f"page-{index + 1:04d}.png"
                page.get_pixmap(matrix=matrix, alpha=False).save(output)
                pages.append(output)
            document.close()
        except Exception as exc:
            raise OmrError(f"PDF rendering failed: {exc}") from exc
        engine = "pymupdf"

    if not pages:
        raise OmrError("PDF contains no renderable pages.")
    return pages, engine


def _merge_musicxml_pages(page_files: list[Path], output_path: Path) -> Path:
    """Append homr's per-page measures into one multi-page MusicXML score."""
    if len(page_files) == 1:
        shutil.copy2(page_files[0], output_path)
        return output_path.resolve()

    try:
        from music21 import converter, stream

        scores = [converter.parse(str(path)) for path in page_files]
        part_lists = [list(score.parts) for score in scores]
        part_count = max((len(parts) for parts in part_lists), default=0)
        if part_count == 0:
            raise ValueError("homr output contains no parts")

        combined = stream.Score()
        for part_index in range(part_count):
            first_part = next(
                (parts[part_index] for parts in part_lists if part_index < len(parts)),
                None,
            )
            part_id = getattr(first_part, "id", None)
            if not isinstance(part_id, str) or part_id.isdigit():
                part_id = f"P{part_index + 1}"
            combined_part = stream.Part(id=part_id)
            if first_part is not None:
                combined_part.partName = first_part.partName
            measure_number = 1
            for parts in part_lists:
                if part_index >= len(parts):
                    continue
                for measure in parts[part_index].getElementsByClass(stream.Measure):
                    cloned = copy.deepcopy(measure)
                    cloned.number = measure_number
                    combined_part.append(cloned)
                    measure_number += 1
            combined.insert(0, combined_part)
        combined.write("musicxml", fp=str(output_path))
    except Exception as exc:
        raise OmrError(f"Could not merge multi-page MusicXML output: {exc}") from exc
    return output_path.resolve()


def transcribe_with_audiveris(
    input_path: str | Path,
    output_dir: str | Path,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Run homr on an image/PDF and return the exported MusicXML path.

    The legacy function name is retained for callers that used the old
    Audiveris wrapper.
    """
    source = Path(input_path).resolve()
    target_dir = Path(output_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    extension = source.suffix.lower()

    if not source.is_file():
        raise OmrError(f"OMR input file not found: {source.name}")
    if extension not in SUPPORTED_TRANSCRIPTION_EXTENSIONS:
        raise OmrError(f"Unsupported OMR input type: {extension}")

    # Preserve direct-call compatibility. Server routes native score files to
    # reader.py and therefore does not label these as OMR results.
    if extension in MUSICXML_EXTENSIONS:
        exported = target_dir / f"{source.stem}_{uuid.uuid4().hex[:10]}{extension}"
        shutil.copy2(source, exported)
        return {
            "engine": "passthrough",
            "enginePath": "",
            "inputPath": str(source),
            "outputDir": str(target_dir),
            "exportedPath": str(exported.resolve()),
            "stdout": f"MusicXML passthrough: {source.name}",
            "stderr": "",
        }

    homr = find_homr()
    if homr is None:
        raise OmrError("homr executable not found. Set HOMR_EXE or add homr to PATH.")

    render_engine: str | None = None
    pages = [source]
    if extension in PDF_EXTENSIONS:
        pages, render_engine = _render_pdf_pages(source, target_dir, timeout_seconds)

    page_outputs: list[Path] = []
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    for page in pages:
        exported, stdout, stderr = _run_homr(homr, page, target_dir, timeout_seconds)
        page_outputs.append(exported)
        stdout_parts.append(stdout)
        stderr_parts.append(stderr)

    if len(page_outputs) == 1 and extension not in PDF_EXTENSIONS:
        exported = page_outputs[0]
    else:
        exported = _merge_musicxml_pages(
            page_outputs,
            target_dir / f"{source.stem}_{uuid.uuid4().hex[:10]}.musicxml",
        )

    return {
        "engine": "homr" if render_engine is None else f"homr+{render_engine}",
        "enginePath": str(homr),
        "inputPath": str(source),
        "outputDir": str(target_dir),
        "exportedPath": str(exported),
        "stdout": "\n".join(stdout_parts)[-4000:],
        "stderr": "\n".join(stderr_parts)[-4000:],
    }


def find_audiveris() -> Path | None:
    """Compatibility shim for old imports."""
    return None
