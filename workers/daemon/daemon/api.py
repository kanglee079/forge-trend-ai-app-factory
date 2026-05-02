from typing import Any
from uuid import UUID

import httpx

from daemon.config import settings


class FactoryApi:
    def __init__(self) -> None:
        self.client = httpx.Client(base_url=settings.worker_api_base_url, timeout=30)

    def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/workers/register", json=payload)

    def heartbeat(self, worker_id: str, status: str = "online", current_job_id: str | None = None) -> None:
        self._request("POST", f"/workers/{worker_id}/heartbeat", json={"status": status, "current_job_id": current_job_id})

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self._request("GET", f"/projects/{project_id}")

    def list_ideas(self) -> list[dict[str, Any]]:
        return self._request("GET", "/ideas")

    def set_project_status(self, project_id: str, status: str, workspace_path: str | None = None) -> dict[str, Any]:
        return self._request("PATCH", f"/internal/projects/{project_id}/status", json={"status": status, "workspace_path": workspace_path})

    def start_run(self, project_id: str, agent_name: str, input_json: dict[str, Any], iteration: int = 0) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/internal/projects/{project_id}/agent-runs",
            json={"agent_name": agent_name, "status": "running", "input_json": input_json, "iteration": iteration},
        )

    def finish_run(
        self,
        run_id: str | UUID,
        status: str,
        output_json: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/internal/agent-runs/{run_id}",
            json={"status": status, "output_json": output_json or {}, "error_message": error_message},
        )

    def event(
        self,
        project_id: str,
        step: str,
        message: str,
        *,
        level: str = "info",
        agent_run_id: str | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> None:
        self._request(
            "POST",
            f"/internal/projects/{project_id}/events",
            json={
                "agent_run_id": agent_run_id,
                "step": step,
                "level": level,
                "message": message,
                "stdout": stdout,
                "stderr": stderr,
                "metadata_json": metadata_json or {},
            },
        )

    def qa_result(self, project_id: str, command: str, exit_code: int, stdout: str, stderr: str) -> None:
        status = "passed" if exit_code == 0 else "failed"
        self._request(
            "POST",
            f"/internal/projects/{project_id}/qa",
            json={"status": status, "command": command, "exit_code": exit_code, "stdout": stdout, "stderr": stderr},
        )

    def policy_result(self, project_id: str, result: dict[str, Any]) -> None:
        self._request("POST", f"/internal/projects/{project_id}/policy", json=result)

    def artifact(self, project_id: str, kind: str, name: str, path: str, metadata_json: dict[str, Any] | None = None) -> None:
        self._request(
            "POST",
            f"/internal/projects/{project_id}/artifacts",
            json={"kind": kind, "name": name, "path": path, "metadata_json": metadata_json or {}},
        )

    def build(self, project_id: str, status: str, platform: str = "android", artifact_path: str | None = None, logs: str | None = None) -> None:
        self._request(
            "POST",
            f"/internal/projects/{project_id}/builds",
            json={"status": status, "platform": platform, "artifact_path": artifact_path, "logs": logs},
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        if response.content:
            return response.json()
        return None
