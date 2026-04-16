"""Tests for the n8n CLI."""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import (
    _compute_diff,
    _find_node,
    _simplify_type,
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
