"""DEPRECATED — superseded by solver.py (Sposobin P0-P8).

This module previously implemented a music21-based 5-chord-pool four-part
harmonizer.  It was the original four_part.py used by the /four-part-answer
endpoint.  As of 2026-08-09 (P8 / Level 2 integration) the Sposobin-aware
solver (solver.py) handles BOTH melody-given and bass-given problems
natively, and /four-part-answer now forwards to the same code path as
/solve-melody.

This file is kept only as a stub so that old import statements (e.g. in
external scripts) don't break.  Do not add new functionality here.  If
you need the legacy behaviour, see git history prior to 2026-08-09.

Replacement entry points (use these instead):
  * soprano-given: solver.solve_melody(key, ts, melody_pitches, ...)
  * bass-given:    solver.solve_melody(key, ts, melody_pitches, bass_pitches=...)
  * HTTP:          POST /solve-melody  (accepts questionType='melody' or 'bass')
"""

from __future__ import annotations

# All legacy code removed.  This stub exists only so old `import four_part`
# statements don't break.  See module docstring for the migration path.
