# Music Reader

Backend service for reading MusicXML/MIDI/OMR output, converting recognized
scores into solver input, and producing four-part harmony answers.

## Current Scope

- Read `.musicxml`, `.xml`, `.mxl`, `.mid`, and `.midi` files.
- Accept image/PDF OMR input through the configured OMR path.
- Accept PhotoScore-exported MusicXML as the preferred recognition result.
- Run structural MusicXML quality checks.
- Convert recognized scores into the internal editor/solver representation.
- Generate rule-based Sposobin-style harmony and four-part answer payloads.
- Render the four-part answer as visible score notation and export PNG.
- Explain solver output through the LLM/agent endpoints when configured.
- Provide a lightweight upload frontend for score photos, PDFs, MusicXML, and MIDI.

The browser-based score-making editor page and bundled sample/evaluation
datasets have been moved out of this repository. The score-photo upload page,
recognition, MusicXML parsing, solver, answer generation, and AI explanation
chain remain in the project.

Use an external notation or OMR tool, such as PhotoScore, to create/export
MusicXML, then submit that file to this backend for analysis and answer
generation.

## End-to-End Answer Chain

Typical PhotoScore workflow:

```text
PhotoScore image/PDF recognition
  -> export MusicXML
  -> POST /api/photoscore/solve
  -> returns the final answer plus text/quality review
  -> POST /api/render/answer.png for a visible score image
  -> optional POST /api/explain or /agent/explain
```

The PhotoScore path treats MusicXML notes, rests, rhythm, voices, clefs, key
signatures, and time signatures as the musical source of truth. Titles,
composer text, lyrics, page text, and OCR-like text are collected under
`textReview` only; they do not drive the solver unless a user confirms them as
exercise constraints. VLM review is reserved for suspected notation regions or
user-selected crops and should produce correction suggestions rather than
silently replacing the PhotoScore XML.

Typical direct OMR workflow:

```text
POST /read-score or /api/omr/enhanced-parse
  -> returns parsed score data and readiness checks
  -> POST /solve-melody or /four-part-answer
  -> optional POST /api/explain or /agent/explain
```

## Useful Commands

```powershell
python reader.py path\to\score.musicxml --pretty
python photoscore_ai.py path\to\photoscore-export.xml --pretty
python server.py
```

Open the upload frontend after starting the server:

```text
http://127.0.0.1:8765/
```

Health check:

```text
GET http://127.0.0.1:8765/health
```

Read a score:

```text
POST http://127.0.0.1:8765/read-score
form-data: file=<MusicXML/MIDI/image/PDF>
```

Parse MusicXML into solver/editor data:

```text
POST http://127.0.0.1:8765/parse-score
form-data: file=<MusicXML file>
```

Internal/debug: inspect the compact PhotoScore analysis payload:

```text
POST http://127.0.0.1:8765/api/photoscore/ai-context
form-data:
  file=<PhotoScore-exported MusicXML>
  measureLimit=32
```

This endpoint is not the main product flow. It exists so developers can inspect
what musical facts the backend extracted before solving.

Run the PhotoScore XML experiment chain and return the answer:

```text
POST http://127.0.0.1:8765/api/photoscore/solve
form-data:
  file=<PhotoScore-exported MusicXML>
  measureLimit=32
  autoSolve=true
```

Render a solved answer as notation:

```text
POST http://127.0.0.1:8765/api/render/answer.svg
POST http://127.0.0.1:8765/api/render/answer.png
Content-Type: application/json

<the /api/photoscore/solve or /solve-melody response>
```

The upload frontend calls these render endpoints automatically after a successful
solve and exposes a PNG export button.

Generate a four-part answer:

```text
POST http://127.0.0.1:8765/solve-melody
Content-Type: application/json

{
  "key": "C",
  "timeSignature": "4/4",
  "questionType": "melody-given",
  "melodyMeasures": [
    [
      {"step": "C", "octave": 4, "duration": "4"},
      {"step": "D", "octave": 4, "duration": "4"},
      {"step": "E", "octave": 4, "duration": "4"},
      {"step": "F", "octave": 4, "duration": "4"}
    ]
  ]
}
```

`/four-part-answer` accepts the same payload and forwards to the same solver.

Explain an answer:

```text
POST http://127.0.0.1:8765/api/explain
POST http://127.0.0.1:8765/agent/explain
```

## Technology Stack

- Python: FastAPI backend, score readers, MusicXML quality checks, OMR pipeline,
  solver, built-in score renderer, and AI/agent integration.
- HTML/CSS/JavaScript: lightweight upload frontend only.
- External recognition tools: PhotoScore exports MusicXML for the backend;
  Audiveris/HOMR-style OMR support is used when configured for image/PDF input.

The built-in renderer is intentionally dependency-light and designed to make the
answer visible immediately. If MuseScore, LilyPond, or Verovio is installed
later, the same render endpoints can be upgraded to professional engraving.

The current repository is therefore not Python-only, but Python is the core
runtime. The browser code is intentionally small and only handles file upload
and result display.
