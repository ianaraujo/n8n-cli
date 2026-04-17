"""Tests for the n8n CLI."""

import json
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from src import cli as cli_mod
from src.cli import (
    _check_active_confirmed,
    _check_blast_radius,
    _check_read_only,
    _compute_diff,
    _find_node,
    _resolve_workflow_id,
    _simplify_type,
    _snapshot_workflow,
    _strip_node_noise,
    app,
)

runner = CliRunner()


# ── Unit tests ──────────────────────────────────────────────────────────────

class TestSimplifyType:
    def test_base_node(self):
        assert _simplify_type("n8n-nodes-base.httpRequest") == "httpRequest"

    def test_langchain_node(self):
        assert _simplify_type("@n8n/n8n-nodes-langchain.agent") == "langchain.agent"

    def test_legacy_langchain(self):
        assert _simplify_type("n8n-nodes-langchain.openAi") == "langchain.openAi"

    def test_unknown_type(self):
        assert _simplify_type("custom.node") == "custom.node"


class TestStripNodeNoise:
    def test_removes_position_and_id(self):
        node = {"name": "HTTP", "type": "httpRequest", "position": [0, 0], "id": "abc"}
        result = _strip_node_noise(node)
        assert "position" not in result
        assert "id" not in result
        assert result["name"] == "HTTP"

    def test_keeps_other_fields(self):
        node = {"name": "HTTP", "parameters": {"url": "https://example.com"}}
        assert _strip_node_noise(node) == node


class TestFindNode:
    def test_finds_existing_node(self):
        wf = {"nodes": [{"name": "Node A"}, {"name": "Node B"}]}
        result = _find_node(wf, "Node A")
        assert result["name"] == "Node A"

    def test_raises_on_missing(self):
        import typer
        wf = {"nodes": [{"name": "Node A"}]}
        with pytest.raises(typer.Exit):
            _find_node(wf, "Missing Node")


class TestComputeDiff:
    def _wf(self, nodes, connections=None):
        return {"nodes": nodes, "connections": connections or {}}

    def test_added_node(self):
        current = self._wf([{"name": "A", "type": "n8n-nodes-base.set"}])
        incoming = self._wf([
            {"name": "A", "type": "n8n-nodes-base.set"},
            {"name": "B", "type": "n8n-nodes-base.httpRequest"},
        ])
        diff = _compute_diff(current, incoming)
        assert any("+ B" in line for line in diff)

    def test_removed_node(self):
        current = self._wf([
            {"name": "A", "type": "n8n-nodes-base.set"},
            {"name": "B", "type": "n8n-nodes-base.httpRequest"},
        ])
        incoming = self._wf([{"name": "A", "type": "n8n-nodes-base.set"}])
        diff = _compute_diff(current, incoming)
        assert any("- B" in line for line in diff)

    def test_modified_node(self):
        current = self._wf([{"name": "A", "type": "n8n-nodes-base.set", "parameters": {"old": 1}}])
        incoming = self._wf([{"name": "A", "type": "n8n-nodes-base.set", "parameters": {"new": 2}}])
        diff = _compute_diff(current, incoming)
        assert any("~ A" in line and "parameters" in line for line in diff)

    def test_no_changes(self):
        node = {"name": "A", "type": "n8n-nodes-base.set", "parameters": {}}
        current = self._wf([node])
        incoming = self._wf([node])
        assert _compute_diff(current, incoming) == []

    def test_connection_change(self):
        node = {"name": "A", "type": "n8n-nodes-base.set"}
        current = self._wf([node], connections={"A": {"main": [[{"node": "B"}]]}})
        incoming = self._wf([node], connections={"A": {"main": [[{"node": "C"}]]}})
        diff = _compute_diff(current, incoming)
        assert any("connections" in line for line in diff)


# ── CLI integration tests ────────────────────────────────────────────────────

