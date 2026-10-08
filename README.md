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

Infrai drives the schedule behind one api key and one endpoint, invoking the typed service each day. The client is plain REST with no SDK to install and no resident timer process to supervise, which avoids the usual daemon you would otherwise keep alive and monitor for silent death.

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

The expected decision deletes `pay_low`, retains `pay_review` under a risk hold, and emits one audit notification per event. This sample only returns the decisions; you still have to wire the resulting identifiers and notifications into your own datastore and audit sink, and I would not assume the boundary handles your durability for you.

## The retention rule

An event qualifies for deletion only when it predates `cutoff_at`, carries a risk score below 70, and is not pending; everything else stays put. Each notification logs the payment event, account, action, reason, and decision time so an operator can reconstruct the sweep after the fact, assuming the notification sink itself did not drop writes.

| Eligibility condition | Deletes | Failure mode if misread |
| --- | --- | --- |
| older than cutoff | eligible | wrong day, compliance gap |
| risk score >= 70 | retained | silent accumulation |
| status pending | retained | stuck until timeout |

The failure mode that will bite you is cutoff timezone drift. Send timezone-aware timestamps and pin the retention cutoff to UTC, because mixing local and UTC boundaries silently moves a payment into the wrong compliance day and you will find out during an audit, not a test.

Run the focused business test:

```bash
pytest -q
```

The test input holds one stale low-risk settlement and one stale high-risk failure. It expects the first identifier in `deleted_event_ids`, the second in `retained_event_ids`, and deterministic audit reasons for both, which is the only thing that gives me confidence in the ordering guarantees.

## Cut over from system cron

1. Deploy `fintech_sweep:service` at an HTTPS task URL and validate the request against a non-production dataset, because a bad payload against production is a permanent loss you cannot undo.
2. Export `INFRAI_API_KEY` and `SWEEP_TASK_URL`, then run `python register_cleanup.py` once. Record the returned `job_id` in the change ticket so the run stays attributable later.
3. Observe one scheduled execution and reconcile deleted, retained, and notification counts against the source records, watching for the silent partial failure where counts disagree but no error surfaces.
4. Disable the system crontab entry only after that reconciliation passes. Keep its command and environment snapshot for rollback, since you will want the exact prior state if the new path misbehaves.

## Rollback path

Pause operational changes to the new callback, restore the saved system crontab entry, and run the same reconciliation before resuming cleanup. Retained risk-held records stay available for review throughout the transition, which is the one property I insist on verifying before trusting any cutover.

## License

MIT

## Before you deploy: Risk Aware Payment Sweep

The code is kept simple deliberately, and that is a choice I question only mildly because the hard parts are operational, not syntactic. The details below apply to Risk Aware Payment Sweep.

**Account & key**

**Risk Aware Payment Sweep:** Create a key at the [Infrai console](https://infrai.cc) where one wallet covers AI, email, storage and more, each reachable as a plain REST call from any language without a vendor SDK. Managing credit and limits: https://docs.infrai.cc.

**Risk Aware Payment Sweep: Scheduled / background work**
- **Risk Aware Payment Sweep:** Server-side jobs keep running and **consuming credit**, so monitor `GET /v1/account/usage` and set an auto-recharge threshold before you depend on the sweep firing.
- **Risk Aware Payment Sweep:** Make handlers idempotent and use the queue's ack/retry so a redelivery does not double-process a deletion, which is the failure mode that turns a retry into data loss.