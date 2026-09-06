import shutil
import subprocess
from pathlib import Path

import pytest

import omr


def test_repeated_image_transcription_uses_fresh_output(monkeypatch, tmp_path):
    source = tmp_path / "score.png"
    source.write_bytes(b"fake image")
    fake_homr = tmp_path / "homr.exe"
    fake_homr.write_bytes(b"")
    monkeypatch.setattr(omr, "find_homr", lambda: fake_homr)

    def fake_run(command, *, cwd, **kwargs):
        Path(cwd, command[1]).with_suffix(".musicxml").write_text("<score/>", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(omr.subprocess, "run", fake_run)
    output_dir = tmp_path / "output"
    first = omr.transcribe_with_audiveris(source, output_dir)
    second = omr.transcribe_with_audiveris(source, output_dir)

    assert first["exportedPath"] != second["exportedPath"]
    assert Path(first["exportedPath"]).is_file()
    assert Path(second["exportedPath"]).is_file()


def test_pdf_is_rendered_page_by_page_and_merged(monkeypatch, tmp_path):
    fitz = pytest.importorskip("fitz")
    music21 = pytest.importorskip("music21")
    source = tmp_path / "two-pages.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "page one")
    document.new_page().insert_text((72, 72), "page two")
    document.save(source)
    document.close()

    template = tmp_path / "template.musicxml"
    score = music21.stream.Score()
    part = music21.stream.Part()
    measure = music21.stream.Measure(number=1)
    measure.append(music21.note.Note("C4", quarterLength=1))
    part.append(measure)
    score.insert(0, part)
    score.write("musicxml", fp=str(template))

    fake_homr = tmp_path / "homr.exe"
    fake_homr.write_bytes(b"")
    monkeypatch.setattr(omr, "find_homr", lambda: fake_homr)
    monkeypatch.setattr(omr.shutil, "which", lambda _name: None)

    calls = []

    def fake_run_homr(_homr, page, target_dir, _timeout):
        calls.append(page)
        output = target_dir / f"recognized-{len(calls)}.musicxml"
        shutil.copy2(template, output)
        return output, "ok", ""

    monkeypatch.setattr(omr, "_run_homr", fake_run_homr)
    result = omr.transcribe_with_audiveris(source, tmp_path / "output")
    parsed = music21.converter.parse(result["exportedPath"])

    assert result["engine"] == "homr+pymupdf"
    assert len(calls) == 2
    assert len(list(parsed.parts[0].getElementsByClass(music21.stream.Measure))) == 2
