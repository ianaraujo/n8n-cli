"""n8n REST API client for fetching workflows and executions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class N8nConfig:
    """Configuration for connecting to an n8n instance."""

    base_url: str
    api_key: str

    @property
    def headers(self) -> dict[str, str]:
        return {
            "X-N8N-API-KEY": self.api_key,
            "Accept": "application/json",
        }

    @property
    def api_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/v1"


class N8nClient:
    """Client for the n8n public REST API."""

    def __init__(self, config: N8nConfig, timeout: float = 30.0):
        self.config = config
        self.client = httpx.Client(
            base_url=config.api_url,
            headers=config.headers,
            timeout=timeout,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "N8nClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ── Workflows ──────────────────────────────────────────────

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Fetch a single workflow by ID.

        Returns the full workflow object including nodes, connections,
        settings, and metadata.

        API: GET /api/v1/workflows/{id}
        """
        resp = self.client.get(f"/workflows/{workflow_id}")
        resp.raise_for_status()
        return resp.json()

    def list_workflows(
        self,
        *,
        active: bool | None = None,
        limit: int = 100,
        cursor: str | None = None,
        tags: str | None = None,
    ) -> dict[str, Any]:
        """List workflows with optional filters.

        API: GET /api/v1/workflows
        """
        params: dict[str, Any] = {"limit": limit}
        if active is not None:
            params["active"] = str(active).lower()
        if cursor:
            params["cursor"] = cursor
        if tags:
            params["tags"] = tags

        resp = self.client.get("/workflows", params=params)
        resp.raise_for_status()
        return resp.json()

    # ── Executions ─────────────────────────────────────────────

    def list_executions(
        self,
        *,
        workflow_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
        include_data: bool = False,
    ) -> dict[str, Any]:
        """List executions with optional filters.

        API: GET /api/v1/executions
        """
        params: dict[str, Any] = {"limit": limit}
        if workflow_id:
            params["workflowId"] = workflow_id
        if status:
            params["status"] = status
        if include_data:
            params["includeData"] = "true"

        resp = self.client.get("/executions", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_execution(
        self, execution_id: str, *, include_data: bool = True
    ) -> dict[str, Any]:
        """Fetch a single execution by ID.

        API: GET /api/v1/executions/{id}
        """
        params: dict[str, Any] = {}
        if include_data:
            params["includeData"] = "true"

        resp = self.client.get(f"/executions/{execution_id}", params=params)
        resp.raise_for_status()
        return resp.json()

    # ── Write Operations ────────────────────────────────────────

    # Settings keys that the n8n PUT endpoint rejects even though
    # GET returns them.  Strip these before sending.
    _REJECTED_SETTINGS_KEYS = frozenset({"binaryMode", "timeSavedMode"})

    def update_workflow(
        self, workflow_id: str, workflow_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing workflow.

        Sends only the safe subset of fields (name, nodes, connections,
        settings, staticData, pinData) to avoid overwriting server-managed
        metadata.  Strips settings keys that the PUT endpoint rejects.

        API: PUT /api/v1/workflows/{id}
        """
        body: dict[str, Any] = {}
        for key in ("name", "nodes", "connections", "staticData"):
            if key in workflow_data:
                body[key] = workflow_data[key]

        # Filter settings to remove keys the API rejects
        if "settings" in workflow_data:
            body["settings"] = {
                k: v
                for k, v in workflow_data["settings"].items()
                if k not in self._REJECTED_SETTINGS_KEYS
            }

        resp = self.client.put(f"/workflows/{workflow_id}", json=body)
        resp.raise_for_status()
        return resp.json()

    def deactivate_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Deactivate (unpublish) a workflow.

        API: POST /api/v1/workflows/{id}/deactivate
        """
        resp = self.client.post(f"/workflows/{workflow_id}/deactivate")
        resp.raise_for_status()
        return resp.json()

    def retry_execution(
        self, execution_id: str, *, load_workflow: bool = False
    ) -> dict[str, Any]:
        """Retry a failed or stopped execution.

        If load_workflow is True, retries using the latest workflow version
        instead of the version at the time of original execution.

        API: POST /api/v1/executions/{id}/retry
        """
        body = {"loadWorkflow": True} if load_workflow else {}
        resp = self.client.post(f"/executions/{execution_id}/retry", json=body)
        resp.raise_for_status()
        return resp.json()