class TestHelp:
    def test_root_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "n8n" in result.output.lower()

    def test_get_help(self):
        result = runner.invoke(app, ["get", "--help"])
        assert result.exit_code == 0
        assert "--node" in result.output

    def test_list_help(self):
        result = runner.invoke(app, ["list", "--help"])
        assert result.exit_code == 0
        assert "--limit" in result.output

    def test_set_node_param_help(self):
        result = runner.invoke(app, ["set-node-param", "--help"])
        assert result.exit_code == 0
        assert "--node" in result.output
        assert "--param" in result.output


class TestMissingCredentials:
    def test_list_requires_url(self):
        result = runner.invoke(app, ["list"], env={"N8N_BASE_URL": "", "N8N_API_KEY": ""})
        assert result.exit_code != 0

    def test_get_requires_url(self):
        result = runner.invoke(app, ["get", "some-id"], env={"N8N_BASE_URL": "", "N8N_API_KEY": ""})
        assert result.exit_code != 0


class TestSetNodeParamValidation:
    def test_requires_node_option(self):
        result = runner.invoke(
            app,
            ["--base-url", "http://localhost:5678", "--api-key", "key",
             "set-node-param", "wf-id", "--param", "url", "--value", "x"],
        )
        assert result.exit_code != 0

    def test_requires_param_option(self):
        result = runner.invoke(
            app,
            ["--base-url", "http://localhost:5678", "--api-key", "key",
             "set-node-param", "wf-id", "--node", "MyNode", "--value", "x"],
        )
        assert result.exit_code != 0

    def test_requires_value_or_json(self):
        result = runner.invoke(
            app,
            ["--base-url", "http://localhost:5678", "--api-key", "key",
             "set-node-param", "wf-id", "--node", "MyNode", "--param", "url"],
        )
        assert result.exit_code != 0
        assert "value" in result.output.lower() or "json" in result.output.lower()

    def test_rejects_both_value_and_json(self):
        result = runner.invoke(
            app,
            ["--base-url", "http://localhost:5678", "--api-key", "key",
             "set-node-param", "wf-id", "--node", "MyNode", "--param", "url",
             "--value", "x", "--json", '"y"'],
        )
        assert result.exit_code != 0


# ── Guardrail tests ─────────────────────────────────────────────────────────


class TestReadOnly:
    def test_blocks_when_flag_set(self, monkeypatch):
        monkeypatch.setenv("N8N_CLI_READ_ONLY", "1")
        with pytest.raises(typer.Exit):
            _check_read_only()

    def test_passes_when_unset(self, monkeypatch):
        monkeypatch.delenv("N8N_CLI_READ_ONLY", raising=False)
        _check_read_only()

    def test_accepts_truthy_variants(self, monkeypatch):
        for val in ("true", "yes", "on", "TRUE"):
            monkeypatch.setenv("N8N_CLI_READ_ONLY", val)
            with pytest.raises(typer.Exit):
                _check_read_only()

    def test_ignores_falsey_variants(self, monkeypatch):
        for val in ("0", "false", "no", ""):
            monkeypatch.setenv("N8N_CLI_READ_ONLY", val)
            _check_read_only()

    def test_set_node_param_blocked(self, monkeypatch):
        monkeypatch.setenv("N8N_CLI_READ_ONLY", "1")
        result = runner.invoke(
            app,
            ["--base-url", "http://localhost:5678", "--api-key", "key",
             "set-node-param", "wf-id", "--node", "N", "--param", "url", "--value", "x"],
        )
        assert result.exit_code != 0

    def test_retry_blocked(self, monkeypatch):
        monkeypatch.setenv("N8N_CLI_READ_ONLY", "1")
        result = runner.invoke(
            app,
            ["--base-url", "http://localhost:5678", "--api-key", "key",
             "retry", "exec-id"],
        )
        assert result.exit_code != 0


class TestActiveConfirmation:
    def test_inactive_workflow_passes(self):
        _check_active_confirmed({"active": False, "name": "W"}, confirm_active=False)

    def test_active_blocked_without_confirm(self):
        with pytest.raises(typer.Exit):
            _check_active_confirmed({"active": True, "name": "W"}, confirm_active=False)

    def test_active_allowed_with_flag(self):
        _check_active_confirmed({"active": True, "name": "W"}, confirm_active=True)

    def test_active_allowed_with_env(self, monkeypatch):
        monkeypatch.setenv("N8N_CLI_CONFIRM_ACTIVE", "1")
        _check_active_confirmed({"active": True, "name": "W"}, confirm_active=False)


