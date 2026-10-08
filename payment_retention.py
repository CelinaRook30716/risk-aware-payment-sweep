"""Payment retention models and deterministic sweep policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class PaymentState(str, Enum):
    SETTLED = "settled"
    FAILED = "failed"
    PENDING = "pending"


@dataclass(frozen=True)
class PaymentEvent:
    event_id: str
    account_id: str
    state: PaymentState
    occurred_at: datetime
    amount_minor: int
    risk_score: int


@dataclass(frozen=True)
class AuditNotification:
    event_id: str
    account_id: str
    action: str
    reason: str
    decided_at: datetime


@dataclass(frozen=True)
class SweepResult:
    deleted_event_ids: list[str]
    retained_event_ids: list[str]
    notifications: list[AuditNotification]


def decide_cleanup(
    events: list[PaymentEvent], *, cutoff_at: datetime, decided_at: datetime
) -> SweepResult:
    deleted: list[str] = []
    retained: list[str] = []
    notices: list[AuditNotification] = []

    for event in events:
        is_stale = event.occurred_at < cutoff_at
        is_risk_sensitive = event.risk_score >= 70 or event.state == PaymentState.PENDING

        if is_stale and not is_risk_sensitive:
            action = "delete"
            reason = "past retention cutoff and no risk hold"
            deleted.append(event.event_id)
        else:
            action = "retain"
            reason = "risk hold" if is_stale else "within retention window"
            retained.append(event.event_id)

        notices.append(
            AuditNotification(
                event_id=event.event_id,
                account_id=event.account_id,
                action=action,
                reason=reason,
                decided_at=decided_at,
            )
        )

    return SweepResult(deleted, retained, notices)
