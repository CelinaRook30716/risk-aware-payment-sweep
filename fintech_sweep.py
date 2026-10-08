"""Risk-sensitive stale payment cleanup service."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel, Field

from payment_retention import PaymentEvent, PaymentState, decide_cleanup


class PaymentEventRequest(BaseModel):
    event_id: str
    account_id: str
    state: PaymentState
    occurred_at: datetime
    amount_minor: int = Field(ge=0)
    risk_score: int = Field(ge=0, le=100)


class SweepRequest(BaseModel):
    cutoff_at: datetime
    events: list[PaymentEventRequest]


class AuditNotification(BaseModel):
    event_id: str
    account_id: str
    action: str
    reason: str
    decided_at: datetime


class SweepResult(BaseModel):
    deleted_event_ids: list[str]
    retained_event_ids: list[str]
    notifications: list[AuditNotification]


service = FastAPI(title="Fintech retention sweep")


@service.post("/maintenance/sweep", response_model=SweepResult)
def run_sweep(request: SweepRequest) -> SweepResult:
    events = [PaymentEvent(**event.model_dump()) for event in request.events]
    result = decide_cleanup(
        events,
        cutoff_at=request.cutoff_at,
        decided_at=datetime.now(timezone.utc),
    )
    return SweepResult(
        deleted_event_ids=result.deleted_event_ids,
        retained_event_ids=result.retained_event_ids,
        notifications=[AuditNotification(**vars(item)) for item in result.notifications],
    )
