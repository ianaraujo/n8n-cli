---
name: n8n-copilot
description: n8n workflow copilot. Use when understanding, debugging, or modifying n8n workflows. Reads and writes workflow definitions through the `n8n` CLI (a thin wrapper over the n8n REST API). All CLI output is JSON.
allowed-tools: Bash(n8n *), Read, Grep, Glob, WebFetch(domain:docs.n8n.io)
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/preflight.sh"
---

# n8n Copilot

You operate n8n through the `n8n` CLI. n8n is a point-and-click tool; the CLI is how you read and write workflow JSON, inspect executions, and patch nodes without the UI.

**You can:** read workflows, inspect execution data, patch node parameters, push full workflow updates, retry executions.
**You cannot:** create or delete workflows, manage credentials, or run ad-hoc executions.

## CLI reference

All commands emit JSON on stdout. Workflow-targeted commands accept either a positional `<WORKFLOW_ID>` or `--name "partial"` (case-insensitive substring; errors on ambiguity).

| Command | Purpose | Key options |
|---|---|---|
| `n8n list` | List workflows (id, name, active, tags, updatedAt) | `--active/--all`, `--limit` |
| `n8n flow <wf>` | Graph only: nodes + edges (cheapest view of structure) | — |
| `n8n get <wf>` | Full workflow JSON | `--node "Name"` (one node only), `--compact` (strip position/id), `--keep-creds` (required for round-trip edits), `-o FILE` |
| `n8n executions <wf>` | Recent executions (id, status, timestamps) | `--status {success,error,waiting,running}`, `--limit` |
| `n8n execution-data <exec_id>` | Per-node run summary (items out, ms, error) | `--node "Name"` for full input/output of one node |
| `n8n set-node-param <wf>` | Patch one param in-place (no file round-trip) | `--node`, `--param "dot.path"`, `--value` OR `--json`, `--dry-run` |
| `n8n update-workflow <wf>` | PUT full workflow JSON (from `--file` or stdin) | `--file`, `--dry-run` (shows diff) |
| `n8n retry <exec_id>` | Retry a failed execution | `--use-latest` (retry with current workflow version) |

Add `--help` to any command for full flags.

## Investigation flow — start cheap, escalate

Fetching full workflow JSON is expensive; use the smallest view that answers the question.

**Understand a workflow**
1. `n8n flow --name "X"` — graph (node names, types, edges). Almost always enough to orient.
2. `n8n get --name "X" --node "Target"` — one node's parameters when you need config detail.
3. `n8n get --name "X" --compact` — full workflow only when you truly need everything.

**Debug a failure**
1. `n8n executions --name "X" --status error --limit 5` — find recent failures.
2. `n8n execution-data <id>` — which node failed and what `error.message` says. The output also includes `failed_node` at the top when the execution errored.
3. `n8n execution-data <id> --node "Failing Node"` — full input/output items for that node's runs. This is where you spot `undefined` values, malformed payloads, etc.

## Modifying workflows

**Both `set-node-param` and `update-workflow` automatically deactivate an active workflow** before writing. The response includes `"deactivated": true` when this happens — surface that to the user so they know to re-activate after testing.

Always preview mutations with `--dry-run` first unless the user has already approved the change.

**Single-parameter patch** (preferred when only one value changes):
```bash
n8n set-node-param --name "X" --node "HTTP Request" --param "url" --value "https://..." --dry-run
n8n set-node-param --name "X" --node "HTTP Request" --param "url" --value "https://..."
```
`--param` is a dotted path under the node's `parameters` object. For non-string values, use `--json` instead of `--value`:
```bash
n8n set-node-param --name "X" --node "Loop" --param "options.batchSize" --json 50
n8n set-node-param --name "X" --node "HTTP" --param "queryParameters.parameters" --json '[{"name":"q","value":"v"}]'
```

**Full-workflow edit** (multiple changes, structural changes, or adding/removing nodes):
```bash
n8n get --name "X" --keep-creds -o /tmp/wf.json   # --keep-creds is required for round-trip
# edit /tmp/wf.json
n8n update-workflow --name "X" --file /tmp/wf.json --dry-run   # shows structural diff
n8n update-workflow --name "X" --file /tmp/wf.json
```
`update-workflow` also backfills credential references from the live workflow, so a file exported without `--keep-creds` won't lose credentials — but keeping them makes the diff cleaner.

**Retry after a fix**
- `n8n retry <id> --use-latest` — retry with the updated workflow (use after any change).
- `n8n retry <id>` — retry with the workflow version captured at original execution time.

## Debugging gotchas (CLI-visible symptoms)

Most n8n semantics live in the docs (see below). These few come up repeatedly when reading `execution-data` output and are the fastest to recognize:

- **`Bearer undefined` / `undefined` in request bodies** → item pairing broke. The expression likely uses `$('Node').item.json.x` but that node is either `executeOnce: true`, in a discarded Merge branch (`chooseBranch` with a different `useDataOfInput`), or otherwise not on the current item's lineage. Switch to `$('Node').first().json.x` or `.all()`.
- **Merge node "swallowed" fields** → `mode: chooseBranch` outputs only the input indicated by `useDataOfInput` and discards the rest. If downstream expects data from another input, either change the mode (`combineByPosition` / `combineByFields`) or reference the other input via `$('Node').first()`.
- **`executeOnce: true` nodes** → they run once regardless of item count; downstream `.item` references against them will not pair. Always use `.first()` to read from them.

For anything else (expression syntax, node-type reference, trigger semantics, credential types, self-hosting, etc.), consult the documentation index below — don't guess.

## n8n documentation

The full n8n documentation index is in `docs/index.md` (this skill's directory). It's a flat list of every doc page with its URL.

**How to use it:**
1. `Grep` for the topic in `docs/index.md` (e.g. `Grep "Merge"`, `Grep "HTTP Request"`, `Grep -i "expression"`).
2. `WebFetch` the URL of the best match.
3. Prefer this over guessing from prior knowledge — n8n node parameters and expression APIs change between versions.

Good queries: node type names (`"Google Sheets"`, `"Webhook"`), concepts (`"expressions"`, `"pinning data"`, `"error workflow"`), or API endpoints (`"workflows"`, `"executions"`).
