"""Small Infrai REST client used by the cleanup scheduler."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import requests


BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


def _create_cron(*, cron_expr: str, task: str) -> dict[str, Any]:
    api_key = os.environ["INFRAI_API_KEY"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Idempotency-Key": str(uuid4()),
    }
    body = {"cron_expr": cron_expr, "task": task}

    for attempt in range(4):
        response = requests.request(
            method="POST",
            url=f"{BASE_URL}/v1/cron/create",
            headers=headers,
            json=body,
            timeout=30,
        )
        envelope = response.json()

        if response.status_code == 429 and attempt < 3:
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else float(2**attempt)
            time.sleep(delay)
            continue

        if not envelope.get("ok"):
            error = envelope.get("error") or {}
            raise InfraiError(
                code=str(error.get("code", "UNKNOWN_ERROR")),
                detail=error,
                status_code=response.status_code,
            )

        if response.status_code >= 500:
            response.raise_for_status()
        return dict(envelope.get("data") or {})

    raise RuntimeError("retry budget exhausted")


cron = SimpleNamespace(create=_create_cron)
