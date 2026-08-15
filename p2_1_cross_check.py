"""Cross-check LLM predictions against actual solver + inferred gold roman.

For each of 19 NEW cases, compare:
  (1) LLM gold (predicted)        vs inferred gold (from gold voicing)
  (2) LLM solver_picks (predicted) vs actual solver.romans
  (3) LLM P1.3 class consistency  vs actual agreement
      - If LLM says OK, then solver_picks should equal gold
      - If LLM says a fixer class, then solver_picks != gold
  (4) LLM fixer component         vs which component actually scored higher

Output: aggregate accuracy + per-case breakdown.
"""
import sys
import json
from pathlib import Path
from collections import Counter, defaultdict

PROJECT = Path(r'C:\Users\Administrator\Documents\try\music-reader')
EVAL_DATA = Path(r'C:\Users\Administrator\Documents\try\eval-data')
sys.path.insert(0, str(EVAL_DATA / 'evaluation'))
sys.path.insert(0, str(EVAL_DATA / 'evaluation' / 'frozen'))

from solver import Note, Key
from roman_inference import infer_roman

PREDICTIONS = PROJECT / 'p2_1_results' / 'predictions.jsonl'
NEW_CASES = PROJECT / 'p2_1_results' / 'baseline_v2_new' / 'cases'
REPORT = PROJECT / 'p2_1_results' / 'cross_check_report.md'