class TestBlastRadius:
    def _wf(self, n_nodes, n_edges=0):
        nodes = [{"name": f"N{i}"} for i in range(n_nodes)]
        connections = {}
        remaining = n_edges
        for i in range(n_nodes):
            if remaining <= 0:
                break
            targets = [{"node": f"T{j}"} for j in range(min(remaining, 3))]
            remaining -= len(targets)
            connections[f"N{i}"] = {"main": [targets]}
        return {"nodes": nodes, "connections": connections}

    def test_no_removal_passes(self):
        wf = self._wf(5, 4)
        stats = _check_blast_radius(wf, wf, force=False)
        assert stats["removed_nodes"] == 0
        assert stats["removed_edges"] == 0

    def test_small_removal_passes(self):
        current = self._wf(10, 10)
        incoming = self._wf(8, 9)
        _check_blast_radius(current, incoming, force=False)

    def test_node_count_cap_blocks(self):
        current = self._wf(20, 0)
        incoming = self._wf(10, 0)  # removes 10 nodes (> 3 cap, > 50%)
        with pytest.raises(typer.Exit):
            _check_blast_radius(current, incoming, force=False)

    def test_node_percent_cap_blocks(self):
        current = self._wf(4, 0)
        incoming = self._wf(1, 0)  # removes 3 (== 75%, exceeds 50%)
        with pytest.raises(typer.Exit):
            _check_blast_radius(current, incoming, force=False)

    def test_edge_cap_blocks(self):
        current = self._wf(5, 20)
        incoming = self._wf(5, 4)  # removes 16 edges (> 5 cap)
        with pytest.raises(typer.Exit):
            _check_blast_radius(current, incoming, force=False)

    def test_force_bypasses(self):
        current = self._wf(20, 0)
        incoming = self._wf(0, 0)
        stats = _check_blast_radius(current, incoming, force=True)
        assert stats["removed_nodes"] == 20


class TestSnapshot:
    def test_writes_json_to_backup_root(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cli_mod, "BACKUP_ROOT", tmp_path)
        wf = {"name": "Demo", "nodes": [{"name": "A"}], "connections": {}}
        path = _snapshot_workflow("wf-123", wf)
        assert path.exists()
        assert path.parent == tmp_path / "wf-123"
        assert json.loads(path.read_text()) == wf

    def test_sanitizes_unsafe_ids(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cli_mod, "BACKUP_ROOT", tmp_path)
        path = _snapshot_workflow("../evil/id", {})
        assert tmp_path in path.parents
        assert ".." not in path.parts
        assert "/" not in path.parent.name


class TestExactMatch:
    def _client(self, names):
        client = MagicMock()
        client.list_workflows.return_value = {
            "data": [{"id": f"id-{i}", "name": n} for i, n in enumerate(names)]
        }
        return client

    def test_fuzzy_substring_works_when_not_exact(self):
        client = self._client(["Sync Prod", "Sync Test"])
        # "Sync Test" exact match among the two — picks it
        result = _resolve_workflow_id(client, None, "sync test", exact=False)
        assert result == "id-1"

    def test_exact_rejects_case_mismatch(self):
        client = self._client(["Sync Prod"])
        with pytest.raises(typer.Exit):
            _resolve_workflow_id(client, None, "sync prod", exact=True)

    def test_exact_rejects_substring(self):
        client = self._client(["Sync Prod"])
        with pytest.raises(typer.Exit):
            _resolve_workflow_id(client, None, "Sync", exact=True)

    def test_exact_accepts_exact_name(self):
        client = self._client(["Sync Prod", "Sync Test"])
        assert _resolve_workflow_id(client, None, "Sync Prod", exact=True) == "id-0"

    def test_id_bypasses_resolution(self):
        client = MagicMock()
        assert _resolve_workflow_id(client, "explicit-id", None, exact=True) == "explicit-id"
        client.list_workflows.assert_not_called()
