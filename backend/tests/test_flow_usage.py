"""
Offline tests for flow usage metering (services/flow_usage.py), on a throwaway
SQLite database:

  - the X and Anthropic connectors' usage blocks measure real response shapes
    (posts + expanded posts/users; tokens priced by the model that answered)
  - a connection's own usage_prices override the connector's, per meter
  - unpriced meters are recorded with no cost; non-2xx answers record nothing
  - record_response writes rows only for a REAL execution, taking the flow id
    from the execution row
  - summary(): totals, per day, per step, per run, the budget state, notes
  - check_budget() refuses once today's cost reaches the budget

Runs under pytest (``pytest tests/test_flow_usage.py``) or standalone
(``python tests/test_flow_usage.py``) from backend/.
"""
import json
import os
import sys
import tempfile
import uuid

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
_DB = os.path.join(tempfile.gettempdir(), f"ioflow_flow_usage_test_{uuid.uuid4().hex[:8]}.db")
os.environ["DATABASE_URL"] = "sqlite:///" + _DB

from sqlalchemy import text  # noqa: E402

from db.database import init_db, engine  # noqa: E402
from services import flow_usage  # noqa: E402


def _seed_usage(app_file: str, service: str) -> dict:
    app = json.load(open(os.path.join(BACKEND, "seed-applications", app_file)))
    svc = next(s for s in app["services"] if s["service_name"] == service)
    return svc["response_config"]["usage"]


X_SEARCH = {"data": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
            "includes": {"tweets": [{"id": "9"}], "users": [{"id": "u1"}, {"id": "u2"}]},
            "meta": {"result_count": 3}}
CLAUDE = {"model": "claude-sonnet-5-5", "content": [{"type": "text", "text": "{}"}],
          "usage": {"input_tokens": 10000, "output_tokens": 4000, "cache_read_input_tokens": 0}}


def _by(rows, meter):
    return [r for r in rows if r["meter"] == meter]


def test_x_search_counts_posts_and_expansions():
    rows = flow_usage.measure(_seed_usage("x_twitter_app.json", "search_tweets"), X_SEARCH)
    posts, users = _by(rows, "post_read"), _by(rows, "user_read")
    assert sum(r["quantity"] for r in posts) == 4          # 3 returned + 1 expanded
    assert sum(r["quantity"] for r in users) == 2
    assert abs(sum(r["cost"] for r in rows) - (4 * 0.005 + 2 * 0.010)) < 1e-9
    assert all(r["price_source"] == "connector" for r in rows)


def test_single_user_lookup_counts_one():
    rows = flow_usage.measure(_seed_usage("x_twitter_app.json", "get_user_by_username"),
                              {"data": {"id": "u1", "username": "a"}})
    assert [(r["meter"], r["quantity"]) for r in rows] == [("user_read", 1.0)]


def test_claude_tokens_priced_by_model():
    rows = flow_usage.measure(_seed_usage("anthropic.json", "extract_structured"), CLAUDE)
    assert {r["meter"] for r in rows} == {"input_tokens", "output_tokens"}  # zero cache read is not a row
    assert abs(sum(r["cost"] for r in rows) - (10000 * 2 / 1e6 + 4000 * 10 / 1e6)) < 1e-9
    assert all(r["dimension"] == "claude-sonnet-5-5" for r in rows)
    haiku = flow_usage.measure(_seed_usage("anthropic.json", "extract_structured"), dict(CLAUDE, model="claude-haiku-5-5"))
    assert abs(sum(r["cost"] for r in haiku) - (10000 * 0.10 / 1e6 + 4000 * 0.50 / 1e6)) < 1e-9


def test_unknown_model_is_unpriced_not_dropped():
    rows = flow_usage.measure(_seed_usage("anthropic.json", "extract_structured"), dict(CLAUDE, model="claude-new-9"))
    assert rows and all(r["cost"] is None and r["price_source"] == "none" for r in rows)


def test_connection_prices_override_per_meter():
    overrides = {"post_read": {"amount": 0.001}}
    rows = flow_usage.measure(_seed_usage("x_twitter_app.json", "search_tweets"), X_SEARCH, overrides)
    posts, users = _by(rows, "post_read"), _by(rows, "user_read")
    assert all(r["price_source"] == "connection" and r["unit_amount"] == 0.001 for r in posts)
    assert all(r["price_source"] == "connector" and r["unit_amount"] == 0.010 for r in users)
    by_override = flow_usage.measure(_seed_usage("anthropic.json", "extract_structured"), CLAUDE,
                                     {"output_tokens": {"by": {"claude-sonnet-5-5": 5.0}}})
    out = _by(by_override, "output_tokens")[0]
    assert out["unit_amount"] == 5.0 and out["price_source"] == "connection"


def test_no_usage_block_measures_nothing():
    assert flow_usage.measure(None, X_SEARCH) == []
    assert flow_usage.measure({"meters": []}, X_SEARCH) == []
    assert flow_usage.measure(_seed_usage("x_twitter_app.json", "search_tweets"), "not json") == []


def _setup_db():
    init_db()
    flow_id, execution_id = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.begin() as c:
        c.execute(text("INSERT INTO flows (flow_id, tenant_id, flow_name, flow_definition) VALUES (:f, 't', 'F', :d)"),
                  {"f": flow_id, "d": json.dumps({"nodes": [{"id": "search", "data": {"label": "X search"}}]})})
        c.execute(text("INSERT INTO flow_executions (execution_id, flow_id, status) VALUES (:x, :f, 'RUNNING')"),
                  {"x": execution_id, "f": flow_id})
    return flow_id, execution_id


def test_record_summary_and_budget():
    flow_id, execution_id = _setup_db()
    cfg = {"service_name": "search_tweets", "app_id": "app-x", "app_name": "X",
           "response_config": {"usage": _seed_usage("x_twitter_app.json", "search_tweets")}}
    ctx = {"execution_id": execution_id, "current_node_id": "search", "schema_name": "default"}
    flow_usage.record_response(ctx, cfg, X_SEARCH, 200)
    flow_usage.record_response(ctx, cfg, X_SEARCH, 429)                       # not billed
    flow_usage.record_response(dict(ctx, execution_id=str(uuid.uuid4())), cfg, X_SEARCH, 200)  # no such run
    definition = {"nodes": [{"id": "search", "data": {"label": "X search"}}], "settings": {"budget": {"daily": 0.05}}}
    s = flow_usage.summary("default", flow_id, definition, days=7, runs=5)
    expected = 4 * 0.005 + 2 * 0.010
    assert abs(s["total_cost"] - expected) < 1e-9 and abs(s["today_cost"] - expected) < 1e-9
    assert [r["execution_id"] for r in s["runs"]] == [execution_id]
    assert {(b["label"], b["meter"]) for b in s["by_step"]} == {("X search", "post_read"), ("X search", "user_read")}
    assert s["budget"]["daily"] == 0.05 and s["budget"]["reached"] is False
    flow_usage.check_budget("default", flow_id, flow_usage.budget_of(definition))   # 0.04 < 0.05: runs
    flow_usage.record_response(ctx, cfg, X_SEARCH, 200)                           # 0.08 >= 0.05
    try:
        flow_usage.check_budget("default", flow_id, flow_usage.budget_of(definition))
        raise AssertionError("budget should have been reached")
    except flow_usage.BudgetReached as exc:
        assert "Daily budget reached" in str(exc)
    assert flow_usage.budget_of({"settings": {"budget": {"daily": 0}}}) is None


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"FAIL {name}: {exc!r}")
    sys.exit(1 if failed else 0)
