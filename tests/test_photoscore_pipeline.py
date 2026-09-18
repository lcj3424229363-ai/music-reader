import json

from fastapi.testclient import TestClient

import server
from photoscore_ai import extract_musicxml_text_review


client = TestClient(server.app)


PHOTOSCORE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <work><work-title>Do not put this title in the answer</work-title></work>
  <movement-title>OCR PAGE NOISE</movement-title>
  <identification><creator type="composer">Unknown OCR Name</creator></identification>
  <credit><credit-words>Given melody, but confirm manually</credit-words></credit>
  <part-list>
    <score-part id="P1"><part-name>Soprano</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note>
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>1</duration><voice>1</voice><type>quarter</type>
        <lyric><text>la</text></lyric>
      </note>
      <note>
        <pitch><step>D</step><octave>4</octave></pitch>
        <duration>1</duration><voice>1</voice><type>quarter</type>
      </note>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>1</duration><voice>1</voice><type>quarter</type>
      </note>
      <note>
        <pitch><step>F</step><octave>4</octave></pitch>
        <duration>1</duration><voice>1</voice><type>quarter</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""


def test_photoscore_text_review_keeps_non_musical_text_out_of_solver(tmp_path):
    score = tmp_path / "photoscore.xml"
    score.write_text(PHOTOSCORE_XML, encoding="utf-8")

    review = extract_musicxml_text_review(score)

    assert review["ignoredForSolving"] is True
    assert any(item["text"] == "OCR PAGE NOISE" for item in review["items"])
    assert any(item["text"] == "la" for item in review["items"])
    assert review["possibleConstraints"][0]["requiresConfirmation"] is True


def test_photoscore_solve_endpoint_reports_answer_without_text_noise():
    response = client.post(
        "/api/photoscore/solve",
        files={"file": ("photoscore.xml", PHOTOSCORE_XML.encode("utf-8"), "application/xml")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow"] == "photoscore-musicxml-to-answer-v1"
    assert payload["inputPolicy"]["textIgnoredForSolving"] is True
    assert payload["textReview"]["items"]
    answer_text = json.dumps(payload["answer"], ensure_ascii=False)
    assert "OCR PAGE NOISE" not in answer_text
    assert "Unknown OCR Name" not in answer_text
