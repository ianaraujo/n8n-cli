# n8n-cli

CLI tool that gives Claude Code read/write access to n8n workflows via the REST API. All output is JSON.

## Setup

1. Install the CLI globally: `cd cli && uv tool install .`
2. Export env vars in `~/.bashrc` or `~/.zshrc`:
   ```
   export N8N_BASE_URL=http://localhost:5678
   export N8N_API_KEY=your-api-key
   ```
3. Copy the skill globally: `cp -r skills/n8n-copilot ~/.claude/skills/n8n-copilot`

For local dev/testing, a `.env` file at the project root also works (shell vars take precedence).

## Project structure

```
n8n-cli/
├── cli/                    # CLI source (Python, uv)
│   ├── src/
│   │   ├── __init__.py
│   │   ├── client.py       # N8nClient API wrapper (httpx)
│   │   └── cli.py          # Typer CLI commands, entry point: n8n
│   ├── tests/
│   │   └── test_cli.py
│   ├── pyproject.toml
│   └── uv.lock
├── skills/
│   └── n8n-copilot/        # Claude skill
│       ├── SKILL.md        # Investigation patterns, n8n domain knowledge
│       ├── examples.md     # Concrete invocation examples
│       ├── docs/
│       │   └── index.md
│       └── scripts/
│           └── preflight.sh
├── .claude/settings.json   # Allowed tools + permissions
├── CLAUDE.md               # This file
└── README.md
```

## Running the CLI

```bash
n8n <command>
```
