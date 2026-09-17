# ScoreIR v1

`ScoreIR` is the canonical score contract between import, validation, editor
projection, and the SATB solver. MusicXML remains the interchange and archival
format; ABC may be added as an optional serialization but is not authoritative.

## Main path

```text
image/PDF -> HOMR MusicXML -> reader -> ScoreIR -> validation
                                             |-> editor projection
                                             |-> SATB solver projection
                                             `-> MusicXML export (planned)
```

The legacy `parts` and editor fields remain available during migration. New code
must prefer `scoreIr` and must inspect `scoreIrValidation` and `editorProjection`
before solving.

## Timing

`onset`, `duration`, `expectedDuration`, and `actualDuration` are rational strings
such as `0/1`, `1/4`, or `85/256`. They must not be converted to floating point in
the canonical layer. Floating-point values exist only in legacy adapters.

## Events

Every event has a stable id and includes:

- `kind`: `note`, `rest`, or `chord`
- `voice` and `staff`
- exact `onset` and `duration`
- spelled pitches (`step`, `alter`, `octave`, `display`, `pitchClass`)
- dots, grace state, ties, and tuplet ratios
- provenance for HOMR/VLM/human changes

## Projection policy

The current teaching editor is intentionally narrower than ScoreIR. It supports
two selected parts, at most two simultaneous voices per part, and a bounded note
duration vocabulary. `editorProjection.lossless` is false whenever conversion
would reduce chords, ignore parts/voices, quantize timing, or omit notation.

Critical losses (`DURATION_QUANTIZED`, ignored parts/voices, or chord reduction)
make `solverEligibility` false. This prevents the SATB solver from silently using
musically changed input. The browser also sends this projection report back as
`sourceProjection`; `/solve-melody` enforces the same rule on the server.

## API

`POST /api/score-ir/validate` accepts a ScoreIR JSON object and returns structural
errors, warnings, and part/event/note counts.

`POST /api/score-ir/apply-corrections` accepts ScoreIR plus a bounded list of
event replacements. Corrections use whole-note onset/duration units and SATB role
names. They are rejected unless `confirmed` is true, each correction matches one
existing event, and the complete patched score passes validation. VLM output is
therefore a review proposal, never an automatic whole-document rewrite.
The response also contains `editorPayload`, regenerated from the validated ScoreIR.
For persisted OMR review runs, submitted corrections must be members of that run's
VLM proposal set; confirmed output is saved separately from immutable HOMR XML.
