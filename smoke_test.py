from __future__ import annotations

import tempfile
from pathlib import Path

from music21 import chord, key, meter, note, stream

from reader import read_score


def build_sample_score() -> stream.Score:
    score = stream.Score()
    part = stream.Part()
    part.partName = "Piano"

    measure_1 = stream.Measure(number=1)
    measure_1.append(key.KeySignature(0))
    measure_1.append(meter.TimeSignature("4/4"))
    measure_1.append(chord.Chord(["C4", "E4", "G4"], quarterLength=2))
    measure_1.append(chord.Chord(["A3", "C4", "E4"], quarterLength=2))

    measure_2 = stream.Measure(number=2)
    measure_2.append(chord.Chord(["D4", "F4", "A4"], quarterLength=2))
    measure_2.append(chord.Chord(["G3", "B3", "D4", "F4"], quarterLength=2))

    measure_3 = stream.Measure(number=3)
    measure_3.append(note.Note("C4", quarterLength=4))

    part.append([measure_1, measure_2, measure_3])
    score.insert(0, part)
    return score


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="music-reader-smoke-") as temp_dir:
        sample_path = Path(temp_dir) / "sample.musicxml"
        build_sample_score().write("musicxml", fp=str(sample_path))
        result = read_score(sample_path)

    assert result["summary"]["status"] == "readable", result["warnings"]
    assert result["summary"]["partCount"] == 1
    assert result["summary"]["measureCount"] == 3
    assert result["parts"][0]["measures"][0]["eventCount"] == 2
    assert result["harmonyTimeline"][0]["harmonies"][0]["root"] == "C"

    print("Music reader smoke test passed.")
    print(f"Analyzed key: {result['summary']['analyzedKey'].get('label')}")
    print(f"Measures: {result['summary']['measureCount']}")
    print(f"First harmony: {result['harmonyTimeline'][0]['harmonies'][0]['commonName']}")


if __name__ == "__main__":
    main()

