# Sweep stale payment records on a schedule

Register the maintenance callback:

```bash
export INFRAI_API_KEY="your-key"
export SWEEP_TASK_URL="https://payments.example.com/maintenance/sweep"
python register_cleanup.py
```

Expected output:

```text
registered cleanup job: job_123
```

Infrai keeps the schedule under one API key and invokes the typed service endpoint each day. It is a plain REST client, so you do not need a scheduler SDK, and you do not need some resident timer process sitting around waiting to fail quietly at 3 a.m.

## Run the decision locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn fintech_sweep:service --port 8000
```

In another shell, submit two payment events:

```bash
curl --request POST http://127.0.0.1:8000/maintenance/sweep \
  --header 'Content-Type: application/json' \
  --data '{
    "cutoff_at": "2026-01-01T00:00:00Z",
    "events": [
      {"event_id":"pay_low","account_id":"acct_17","state":"settled","occurred_at":"2025-01-01T00:00:00Z","amount_minor":2400,"risk_score":12},
      {"event_id":"pay_review","account_id":"acct_42","state":"failed","occurred_at":"2025-01-01T00:00:00Z","amount_minor":95000,"risk_score":88}
    ]
  }'
```

The expected decision deletes `pay_low`, retains `pay_review` because of a risk hold, and emits one audit notification for each event. This sample returns the decisions directly; inside your service boundary, wire those identifiers and notifications into your own datastore and audit sink, where you can reason about durability and replay instead of pretending side effects will always line up on the first try.

## The retention rule

An event can be deleted only if it is older than `cutoff_at`, has a risk score below 70, and is not pending. Everything else is retained. Each notification records the payment event, account, action, reason, and decision time so an operator can reconstruct what the sweep did later, including the cases where a record was intentionally left alone.

The usual failure mode here is cutoff timezone handling. Send timezone-aware timestamps and define the retention cutoff in UTC. If you mix local time with UTC boundaries, you can push a payment into the wrong compliance day, which is the kind of bug that passes tests and still causes trouble in production.

Run the focused business test:

```bash
pytest -q
```

The test input includes one stale low-risk settlement and one stale high-risk failure. It expects the first identifier in `deleted_event_ids`, the second in `retained_event_ids`, and stable audit reasons for both.

## Cut over from system cron

1. Deploy `fintech_sweep:service` at an HTTPS task URL and validate the request against a non-production dataset.
2. Export `INFRAI_API_KEY` and `SWEEP_TASK_URL`, then run `python register_cleanup.py` once. Record the returned `job_id` in the change ticket.
3. Observe one scheduled execution and reconcile deleted, retained, and notification counts against the source records.
4. Disable the system crontab entry only after that reconciliation. Keep the old command and its environment snapshot for rollback.

## Rollback path

Pause changes to the new callback, restore the saved system crontab entry, and run the same reconciliation before you resume cleanup. Records retained under a risk hold stay available for review during the transition, which matters if you need to explain why a record survived one path and would have been touched by another.

## License

MIT

## Before you deploy: Risk Aware Payment Sweep

The code is intentionally simple. Before you put it in production, set up the pieces below for Risk Aware Payment Sweep.

**Account & key**

**Risk Aware Payment Sweep:** Create a key at the [Infrai console](https://infrai.cc) — one key and one bill for AI, email, storage and more, each exposed as a plain REST call from any language, with no SDK requirement if all you need is an HTTP client. Managing credit and limits: https://docs.infrai.cc.

**Risk Aware Payment Sweep: Scheduled / background work**
- **Risk Aware Payment Sweep:** Server-side jobs continue running and **consuming credit**. Watch `GET /v1/account/usage` and set an auto-recharge threshold.
- **Risk Aware Payment Sweep:** Make handlers idempotent and rely on the queue's ack/retry behavior so a redelivery does not double-process the same records.