from pathlib import Path
import subprocess

from fastapi.testclient import TestClient
from music21 import converter

import server
from reader import read_score
from reader_to_editor import reader_payload_to_editor
from server import _musicxml_import_route, _read_source_musicxml


client = TestClient(server.app)


def test_frontend_propagates_import_projection_to_solver_request():
    app_js = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")

    assert "payload.sourceProjection = activeSourceProjection;" in app_js
    assert 'fetch("/api/score-ir/apply-corrections"' in app_js
    assert "activeScoreIrRevision !== editorRevision" in app_js
    assert 'bindEvent(applyOmrCorrectionsButton, "click", applySelectedOmrCorrections);' in app_js
    assert '".tif", ".tiff", ".bmp", ".pdf"' in app_js


FRONTEND_STYLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list><score-part id="P1"><part-name>Manual Score</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>48</divisions>
        <key><fifths>0</fifths><mode>minor</mode></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <staves>2</staves>
        <clef number="1"><sign>G</sign><line>2</line></clef>
        <clef number="2"><sign>F</sign><line>4</line></clef>
      </attributes>
      <note><pitch><step>A</step><octave>4</octave></pitch><duration>192</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>192</duration></backup>
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>192</duration><voice>2</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>192</duration></backup>
      <note><pitch><step>C</step><octave>3</octave></pitch><duration>192</duration><voice>3</voice><type>whole</type><staff>2</staff></note>
      <backup><duration>192</duration></backup>
      <note><rest/><duration>96</duration><voice>4</voice><type>half</type><staff>2</staff></note>
      <note><pitch><step>A</step><octave>2</octave></pitch><duration>96</duration><voice>4</voice><type>half</type><staff>2</staff></note>
    </measure>
  </part>
</score-partwise>
"""

FRONTEND_CANONICAL_XML = FRONTEND_STYLE_XML.replace(
    '<part-list>',
    '<identification><miscellaneous><miscellaneous-field name="music-reader-schema">manual-score-v1</miscellaneous-field></miscellaneous></identification><part-list>',
)


def test_frontend_style_musicxml_preserves_key_voices_and_rests(tmp_path: Path):
    score_path = tmp_path / "frontend.musicxml"
    score_path.write_text(FRONTEND_STYLE_XML, encoding="utf-8")

    raw = read_score(score_path)
    editor = reader_payload_to_editor(raw)

    assert raw["parts"][0]["measures"][0]["keySignature"]["declaredLabel"] == "A minor"
    assert editor["key"] == "A minor"
    assert editor["timeSignature"] == "4/4"
    assert [len(editor[name][0]) for name in (
        "sopranoMeasures", "altoMeasures", "tenorMeasures", "bassMeasures"
    )] == [1, 1, 1, 2]
    assert editor["bassMeasures"][0][0]["kind"] == "rest"
    assert all(
        sum(entry["units"] for entry in editor[name][0]) == 32
        for name in ("sopranoMeasures", "altoMeasures", "tenorMeasures", "bassMeasures")
    )


def test_frontend_loader_writes_all_satb_voices():
    source = (Path(__file__).parents[1] / "web" / "app.js").read_text(encoding="utf-8")
    assert 'writeVoice("treble", 1, sopranoMeasures);' in source
    assert 'writeVoice("treble", 2, altoMeasures);' in source
    assert 'writeVoice("bass",   1, tenorMeasures);' in source
    assert 'writeVoice("bass",   2, bassMeasures);' in source


def test_plain_musicxml_is_carried_as_canonical_source(tmp_path: Path):
    score_path = tmp_path / "canonical.musicxml"
    score_path.write_text(FRONTEND_STYLE_XML, encoding="utf-8")

    assert _read_source_musicxml(score_path) == FRONTEND_STYLE_XML
    assert _read_source_musicxml(tmp_path / "packed.mxl") is None


def test_parse_score_endpoint_returns_exact_canonical_xml():
    response = client.post(
        "/parse-score",
        files={"file": ("canonical.musicxml", FRONTEND_STYLE_XML.encode("utf-8"), "application/vnd.recordare.musicxml+xml")},
    )

    assert response.status_code == 200
    assert response.json()["sourceMusicXml"] == FRONTEND_STYLE_XML
    assert response.json()["importRoute"] == "reader-projection"
    assert response.json()["solverEligibility"]["melody"]["eligible"] is True


def test_parse_score_endpoint_marks_frontend_owned_xml_as_canonical():
    response = client.post(
        "/parse-score",
        files={"file": ("frontend.musicxml", FRONTEND_CANONICAL_XML.encode("utf-8"), "application/vnd.recordare.musicxml+xml")},
    )

    assert response.status_code == 200
    assert response.json()["importRoute"] == "frontend-canonical"
    assert response.json()["sourceMusicXml"] == FRONTEND_CANONICAL_XML


def test_only_frontend_marked_xml_uses_the_canonical_frontend_route():
    source = (Path(__file__).parents[1] / "web" / "app.js").read_text(encoding="utf-8")
    assert 'editorPayload?.importRoute === "frontend-canonical"' in source
    assert "loadParsedMusicXml(parseMusicXmlText(editorPayload.sourceMusicXml)," in source
    assert _musicxml_import_route(FRONTEND_STYLE_XML) == "reader-projection"
    assert _musicxml_import_route(
        '<miscellaneous-field name="music-reader-schema">manual-score-v1</miscellaneous-field>'
    ) == "frontend-canonical"


def test_frontend_export_is_readable_by_music21():
    project_root = Path(__file__).parents[1]
    script = """
const { loadMusicXmlFunctions } = require('./tests/musicxml_harness');
const { fixture } = require('./tests/musicxml_fixture');
process.stdout.write(loadMusicXmlFunctions().buildMusicXml(fixture()));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    score = converter.parseData(completed.stdout, format="musicxml")
    # music21 splits one MusicXML piano part into one internal Part per staff.
    assert len(score.parts) == 2
    assert all(len(part.getElementsByClass("Measure")) == 1 for part in score.parts)
