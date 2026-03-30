# n8n-cli

CLI tool for reading and writing n8n workflows via the REST API. Built for use with **Claude Code** as an AI-assisted n8n workflow copilot.

All output is JSON, optimized for AI agent consumption.

## Install

```bash
# Requires Python 3.12+ and uv
uv sync
```

## Setup

Create a `.env` file at the project root:

```bash
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your-api-key
N8N_DEFAULT_WORKFLOW=optional-default-workflow-id
```

Generate an API key in n8n: **Settings > n8n API > Create API Key**.

## Usage

```bash
# List all workflows
uv run n8n list

# Workflow graph (nodes + edges)
uv run n8n flow <WORKFLOW_ID>

# Full workflow JSON
uv run n8n get <WORKFLOW_ID>

# Single node's JSON
uv run n8n get <WORKFLOW_ID> --node "Node Name"

# Recent executions
uv run n8n executions <WORKFLOW_ID>

# Execution details
uv run n8n execution-data <EXECUTION_ID>

# Patch a node parameter
uv run n8n set-node-param <WORKFLOW_ID> --node "Node" --param "url" --value "https://example.com"

# Update full workflow from file
uv run n8n update-workflow <WORKFLOW_ID> --file workflow.json

# Retry a failed execution
uv run n8n retry <EXECUTION_ID> --use-latest
```

All workflow commands accept `--name "partial match"` as an alternative to a workflow ID.

## Claude Code Integration

See [n8n-copilot skill](.claude/skills/n8n-copilot/SKILL.md) for the full skill definition.

## License

MIT
