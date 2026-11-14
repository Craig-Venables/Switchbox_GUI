# TOKEN_LIMITS.md — keeping token usage down in the multi-agent workflow

The main agent and all subagents follow these rules. No secrets or cookies belong in this file or any prompt.

1. **Prefer MCP tool calls over GUI screenshots for testing.** Tool calls (e.g. `get_status`, `run_iv_sweep`, `read_results`) return short structured text; screenshots are token-heavy. Test behaviour through tools or pytest first.
2. **Screenshots only for explicit layout checks.** Take one only when a task specifically needs layout verification. Crop to the relevant region (the changed panel or widget) rather than capturing the full window, and avoid repeat captures of unchanged views.
3. **Keep subagent prompts minimal.** Subagents start with no conversation context. Pass only the task-specific details (goal, files, acceptance check). Don't restate AGENTS.md; tell the subagent to follow it.
4. **Use the cheapest suitable model.** The tester and any read-only or simple roles (reviewer, search, summarising) use Composer (e.g. `model: composer-2.5`). Reserve `inherit` / stronger models for implementation that needs it.
5. **Return concise summaries.** Subagents report a short summary: pass/fail counts, failures with command, error line and file:line, files changed. No full logs, tracebacks beyond the relevant lines, or data dumps; point to a file path instead.
6. **Batch independent checks.** Group independent checks (pytest, ruff, simulator smoke run) into one tester run rather than many separate subagent invocations.
7. **Scope tests to the change.** For small changes, run only the affected modules' tests (e.g. `pytest tests/test_<module>.py`) and the related simulator path. Run the full suite before merging or after larger changes.
