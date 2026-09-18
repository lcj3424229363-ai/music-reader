# Music Reader

Backend service for reading MusicXML/MIDI/OMR output, converting recognized
scores into solver input, and producing four-part harmony answers plus
AI-readable analysis.

## Current Scope

- Read `.musicxml`, `.xml`, `.mxl`, `.mid`, and `.midi` files.
- Accept image/PDF OMR input through the configured OMR path.
- Accept PhotoScore-exported MusicXML and convert it into compact AI context.
- Run structural MusicXML quality checks.
- Convert recognized scores into the internal editor/solver representation.
- Generate rule-based Sposobin-style harmony and four-part answer payloads.
- Explain solver output through the LLM/agent endpoints when configured.

The browser-based score-making editor page and bundled sample/evaluation
datasets have been moved out of this repository. The recognition, MusicXML
parsing, solver, answer generation, and AI explanation chain remains in the
backend.

Use an external notation or OMR tool, such as PhotoScore, to create/export
MusicXML, then submit that file to this backend for analysis and answer
generation.

## End-to-End Answer Chain

Typical PhotoScore workflow:

```text
PhotoScore image/PDF recognition
  -> export MusicXML
  -> POST /api/photoscore/ai-context or /parse-score
  -> POST /solve-melody or /four-part-answer
  -> optional POST /api/explain or /agent/explain
```

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

Build AI context from PhotoScore MusicXML:

```text
POST http://127.0.0.1:8765/api/photoscore/ai-context
form-data:
  file=<PhotoScore-exported MusicXML>
  measureLimit=32
```

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
