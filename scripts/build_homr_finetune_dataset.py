from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageChops


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "data" / "omr-training" / "sposobin-shte-v1"
DEFAULT_REVIEWS = PROJECT_ROOT / "data" / "omr-review-runs"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "omr-training" / "homr-sposobin-native"
DEFAULT_HOMR_SOURCE = PROJECT_ROOT / "data" / "omr-benchmark" / "homr-source"
WINDOW_SIZE = 8
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
HUMAN_SOURCE_SUFFIXES = IMAGE_SUFFIXES | {".pdf"}
CHROME_CANDIDATES = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(element: ET.Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""


def _child(element: ET.Element, name: str) -> ET.Element | None:
    return next((item for item in element if _local_name(item.tag) == name), None)


def musical_fingerprint(path: Path) -> str:
    """Hash notation content while ignoring engraving metadata and XML formatting."""
    root = ET.parse(path).getroot()
    events: list[Any] = [(_local_name(root.tag), root.get("version", ""))]
    for part_index, part in enumerate(
        (item for item in root if _local_name(item.tag) == "part"), start=1
    ):
        events.append(("part", part_index))
        for measure_index, measure in enumerate(
            (item for item in part if _local_name(item.tag) == "measure"), start=1
        ):
            events.append(("measure", measure_index))
            for item in measure:
                tag = _local_name(item.tag)
                if tag == "attributes":
                    values: list[Any] = ["attributes"]
                    for attr in item:
                        attr_tag = _local_name(attr.tag)
                        if attr_tag in {"divisions", "staves"}:
                            values.append((attr_tag, _text(attr)))
                        elif attr_tag == "key":
                            values.append(("key", _text(_child(attr, "fifths")), _text(_child(attr, "mode"))))
                        elif attr_tag == "time":
                            values.append(("time", _text(_child(attr, "beats")), _text(_child(attr, "beat-type"))))
                        elif attr_tag == "clef":
                            values.append(("clef", attr.get("number", ""), _text(_child(attr, "sign")), _text(_child(attr, "line"))))
                    events.append(values)
                elif tag == "note":
                    pitch = _child(item, "pitch")
                    events.append(
                        (
                            "note",
                            _child(item, "rest") is not None,
                            _child(item, "chord") is not None,
                            _text(_child(pitch, "step")) if pitch is not None else "",
                            _text(_child(pitch, "alter")) if pitch is not None else "",
                            _text(_child(pitch, "octave")) if pitch is not None else "",
                            _text(_child(item, "duration")),
                            _text(_child(item, "voice")),
                            _text(_child(item, "staff")),
                            tuple(sorted(tie.get("type", "") for tie in item if _local_name(tie.tag) == "tie")),
                        )
                    )
                elif tag in {"backup", "forward"}:
                    events.append((tag, _text(_child(item, "duration"))))
                elif tag == "barline":
                    repeat = next((child for child in item if _local_name(child.tag) == "repeat"), None)
                    events.append(("barline", item.get("location", ""), repeat.get("direction", "") if repeat is not None else ""))
    payload = json.dumps(events, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def split_for_group(group_hash: str) -> str:
    bucket = int(group_hash[:8], 16) % 100
    if bucket < 10:
        return "test"
    if bucket < 20:
        return "validation"
    return "train"


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected an object at {path}:{line_number}")
            yield value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_published_records(source: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    manifest = source / "manifest.jsonl"
    if not manifest.is_file():
        return [], [{"source": str(source), "reason": "missing_manifest"}]
    seen_ids: set[str] = set()
    for raw in _read_jsonl(manifest):
        sample_id = str(raw.get("id", "")).strip()
        image = source / str(raw.get("image", ""))
        musicxml = source / str(raw.get("musicxml", ""))
        reason = ""
        if not sample_id or sample_id in seen_ids:
            reason = "missing_or_duplicate_id"
        elif not image.is_file() or image.suffix.lower() not in IMAGE_SUFFIXES:
            reason = "missing_or_unsupported_image"
        elif not musicxml.is_file():
            reason = "missing_musicxml"
        if reason:
            rejected.append({"source": sample_id or str(manifest), "reason": reason})
            continue
        try:
            with Image.open(image) as opened:
                opened.verify()
            group = musical_fingerprint(musicxml)
        except (OSError, ET.ParseError, ValueError) as exc:
            rejected.append({"source": sample_id, "reason": f"invalid_pair: {exc}"})
            continue
        seen_ids.add(sample_id)
        records.append(
            {
                "id": sample_id,
                "image": image.resolve(),
                "musicxml": musicxml.resolve(),
                "group": group,
                "split": split_for_group(group),
                "labelTier": "gold-published",
                "provenance": raw.get("source", "published-manifest"),
            }
        )
    return records, rejected


def collect_human_review_records(review_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    if not review_root.is_dir():
        return records, rejected
    for run_dir in sorted(path for path in review_root.iterdir() if path.is_dir()):
        record_path = run_dir / "review.json"
        if not record_path.is_file():
            rejected.append({"source": run_dir.name, "reason": "missing_review_record"})
            continue
        try:
            metadata = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            rejected.append({"source": run_dir.name, "reason": f"invalid_review_record: {exc}"})
            continue
        if metadata.get("humanFinalAvailable") is not True:
            rejected.append({"source": run_dir.name, "reason": "missing_human_final"})
            continue
        if metadata.get("labelStatus") not in {None, "gold-human"}:
            rejected.append({"source": run_dir.name, "reason": "human_final_not_gold"})
            continue
        if (metadata.get("humanFinalAudit") or {}).get("status") == "invalid":
            rejected.append({"source": run_dir.name, "reason": "invalid_human_final_audit"})
            continue
        if (metadata.get("trainingEvidence") or {}).get("labelEligible") is False:
            rejected.append({"source": run_dir.name, "reason": "human_final_not_label_eligible"})
            continue
        musicxml = run_dir / "human-final.musicxml"
        sources = sorted(path for path in run_dir.iterdir() if path.suffix.lower() in HUMAN_SOURCE_SUFFIXES)
        if not musicxml.is_file() or len(sources) != 1:
            rejected.append({"source": run_dir.name, "reason": "incomplete_human_pair"})
            continue
        source = sources[0]
        try:
            if source.suffix.lower() == ".pdf":
                if not source.read_bytes()[:5] == b"%PDF-":
                    raise ValueError("source PDF signature is invalid")
            else:
                with Image.open(source) as opened:
                    opened.verify()
            expected_source_hash = metadata.get("sourceSha256")
            if expected_source_hash and _sha256_file(source) != expected_source_hash:
                raise ValueError("source file hash does not match review record")
            expected_final_hash = metadata.get("humanFinalSha256")
            if expected_final_hash and _sha256_file(musicxml) != expected_final_hash:
                raise ValueError("human final hash does not match review record")
            group = musical_fingerprint(musicxml)
        except (OSError, ET.ParseError, ValueError) as exc:
            rejected.append({"source": run_dir.name, "reason": f"invalid_human_pair: {exc}"})
            continue
        records.append(
            {
                "id": f"human-{run_dir.name}",
                "image": source.resolve(),
                "musicxml": musicxml.resolve(),
                "group": group,
                "split": split_for_group(group),
                "labelTier": "gold-human",
                "sourceImageDomain": "document-level-real",
                "sourceType": source.suffix.lower().lstrip("."),
                "realImageAligned": bool(
                    (metadata.get("trainingEvidence") or {}).get("realImageAligned")
                ),
                "provenance": str(record_path.resolve()),
            }
        )
    return records, rejected


def _find_browser() -> Path:
    for candidate in CHROME_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Chrome or Edge is required to rasterize HOMR token SVGs")


def _crop_white_margin(path: Path, margin: int = 24) -> tuple[int, int]:
    with Image.open(path) as source:
        image = source.convert("L")
        difference = ImageChops.difference(image, Image.new("L", image.size, 255))
        bbox = difference.point(lambda value: 255 if value > 10 else 0).getbbox()
        if bbox:
            left, top, right, bottom = bbox
            image = image.crop(
                (max(0, left - margin), max(0, top - margin), min(image.width, right + margin), min(image.height, bottom + margin))
            )
        image.save(path, "JPEG", quality=94, optimize=True)
        return image.size


def _svg_viewport(svg: str) -> tuple[int, int]:
    try:
        root = ET.fromstring(svg)
        view_box = [float(value) for value in root.get("viewBox", "").replace(",", " ").split()]
        if len(view_box) == 4:
            return max(640, min(6000, int(view_box[2] / 10) + 80)), max(320, min(2400, int(view_box[3] / 10) + 80))
    except (ET.ParseError, ValueError):
        pass
    return 3200, 1200


def _rasterize_svg(svg: str, svg_path: Path, image_path: Path, browser: Path) -> tuple[int, int]:
    svg_path.write_text(svg, encoding="utf-8")
    image_path.unlink(missing_ok=True)
    width, height = _svg_viewport(svg)
    subprocess.run(
        [
            str(browser), "--headless", "--disable-gpu", "--hide-scrollbars",
            "--allow-file-access-from-files", "--force-device-scale-factor=1",
            f"--window-size={width},{height}", f"--screenshot={image_path.resolve()}",
            svg_path.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=45,
    )
    for _ in range(40):
        if image_path.is_file() and image_path.stat().st_size:
            break
        time.sleep(0.05)
    if not image_path.is_file():
        raise RuntimeError("Browser did not create the rendered training image")
    return _crop_white_margin(image_path)


def _homr_api(homr_source: Path) -> dict[str, Any]:
    if not (homr_source / "training" / "omr_datasets" / "music_xml_parser.py").is_file():
        raise FileNotFoundError(f"HOMR training source is missing below {homr_source}")
    source = str(homr_source.resolve())
    if source not in sys.path:
        sys.path.insert(0, source)
    from homr.circle_of_fifths import strip_naturals
    from homr.transformer.configs import default_config
    from training.omr_datasets.convert_lieder import MeasureCutter, _count_staffs, contains_only_supported_clefs, is_grandstaff
    from training.omr_datasets.convert_musetrainer import _context_at_measure, _tokens_to_svg
    from training.omr_datasets.music_xml_parser import music_xml_file_to_tokens
    from training.transformer.training_vocabulary import calc_ratio_of_tuplets, check_token_lines, token_lines_to_str
    return locals()


def materialize(
    records: list[dict[str, Any]], output: Path, homr_source: Path, train_renders: int = 2
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    api = _homr_api(homr_source)
    browser = _find_browser()
    image_dir, token_dir, svg_dir = output / "images", output / "tokens", output / "svg"
    for directory in (image_dir, token_dir, svg_dir):
        directory.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for source_index, record in enumerate(records, start=1):
        try:
            voices = api["music_xml_file_to_tokens"](str(record["musicxml"]))
            if not voices:
                raise ValueError("HOMR parser produced no voices")
            created = 0
            for voice_index, voice in enumerate(voices):
                if api["_count_staffs"](voice) < 1 or len(voice) < 2:
                    continue
                staff_count = 2 if api["is_grandstaff"](voice) else 1
                for window_index, start in enumerate(range(0, len(voice), WINDOW_SIZE)):
                    measures = voice[start : start + WINDOW_SIZE]
                    clefs, key, time_symbol = api["_context_at_measure"](voice, start, staff_count)
                    cutter = api["MeasureCutter"](list(measures))
                    cutter.clefs, cutter.key, cutter.time = clefs, key, time_symbol
                    tokens = cutter.extract_measures(len(measures), always_include_time=True)
                    tokens = api["strip_naturals"](tokens)
                    if api["calc_ratio_of_tuplets"](tokens) > 0.2:
                        raise ValueError("tuplet ratio exceeds HOMR training limit")
                    if not api["contains_only_supported_clefs"](tokens):
                        raise ValueError("unsupported clef")
                    if len(tokens) > api["default_config"].max_seq_len - 2:
                        raise ValueError("token sequence exceeds HOMR model limit")
                    api["check_token_lines"](tokens)
                    token_text = api["token_lines_to_str"](tokens)
                    variants = train_renders if record["split"] == "train" else 1
                    for variant in range(variants):
                        sample_id = f"{record['id']}-v{voice_index}-w{window_index}-r{variant}"
                        token_path = token_dir / f"{sample_id}.tokens"
                        svg_path = svg_dir / f"{sample_id}.svg"
                        image_path = image_dir / f"{sample_id}.jpg"
                        cached = False
                        if token_path.is_file() and svg_path.is_file() and image_path.is_file():
                            try:
                                if token_path.read_text(encoding="utf-8") == token_text:
                                    with Image.open(image_path) as existing:
                                        existing.verify()
                                    with Image.open(image_path) as existing:
                                        width, height = existing.size
                                    cached = width > 0 and height > 0 and svg_path.stat().st_size > 0
                            except OSError:
                                cached = False
                        if not cached:
                            token_path.write_text(token_text, encoding="utf-8", newline="\n")
                            state = random.getstate()
                            random.seed(int(hashlib.sha256(sample_id.encode()).hexdigest()[:16], 16))
                            try:
                                svg = api["_tokens_to_svg"](tokens)
                            finally:
                                random.setstate(state)
                            if not svg:
                                raise ValueError("Verovio could not render HOMR tokens")
                            width, height = _rasterize_svg(svg, svg_path, image_path, browser)
                        samples.append(
                            {
                                "id": sample_id, "sourceId": record["id"], "group": record["group"],
                                "split": record["split"], "labelTier": record["labelTier"],
                                "imageDomain": "synthetic-token-render",
                                "voice": voice_index, "window": window_index, "measureStart": start + 1,
                                "measureCount": len(measures), "tokenCount": len(tokens),
                                "image": image_path.resolve(), "tokens": token_path.resolve(),
                                "width": width, "height": height,
                            }
                        )
                        created += 1
            if created == 0:
                raise ValueError("no supported HOMR staff windows")
            print(f"[{source_index}/{len(records)}] {record['id']}: {created} samples", flush=True)
        except Exception as exc:
            rejected.append({"source": record["id"], "reason": f"conversion_failed: {exc}"})
    return samples, rejected


def _index_path(path: Path, homr_source: Path) -> str:
    return Path(os.path.relpath(path.resolve(), homr_source.resolve())).as_posix()


def write_outputs(
    output: Path, homr_source: Path, sources: list[dict[str, Any]], samples: list[dict[str, Any]], rejected: list[dict[str, str]]
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    with (output / "manifest.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for sample in samples:
            serializable = {key: str(value) if isinstance(value, Path) else value for key, value in sample.items()}
            handle.write(json.dumps(serializable, ensure_ascii=False) + "\n")
    for split in ("train", "validation", "test"):
        lines = [
            f"{_index_path(sample['image'], homr_source)},{_index_path(sample['tokens'], homr_source)}\n"
            for sample in samples if sample["split"] == split
        ]
        (output / f"{split}-index.txt").write_text("".join(lines), encoding="utf-8", newline="\n")
    source_counts = Counter(record["split"] for record in sources)
    sample_counts = Counter(sample["split"] for sample in samples)
    tier_counts = Counter(record["labelTier"] for record in sources)
    group_splits: dict[str, set[str]] = {}
    for sample in samples:
        group_splits.setdefault(sample["group"], set()).add(sample["split"])
    leaks = sorted(group for group, splits in group_splits.items() if len(splits) > 1)
    real_image_samples = sum(sample.get("imageDomain") == "aligned-real-image" for sample in samples)
    unaligned_real_sources = sum(
        record.get("sourceImageDomain") == "document-level-real"
        and not record.get("realImageAligned")
        for record in sources
    )
    warnings: list[str] = []
    if not tier_counts.get("gold-human"):
        warnings.append("No human-confirmed transcriptions are available.")
    if real_image_samples == 0:
        warnings.append("No staff-aligned real-image training pairs are available; generated images are synthetic renders.")
    missing_splits = [split for split in ("train", "validation", "test") if not sample_counts.get(split)]
    if missing_splits:
        warnings.append(f"Missing generated split(s): {', '.join(missing_splits)}.")
    report = {
        "sourceRecords": len(sources), "generatedSamples": len(samples),
        "sourceSplits": dict(source_counts), "sampleSplits": dict(sample_counts),
        "labelTiers": dict(tier_counts), "rejected": len(rejected),
        "realImageSamples": real_image_samples,
        "unalignedRealSourceRecords": unaligned_real_sources,
        "crossSplitLeakage": leaks,
        "readyForTraining": bool(samples) and not leaks and not missing_splits,
        "warnings": warnings,
    }
    (output / "quality-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "rejected.json").write_text(json.dumps(rejected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def build(
    source: Path, review_root: Path, output: Path, homr_source: Path,
    *, limit: int | None = None, train_renders: int = 2, audit_only: bool = False,
) -> dict[str, Any]:
    published, rejected = collect_published_records(source.resolve())
    human, human_rejected = collect_human_review_records(review_root.resolve())
    rejected.extend(human_rejected)
    records = published + human
    if limit is not None:
        records = records[:limit]
    samples: list[dict[str, Any]] = []
    if not audit_only:
        samples, conversion_rejected = materialize(records, output.resolve(), homr_source.resolve(), train_renders)
        rejected.extend(conversion_rejected)
    return write_outputs(output.resolve(), homr_source.resolve(), records, samples, rejected)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build leakage-safe native HOMR fine-tuning data")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--homr-source", type=Path, default=DEFAULT_HOMR_SOURCE)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--train-renders", type=int, default=2)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    if args.train_renders < 1:
        parser.error("--train-renders must be at least 1")
    print(json.dumps(build(args.source, args.reviews, args.output, args.homr_source, limit=args.limit, train_renders=args.train_renders, audit_only=args.audit_only), indent=2))


if __name__ == "__main__":
    main()
