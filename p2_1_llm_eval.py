"""P2.1: Test DeepSeek API on 19 NEW SHTE cases with policy + 4 few-shot.

Designed for FAST iteration:
- 4 representative few-shot examples (covers 3 P1.3 classes + edge case)
- Strict 1-line-per-beat output format
- max_tokens=800 to bound cost
- output goes to JSONL file with prediction + actual gold + diff

Usage:
  $env:DEEPSEEK_API_KEY = 'sk-...'
  py -3 p2_1_llm_eval.py
"""
import os
import sys
import json
import time
import httpx
import re
from pathlib import Path
from collections import defaultdict

PROJECT = Path(r'C:\Users\Administrator\Documents\try\music-reader')
EVAL_DATA = Path(r'C:\Users\Administrator\Documents\try\eval-data')

# ---------------- CONFIG ----------------
MODEL = 'deepseek-chat'
TEMPERATURE = 0.0
MAX_TOKENS = 800
TIMEOUT = 60
OUT_DIR = PROJECT / 'p2_1_results'
SHTE = EVAL_DATA / 'extracted' / 'hamony dataset'
NEW_CASES = PROJECT / '_new_test_cases.json'
BASELINE_V2 = EVAL_DATA / 'eval' / 'baseline_v2' / 'cases'

# ---------------- PROMPT ----------------

SYSTEM = '''You are a chord-analysis assistant for the Sposobin SATB
4-part harmonization solver (v1.1, frozen).
You are given a (case_id, key, time_signature, chapter, melody,
gold SATB voicing) and must produce ONE LINE PER BEAT using the
strict output format below.

# CANONICAL FACTS (memorize)

**Baseline (K=3, frozen v1.1, 19 cases):**
  L1 (high-conf)         = 9.1%
  L1_internal (in-pool)  = 13.6%
  L2 (high-conf)         = 48.3%
  L3 (legality)          = 98.8%
  L4 (exact pitch)       = 10.9%
  profile_coverage       = 66.4%
**P1.0 Oracle ceiling:** L1_internal_max = 58.4%
**P1.3 distribution (69 P1.1 candidates):**
  immediate_loss=25, previous_path_starvation=19, global_scoring_mismatch=25
**P1.4 single-component fixability (22 of 69 = 32%):**
  8.6b=13, 8.5=5, 8.8=3, 8.4=2

# SCORING COMPONENTS (the 13+1 that matter)

  8.1 chord_membership  (+1/-5 per voice)        8.8  bass_stability (+1/+3)
  8.2 voice_range       (+0.5/-100)                8.9  chord_repetition (+0.2-1.1)
  8.3 cadence_soprano   (-3.0)                     8.10 common_tone (+0.4)
  8.4 doubling_rule     (pref*1.5, -3 doubled-3)    nct  bonus (+1-1.5)
  8.5 voice_leading     (-1.5 to +1)               8.7  cadence_bass (+1)
  8.6 melody_adherence  (+5/-100)                  8.7b c64_beat (+1.5-8)
  8.6b melody_tone_pref (+0.4 to +3.5)  *** 8.6b is the #1 lever ***
  8.7c ninth_melody     (+2.0)

# PROFILES (5 declarative whitelists)

  ch1-4_triad_only:     I, ii, IV, V, VI (major) / i, ii°, iv, v, VI (minor)
  ch5-7_triad_plus_v64: + V6/4
  ch8-20_v7:            + V7
  ch21-22_d7_ii7_vii7:  + ii7, vii7
  ch23_v9:              + D9

  CH1-4 minor EXCLUDES III and VII (Sposobin ch1-4 rule).
  Functions: T={1,3,6}, S={2,4}, D={5,7}.

# DIAGNOSTIC OUTPUT FORMAT (STRICT, one line per beat)

For each beat, output EXACTLY this format:
  beat N | <chord_roman> | solver_picks: <chord> | P1.3: <class> | fixer: <component>

Where:
  <chord_roman>  = your inferred chord (e.g. I, V6, ii°, V7, V6/4, I6)
  <chord>        = what the ACTUAL solver picked (use ? if unknown)
  <class>        = OK | immediate_loss | previous_path_starvation | global_scoring_mismatch
  <component>    = none | 8.1 | 8.5 | 8.6b | 8.8 | 8.4 (or blank if OK)

After the per-beat lines, output 3 summary lines:
  immediate_loss_fixes: <comma-separated beats that should be fixed>
  prev_path_beat: <beats where prev beam was the bottleneck>
  global_mismatch_beat: <beats where no beam helps>

Keep total output under 800 tokens.  No prose, no explanations.
'''


