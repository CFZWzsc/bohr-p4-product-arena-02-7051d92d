# Runtime contract

Bohrium Playground Period 4 submission — challenge `product-arena-02-7051d92d` (track: `academic-writing`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable entry point and all supporting scripts. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `academic-language-polisher`
- Summary: Polish academic English or Chinese prose with minimal, sentence-level edits while locking numbers, units, citation markers and hedging strength so the author's claims are never strengthened or weakened. Use when a task asks for grammar/terminology/tone polishing with a per-edit rationale and term consistency.

## Contents

| File |
|------|
| `SKILL.md` |
| `scripts/run_skill.py` |
| `README.md` |

## How to run

```bash
python scripts/run_skill.py --case /input/case.json --output /app/output/result.json
```

The entry point is `SKILL.md`; input/output contracts, error handling and a minimal
usage example are documented there.

## Notes

- Pure Python standard library; no network access required.
- The result JSON keeps the input case id, the main results, per-item evidence,
  a run status and an uncertainty section.
