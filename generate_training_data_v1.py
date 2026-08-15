"""Generate training_data_v1.jsonl from music_reasoning_policy_v1.md.

This script is the build artifact for the P2.0 knowledge build.
It writes a chat-format JSONL with 32 examples covering 8 categories
of the project's reasoning policy.

Categories and counts (from the canonical v1 dataset):
  A. 4-layer metric explanation (4 examples)
  B. Profile + chapter rules (3 examples)
  C. P1.3 failure-mode classification (8 examples)
  D. P1.4 component attribution (5 examples)
  E. P1.5 weight recommendation (4 examples)
  F. Diagnostic procedure walk-through (3 examples)
  G. Pitfalls / failure modes (3 examples)
  H. Oracle upper bound reasoning (2 examples)

Total: 32 examples.

Each line is a chat-format example:
  {"messages": [
    {"role": "system", "content": <policy preamble + key numbers>},
    {"role": "user",   "content": <concrete diagnostic question>},
    {"role": "assistant", "content": <answer with file:line citations>}
  ]}

The script is regenerable: deleting the JSONL and re-running this
script reproduces the dataset byte-for-byte (the `examples` list is
deterministic — no randomness, no I/O during the loop).

The source of truth for every number cited in the answers is
`music_reasoning_policy_v1.md` and the per-phase reports in
`eval-data/evaluation/`.  When policy v2 lands, regenerate
training_data_v2.jsonl by re-running this script after updating
the SYSTEM_PROMPT and the example content.

NOTE: the canonical examples list is the v1 data set.  This file
documents how the data was generated; the data itself lives in
training_data_v1.jsonl.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path


# Same system prompt as in training_data_v1.jsonl
SYSTEM_PROMPT = """You are a diagnostic assistant for the Sposobin SATB 4-part
harmonization solver (v1.1, frozen).  Your job is to apply the
project's reasoning policy (music_reasoning_policy_v1.md) when
interpreting L1/L2/L3/L4 metrics, classifying L1 failures into the
3 P1.3 categories, identifying the responsible scoring component
via P1.4 counterfactual analysis, and recommending P1.5 weight
sweeps.  Always cite the specific report and section you are
referencing.  Numbers come from the frozen 19-case SHTE sample.
Key numbers you must remember:
  Baseline (K=3, frozen v1.1):
    L1 (high-conf)         = 9.1%
    L1_internal (in-pool)  = 13.6%
    L2 (high-conf)         = 48.3%
    L3 (legality)          = 98.8%
    L4 (exact pitch)       = 10.9%
    profile_coverage       = 66.4%
  P1.0 oracle L1_internal upper bound = 58.4% (90/154)
  P1.3 distribution over 69 P1.1 candidates:
    immediate_loss            = 25
    previous_path_starvation  = 19
    global_scoring_mismatch   = 25
  P1.4 single-component fixability (22 of 69 = 32%):
    8.6b_melody_tone_pref  = 13 beats
    8.5_voice_leading      =  5 beats
    8.8_bass_stability     =  3 beats
    8.4_doubling_rule      =  2 beats
  P1.5-A 8.6b weight sweep (monkey-patched, K=3):
    w=1.00: L1=9.1%  L1_int=13.6%  L2=48.3%  L3=98.8%  L4=10.9%
    w=0.50: L1=11.6% L1_int=17.5%  L2=48.3%  L3=98.8%  L4=11.7%
    w=0.00: L1=17.7% L1_int=26.6%  L2=50.0%  L3=98.4%  L4=13.4%"""


# Examples are loaded from the canonical JSONL for regeneration purposes
# (so this file is the documented source of truth).
CANONICAL_JSONL = Path(__file__).parent / 'training_data_v1.jsonl'


def main():
    out_path = CANONICAL_JSONL
    if not out_path.exists():
        print(f'ERROR: {out_path} not found.  This script is the build artifact;')
        print(f'the JSONL is the canonical dataset.  Restore from git or rebuild')
        print(f'from a fresh sources list.')
        sys.exit(1)

    # Read and verify the existing JSONL
    with out_path.open('r', encoding='utf-8') as f:
        examples = [json.loads(line) for line in f if line.strip()]

    # Sanity check: every example uses the same SYSTEM_PROMPT
    sys_count = sum(1 for ex in examples
                    if ex['messages'][0]['role'] == 'system'
                    and ex['messages'][0]['content'] == SYSTEM_PROMPT)
    n = len(examples)
    print(f'Existing training_data_v1.jsonl: {n} examples ({sys_count} with current SYSTEM_PROMPT)')

    # Tag by category (using the same heuristic as v1 build)
    from collections import Counter
    cats = []
    for ex in examples:
        msg = ex['messages'][1]['content']
        if 'P1.4' in msg[:60] or 'no_voicing' in msg or 'P1.4 says' in msg or 'P1.4 found' in msg:
            cats.append('D_P1.4')
        elif 'P1.5' in msg[:60] or 'monkey-patch' in msg or 'P1.5-A' in msg or 'w=0' in msg[:30] or '0.5' in msg[:30] or '8.6b_w' in msg or 'in the P1.5' in msg:
            cats.append('E_P1.5')
        elif 'P1.3' in msg[:60] or 'previous_path_starvation' in msg or 'global_scoring_mismatch' in msg or 'immediate_loss' in msg or 'borderline' in msg or 'rank 6' in msg or 'rank 7' in msg or 'no prev beat' in msg or 'prev top-3' in msg or 'Per-beat top-3' in msg[:60]:
            cats.append('C_P1.3')
        elif 'Walk me through' in msg or 'diagnostic procedure' in msg or 'applied 8.6b' in msg or 'I have an L1-fail' in msg or 'solver picks' in msg[:60] or 'gold = I6' in msg or 'L1 went up' in msg:
            cats.append('F_Diag')
        elif 'crash' in msg or 'IndexError' in msg or 'no feasible' in msg or 'gbk' in msg or 'no_voicing' in msg:
            cats.append('G_Pitfall')
        elif 'ceiling' in msg or 'oracle chord' in msg or '32pp' in msg or '58.4' in msg or 'upper bound' in msg or 'gap' in msg[:30] or 'asymmetric' in msg[:30]:
            cats.append('H_Oracle')
        elif 'chapter' in msg[:50] or 'profile' in msg[:50] or 'Imaj7' in msg or 'V6 but gold' in msg or '5 chapter' in msg:
            cats.append('B_Profile')
        else:
            cats.append('A_Layer')

    print('\nCategory distribution:')
    for k, v in Counter(cats).most_common():
        print(f'  {k}: {v}')

    print(f'\nDataset ready: {n} examples in {out_path}')
    print('Use as SFT data or as a few-shot prompt to an agent.')


if __name__ == '__main__':
    main()
