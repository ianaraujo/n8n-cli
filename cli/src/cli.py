"""CLI interface for n8n-workflow-fetcher."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from dotenv import load_dotenv

from .client import N8nClient, N8nConfig

load_dotenv(override=False)

app = typer.Typer(
    help="n8n Workflow Fetcher — fetch, inspect, and update n8n workflows via the REST API.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _out(data: Any, compact: bool = False) -> None:
    """Print JSON to stdout. All commands use this for consistent output."""
    print(json.dumps(data, indent=None if compact else 2, ensure_ascii=False))


def _get_config(ctx: typer.Context) -> N8nConfig:
    url: str | None = ctx.obj.get("base_url")
    key: str | None = ctx.obj.get("api_key")

    if not url:
        _err("Error: n8n base URL required. Pass --base-url or set N8N_BASE_URL.")
        raise typer.Exit(1)
    if not key:
        _err("Error: n8n API key required. Pass --api-key or set N8N_API_KEY.")
        raise typer.Exit(1)

    return N8nConfig(base_url=url, api_key=key)


def _resolve_workflow_id(client: N8nClient, workflow_id: str | None, name: str | None) -> str:
    if workflow_id:
        return workflow_id
    if not name:
        _err("Error: Provide a workflow ID argument or --name.")
        raise typer.Exit(1)

    result = client.list_workflows(limit=100)
    workflows = result.get("data", [])

    exact = [w for w in workflows if w.get("name", "").lower() == name.lower()]
    matches = exact or [w for w in workflows if name.lower() in w.get("name", "").lower()]

    if not matches:
        _err(f"Error: No workflow found matching '{name}'")
        raise typer.Exit(1)
    if len(matches) > 1:
        _err(f"Error: Multiple workflows match '{name}':")
        for m in matches:
            _err(f"  {m['id']} — {m['name']}")
        raise typer.Exit(1)

    return matches[0]["id"]


def _fetch_workflow(
    client: N8nClient, workflow_id: str | None, name: str | None,
) -> tuple[str, dict[str, Any]]:
    """Resolve workflow ID and fetch workflow data. Raises typer.Exit(1) on error."""
    try:
        wf_id = _resolve_workflow_id(client, workflow_id, name)
        wf = client.get_workflow(wf_id)
    except typer.Exit:
        raise
    except Exception as e:
        _err(f"Error fetching workflow: {e}")
        raise typer.Exit(1)
    return wf_id, wf


def _find_node(wf: dict[str, Any], node_name: str) -> dict[str, Any]:
    """Find a node by name in a workflow. Raises typer.Exit(1) if not found."""
    nodes_by_name = {n["name"]: n for n in wf.get("nodes", [])}
    matched = nodes_by_name.get(node_name)
    if not matched:
        _err(f"Error: Node '{node_name}' not found. Available: {', '.join(sorted(nodes_by_name))}")
        raise typer.Exit(1)
    return matched


def _simplify_type(node_type: str) -> str:
    return (
        node_type
        .replace("n8n-nodes-base.", "")
        .replace("@n8n/n8n-nodes-langchain.", "langchain.")
        .replace("n8n-nodes-langchain.", "langchain.")
    )


@app.callback()
def main(
    ctx: typer.Context,
    base_url: Annotated[str | None, typer.Option(help="n8n instance URL", envvar=["N8N_BASE_URL", "N8N_HOST"])] = None,
    api_key: Annotated[str | None, typer.Option(help="n8n API key", envvar="N8N_API_KEY")] = None,
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url
    ctx.obj["api_key"] = api_key


@app.command()
def get(
    ctx: typer.Context,
    workflow_id: Annotated[str | None, typer.Argument(help="Workflow ID")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Find by name (case-insensitive, partial match)")] = None,
    node: Annotated[str | None, typer.Option("--node", "-N", help="Return only this node's JSON")] = None,
    output: Annotated[Path | None, typer.Option("-o", "--output", help="Save to file instead of stdout")] = None,
    strip_creds: Annotated[bool, typer.Option("--strip-creds/--keep-creds", help="Strip credential IDs from export")] = True,
    compact: Annotated[bool, typer.Option("--compact", help="Compact JSON, strip position/IDs from nodes")] = False,
) -> None:
    """Fetch a workflow as JSON. Use --node for a single node (much smaller)."""
    config = _get_config(ctx)

    with N8nClient(config) as client:
        _wf_id, wf = _fetch_workflow(client, workflow_id, name)

    if node:
        matched = _find_node(wf, node)
        if compact:
            matched = _strip_node_noise(matched)
        _out(matched, compact=compact)
        return

    export = {
        "name": wf.get("name", "Untitled"),
        "nodes": wf.get("nodes", []),
        "connections": wf.get("connections", {}),
        "settings": wf.get("settings", {}),
    }

    static = wf.get("staticData")
    if static is not None:
        export["staticData"] = static

    if strip_creds:
        for node_obj in export["nodes"]:
            if "credentials" in node_obj:
                for cred_key in node_obj["credentials"]:
                    cred = node_obj["credentials"][cred_key]
                    if isinstance(cred, dict):
                        cred.pop("id", None)

    if compact:
        export["nodes"] = [_strip_node_noise(n) for n in export["nodes"]]

    if output:
        text = json.dumps(export, indent=None if compact else 2, ensure_ascii=False)
        output.write_text(text, encoding="utf-8")
        _err(f"Saved to {output}")
    else:
        _out(export, compact=compact)


def _strip_node_noise(node: dict) -> dict:
    """Remove fields that waste tokens without affecting understanding."""
    return {k: v for k, v in node.items() if k not in ("position", "id")}


@app.command(name="list")
def list_workflows(
    ctx: typer.Context,
    active: Annotated[bool | None, typer.Option("--active/--all", help="Filter by active status")] = None,
    limit: Annotated[int, typer.Option(help="Max workflows to return")] = 50,
) -> None:
    """List workflows as JSON (id, name, active, tags, updatedAt)."""
    config = _get_config(ctx)

    with N8nClient(config) as client:
        try:
            result = client.list_workflows(active=active, limit=limit)
        except Exception as e:
            _err(f"Error: {e}")
            raise typer.Exit(1)

    rows = []
    for w in result.get("data", []):
        rows.append({
            "id": w["id"],
            "name": w["name"],
            "active": w.get("active", False),
            "tags": [t["name"] for t in w.get("tags", []) if "name" in t],
            "updatedAt": w.get("updatedAt"),
        })

    _out(rows)


@app.command()
def flow(
    ctx: typer.Context,
    workflow_id: Annotated[str | None, typer.Argument(help="Workflow ID")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Find by name (case-insensitive, partial match)")] = None,
) -> None:
    """Show workflow graph as JSON: nodes (name, type, disabled) and edges (from, to, input)."""
    config = _get_config(ctx)

    with N8nClient(config) as client:
        wf_id, wf = _fetch_workflow(client, workflow_id, name)

    connections = wf.get("connections", {})

    nodes = []
    for n in wf.get("nodes", []):
        entry: dict[str, Any] = {
            "name": n["name"],
            "type": _simplify_type(n.get("type", "")),
        }
        if n.get("disabled"):
            entry["disabled"] = True
        if n.get("executeOnce"):
            entry["executeOnce"] = True
        nodes.append(entry)

    edges = []
    for src_name, outputs in connections.items():
        for branch in outputs.get("main", []):
            for conn in branch:
                edge: dict[str, Any] = {
                    "from": src_name,
                    "to": conn["node"],
                }
                idx = conn.get("index", 0)
                if idx > 0:
                    edge["input"] = idx
                edges.append(edge)

    _out({
        "id": wf.get("id", wf_id),
        "name": wf["name"],
        "active": wf.get("active", False),
        "nodes": nodes,
        "edges": edges,
    })


@app.command()
def executions(
    ctx: typer.Context,
    workflow_id: Annotated[str | None, typer.Argument(help="Workflow ID")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Find by name (case-insensitive, partial match)")] = None,
    status: Annotated[str | None, typer.Option(help="Filter: success, error, waiting, running")] = None,
    limit: Annotated[int, typer.Option(help="Max executions to return")] = 10,
) -> None:
    """List recent executions as JSON. Use with 'execution-data' to debug."""
    config = _get_config(ctx)

    with N8nClient(config) as client:
        try:
            wf_id = _resolve_workflow_id(client, workflow_id, name)
            result = client.list_executions(workflow_id=wf_id, status=status, limit=limit)
        except typer.Exit:
            raise
        except Exception as e:
            _err(f"Error: {e}")
            raise typer.Exit(1)

    rows = []
    for ex in result.get("data", []):
        rows.append({
            "id": ex["id"],
            "status": ex.get("status"),
            "startedAt": ex.get("startedAt"),
            "stoppedAt": ex.get("stoppedAt"),
        })

    _out(rows)


@app.command(name="execution-data")
def execution_data(
    ctx: typer.Context,
    execution_id: Annotated[str, typer.Argument(help="Execution ID (from 'executions' command)")],
    node: Annotated[str | None, typer.Option("--node", "-n", help="Show full data for a specific node")] = None,
) -> None:
    """Inspect execution data. Without --node: summary. With --node: full run data for that node."""
    config = _get_config(ctx)

    with N8nClient(config) as client:
        try:
            exec_data = client.get_execution(execution_id, include_data=True)
        except Exception as e:
            _err(f"Error: {e}")
            raise typer.Exit(1)

    result_data = (exec_data.get("data") or {}).get("resultData", {})
    run_data: dict = result_data.get("runData", {})
    exec_error: dict | None = result_data.get("error")

    if node:
        node_runs = run_data.get(node)
        if not node_runs:
            _err(f"Error: Node '{node}' not found. Nodes that ran: {', '.join(sorted(run_data))}")
            raise typer.Exit(1)
        _out(node_runs)
        return

    wf_nodes = (exec_data.get("workflowData") or {}).get("nodes", [])
    node_types = {n["name"]: _simplify_type(n.get("type", "")) for n in wf_nodes}

    nodes_summary = []
    for node_name, runs in run_data.items():
        for run in runs:
            error = run.get("error")
            main_out = (run.get("data") or {}).get("main", [])
            item_count = sum(len(b) for b in main_out if b)
            entry: dict[str, Any] = {
                "node": node_name,
                "type": node_types.get(node_name, ""),
                "items_out": item_count,
                "ms": run.get("executionTime"),
            }
            if error:
                entry["error"] = error.get("message")
            nodes_summary.append(entry)

    out: dict[str, Any] = {"execution_id": execution_id}
    if exec_error:
        out["error"] = exec_error.get("message")
        failed = (exec_error.get("node") or {}).get("name")
        if failed:
            out["failed_node"] = failed
    out["nodes"] = nodes_summary

    _out(out)


def _read_workflow_json(file: Path | None) -> dict[str, Any]:
    if file:
        text = file.read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            _err("Error: Provide workflow JSON via --file or pipe to stdin.")
            raise typer.Exit(1)
        text = sys.stdin.read()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        _err(f"Error: Invalid JSON: {e}")
        raise typer.Exit(1)

    if "nodes" not in data or "connections" not in data:
        _err("Error: JSON must contain 'nodes' and 'connections' keys.")
        raise typer.Exit(1)

    return data


def _compute_diff(current: dict[str, Any], incoming: dict[str, Any]) -> list[str]:
    """Compute a structural diff between two workflow versions. Returns list of change descriptions."""
    cur_nodes = {n["name"]: n for n in current.get("nodes", [])}
    inc_nodes = {n["name"]: n for n in incoming.get("nodes", [])}

    cur_names = set(cur_nodes)
    inc_names = set(inc_nodes)
    lines: list[str] = []

    for n in sorted(inc_names - cur_names):
        lines.append(f"+ {n} ({_simplify_type(inc_nodes[n].get('type', ''))})")
    for n in sorted(cur_names - inc_names):
        lines.append(f"- {n} ({_simplify_type(cur_nodes[n].get('type', ''))})")

    for n in sorted(cur_names & inc_names):
        changed = [k for k in ("type", "parameters", "disabled", "credentials")
                    if cur_nodes[n].get(k) != inc_nodes[n].get(k)]
        if changed:
            lines.append(f"~ {n}: {', '.join(changed)}")

    if current.get("connections", {}) != incoming.get("connections", {}):
        lines.append("~ connections changed")

    return lines


def _set_nested(obj: Any, path: str, value: Any) -> None:
    keys = path.split(".")
    for key in keys[:-1]:
        if isinstance(obj, list):
            obj = obj[int(key)]
        else:
            obj = obj[key]
    last = keys[-1]
    if isinstance(obj, list):
        obj[int(last)] = value
    else:
        obj[last] = value


@app.command(name="set-node-param")
def set_node_param(
    ctx: typer.Context,
    node: Annotated[str, typer.Option("--node", "-N", help="Node name to modify")],
    param: Annotated[str, typer.Option("--param", "-p", help="Dotted path (e.g. 'queryParameters.parameters')")],
    workflow_id: Annotated[str | None, typer.Argument(help="Workflow ID")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Find by name")] = None,
    value: Annotated[str | None, typer.Option("--value", "-v", help="New value (string)")] = None,
    json_value: Annotated[str | None, typer.Option("--json", "-j", help="New value as JSON (objects, arrays, numbers, booleans)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying")] = False,
) -> None:
    """Patch a single node parameter in-place."""
    if value is None and json_value is None:
        _err("Error: Provide either --value or --json.")
        raise typer.Exit(1)
    if value is not None and json_value is not None:
        _err("Error: Provide --value or --json, not both.")
        raise typer.Exit(1)

    parsed_value: Any = value
    if json_value is not None:
        try:
            parsed_value = json.loads(json_value)
        except json.JSONDecodeError as e:
            _err(f"Error: Invalid JSON for --json: {e}")
            raise typer.Exit(1)

    config = _get_config(ctx)

    with N8nClient(config) as client:
        try:
            wf_id, wf = _fetch_workflow(client, workflow_id, name)
            target = _find_node(wf, node)

            param_root = target["parameters"]
            try:
                obj = param_root
                for key in param.split("."):
                    obj = obj[int(key)] if isinstance(obj, list) else obj[key]
                current_value = obj
            except (KeyError, IndexError, TypeError):
                current_value = None

            if dry_run:
                _out({
                    "dry_run": True,
                    "workflow": wf.get("name", wf_id),
                    "node": node,
                    "param": f"parameters.{param}",
                    "current": current_value,
                    "new": parsed_value,
                })
                return

            _set_nested(param_root, param, parsed_value)

            was_active = wf.get("active", False)
            if was_active:
                client.deactivate_workflow(wf_id)

            client.update_workflow(wf_id, wf)
        except typer.Exit:
            raise
        except (KeyError, IndexError, TypeError) as e:
            _err(f"Error: Invalid parameter path 'parameters.{param}': {e}")
            raise typer.Exit(1)
        except Exception as e:
            _err(f"Error updating workflow: {e}")
            raise typer.Exit(1)

    result: dict[str, Any] = {
        "updated": True,
        "workflow": wf.get("name", wf_id),
        "node": node,
        "param": f"parameters.{param}",
    }
    if was_active:
        result["deactivated"] = True
    _out(result)


def _merge_credentials(
    current_nodes: list[dict[str, Any]],
    incoming_nodes: list[dict[str, Any]],
) -> None:
    """Backfill credential references from the live workflow into incoming nodes."""
    live_creds = {n["name"]: n.get("credentials", {}) for n in current_nodes}

    for node_obj in incoming_nodes:
        live = live_creds.get(node_obj.get("name"))
        if not live:
            continue

        incoming = node_obj.get("credentials")

        if incoming is None:
            node_obj["credentials"] = live
            continue

        for cred_key, live_cred in live.items():
            if cred_key not in incoming:
                incoming[cred_key] = live_cred
            elif isinstance(incoming[cred_key], dict) and isinstance(live_cred, dict):
                if "id" not in incoming[cred_key] and "id" in live_cred:
                    incoming[cred_key]["id"] = live_cred["id"]


@app.command(name="update-workflow")
def update_workflow(
    ctx: typer.Context,
    workflow_id: Annotated[str | None, typer.Argument(help="Workflow ID")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Find by name")] = None,
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Path to workflow JSON file")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show diff without applying")] = False,
) -> None:
    """Update a workflow from JSON (file or stdin). Deactivates active workflows before update.

    Credentials are automatically backfilled from the live workflow.
    """
    payload = _read_workflow_json(file)
    config = _get_config(ctx)

    with N8nClient(config) as client:
        try:
            wf_id, current = _fetch_workflow(client, workflow_id, name)
            changes = _compute_diff(current, payload)

            _merge_credentials(current.get("nodes", []), payload.get("nodes", []))

            if dry_run:
                _out({
                    "dry_run": True,
                    "workflow": current.get("name", wf_id),
                    "id": wf_id,
                    "active": current.get("active", False),
                    "changes": changes or ["no structural changes"],
                })
                return

            was_active = current.get("active", False)
            if was_active:
                client.deactivate_workflow(wf_id)

            updated = client.update_workflow(wf_id, payload)
        except typer.Exit:
            raise
        except Exception as e:
            _err(f"Error updating workflow: {e}")
            raise typer.Exit(1)

    result: dict[str, Any] = {
        "updated": True,
        "workflow": updated.get("name", wf_id),
        "id": wf_id,
        "node_count": len(updated.get("nodes", [])),
        "changes": changes or ["no structural changes"],
    }
    if was_active:
        result["deactivated"] = True
    _out(result)


@app.command()
def retry(
    ctx: typer.Context,
    execution_id: Annotated[str, typer.Argument(help="Execution ID")],
    use_latest: Annotated[bool, typer.Option("--use-latest", help="Retry with the latest workflow version")] = False,
) -> None:
    """Retry a failed execution. Returns the new execution ID and status."""
    config = _get_config(ctx)

    with N8nClient(config) as client:
        try:
            result = client.retry_execution(execution_id, load_workflow=use_latest)
        except Exception as e:
            _err(f"Error retrying execution: {e}")
            raise typer.Exit(1)

    _out({
        "retried": True,
        "new_execution_id": result.get("id"),
        "status": result.get("status"),
        "retryOf": execution_id,
        "used_latest_workflow": use_latest,
    })


if __name__ == "__main__":
    app()
