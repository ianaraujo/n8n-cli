# n8n-cli

CLI tool that gives Claude Code read/write access to n8n workflows via the REST API. All output is JSON.

## 1. Install the CLI

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd /path/to/n8n-cli/cli
uv tool install .
```

This puts the `n8n` binary on your PATH. Verify with `n8n --help`.

## 2. Add the skill globally

Copy the n8n-copilot skill to your global Claude skills directory so it's available in any project:

```bash
cp -r /path/to/n8n-cli/skills/n8n-copilot ~/.claude/skills/n8n-copilot
```

## 3. Export environment variables

Add these to your `~/.bashrc` or `~/.zshrc`:

```bash
export N8N_BASE_URL=http://localhost:5678
export N8N_API_KEY=your-api-key
export N8N_DEFAULT_WORKFLOW=optional-default-workflow-id  # optional
```

Generate an API key in n8n: **Settings > n8n API > Create API Key**.

> **Local testing:** You can also create a `.env` file in the `cli/` directory. Shell variables take precedence over `.env`.

## 4. Example workflow with Claude

Open any project in Claude Code and use the n8n-copilot skill:

```
/n8n list my workflows
/n8n show me the last failed execution of "My Workflow"
/n8n fix the HTTP node in workflow 42 to use POST instead of GET
```

Claude will use the `n8n` CLI to inspect and edit workflows directly.

## CLI reference

```bash
n8n list                                          # list all workflows
n8n flow <ID>                                     # workflow graph (nodes + edges)
n8n get <ID>                                      # full workflow JSON
n8n get <ID> --node "Node Name"                   # single node JSON
n8n executions <ID>                               # recent executions
n8n execution-data <EXECUTION_ID>                 # execution details
n8n set-node-param <ID> --node "N" --param "url" --value "https://…"
n8n update-workflow <ID> --file workflow.json     # update from file
n8n retry <EXECUTION_ID> --use-latest             # retry failed execution
```

All workflow commands accept `--name "partial match"` instead of an ID.

## Updating the CLI

When you pull changes to the CLI source, reinstall the tool to pick them up:

```bash
cd /path/to/n8n-cli/cli
uv tool install . --force
```

To also update the global skill:

```bash
cp -r /path/to/n8n-cli/skills/n8n-copilot ~/.claude/skills/n8n-copilot
```
