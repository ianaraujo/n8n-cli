# Snapshot / Backup System

Every successful write command (`update-workflow` and `set-node-param`) automatically
saves a snapshot of the **pre-change** workflow to disk before applying the mutation.

## Where backups are stored

```
~/.n8n-cli/backups/<workflow_id>/<timestamp>.json
```

- `<workflow_id>` is the n8n workflow ID with any unsafe characters replaced by `_`.
- `<timestamp>` is a UTC ISO-8601 instant: `20260417T145356Z`.
- The directory is created on first write; subsequent updates append new files.

## What is saved

The full workflow object returned by `GET /api/v1/workflows/{id}` — identical to what
`n8n get --keep-creds` returns, including live credential IDs, metadata fields, and
`versionId`. This is intentionally the **full API response**, not the stripped export,
so the restore command is always a clean round-trip.

## When snapshots are taken

| Command | Snapshot taken? |
|---|---|
| `update-workflow` (live) | Yes — before the PUT |
| `set-node-param` (live) | Yes — before the PUT |
| `update-workflow --dry-run` | No |
| `set-node-param --dry-run` | No |

Dry-run calls exit before the snapshot so the backup directory stays clean.

## Reading the restore command from output

Both write commands include `backup` in their JSON result:

```json
{
  "updated": true,
  "workflow": "My Workflow",
  "id": "aA1xyIkUKULeMVzC",
  "backup": {
    "path": "/home/you/.n8n-cli/backups/aA1xyIkUKULeMVzC/20260417T145356Z.json",
    "restore_cmd": "n8n update-workflow aA1xyIkUKULeMVzC --file /home/you/.n8n-cli/backups/aA1xyIkUKULeMVzC/20260417T145356Z.json --force"
  }
}
```

**Always surface `backup.restore_cmd` to the user** after any write. It's the fastest
way to revert if the change breaks something.

## Restoring from a backup

Use the `restore_cmd` verbatim. `--force` is included because the backup contains the
complete pre-change workflow; blast-radius checks would otherwise block structural
differences unnecessarily.

```bash
n8n update-workflow <wf_id> --file ~/.n8n-cli/backups/<wf_id>/<timestamp>.json --force
```

You can first preview the restore with `--dry-run`:

```bash
n8n update-workflow <wf_id> --file ~/.n8n-cli/backups/<wf_id>/<timestamp>.json --force --dry-run
```

## Multiple backups / choosing a version

Each write creates a new timestamped file, so multiple snapshots accumulate:

```
~/.n8n-cli/backups/aA1xyIkUKULeMVzC/
  20260417T145356Z.json   ← before update-workflow
  20260417T145438Z.json   ← before set-node-param
```

To restore an earlier version, pick the file whose timestamp precedes the change you
want to undo and pass it to `update-workflow --force`.

## Implementation notes (for debugging)

- `_snapshot_workflow` in `cli/src/cli.py` does the write. It runs **inside** the
  `try` block, after all guard checks pass but before `client.update_workflow` is
  called. If the snapshot fails, the entire command aborts — the live workflow is
  never mutated.
- The backup contains the **raw API response** including `active`, `versionId`, and
  server-managed metadata. `client.update_workflow` strips those keys before sending
  the PUT, so passing the backup file through `update-workflow` is safe.
- `N8N_CLI_READ_ONLY=1` blocks all writes, so no snapshots are ever created in
  read-only mode.

## Known limitation: installed CLI must be up to date

The backup feature was added after the initial release. If `n8n update-workflow`
returns a result **without** a `backup` key, the installed CLI is stale. Reinstall:

```bash
cd /path/to/n8n-cli/cli && uv tool install . --reinstall
```