# 4 representative few-shot examples (one per P1.3 class + one OK)
FEW_SHOT = [
    # 1. immediate_loss (P1.4: 8.6b)
    {
        'user': '''case: ch11-01_F major | key: F | tsig: 4/4 | chapter: 11
melody: A4 G4 A4 C5 F5 E5 D5 C5
gold: (A4,C4,F3,D3) (G4,C4,A3,D3) (A4,C4,F3,D3) (C5,A4,F3,E3) (F5,C5,A3,F3) (E5,C5,A3,G3) (D5,A4,F3,A3) (C5,A4,F3,G3)
PROFILE: ch8-20_v7.  Diagnose.''',
        'assistant': '''beat 1 | V | solver_picks: V6/4 | P1.3: immediate_loss | fixer: 8.6b
beat 2 | I6 | solver_picks: I | P1.3: immediate_loss | fixer: 8.5
beat 3 | I | solver_picks: I | P1.3: OK | fixer:
beat 4 | V | solver_picks: V | P1.3: OK | fixer:
beat 5 | I | solver_picks: I | P1.3: OK | fixer:
beat 6 | I | solver_picks: I | P1.3: OK | fixer:
beat 7 | V7 | solver_picks: V7 | P1.3: OK | fixer:
beat 8 | I | solver_picks: I | P1.3: OK | fixer:
immediate_loss_fixes: 1, 2
prev_path_beat: none
global_mismatch_beat: none'''
    },
    # 2. previous_path_starvation
    {
        'user': '''case: ch16-01_E major | key: E | tsig: 4/4 | chapter: 16
melody: E5 D5 E5 G5 B4 A4 B4 E5
gold: (E5,B4,G3,E3) (D5,B4,G3,E3) (E5,B4,G3,E3) (G5,E5,B4,E3) (B4,G4,E4,B3) (A4,F4,E4,A3) (B4,G4,E4,B3) (E5,B4,G3,E3)
PROFILE: ch8-20_v7.  Diagnose.''',
        'assistant': '''beat 1 | I | solver_picks: vi | P1.3: immediate_loss | fixer: 8.6b
beat 2 | V6 | solver_picks: vi6 | P1.3: previous_path_starvation | fixer: none
beat 3 | I | solver_picks: V7 | P1.3: global_scoring_mismatch | fixer:
beat 4 | I | solver_picks: I | P1.3: OK | fixer:
beat 5 | IV6 | solver_picks: IV6 | P1.3: OK | fixer:
beat 6 | IV | solver_picks: vi6 | P1.3: immediate_loss | fixer: 8.5
beat 7 | V | solver_picks: V | P1.3: OK | fixer:
beat 8 | I | solver_picks: I | P1.3: OK | fixer:
immediate_loss_fixes: 1, 6
prev_path_beat: 2
global_mismatch_beat: 3'''
    },
    # 3. global_scoring_mismatch (gold rank > 5)
    {
        'user': '''case: ch14-01_C major | key: C | tsig: 4/4 | chapter: 14
melody: C5 D5 E5 C5 G4 C5 D5 E5
gold: (C5,G4,E4,C4) (D5,A4,F4,D4) (E5,G4,E4,C4) (C5,G4,E4,C4) (G4,E4,C4,G3) (C5,G4,E4,C4) (D5,F4,D4,A3) (E5,G4,E4,G3)
PROFILE: ch8-20_v7.  Diagnose.''',
        'assistant': '''beat 1 | I | solver_picks: V6 | P1.3: global_scoring_mismatch | fixer: 8.6b
beat 2 | ii | solver_picks: ii6 | P1.3: OK | fixer:
beat 3 | V | solver_picks: V | P1.3: OK | fixer:
beat 4 | I | solver_picks: I | P1.3: OK | fixer:
beat 5 | V | solver_picks: V | P1.3: OK | fixer:
beat 6 | I | solver_picks: I | P1.3: OK | fixer:
beat 7 | ii6/4 | solver_picks: ii6 | P1.3: OK | fixer:
beat 8 | V | solver_picks: V | P1.3: OK | fixer:
immediate_loss_fixes: none
prev_path_beat: none
global_mismatch_beat: 1'''
    },
    # 4. All OK (sanity check)
    {
        'user': '''case: ch9-01_F major | key: F | tsig: 4/4 | chapter: 9
melody: F5 A5 G5 C5 F5 A5 Bb5 A5
gold: (F5,C5,A4,F4) (A5,F5,C5,A4) (G5,E5,C5,B4) (C5,A4,F4,E4) (F5,C5,A4,F4) (A5,F5,C5,A4) (Bb5,F5,C5,Bb4) (A5,F5,C5,A4)
PROFILE: ch8-20_v7.  Diagnose.''',
        'assistant': '''beat 1 | I | solver_picks: I | P1.3: OK | fixer:
beat 2 | vi | solver_picks: vi | P1.3: OK | fixer:
beat 3 | IV | solver_picks: IV | P1.3: OK | fixer:
beat 4 | ii6 | solver_picks: ii6 | P1.3: OK | fixer:
beat 5 | I | solver_picks: I | P1.3: OK | fixer:
beat 6 | vi | solver_picks: vi | P1.3: OK | fixer:
beat 7 | V7 | solver_picks: V7 | P1.3: OK | fixer:
beat 8 | vi | solver_picks: vi | P1.3: OK | fixer:
immediate_loss_fixes: none
prev_path_beat: none
global_mismatch_beat: none'''
    },
]


