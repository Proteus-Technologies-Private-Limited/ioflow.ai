# Flow usage & cost — what a flow's paid API calls use and cost

A flow that calls a paid API (X reads, Claude tokens) is metered per run and
per step, so the flow's owner can see what it costs and cap it. This is the
cost the THIRD-PARTY API charges the connection's owner — not IOFlow's own
marketplace billing (`execution_cost_logs`, `ApplicationPricing`), which is
untouched.

## Declaring meters (connector data)

A service's `response_config.usage`:

```json
"usage": {
  "currency": "USD",
  "price_note": "Where the price comes from and what the estimate cannot see",
  "meters": [
    {"meter": "post_read", "label": "Posts read", "unit": "post",
     "count": "data", "price": {"amount": 0.005, "per": 1}},
    {"meter": "output_tokens", "label": "Output tokens", "unit": "token",
     "value": "usage.output_tokens", "dimension_path": "model",
     "price": {"per": 1000000, "by": {"claude-sonnet-5-5": 10.0}}}
  ]
}
```

- `count`: dotted path in the response body — a list counts its items, an
  object counts 1. `value`: dotted path to a number.
- `dimension_path`: what the price depends on (e.g. the model that answered);
  `price.by` maps it, `price.amount` is the flat / fallback price. No price ⇒
  the quantity is recorded as **unpriced** (never dropped, never guessed).
- Shipped: `x_twitter_app` and `x_twitter` reads (posts + expanded posts and
  users), `anthropic` create_message / ask_claude / extract_structured. After
  editing a seed file, bump its `application.version` and update the installed
  application (Seed applications → Update).

A tenant whose contract differs sets its own prices on the **connection**:
`subscription_config.usage_prices = {"post_read": {"amount": 0.004}}` (merged
per meter over the connector's; `by` maps merge per key).

## Recording

`services/flow_usage.py`, called from `ApiCallExecutor._log_http_response`:
2xx answers of a real execution only (`INSERT … SELECT` from
`flow_executions`, so a direct "test this service" call records nothing and the
flow id never comes from the caller). One row per meter in `flow_usage`,
stored BESIDE `flow_executions` (the schema the FlowExecution model names —
`ioflow` on PostgreSQL, where every tenant's runs live — not the engine's
tenant schema, which holds no runs), created on first use (existence checked first),
carrying the unit price it was costed at. Metering never fails a run.

`scripts/backfill_flow_usage.py [--flow ID] [--days 30] [--dry-run]` meters
runs logged before metering existed, from their `API Response` logs (steps no
longer in the flow are found through the run's own "Executing action node"
log); a run already metered is skipped.

## Reading and budgets

- `GET /api/v1/flows/{flow_id}/usage?days=30&runs=20` — today / last 7 days /
  period totals, per UTC day, per step × meter × dimension, per run, the
  budget state and each connector's `price_note`.
- `PUT /api/v1/flows/{flow_id}/budget` `{"daily": 5.0, "currency": "USD"}` (or
  `null` to remove) — stored at `flow_definition.settings.budget`. Flow owner
  or tenant/instance admin.
- Enforcement (`services/execution_engine.py`): a run is refused at its start,
  and a metered call is refused during a run, once the UTC day's recorded cost
  has reached the budget; the run fails with "Daily budget reached …".

## Fixes made alongside

- The engine now passes a service's `timeout_seconds` column to the executor
  (it never did: every API call used the 30 s default whatever the connector
  declared — a 300 s Claude call timed out at 30 s).
- `POST /api/v1/applications/services/{id}/execute` built the engine with
  `ExecutionEngine(db, user)` (a session as the schema name) and failed every
  call; it now passes the caller's tenant schema.

Tests: `backend/tests/test_flow_usage.py` (offline, SQLite).
