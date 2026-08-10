# Local classification fixtures

Seed Excel workbooks for offline `historical_yield` when OneDrive cloud files cannot be read.

The thesis LLM lives in the sibling repo `llm model` and reads this tool’s SQLite/CSV outputs.

When OneDrive hydrates, re-enable real data roots in `../config.json` and run:

```text
py -3 -m historical_yield scan --rebuild
py -3 -m historical_yield report
```