# ---------------- API CALL ----------------

def call_deepseek(api_key, system, messages, model=MODEL,
                  max_tokens=MAX_TOKENS, temperature=TEMPERATURE):
    resp = httpx.post(
        'https://api.deepseek.com/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': model,
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature,
        },
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        return {'error': f'HTTP {resp.status_code}: {resp.text[:300]}'}
    j = resp.json()
    return {
        'content': j['choices'][0]['message']['content'],
        'usage': j.get('usage', {}),
        'model': j.get('model', model),
    }


# ---------------- DATA PREP ----------------

def extract_case(xml_path):
    """Extract (key, time_sig, melody, gold_satb) from SHTE XML.
    Uses our existing run_eval helper.
    """
    sys.path.insert(0, str(EVAL_DATA))
    try:
        from run_eval import extract_gold
    except Exception:
        return None
    g = extract_gold(xml_path)
    if g is None or 'error' in g:
        return None
    sol = g['voices']
    key = g['solver_key']
    tsig = g['time_sig']
    sg, ag, tg, bg = sol
    bpm = int(tsig.split('/')[0])
    n_beats = g['n_beats']
    n_measures = (n_beats + bpm - 1) // bpm
    # Build per-beat 4-tuples
    satb = []
    for i in range(n_beats):
        satb.append((sg[i], ag[i] if i < len(ag) else 'rest',
                     tg[i] if i < len(tg) else 'rest',
                     bg[i] if i < len(bg) else 'rest'))
    melody = sg
    return {'key': key, 'time_sig': tsig, 'melody': melody, 'gold_satb': satb,
            'case_id': xml_path.stem}


def build_user_prompt(case):
    """Build user prompt for one case (max 12 beats shown)."""
    beats = case['gold_satb'][:12]
    melody = case['melody'][:12]
    n = len(beats)
    lines = []
    for i, (s, a, t, b) in enumerate(beats):
        m = melody[i] if i < len(melody) else '?'
        lines.append(f'  beat {i+1}: melody={m} | gold=({s},{a},{t},{b})')
    beats_block = '\n'.join(lines)
    return f'''case: {case["case_id"]} | key: {case["key"]} | tsig: {case["time_sig"]} | chapter: {case["case_id"].split("-")[0].replace("ch","")}
melody: {' '.join(melody[:n])}
gold: {' '.join(f'({s},{a},{t},{b})' for s,a,t,b in beats)}
PROFILE: lookup from system prompt based on chapter.  Diagnose.'''


# ---------------- SCORING ----------------

def parse_prediction(text):
    """Parse the model's output into a list of {beat, chord, p13, fixer}."""
    out = []
    for line in text.split('\n'):
        line = line.strip()
        if not line.startswith('beat '):
            continue
        # Format: beat N | chord | solver_picks: X | P1.3: Y | fixer: Z
        m = re.match(
            r'beat\s+(\d+)\s*\|\s*(\S+)\s*\|\s*solver_picks:\s*(\S+)\s*\|\s*P1\.3:\s*(\S+)\s*\|\s*fixer:\s*(.*?)\s*$',
            line,
        )
        if m:
            out.append({
                'beat': int(m.group(1)),
                'gold': m.group(2),
                'solver': m.group(3),
                'p13': m.group(4),
                'fixer': m.group(5) or 'none',
            })
    return out


def get_actual_solver(case_id):
    """Load the actual solver output for a case from baseline_v2."""
    p = BASELINE_V2 / f'{case_id}.json'
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding='utf-8'))
    return d.get('solver_output', {})


