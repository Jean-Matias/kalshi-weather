# Workspace Map

Root stays intentionally small so future AI sessions can orient quickly.

## Root Files

- `AGENTS.md`: mandatory local agent rules and RTK command wrapper instructions.
- `README.md`: human-ish setup/run summary.
- `scanner.py`: main command, keep runnable with `python scanner.py`.
- `config.py`: market/station configuration.
- `weather_sources.py`: weather collection and derived source state.
- `kalshi_browser.py`: read-only Kalshi browser scrape.
- `scoring.py`: probability, risk, source/bucket states, signal labels.
- `report.py`: Markdown output rendering.
- `database.py`: SQLite snapshot writer.
- `requirements.txt`: Python dependencies.

## Folders

- `tests/`: regression and unit tests.
- `reports/`: generated Markdown reports from `scanner.py`.
- `data/`: generated SQLite snapshots.
- `docs/`: AI handoff and project context.
- `.claude/`: empty local Claude plugin/skill placeholder folders; not required for scanner runtime.

## Review Context

- `docs/prompts/low-temperature-audit.md`: prompt for external low-temperature accuracy reviews.

## Generated Clutter Policy

Safe to delete anytime:

- `__pycache__/`
- `tests/__pycache__/`
- `.pytest_cache/`
- `*.pyc`

Do not casually delete:

- `data/snapshots.sqlite3`, unless intentionally resetting history.
- `reports/*.md`, unless intentionally regenerating with `python scanner.py`.
