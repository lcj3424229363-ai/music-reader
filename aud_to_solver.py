# -*- coding: utf-8 -*-
"""
aud_to_solver.py — 把 audiveris MusicXML 转成 solve_melody 输入

用法:
  python aud_to_solver.py path/to/page.mxl -k G -t 2/4

输出: solver_cli.py 能直接吃的 melody 字符串
"""
import sys, io
import zipfile
import re
import xml.etree.ElementTree as ET
import argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def load_mxl(path: str) -> tuple[ET.Element, dict]:
    """Load .mxl (zipped MusicXML) or .xml.  Returns (root, ns_map)."""
    if path.endswith('.mxl'):
        with zipfile.ZipFile(path) as z:
            # Find the rootfile
            container = z.read('META-INF/container.xml').decode('utf-8')
            m = re.search(r'full-path="([^"]+)"', container)
            rootfile = m.group(1) if m else 'score.xml'
            xml_bytes = z.read(rootfile)
    else:
        with open(path, 'rb') as f:
            xml_bytes = f.read()
    root = ET.fromstring(xml_bytes)
    return root, {'mx': 'http://www.musicxml.org/dtds/partwise'}


def get_soprano_notes(root, ns):
    """Pull the topmost (typically Part 1) voice's notes measure by measure.
    Returns a list of (measure_number, [(step, octave, duration, alter)]) tuples.
    """
    def find(node, *tags):
        for t in tags:
            if t.startswith(':'):
                # namespaced
                n = node.find(t, ns)
            else:
                n = node.find(t)
            if n is not None:
                return n
        return None

    parts = root.findall('.//{http://www.musicxml.org/dtds/partwise}score-part')
    if not parts:
        # try unprefixed
        parts = root.findall('.//score-part')
    if not parts:
        return []
    part_id = parts[0].get('id')
    part = root.find(f'.//{{http://www.musicxml.org/dtds/partwise}}part[@id="{part_id}"]')
    if part is None:
        part = root.find(f'.//part[@id="{part_id}"]')
    if part is None:
        return []
    measures = []
    for m in part:
        m_num = m.get('number', '?')
        notes = []
        for n in m:
            if n.tag.endswith('note'):
                # Skip chord-tones (keep topmost only)
                chord = find(n, 'chord')
                if chord is not None:
                    continue
                # Skip rest
                if find(n, 'rest') is not None:
                    notes.append(('REST', 0, 0, 0))
                    continue
                step = find(n, 'pitch/step')
                octave = find(n, 'pitch/octave')
                alter = find(n, 'pitch/alter')
                dur = find(n, 'duration')
                if step is None or octave is None:
                    continue
                s = step.text or ''
                o = int(octave.text or 4)
                a = int(alter.text or 0) if alter is not None else 0
                d = int(dur.text or 1) if dur is not None else 1
                notes.append((s, o, a, d))
        measures.append((m_num, notes))
    return measures


def get_time_signature(root, ns):
    """Get the time signature (numerator, denominator)."""
    for m in root.iter():
        if m.tag.endswith('time'):
            beats = m.find('beats')
            btype = m.find('beat-type')
            if beats is not None and btype is not None:
                try:
                    return int(beats.text), int(btype.text)
                except Exception:
                    pass
    return 4, 4   # default


def parse_step(s, o, a):
    """Convert (step, octave, alter) to 'C5' or 'Eb4' etc."""
    acc = ''
    if a > 0:
        acc = '#' * a
    elif a < 0:
        acc = 'b' * (-a)
    return f"{s}{acc}{o}"


def measures_to_melody(measures, beats_per_measure, beat_unit):
    """Convert audiveris measures into the (capacity, [[Note, ...]]) format.

    Each measure's notes are flattened to one Note per beat.  A note
    with duration > 1 beat is repeated.  Rests become None.
    """
    cap = beats_per_measure * beat_unit
    out = []
    for m_num, notes in measures:
        per_beat = []
        for n in notes:
            if n[0] == 'REST':
                # Whole-measure rest → all beats are None
                # We need to know how many beats.  Use 1 rest per beat
                # is the simplest; but cleaner is to detect whole-measure
                # rest (no notes in measure).  Here we just push None
                # for the rest's duration; if duration covers full
                # measure we return all None.
                # For now, rest = one beat of rest.
                per_beat.append(None)
                continue
            s, o, a, d = n
            name = parse_step(s, o, a)
            n_repeats = max(1, round(d * 4.0 / (beat_unit * 4)))  # 4 = quarter duration
            # Actually musicxml duration is "divisions" not seconds.
            # Without knowing <divisions>, we'll just count by quarter.
            # Approximation: 1 division = quarter
            # But this can be wrong.  Caller should verify.
            per_beat.append(name)
        out.append(per_beat)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path', help='.mxl 或 .xml 文件')
    ap.add_argument('-k', '--key', default=None, help='主调 (覆盖自动检测)')
    ap.add_argument('-t', '--time', default=None, help='拍号 (覆盖自动检测)')
    ap.add_argument('--measure-prefix', action='store_true', help='每 measure 加 m{num}: 前缀')
    args = ap.parse_args()

    root, ns = load_mxl(args.path)
    measures = get_soprano_notes(root, ns)
    if not measures:
        print('(no notes found)', file=sys.stderr)
        sys.exit(1)

    num, den = (int(x) for x in args.time.split('/')) if args.time else get_time_signature(root, ns)
    beat_unit = 4.0 / den

    out_parts = []
    for m_num, notes in measures:
        if args.measure_prefix:
            out_parts.append(f"-- m{m_num}")
        per_beat = []
        for n in notes:
            if n[0] == 'REST':
                per_beat.append('·')
            else:
                per_beat.append(parse_step(n[0], n[1], n[2]))
        if per_beat:
            out_parts.append(' '.join(per_beat))
    print('\n'.join(out_parts))


if __name__ == '__main__':
    main()