def score_prediction(pred, case):
    """Compare model prediction to actual solver output.
    For each beat in pred, check if model's solver_picks matches actual.
    """
    actual = get_actual_solver(case['case_id'])
    if actual is None:
        return None
    actual_romans = actual.get('romans', [])
    matches = 0
    diffs = []
    for p in pred:
        beat_idx = p['beat'] - 1
        if beat_idx < len(actual_romans):
            actual_roman = actual_romans[beat_idx]
            if p['solver'].lower() == actual_roman.lower():
                matches += 1
            else:
                diffs.append({
                    'beat': p['beat'],
                    'model_says_solver_picked': p['solver'],
                    'actual_solver_picked': actual_roman,
                })
    return {'matches': matches, 'total': len(pred), 'diffs': diffs,
            'match_rate': matches / len(pred) if pred else 0}


# ---------------- MAIN ----------------

def main():
    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    if not api_key:
        print('ERROR: DEEPSEEK_API_KEY env not set')
        sys.exit(1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with NEW_CASES.open('r', encoding='utf-8') as f:
        cases_meta = json.load(f)
    print(f'Loaded {len(cases_meta)} new test cases')

    # Build system + few-shot messages
    messages = [{'role': 'system', 'content': SYSTEM}]
    for ex in FEW_SHOT:
        messages.append({'role': 'user', 'content': ex['user']})
        messages.append({'role': 'assistant', 'content': ex['assistant']})

    # Run all cases
    results = []
    for i, meta in enumerate(cases_meta):
        print(f'\n[{i+1}/{len(cases_meta)}] {meta["case_id"]} ({meta["chapter"]}) ...', end=' ', flush=True)
        xml = Path(meta['xml'])
        case = extract_case(xml)
        if case is None:
            print('SKIP (extract failed)')
            continue
        user_prompt = build_user_prompt(case)
        messages_with_user = messages + [{'role': 'user', 'content': user_prompt}]
        t0 = time.perf_counter()
        result = call_deepseek(api_key, SYSTEM, messages_with_user)
        elapsed = time.perf_counter() - t0
        if 'error' in result:
            print(f'ERROR: {result["error"]}')
            continue
        pred = parse_prediction(result['content'])
        score = score_prediction(pred, case)
        results.append({
            'case_id': meta['case_id'],
            'chapter': meta['chapter'],
            'latency_s': round(elapsed, 2),
            'usage': result['usage'],
            'prediction': pred,
            'score': score,
        })
        n_pred = len(pred)
        match_rate = score['match_rate'] if score else 0
        print(f'{n_pred} beats parsed | match_rate={match_rate:.0%} | {elapsed:.1f}s')

    # Save results
    out_jsonl = OUT_DIR / 'predictions.jsonl'
    with out_jsonl.open('w', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'\nWrote: {out_jsonl}')

    # Aggregate stats
    n = len(results)
    if n > 0:
        # New cases aren't in baseline_v2, so score=None.
        # We instead compute: model gold inference vs actual gold
        # (did the model correctly identify the chord at each beat?)
        scored = [r for r in results if r['score']]
        # Compute gold-match rate from pred
        total_gold_match = 0
        total_gold_total = 0
        for r in results:
            for p in r['prediction']:
                # We don't have a direct "actual gold" string here, but
                # we can use the gold SATB voicing in the case to
                # reverse-infer.  However, that's a separate computation.
                # For now, just count predictions.
                total_gold_total += 1
                # p['gold'] is the model's inference; we can't directly
                # verify without re-running roman_inference.
                pass

        total_cost = sum(
            (r['usage'].get('prompt_tokens', 0) + r['usage'].get('completion_tokens', 0)) * 0.0001
            for r in results  # rough: 0.1 yuan per 1K tokens
        )
        avg_latency = sum(r['latency_s'] for r in results) / n
        print(f'\n=== Aggregate ===')
        print(f'Cases: {n}')
        print(f'Total beats parsed: {sum(len(r["prediction"]) for r in results)}')
        print(f'Avg latency: {avg_latency:.2f}s')
        print(f'Total tokens: {sum(r["usage"].get("total_tokens", 0) for r in results):,}')
        print(f'Estimated cost: {total_cost:.2f} yuan (~${total_cost/7:.2f})')
        if not scored:
            print('(no scored cases — these are NEW test cases not in baseline_v2)')
            print(' -> re-evaluate by re-running the actual solver on these cases and')
            print('    comparing model solver_picks to actual solver romans.')


if __name__ == '__main__':
    main()
