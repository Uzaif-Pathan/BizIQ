# Verification record

Last verified in the project workspace during Part 2 completion.

- Automated tests: **273 passed**.
- Synthetic scenarios: **4 passed** (`retail`, `service`, `cold_start`, `messy`).
- JSON serialization: strict `allow_nan=False` check passed for every scenario.
- JSON contract: each scenario output validated against `contracts/analysis-result.schema.json`.
- Expected scenario outcomes:
  - `retail`: completed, high evidence
  - `service`: completed, high evidence
  - `cold_start`: completed, low evidence
  - `messy`: partial, medium evidence; data-quality issues are reported instead of hidden

Re-run locally after changes:

```bash
cd backend
python -m pytest analytics_engine/tests -q
cd ..
python scripts/check_samples.py
```

A `partial` result for the deliberately messy dataset is expected and is not a test failure.
\nThe CLI also supports `--summary` for a readable presentation/demo view while keeping JSON as the machine-integration output.\n