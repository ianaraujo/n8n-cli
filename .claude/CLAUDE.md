# n8n-cli

CLI tool that gives Claude Code read/write access to n8n workflows via the REST API. All output is JSON.

## Setup

Requires `.env` at project root with `N8N_BASE_URL` and `N8N_API_KEY`. Install with `uv sync`.

Optionally set `N8N_DEFAULT_WORKFLOW` in `.env` to configure a default workflow ID for the n8n-copilot skill.

## Project structure

- `src/client.py` — N8nClient API wrapper (httpx)
- `src/cli.py` — Typer CLI commands, entry point: `n8n`
- `.claude/skills/n8n-copilot/SKILL.md` — n8n copilot skill (investigation patterns, n8n domain knowledge)
- `.claude/skills/typer/SKILL.md` - Typer official skill to write code with best practices, keeping up to date with new versions and features.
