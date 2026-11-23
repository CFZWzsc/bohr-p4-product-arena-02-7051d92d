# Runtime contract

Bohrium Playground Period 4 submission — challenge `product-arena-02-7051d92d` (track: `academic-writing`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable pipeline and all supporting documents. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `academic-language-polisher`
- Summary: Use when a case supplies an academic manuscript and asks for language polishing or terminology consistency; performs deterministic minimal edits with guards that preserve numbers, units, citations and hedging, then writes a contract-complete /app/output/result.json plus polished.md.

## Contents

| File |
|------|
| `SKILL.md` |
| `assets/policy.json` |
| `examples/demo-case/case.json` |
| `examples/demo-case/manuscript.md` |
| `examples/quickstart.md` |
| `references/evidence-discipline.md` |
| `references/method.md` |
| `references/task-spec.md` |
| `scripts/run_skill.py` |
| `scripts/sk_entry.py` |
| `README.md` |

## How to run

```bash
python scripts/sk_entry.py --input /input --work /app/work --out /app/output
```

A single deterministic pass reads `/input`, computes the deliverable and writes a
contract-complete `/app/output/result.json` plus the human-readable review files
described in `SKILL.md`. The same input always produces byte-identical output; no
network access is used, and fields the materials cannot support are reported
explicitly instead of being left empty.

## Notes

- Pure Python standard library; no network access required.
- Every claim is anchored to paragraph-level evidence; unknown items are reported
  in `uncertainty` instead of being fabricated.
