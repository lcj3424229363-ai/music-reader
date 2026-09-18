# Music Reader

Backend service for reading MusicXML/MIDI/OMR output and producing structured
music-analysis data.

## Current Scope

- Read `.musicxml`, `.xml`, `.mxl`, `.mid`, and `.midi` files.
- Accept image/PDF OMR input through the configured OMR path.
- Accept PhotoScore-exported MusicXML and convert it into compact AI context.
- Run structural MusicXML quality checks.
- Generate rule-based harmony and four-part analysis payloads.

The browser-based score editor and bundled sample/evaluation datasets have been
moved out of this repository. Use an external notation or OMR tool, such as
PhotoScore, to create/export MusicXML, then submit that file to this backend.

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

Build AI context from PhotoScore MusicXML:

```text
POST http://127.0.0.1:8765/api/photoscore/ai-context
form-data:
  file=<PhotoScore-exported MusicXML>
  measureLimit=32
```
