from datetime import datetime, timezone

from payment_retention import PaymentEvent, PaymentState, decide_cleanup


def test_stale_low_risk_is_deleted_while_high_risk_is_retained() -> None:
    cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
    decided_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    events = [
        PaymentEvent(
            event_id="pay_low",
            account_id="acct_17",
            state=PaymentState.SETTLED,
            occurred_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            amount_minor=2400,
            risk_score=12,
        ),
        PaymentEvent(
            event_id="pay_review",
            account_id="acct_42",
            state=PaymentState.FAILED,
            occurred_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            amount_minor=95000,
            risk_score=88,
        ),
    ]

    result = decide_cleanup(events, cutoff_at=cutoff, decided_at=decided_at)

    assert result.deleted_event_ids == ["pay_low"]
    assert result.retained_event_ids == ["pay_review"]
    assert [(item.event_id, item.action, item.reason) for item in result.notifications] == [
        ("pay_low", "delete", "past retention cutoff and no risk hold"),
        ("pay_review", "retain", "risk hold"),
    ]
    assert all(item.decided_at == decided_at for item in result.notifications)
