from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import verovio
from PIL import Image, ImageChops


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "data" / "external" / "sposobin-shte" / "SHTE_V1"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "omr-training" / "sposobin-shte-v1"
CHROME_CANDIDATES = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)


def _safe_id(xml_path: Path) -> str:
    chapter = xml_path.parents[1].name.lower()
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", xml_path.stem).strip("_")
    return f"{chapter}__{stem}"


def _split(sample_id: str) -> str:
    bucket = int(hashlib.sha256(sample_id.encode("utf-8")).hexdigest()[:8], 16) % 10
    if bucket == 0:
        return "test"
    if bucket == 1:
        return "validation"
    return "train"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _find_browser() -> Path:
    for path in CHROME_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError("Chrome or Edge is required to rasterize Verovio SVG output")


def _crop_white_margin(path: Path, margin: int = 48) -> tuple[int, int]:
    with Image.open(path) as source:
        image = source.convert("RGB")
        background = Image.new("RGB", image.size, "white")
        difference = ImageChops.difference(image, background).convert("L")
        mask = difference.point(lambda value: 255 if value > 12 else 0)
        bbox = mask.getbbox()
        if bbox:
            left, top, right, bottom = bbox
            bbox = (
                max(0, left - margin),
                max(0, top - margin),
                min(image.width, right + margin),
                min(image.height, bottom + margin),
            )
            image = image.crop(bbox)
        image.save(path, "PNG", optimize=True)
        return image.size


def _render_png(toolkit: verovio.toolkit, xml_path: Path, svg_path: Path, png_path: Path) -> tuple[int, int, int]:
    if not toolkit.loadFile(str(xml_path.resolve())):
        raise ValueError(f"Verovio could not load {xml_path}")
    page_count = toolkit.getPageCount()
    if page_count != 1:
        raise ValueError(f"Expected one-page exercise, found {page_count} pages in {xml_path}")

    svg_path.write_text(toolkit.renderToSVG(1), encoding="utf-8")
    browser = _find_browser()
    subprocess.run(
        [
            str(browser),
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            "--allow-file-access-from-files",
            "--window-size=2800,3400",
            f"--screenshot={png_path.resolve()}",
            svg_path.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=45,
    )
    for _ in range(40):
        if png_path.exists() and png_path.stat().st_size:
            break
        time.sleep(0.05)
    if not png_path.exists():
        raise RuntimeError(f"Browser did not create {png_path}")
    width, height = _crop_white_margin(png_path)
    return page_count, width, height


def prepare(source: Path, output: Path, limit: int | None = None) -> dict[str, int]:
    source = source.resolve()
    output = output.resolve()
    xml_files = sorted(path for path in source.rglob("*.xml") if path.parent.name == "four")
    if limit is not None:
        xml_files = xml_files[:limit]
    if not xml_files:
        raise FileNotFoundError(f"No four-part MusicXML files found below {source}")

    image_dir = output / "images"
    score_dir = output / "musicxml"
    svg_dir = output / "svg"
    for directory in (image_dir, score_dir, svg_dir):
        directory.mkdir(parents=True, exist_ok=True)

    source_license = source.parent / "LICENSE"
    if source_license.exists():
        shutil.copy2(source_license, output / "SOURCE_LICENSE")

    toolkit = verovio.toolkit()
    toolkit.setOptions(
        {
            "adjustPageHeight": True,
            "breaks": "auto",
            "pageHeight": 3300,
            "pageWidth": 2400,
            "scale": 80,
        }
    )

    manifest_path = output / "manifest.jsonl"
    records: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for index, source_xml in enumerate(xml_files, start=1):
        sample_id = _safe_id(source_xml)
        score_path = score_dir / f"{sample_id}.musicxml"
        svg_path = svg_dir / f"{sample_id}.svg"
        image_path = image_dir / f"{sample_id}.png"
        try:
            root = ET.parse(source_xml).getroot()
            if root.tag not in {"score-partwise", "score-timewise"}:
                raise ValueError(f"Unexpected MusicXML root: {root.tag}")
            shutil.copy2(source_xml, score_path)
            pages, width, height = _render_png(toolkit, score_path, svg_path, image_path)
            records.append(
                {
                    "id": sample_id,
                    "chapter": source_xml.parents[1].name,
                    "split": _split(sample_id),
                    "image": image_path.relative_to(output).as_posix(),
                    "musicxml": score_path.relative_to(output).as_posix(),
                    "svg": svg_path.relative_to(output).as_posix(),
                    "pages": pages,
                    "width": width,
                    "height": height,
                    "sha256_image": _sha256(image_path),
                    "sha256_musicxml": _sha256(score_path),
                    "source": "https://github.com/lqnankai/Music-Dataset",
                    "license": "MIT",
                    "ground_truth": "professionally proofread SHTE_V1 four-part transcription",
                    "synthetic_render": True,
                }
            )
        except Exception as exc:  # Keep the batch useful while preserving every failure.
            failures.append({"source": str(source_xml), "error": str(exc)})
        print(f"[{index}/{len(xml_files)}] {sample_id}")

    with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    (output / "failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "source_files": len(xml_files),
        "rendered": len(records),
        "failed": len(failures),
        "train": sum(record["split"] == "train" for record in records),
        "validation": sum(record["split"] == "validation" for record in records),
        "test": sum(record["split"] == "test" for record in records),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "README.md").write_text(
        "# Sposobin SHTE V1 OMR pairs\n\n"
        "Source: https://github.com/lqnankai/Music-Dataset\n\n"
        "The `musicxml/` files are the professionally proofread four-part SHTE V1 "
        "transcriptions. The `images/` files are synthetic PNG renders generated from "
        "those files with Verovio; they are not scans of the printed textbook. `svg/` "
        "contains the intermediate lossless renders. Pairing, hashes, provenance, and "
        "deterministic score-level splits are recorded in `manifest.jsonl`.\n\n"
        "Use this set for parser, renderer, solver, and clean-score OMR evaluation. Do "
        "not use it as evidence of camera-photo robustness. See `SOURCE_LICENSE` for "
        "the upstream MIT license.\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare paired SHTE MusicXML and rendered score images")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output, args.limit), indent=2))


if __name__ == "__main__":
    main()
