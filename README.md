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

## 3. Set environment variables

Generate an API key in n8n: **Settings > n8n API > Create API Key**.

**Recommended — Claude Code project settings** (vars are injected into every Claude shell automatically):

Add an `"env"` block to your project's `.claude/settings.json`:

```json
{
  "env": {
    "N8N_BASE_URL": "http://localhost:5678",
    "N8N_API_KEY": "your-api-key"
  }
}
```

**Alternative — `.env` file** at the project root for local dev/testing. Shell variables take precedence over `.env`.

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

## Read-only mode

Set `N8N_CLI_READ_ONLY=1` to disable all write commands (`set-node-param`, `update-workflow`, `retry`). Useful when you want Claude to inspect and debug workflows without any risk of modifying them.

```bash
export N8N_CLI_READ_ONLY=1   # block all writes
unset N8N_CLI_READ_ONLY      # re-enable writes
```

Any write attempt while the flag is set exits with an error and a message explaining how to unset it.

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
