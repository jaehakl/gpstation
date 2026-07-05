from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel


class WorkerSession(BaseModel):
    id: str
    user_id: str
    worker_name: str
    status: str
    capabilities: list[str]
    active_session_count: int
    connected_at: str
    last_heartbeat_at: str


class SessionDescriptor(BaseModel):
    session_id: str
    worker_session_id: str
    signaling_url: str
    token: str
    expires_at: str


class GpStationClient:
    def __init__(self, api_base_url: str, token: str, timeout: float = 15.0) -> None:
        self.api_base_url = api_base_url.rstrip("/") or "http://127.0.0.1:8100"
        self.token = token
        self.timeout = timeout

    def list_workers(self) -> list[WorkerSession]:
        payload = self._request("GET", "/v1/workers")
        return [WorkerSession.model_validate(item) for item in payload]

    def create_session(self, worker_session_id: str, ttl_seconds: int | None = None) -> SessionDescriptor:
        payload = self._request(
            "POST",
            "/v1/sessions",
            json={"worker_session_id": worker_session_id, "ttl_seconds": ttl_seconds},
        )
        return SessionDescriptor.model_validate(payload)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = {"Authorization": f"Bearer {self.token}"}
        with httpx.Client(timeout=self.timeout, headers=headers) as client:
            response = client.request(method, f"{self.api_base_url}{path}", **kwargs)
            response.raise_for_status()
            return response.json()
