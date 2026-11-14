"""
Offline tests for three IOFlow fixes found while building the OmniChannel
(Amazon / Flipkart / Shopify) flows (no network, no database):

  F1  create_or_update_flow: FlowValidator raised NameError('warnings') on
      every flow with an action node, and the MCP bridge reported the tool's
      "Error …" text as a success. -> validator fixed; flow_save_verdict()
      turns the tool's answer into {success, content, flow_id | error}.
  F2  subscription create rejected a templated base URL ({{auth.endpoint}},
      https://{{auth.shop_domain}}/…) with "Missing required configuration
      variables: {auth.endpoint" -> only single-brace {var} are config
      variables; {{auth.x}} is checked against the supplied credentials.
  F3  execution / server logs carried secrets in plain text (the inbound API
      Bearer key inside a logged service_config, x-amz-access-token,
      X-Shopify-Access-Token, ?api_key=) -> redact_secrets()/redact_text() at
      the ExecutionLog choke point and on the config/header log lines.

Runs under pytest (``pytest tests/test_ecommerce_ioflow_fixes.py``) or
standalone (``python tests/test_ecommerce_ioflow_fixes.py``) from backend/.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.tools.flow_design_tools import FlowValidator, flow_save_verdict  # noqa: E402
from services.jinja_templating import (  # noqa: E402
    config_placeholders, fill_config_placeholders, missing_auth_fields,
    render_auth_placeholders,
)
from utils.crypto_utils import REDACTED, is_secret_key, redact_secrets, redact_text  # noqa: E402

INBOUND_KEY = "twk_9f3c1d2e7a6b5c4d3e2f1a0b9c8d7e6f"


# ---------------------------------------------------------------------------
# F1 — create_or_update_flow
# ---------------------------------------------------------------------------

def _flow_with_action():
    return {
        "nodes": [
            {"id": "trigger", "type": "trigger", "position": {"x": 0, "y": 0},
             "data": {"label": "Event", "triggerType": "event", "appId": "app-1",
                      "eventId": "evt-1", "eventName": "ecom_order_pull_requested"}},
            {"id": "gate", "type": "condition", "position": {"x": 1, "y": 0},
             "data": {"label": "Amazon?", "expression": "input.arguments.platform == 'AMAZON'"}},
            {"id": "init", "type": "transform", "position": {"x": 2, "y": 0},
             "data": {"label": "Init", "script": "output = {'ok': True}\n"}},
            {"id": "skip", "type": "transform", "position": {"x": 2, "y": 1},
             "data": {"label": "Other channel", "script": "output = {'skipped': True}\n"}},
            {"id": "call", "type": "action", "position": {"x": 3, "y": 0},
             "data": {"label": "List orders", "appId": "app-2", "appName": "amazon_sp_api",
                      "serviceId": "svc-1", "serviceName": "list_orders",
                      "parameterMapping": {
                          "created_after": {"source": "variable", "value": "input.arguments.created_after"},
                          "page_size": {"source": "static", "value": 100}}}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "target": "gate", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e2", "source": "gate", "target": "init", "sourceHandle": "true", "targetHandle": "input"},
            {"id": "e3", "source": "init", "target": "call", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e4", "source": "gate", "target": "skip", "sourceHandle": "false", "targetHandle": "input"},
        ],
    }


def test_f1_validator_accepts_flow_with_action_node():
    # Before the fix this raised NameError: name 'warnings' is not defined.
    valid, errors = FlowValidator.validate_flow_definition(_flow_with_action())
    assert valid, errors


def test_f1_validator_still_reports_real_errors_on_action_nodes():
    flow = _flow_with_action()
    del flow["nodes"][4]["data"]["label"]
    valid, errors = FlowValidator.validate_flow_definition(flow)
    assert not valid
    assert any("label" in e for e in errors), errors


def test_f1_verdict_success_names_flow_id():
    text = ("✅ Flow created successfully!\n\n**Flow Details:**\n"
            "- Flow ID: 4d0550c1-9bae-446f-9c4c-c67ba360a112\n- Flow Name: X")
    v = flow_save_verdict(text)
    assert v["success"] is True
    assert v["flow_id"] == "4d0550c1-9bae-446f-9c4c-c67ba360a112"
    assert "error" not in v and v["content"] == text


def test_f1_verdict_failures_are_failures():
    for text in ("Error creating/updating flow: name 'warnings' is not defined",
                 "# Flow Validation Failed\n\n1. Node x missing 'label'",
                 "Error: A flow with name 'X' already exists.",
                 "✅ Flow created successfully! (but no id)",
                 "", None):
        v = flow_save_verdict(text)
        assert v["success"] is False, text
        assert v["error"], text
        assert "flow_id" not in v


# ---------------------------------------------------------------------------
# F2 — templated base URLs on subscription create
# ---------------------------------------------------------------------------

def test_f2_auth_placeholders_are_not_config_variables():
    assert config_placeholders("{{auth.endpoint}}") == []
    assert config_placeholders("https://{{auth.shop_domain}}/admin/api/2026-07") == []
    assert config_placeholders("https://{{ auth.shop_domain }}/x") == []


def test_f2_single_brace_config_variables_still_found_and_filled():
    url = "https://{shop}.myshopify.com/admin/api/{version}"
    assert config_placeholders(url) == ["shop", "version"]
    assert fill_config_placeholders(url, {"shop": "acme", "version": "2024-01"}) == \
        "https://acme.myshopify.com/admin/api/2024-01"
    # a mixed URL keeps the per-call auth placeholder
    mixed = "https://{{auth.shop_domain}}/admin/api/{version}"
    assert config_placeholders(mixed) == ["version"]
    assert fill_config_placeholders(mixed, {"version": "2026-07"}) == \
        "https://{{auth.shop_domain}}/admin/api/2026-07"


def test_f2_unknown_config_variable_left_for_the_missing_check():
    assert fill_config_placeholders("https://{tenant}.x.com", {}) == "https://{tenant}.x.com"


def test_f2_missing_auth_fields_against_supplied_credentials():
    assert missing_auth_fields("{{auth.endpoint}}", {"endpoint": "https://api.flipkart.net"}) == []
    assert missing_auth_fields("{{auth.endpoint}}", {"client_id": "x"}) == ["endpoint"]
    assert missing_auth_fields("https://{{auth.shop_domain}}/a", {"shop_domain": "  "}) == ["shop_domain"]
    assert missing_auth_fields("https://static.example.com", {}) == []


def test_f2_stored_template_renders_per_call_like_before():
    # What subscription create now stores for amazon_sp_api is the template
    # itself; the executor renders it from the connection per call.
    stored = fill_config_placeholders("{{auth.endpoint}}", {"using_default_credentials": False})
    assert stored == "{{auth.endpoint}}"
    assert render_auth_placeholders(stored, {"endpoint": "http://127.0.0.1:7091/amazon"}, "base_url") == \
        "http://127.0.0.1:7091/amazon"


# ---------------------------------------------------------------------------
# F3 — secrets never reach logs
# ---------------------------------------------------------------------------

def _twasta_service_config():
    return {
        "endpoint_template": "https://twasta.example/api/integration/v1/call/ecom_update_listing",
        "method": "POST",
        "request_config": {"method": "POST", "parameter_method": "json_payload",
                           "headers": {"Authorization": f"Bearer {INBOUND_KEY}",
                                       "Content-Type": "application/json"}},
        "parameter_schema": {"type": "object", "properties": {"txn_id": {"type": "string"}}},
        "service_name": "ecom_update_listing",
    }


def test_f3_service_config_dump_loses_the_inbound_bearer_key():
    out = redact_secrets({"service_type": "api_call", "config": _twasta_service_config()})
    blob = json.dumps(out)
    assert INBOUND_KEY not in blob
    assert out["config"]["request_config"]["headers"]["Authorization"] == REDACTED
    # the rest stays readable for debugging
    assert out["config"]["request_config"]["headers"]["Content-Type"] == "application/json"
    assert out["config"]["service_name"] == "ecom_update_listing"


def test_f3_channel_headers_and_credentials_redacted():
    headers = {"x-amz-access-token": "Atza|IwEBIExampleToken", "X-Shopify-Access-Token": "shpat_0123456789",
               "X-API-Key": "k-123456", "user-agent": "IOFlow-Twasta/1.0", "Cookie": "sid=abc"}
    creds = {"client_id": "amzn1.application-oa2-client.x", "client_secret": "s3cr3t",
             "refresh_token": "Atzr|x", "access_token": "Atza|y", "endpoint": "https://sellingpartnerapi-eu.amazon.com",
             "seller_id": "A1EXAMPLESELLER", "invocation_api_key": "ioflow_abcdefghijklmnopqrstuvwxyz123456"}
    h = redact_secrets(headers)
    c = redact_secrets(creds)
    for k in ("x-amz-access-token", "X-Shopify-Access-Token", "X-API-Key", "Cookie"):
        assert h[k] == REDACTED, k
    assert h["user-agent"] == "IOFlow-Twasta/1.0"
    for k in ("client_secret", "refresh_token", "access_token", "invocation_api_key"):
        assert c[k] == REDACTED, k
    assert c["endpoint"].startswith("https://") and c["seller_id"] == "A1EXAMPLESELLER"


def test_f3_secrets_inside_free_text_are_scrubbed():
    msg = (f"POST https://h/call?api_key=SECRET123&page=2 Authorization: Bearer {INBOUND_KEY} "
           f"basic Basic dXNlcjpwYXNzd29yZA== key ioflow_abcdefghijklmnopqrstuvwxyz0123")
    out = redact_text(msg)
    for secret in ("SECRET123", INBOUND_KEY, "dXNlcjpwYXNzd29yZA==", "abcdefghijklmnopqrstuvwxyz0123"):
        assert secret not in out, (secret, out)
    assert "page=2" in out
    assert redact_text(str({"Authorization": f"Bearer {INBOUND_KEY}"})).count(INBOUND_KEY) == 0


def test_f3_paging_cursors_and_counters_stay_readable():
    data = {"next_page_token": "2YgYW55IGNhcm5hbA", "page_token": "abc", "max_tokens": 1000,
            "output_keys": ["a", "b"], "total_tokens": 12, "data_keys": ["x"]}
    assert redact_secrets(data) == data
    assert not is_secret_key("next_page_token") and is_secret_key("x-amz-access-token")


def test_f3_redaction_never_raises_and_copies():
    class Odd:
        pass
    src = {"headers": {"Authorization": "Bearer abcdefgh"}, "odd": Odd(), "n": None, "t": ("Bearer abcdefgh",)}
    out = redact_secrets(src)
    assert src["headers"]["Authorization"] == "Bearer abcdefgh"      # input untouched
    assert out["headers"]["Authorization"] == REDACTED
    assert out["t"] == ("Bearer " + REDACTED,)
    assert redact_secrets(None) is None and redact_text(None) is None


def test_f3_execution_log_rows_are_redacted_at_the_model():
    from db import models
    row = models.ExecutionLog(execution_id="e", step_id="s", level="debug",
                              message=f"API Request: POST https://h/x?access_token=abc123secret with Bearer {INBOUND_KEY}",
                              data={"service_type": "api_call", "config": _twasta_service_config()})
    models._redact_execution_log(None, None, row)
    assert INBOUND_KEY not in row.message and "abc123secret" not in row.message
    assert INBOUND_KEY not in json.dumps(row.data)
    # registered for every writer (engine, executors, debug manager, API)
    from sqlalchemy import event
    assert event.contains(models.ExecutionLog, "before_insert", models._redact_execution_log)
    assert event.contains(models.ExecutionLog, "before_update", models._redact_execution_log)


# ---------------------------------------------------------------------------
# standalone runner
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import logging
    import traceback
    logging.basicConfig(level=logging.CRITICAL)
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith('test_') and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