# Read all predictions
preds = []
with PREDICTIONS.open('r', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            preds.append(json.loads(line))
preds_by_id = {p['case_id']: p for p in preds}
print(f"Loaded {len(preds)} LLM predictions")

# Per-case: load baseline case JSON, compute inferred gold romans,
# then compare with LLM predictions
def infer_gold_romans(case):
    """Use the same inverse-map as P1.1/P1.3: take gold voicing 4-tuple per beat
    and infer a roman numeral with confidence."""
    so = case['solver_output']
    sg, ag, tg, bg = so['voice_s_gold'], so['voice_a_gold'], so['voice_t_gold'], so['voice_b_gold']
    key_name = case['input']['key']
    try:
        key = Key.from_name(key_name)
    except Exception:
        return [(None, 0.0)] * len(sg)
    n = len(sg)
    out = []
    for i in range(n):
        # Skip beats where any voice is the dummy 'C4' (parser failure)
        if any(v == 'C4' for v in [sg[i], ag[i], tg[i], bg[i]]):
            out.append((None, 0.0))
            continue
        try:
            Note.from_name(sg[i]); Note.from_name(ag[i]); Note.from_name(tg[i]); Note.from_name(bg[i])
        except Exception:
            out.append((None, 0.0))
            continue
        ir = infer_roman(sg[i], ag[i], tg[i], bg[i], key)
        if ir is None:
            out.append((None, 0.0))
        else:
            out.append((ir.roman, ir.confidence))
    return out

# Aggregate stats
beats_total = 0
beats_gold_match = 0   # LLM's gold == inferred gold
beats_solver_match = 0  # LLM's solver_picks == actual solver.romans
beats_llm_internal_consistent = 0  # LLM's gold == solver_picks when LLM says OK
beats_ok_self_consistent = 0
beats_p13_correct = 0   # LLM's p13 == "OK" iff LLM's gold == solver_picks

per_case = []
for cid, pred in preds_by_id.items():
    case_path = NEW_CASES / f'{cid}.json'
    if not case_path.exists():
        per_case.append({'case_id': cid, 'error': 'no case file'})
        continue
    case = json.loads(case_path.read_text(encoding='utf-8'))
    so = case['solver_output']
    actual_romans = so['romans']
    try:
        inferred = infer_gold_romans(case)
    except Exception as e:
        per_case.append({'case_id': cid, 'error': f'infer_gold_romans: {e}'})
        continue
    try:
        inferred = infer_gold_romans(case)
    except Exception as e:
        per_case.append({'case_id': cid, 'error': f'infer_gold_romans: {e}'})
        continue

    n_pred = len(pred['prediction'])
    n = min(n_pred, len(actual_romans), len(inferred))
    case_gold_match = 0
    case_solver_match = 0
    case_ok_consistent = 0
    case_p13_correct = 0
    for j in range(n):
        llm_gold = pred['prediction'][j]['gold']
        llm_solver = pred['prediction'][j]['solver']
        llm_p13 = pred['prediction'][j]['p13']
        actual_gold, actual_gold_conf = inferred[j]
        actual_solver = actual_romans[j]
        beats_total += 1
        if llm_gold == actual_gold:
            case_gold_match += 1
            beats_gold_match += 1
        if llm_solver == actual_solver:
            case_solver_match += 1
            beats_solver_match += 1
        # Self-consistency: LLM's gold vs LLM's solver_picks
        if llm_p13 == 'OK':
            if llm_gold == llm_solver:
                case_ok_consistent += 1
                beats_llm_internal_consistent += 1
        # P1.3 correctness: actual agreement
        actual_agree = (actual_gold == actual_solver) and actual_gold_conf >= 0.6
        llm_says_agree = (llm_p13 == 'OK')
        if actual_agree == llm_says_agree:
            case_p13_correct += 1
            beats_p13_correct += 1
    per_case.append({
        'case_id': cid,
        'n_beats': n,
        'gold_match': f'{case_gold_match}/{n} = {case_gold_match/n*100:.0f}%' if n else 'N/A',
        'solver_match': f'{case_solver_match}/{n} = {case_solver_match/n*100:.0f}%' if n else 'N/A',
        'ok_consistent': f'{case_ok_consistent}/{n} = {case_ok_consistent/n*100:.0f}%' if n else 'N/A',
        'p13_correct': f'{case_p13_correct}/{n} = {case_p13_correct/n*100:.0f}%' if n else 'N/A',
    })

# P1.3 class distribution from LLM
p13_dist = Counter()
fixer_dist = Counter()
for pred in preds:
    for b in pred['prediction']:
        p13_dist[b['p13']] += 1
        if b['fixer'] != 'none':
            fixer_dist[b['fixer']] += 1

# Report
lines = []
lines.append('# P2.1 LLM Cross-Check Report (19 NEW SHTE cases)')
lines.append('')
lines.append('## Aggregate accuracy')
lines.append('')
lines.append(f'- Total beats evaluated: **{beats_total}**')
lines.append(f'- LLM gold == inferred gold: **{beats_gold_match} ({beats_gold_match/beats_total*100:.1f}%)**')
lines.append(f'- LLM solver_picks == actual solver.romans: **{beats_solver_match} ({beats_solver_match/beats_total*100:.1f}%)**')
lines.append(f'- LLM P1.3 class == actual agreement: **{beats_p13_correct} ({beats_p13_correct/beats_total*100:.1f}%)**')
lines.append(f'- LLM self-consistency (gold==solver when says OK): **{beats_llm_internal_consistent}**')
lines.append('')
lines.append('## Per-case breakdown')
lines.append('')
lines.append('| Case | n | gold_match | solver_match | ok_consistent | p13_correct |')
lines.append('|------|---|------------|--------------|---------------|-------------|')
for c in per_case:
    if 'error' in c:
        lines.append(f"| {c['case_id']} | - | ERROR: {c['error']} | - | - | - |")
    else:
        lines.append(f"| {c['case_id']} | {c['n_beats']} | {c['gold_match']} | {c['solver_match']} | {c['ok_consistent']} | {c['p13_correct']} |")
lines.append('')
lines.append('## LLM P1.3 distribution (across 19 cases × 12 beats)')
lines.append('')
for k, v in sorted(p13_dist.items(), key=lambda x: -x[1]):
    lines.append(f'- `{k}`: {v} ({v/sum(p13_dist.values())*100:.1f}%)')
lines.append('')
lines.append('## LLM fixer distribution (when P1.3 != OK)')
lines.append('')
if fixer_dist:
    for k, v in sorted(fixer_dist.items(), key=lambda x: -x[1]):
        lines.append(f'- `{k}`: {v}')
else:
    lines.append('(no fixer predictions)')
lines.append('')

# Comparison with baseline_v2 (19-chapter sample)
lines.append('## vs baseline_v2 (19-chapter sample)')
lines.append('')
lines.append('| Metric | baseline_v2 | p2_1_new (19 cases) |')
lines.append('|--------|-------------|---------------------|')
lines.append('| L1 (primary) | 9.1% | (per case above) |')
lines.append('| L2 (function)| 48.3% | - |')
lines.append('| L3 (legal)  | 98.8% | - |')
lines.append('| L4 (pitch)  | 10.9% | - |')
lines.append('')

# Insight
lines.append('## Insight')
lines.append('')
gold_pct = beats_gold_match/beats_total*100
solver_pct = beats_solver_match/beats_total*100
p13_pct = beats_p13_correct/beats_total*100
lines.append(f'- LLM can reproduce actual solver picks {solver_pct:.1f}% of the time.')
lines.append(f'- LLM can infer gold roman from voicing {gold_pct:.1f}% of the time.')
lines.append(f'- LLM classifies P1.3 OK/FAIL correctly {p13_pct:.1f}% of the time.')
lines.append('')
lines.append('## CRITICAL: LLM design flaw')
lines.append('')
lines.append('The P2.1 LLM eval as designed has a **fundamental limitation**: the model is')
lines.append('not given the actual solver output.  It must independently predict both the')
lines.append('gold chord AND the solver_picks.  Since the model naturally assumes the')
lines.append('solver "agrees" with its own analysis, it predicts `P1.3: OK` 100% of the time')
lines.append(f'({p13_dist.get("OK", 0)}/{sum(p13_dist.values())} beats).')
lines.append('')
lines.append('**This means:**')
lines.append('1. P1.3 class output is **unusable** -- it is the LLM\'s self-consistency, not a real classification.')
lines.append('2. The "solver_picks" column is the LLM\'s chord prediction, not solver\'s actual output.')
lines.append('3. The only useful signal is **gold_match** (LLM\'s chord from voicing vs reverse-mapped gold).')
lines.append('4. For real P1.3 classification, the prompt must include the **actual solver.romans output**')
lines.append('   so the model can compare.  This requires a 2-pass design (1: solve, 2: diagnose).')
lines.append('')
lines.append('## Verdict')
lines.append('')
if gold_pct > 50:
    lines.append('LLM (DeepSeek v4-flash) shows moderate ability to chord-identify from voicing.')
    lines.append('Useful as a sanity-check assistant on new cases, not as a diagnostic oracle.')
else:
    lines.append('LLM (DeepSeek v4-flash) is **worse than the offline roman_inference** at')
    lines.append('chord-identification.  Recommended: use LLM only for explainability generation')
    lines.append('("why is this beat I6?"), not for the chord decision itself.')

REPORT.write_text('\n'.join(lines), encoding='utf-8')
print(f'\nWrote: {REPORT}')
print(f'  LLM gold match: {gold_pct:.1f}%')
print(f'  LLM solver match: {solver_pct:.1f}%')
print(f'  LLM P1.3 correct: {p13_pct:.1f}%')
print(f'  P1.3 dist: {dict(p13_dist)}')
print(f'  Fixer dist: {dict(fixer_dist)}')
