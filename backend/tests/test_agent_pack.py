"""
Offline tests for the agent pack, the bridge proxy and tenant seed applications
(no network, no database server):

  - the pack parses, every agent declares tools, and every tool is a bridge tool
  - the plugin's agents/*.md are exactly what the pack generates
  - the ADK agents read their instruction from the pack (no inline copy)
  - bridge_proxy speaks MCP over stdio and honours the tool allow-list
  - tenant seed applications: validate / save / list / key rules / global-key
    refusal / install creates, then updates IN PLACE (ids kept, removed rows
    deactivated) and never touches a global install

Runs under pytest (``pytest tests/test_agent_pack.py``) or standalone
(``python tests/test_agent_pack.py``) from backend/.
"""
import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
# The seed manager imports db.database, which connects at import time; keep it
# on a throwaway SQLite file unless the caller chose a database.
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.gettempdir(), "ioflow_agent_pack_test.db"))

from agent_pack import load_pack, get_agent, render_plugin_agent  # noqa: E402

REPO = os.path.dirname(BACKEND)


def _bridge_tool_names():
    """Every tool name the MCP bridge declares (wrapper list + registry keys)."""
    src = open(os.path.join(BACKEND, "api", "mcp_bridge.py"), encoding="utf-8").read()
    names = set(re.findall(r'^\s+"([a-z_]+)",?\s*(?:#.*)?$', src, re.M))       # _api_wrapper_tools
    names |= set(re.findall(r'^\s+"([a-z_]+)": [a-z_.]+,?\s*(?:#.*)?$', src, re.M))  # registries
    return names


# ---------------------------------------------------------------------------
# pack
# ---------------------------------------------------------------------------

def test_pack_parses_and_versions():
    pack = load_pack()
    assert pack["schema"] == 1 and len(pack["version"]) == 16
    names = {a["name"] for a in pack["agents"]}
    assert {"seed-app-designer", "flow-designer", "flow-editor"} <= names
    for agent in pack["agents"]:
        assert agent["description"] and agent["tools"] and len(agent["prompt"]) > 200


def test_get_agent_by_name_or_adk_id():
    assert get_agent("flow_designer")["name"] == "flow-designer"
    assert get_agent("seed-app-designer")["adk_id"] == "seed_application_designer"
    assert get_agent("nope") is None


def test_every_pack_tool_is_a_bridge_tool():
    bridge = _bridge_tool_names()
    for agent in load_pack()["agents"]:
        missing = [t for t in agent["tools"] if t not in bridge]
        assert not missing, f"{agent['name']} names tools the bridge lacks: {missing}"


def test_prompt_only_names_tools_the_agent_has():
    bridge = _bridge_tool_names()
    for agent in load_pack()["agents"]:
        called = set(re.findall(r"`?\b([a-z]+(?:_[a-z]+)+)\(", agent["prompt"]))
        called &= bridge  # ignore example python function names
        extra = called - set(agent["tools"])
        assert not extra, f"{agent['name']} prompt calls tools not in its tools list: {sorted(extra)}"


def test_seed_designer_uses_tenant_catalog_and_full_json():
    agent = get_agent("seed-app-designer")
    assert "save_tenant_seed_application" in agent["tools"]
    assert "add_service_to_application" not in agent["tools"]  # global, piecemeal
    assert "get_seed_application_guide" in agent["tools"]


def test_plugin_agents_are_generated_from_pack():
    for agent in load_pack()["agents"]:
        path = os.path.join(REPO, "ioflow-plugin", "agents", f"{agent['name']}.md")
        assert open(path, encoding="utf-8").read() == render_plugin_agent(agent), (
            f"{path} is stale: run python backend/scripts/build_plugin_agents.py")


def test_adk_agents_read_the_pack():
    for agent in load_pack()["agents"]:
        src = open(os.path.join(BACKEND, "agent", agent["adk_id"], "agent.py"), encoding="utf-8").read()
        assert f'instruction=agent_prompt("{agent["name"]}")' in src
        assert 'instruction="""' not in src
        assert f'bridge_server_params("{agent["name"]}")' in src


# ---------------------------------------------------------------------------
# bridge proxy
# ---------------------------------------------------------------------------

class _FakeBridge(http.server.BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *a):
        pass

    def _reply(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        assert self.headers["Authorization"] == "Bearer tok-123"
        self._reply([
            {"name": "get_seed_application_guide", "description": "g", "input_schema": {"type": "object"}},
            {"name": "delete_seed_application", "description": "d", "input_schema": {"type": "object"}},
        ])

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _FakeBridge.calls.append(body)
        self._reply({"success": True, "result": {"echo": body["tool"]}, "tool": body["tool"]})


def test_bridge_proxy_lists_and_calls_with_allowlist():
    server = http.server.HTTPServer(("127.0.0.1", 0), _FakeBridge)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        env = {**os.environ, "IOFLOW_API_KEY": "tok-123",
               "IOFLOW_BASE_URL": f"http://127.0.0.1:{server.server_port}",
               "IOFLOW_TOOL_ALLOWLIST": "get_seed_application_guide"}
        reqs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "get_seed_application_guide", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "delete_seed_application", "arguments": {"app_key": "x"}}},
        ]
        out = subprocess.run(
            [sys.executable, os.path.join(BACKEND, "mcp_server", "bridge_proxy.py")],
            input="\n".join(json.dumps(r) for r in reqs) + "\n",
            capture_output=True, text=True, env=env, timeout=30,
        ).stdout
        replies = {r["id"]: r for r in map(json.loads, out.splitlines())}
        assert set(replies) == {1, 2, 3, 4}  # the notification gets no reply
        assert [t["name"] for t in replies[2]["result"]["tools"]] == ["get_seed_application_guide"]
        assert replies[3]["result"]["isError"] is False
        assert json.loads(replies[3]["result"]["content"][0]["text"]) == {"echo": "get_seed_application_guide"}
        assert replies[4]["result"]["isError"] is True  # not allowed: never reaches the bridge
        assert [c["tool"] for c in _FakeBridge.calls] == ["get_seed_application_guide"]
    finally:
        server.shutdown()


# ---------------------------------------------------------------------------
# tenant seed applications (needs the backend's Python dependencies)
# ---------------------------------------------------------------------------

def _seed(version="1.0.0", services=("get_item", "list_items"), events=("item_created",)):
    """A valid seed built from a real catalog app (github.json), so the test
    tracks IOFlow's actual schema rather than a guess at it."""
    base = json.load(open(os.path.join(BACKEND, "seed-applications", "github.json"), encoding="utf-8"))
    template_svc, template_ev = base["services"][0], base["events"][0]
    seed = {
        "key": "acme_inventory",
        "application": {**base["application"], "app_name": "Acme Inventory", "version": version},
        "services": [], "events": [],
    }
    seed["application"].pop("app_scope", None)
    for name in services:
        svc = json.loads(json.dumps(template_svc))
        svc["service_name"] = name
        svc["display_name"] = name
        seed["services"].append(svc)
    for name in events:
        ev = json.loads(json.dumps(template_ev))
        ev["event_name"] = name
        ev["display_name"] = name
        ev.pop("api_endpoint", None)  # unique per install
        seed["events"].append(ev)
    return seed


def _manager_and_db(tmp):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.application_models import (Application, ApplicationService, ApplicationEvent,
                                       ApplicationSubscription, OAuthState)
    from services.json_seed_manager import JsonSeedManager

    engine = create_engine(f"sqlite:///{os.path.join(tmp, 'apps.db')}")
    try:
        # Everything the ORM may touch (delete cascades walk relationships).
        Application.metadata.create_all(engine)
    except Exception:  # a dialect-specific column type: fall back to the core set
        for model in (Application, ApplicationService, ApplicationEvent, ApplicationSubscription, OAuthState):
            model.__table__.create(engine, checkfirst=True)
    manager = JsonSeedManager()
    manager._applications_path = os.path.join(tmp, "seed-applications")
    os.makedirs(manager._applications_path)
    manager._applications_cache = {}
    return manager, sessionmaker(bind=engine)()


def _skip_without_deps():
    try:
        import sqlalchemy  # noqa: F401
        import fastapi  # noqa: F401
    except ImportError:
        try:
            import pytest
            pytest.skip("backend dependencies not installed")
        except ImportError:
            return True
    return False


def test_tenant_seed_lifecycle():
    if _skip_without_deps():
        return
    with tempfile.TemporaryDirectory() as tmp:
        manager, db = _manager_and_db(tmp)
        from db.application_models import Application, ApplicationService, ApplicationEvent
        tenant = "11111111-2222-3333-4444-555555555555"

        assert manager.validate_seed_document(_seed())["valid"], manager.validate_seed_document(_seed())
        bad = _seed()
        bad["services"][0]["input_schema"] = bad["services"][0].pop("parameter_schema", {})
        assert manager.validate_seed_document(bad)["valid"] is False
        assert manager.save_tenant_application(tenant, bad)["success"] is False
        assert manager.list_tenant_applications(tenant) == []

        for key in ("Bad-Key", "../x", "a"):
            try:
                manager._tenant_file(tenant, key)
                raise AssertionError(f"{key!r} accepted")
            except ValueError:
                pass
        try:
            manager._tenant_dir("../other")
            raise AssertionError("tenant path traversal accepted")
        except ValueError:
            pass

        saved = manager.save_tenant_application(tenant, _seed(), user_id="u1")
        assert saved["success"] and saved["created"], saved
        assert [s["key"] for s in manager.list_tenant_applications(tenant)] == ["acme_inventory"]
        assert manager.list_tenant_applications("99999999-0000-0000-0000-000000000000") == []
        assert manager.discover_applications() == {}  # never in the global catalog

        # A global key cannot be reused by a tenant.
        manager._applications_cache = {"acme_inventory": {}}
        assert manager.save_tenant_application(tenant, _seed())["success"] is False
        manager._applications_cache = {}

        first = manager.install_tenant_application(db, tenant, "acme_inventory", user_id="u1")
        assert first["success"] and first["created"] and first["services_created"] == 2, first
        app = db.query(Application).one()
        assert (app.app_scope, app.tenant_id_owner, app.seed_key) == ("tenant", tenant, "acme_inventory")
        ids = {s.service_name: s.service_id for s in db.query(ApplicationService).all()}

        manager.save_tenant_application(tenant, _seed("1.1.0", services=("get_item", "update_item"),
                                                      events=("item_deleted",)), user_id="u1")
        second = manager.install_tenant_application(db, tenant, "acme_inventory", user_id="u1")
        assert second["success"] and not second["created"], second
        assert (second["services_updated"], second["services_created"], second["services_deactivated"]) == (1, 1, 1)
        assert (second["events_created"], second["events_deactivated"]) == (1, 1)
        assert db.query(Application).count() == 1 and db.query(Application).one().version == "1.1.0"
        services = {s.service_name: s for s in db.query(ApplicationService).all()}
        assert services["get_item"].service_id == ids["get_item"]  # id kept
        assert services["list_items"].is_active is False            # deactivated, not deleted
        assert {e.event_name: e.is_active for e in db.query(ApplicationEvent).all()} == {
            "item_created": False, "item_deleted": True}

        assert manager.uninstall_tenant_application(db, tenant, "acme_inventory")["removed"] is True
        assert manager.delete_tenant_application(tenant, "acme_inventory") is True
        assert manager.get_tenant_application(tenant, "acme_inventory") is None


def test_global_soft_update_is_in_place_on_the_request_session():
    """Re-publishing a GLOBAL seed soft-updates its install through the request's
    own session (the old soft updater opened a SQLite file and failed on
    PostgreSQL): ids kept, new rows added, dropped rows deactivated, and a
    tenant's same-named application left alone."""
    if _skip_without_deps():
        return
    with tempfile.TemporaryDirectory() as tmp:
        manager, db = _manager_and_db(tmp)
        from db.application_models import Application, ApplicationService
        seed = _seed()
        seed["key"] = "acme_global"
        manager._applications_cache = {"acme_global": seed}
        manager.discover_applications = lambda: manager._applications_cache
        installed = manager.install_application(db, "acme_global", user_id="admin")
        assert installed["success"], installed
        app = db.query(Application).filter(Application.seed_key == "acme_global").one()
        app_id = app.app_id
        ids = {s.service_name: s.service_id for s in db.query(ApplicationService).filter(
            ApplicationService.app_id == app_id)}

        tenant = "11111111-2222-3333-4444-555555555555"
        assert manager.save_tenant_application(tenant, _seed(), user_id="u")["success"]
        assert manager.install_tenant_application(db, tenant, "acme_inventory", user_id="u")["success"]

        newer = _seed("1.1.0", services=("get_item", "update_item"))
        newer["key"] = "acme_global"
        manager._applications_cache = {"acme_global": newer}
        out = manager.soft_update_global_application(db, "acme_global")
        assert out["success"] and out["app_id"] == str(app_id), out
        assert (out["services_updated"], out["services_created"], out["services_deactivated"]) == (1, 1, 1), out
        assert out["previous_version"] == "1.0.0" and out["new_version"] == "1.1.0", out
        services = {s.service_name: s for s in db.query(ApplicationService).filter(
            ApplicationService.app_id == app_id)}
        assert services["get_item"].service_id == ids["get_item"]
        assert services["list_items"].is_active is False and services["update_item"].is_active
        tenant_app = manager.find_tenant_installation(db, tenant, "acme_inventory")
        assert tenant_app.version == "1.0.0"  # untouched
        assert manager.soft_update_global_application(db, "nope")["success"] is False


def test_same_key_in_two_tenants_resolves_to_the_callers_own():
    """Two tenants may own a connector with the same key; a lookup by that key
    (or name) answers each with ITS OWN, never the other tenant's."""
    if _skip_without_deps():
        return
    with tempfile.TemporaryDirectory() as tmp:
        manager, db = _manager_and_db(tmp)
        from types import SimpleNamespace
        from services.application_lookup import find_application, find_by_seed_key
        t_a = "11111111-2222-3333-4444-555555555555"
        t_b = "66666666-7777-8888-9999-000000000000"
        for tenant in (t_a, t_b):
            assert manager.save_tenant_application(tenant, _seed(), user_id="u")["success"]
            assert manager.install_tenant_application(db, tenant, "acme_inventory", user_id="u")["success"]
        user_a = SimpleNamespace(tenant_id=t_a, role="TENANT_ADMIN")
        user_b = SimpleNamespace(tenant_id=t_b, role="TENANT_ADMIN")
        stranger = SimpleNamespace(tenant_id="99999999-0000-0000-0000-000000000000", role="TENANT_ADMIN")
        for ref in ("acme_inventory", _seed()["application"]["app_name"]):
            assert find_application(db, ref, user_a).tenant_id_owner == t_a, ref
            assert find_application(db, ref, user_b).tenant_id_owner == t_b, ref
            assert find_application(db, ref, stranger) is None, ref
        assert find_by_seed_key(db, "acme_inventory") is None  # global-only lookup
        own_id = find_by_seed_key(db, "acme_inventory", user_b).app_id
        assert find_application(db, str(own_id), user_a) is not None  # by app_id: unchanged


def test_validator_checks_the_service_of_the_app_it_finds():
    """/flow-design/validate checks an action node's service and required
    parameters for the application it actually resolves — those checks used to
    run only for an app reached through a subscription, and json.loads on a
    JSONB input_schema made the parameter check a silent no-op. Another
    tenant's own application is "not found", by id as well as by key."""
    if _skip_without_deps():
        return
    with tempfile.TemporaryDirectory() as tmp:
        manager, db = _manager_and_db(tmp)
        from types import SimpleNamespace
        from db.application_models import Application, ApplicationService, ApplicationSubscription
        from api.flow_design import FlowNode, _check_action_node
        t_a = "11111111-2222-3333-4444-555555555555"
        t_b = "66666666-7777-8888-9999-000000000000"
        assert manager.save_tenant_application(t_a, _seed(), user_id="u")["success"]
        assert manager.install_tenant_application(db, t_a, "acme_inventory", user_id="u")["success"]
        app = db.query(Application).one()
        svc = db.query(ApplicationService).filter(ApplicationService.service_name == "get_item").one()
        svc.input_schema = {"type": "object", "required": ["item_id"],
                            "properties": {"item_id": {"type": "string"}}}
        db.commit()
        user_a = SimpleNamespace(tenant_id=t_a, role="TENANT_ADMIN")
        user_b = SimpleNamespace(tenant_id=t_b, role="TENANT_ADMIN")

        def node(**data):
            return FlowNode(id="act", type="action", position={"x": 0, "y": 0},
                            data={"label": "Act", "appName": "Acme Inventory", **data})

        def check(n, user):
            warnings = []
            return [e.message for e in _check_action_node(db, n, user, warnings)], \
                   [w.message for w in warnings]

        good = node(appId=app.app_id, serviceId=svc.service_id,
                    parameterMapping={"item_id": {"source": "static", "value": "7"}})
        errors, warnings = check(good, user_a)
        assert errors == [], errors
        assert any("not connected" in w for w in warnings), warnings  # no subscription yet

        db.add(ApplicationSubscription(tenant_id=t_a, app_id=app.app_id, status="active"))
        db.commit()
        assert check(good, user_a) == ([], [])

        # the same node by seed key resolves to the same app
        assert check(node(appId="acme_inventory", serviceId=svc.service_id,
                          parameters={"item_id": "7"}), user_a)[0] == []

        errors, _ = check(node(appId=app.app_id, serviceId=svc.service_id), user_a)
        assert errors == ["Missing required parameters: item_id"], errors

        errors, _ = check(node(appId=app.app_id, serviceId="no-such-service",
                               parameters={"item_id": "7"}), user_a)
        assert errors and "not found in application" in errors[0], errors

        # another tenant's own application: not found, by id or by key
        for ref in (app.app_id, "acme_inventory"):
            errors, _ = check(node(appId=ref, serviceId=svc.service_id,
                                   parameters={"item_id": "7"}), user_b)
            assert errors and "not found or not subscribed" in errors[0], (ref, errors)


def test_bridge_tools_see_the_callers_tenant():
    """A flow belongs to the tenant of the signed-in user who saved it — never
    'default'. /api/v1/auth/me nests the tenant; the bridge's auth handlers
    flatten it, the flow tools refuse a caller they cannot place, and only the
    caller's own tenant's flows can be changed."""
    if _skip_without_deps():
        return
    import asyncio
    from types import SimpleNamespace
    from mcp_server.auth.enhanced_mcp_auth import _flatten_me
    from mcp_server.tools.flow_design_tools import CreateOrUpdateFlow, DeleteFlow, ListFlows
    me = _flatten_me({"user_id": "u1", "email": "a@x", "role": "TENANT_ADMIN",
                      "tenant": {"tenant_id": "t1", "tenant_name": "A"}})
    assert (me["id"], me["tenant_id"]) == ("u1", "t1"), me
    assert _flatten_me({"id": "u2", "tenant_id": "t2"}) == {"id": "u2", "tenant_id": "t2"}

    tool = CreateOrUpdateFlow(auth_handler=SimpleNamespace(user_info=me))
    caller = tool._caller()
    assert caller == {"id": "u1", "tenant_id": "t1", "role": "TENANT_ADMIN"}, caller
    # the unflattened /me answer is read too
    raw = {"user_id": "u1", "role": "TENANT_ADMIN", "tenant": {"tenant_id": "t1"}}
    assert CreateOrUpdateFlow(auth_handler=SimpleNamespace(user_info=raw))._caller() == caller

    flow = lambda tenant, by="u1": SimpleNamespace(tenant_id=tenant, created_by=by)  # noqa: E731
    may = CreateOrUpdateFlow._may_write_flow
    assert may(flow("t1"), caller)
    assert not may(flow("t2"), caller)
    assert not may(flow("default"), caller)       # no "default" tenant, for anyone
    assert may(flow("t2"), dict(caller, role="INSTANCE_ADMIN"))

    # No identity (or no tenant): every flow tool refuses before touching the DB.
    definition = {"nodes": [{"id": "t", "type": "trigger", "data": {"triggerType": "manual"}}],
                  "edges": []}
    for info in (None, {"user_id": "u1"}, {"tenant_id": "t1"}):
        handler = SimpleNamespace(user_info=info)
        for result in (
            asyncio.run(CreateOrUpdateFlow(auth_handler=handler).run(
                flow_name="x", flow_definition=definition)),
            asyncio.run(ListFlows(auth_handler=handler).run()),
            asyncio.run(DeleteFlow(auth_handler=handler).run(flow_id="f", confirm=True)),
        ):
            assert "could not tell which user and organization" in result.text, (info, result.text)


def test_edge_handles_match_the_designer():
    """An edge may leave its handles out (the designer uses the node's default)
    but must never name a handle the node does not have — the flow runs, yet
    opens in the designer as unconnected boxes. NODE_HANDLES must match the
    <Handle id=…> declarations of the designer's node components."""
    from services.flow_handles import NODE_HANDLES, ERROR_HANDLE, edge_handle_errors
    flow_dir = os.path.join(REPO, "frontend", "src", "components", "flow")
    component = {"trigger": "TriggerNode", "action": "ActionNode", "transform": "TransformNode",
                 "human_in_loop": "HumanInLoopNode", "wait_for_event": "WaitForEventNode",
                 "response": "ResponseNode", "condition": "ConditionNode", "loop": "LoopNode"}
    assert set(component) == set(NODE_HANDLES)
    for node_type, name in component.items():
        src = open(os.path.join(flow_dir, f"{name}.js"), encoding="utf-8").read()
        found = {"source": set(), "target": set()}
        for block in re.findall(r"<Handle(.*?)/?>", src, re.S):
            kind = re.search(r'type="(source|target)"', block)
            hid = re.search(r'id="([^"]*)"', block)
            if kind and hid:
                found[kind.group(1)].add(hid.group(1))
        assert found["source"] == set(NODE_HANDLES[node_type]["source"]), (node_type, found)
        assert found["target"] == set(NODE_HANDLES[node_type]["target"]), (node_type, found)
    errors_js = open(os.path.join(flow_dir, "NodeErrorHandlingConfig.js"), encoding="utf-8").read()
    assert f"ERROR_HANDLE_ID = '{ERROR_HANDLE}'" in errors_js

    types = {"t": "trigger", "x": "transform", "r": "response", "c": "condition"}
    ok = [{"id": "e1", "source": "t", "target": "x"},                               # defaults
          {"id": "e2", "source": "x", "target": "r", "sourceHandle": "right", "targetHandle": "left"},
          {"id": "e3", "source": "c", "target": "r", "sourceHandle": "false", "targetHandle": "top"},
          {"id": "e4", "source": "x", "target": "r", "sourceHandle": "error", "targetHandle": ""}]
    for edge in ok:
        assert edge_handle_errors(edge, types) == [], edge
    bad = edge_handle_errors({"id": "e9", "source": "t", "target": "x",
                              "sourceHandle": "output", "targetHandle": "input"}, types)
    assert len(bad) == 2 and "sourceHandle 'output'" in bad[0] and "bottom, right" in bad[0], bad
    assert "targetHandle 'input'" in bad[1] and "top, left" in bad[1], bad


def test_tenant_router_over_http():
    """The REST surface: tenant from the caller, never the request; the key in
    the URL must match the seed; save+install in one call; read-only roles refused."""
    if _skip_without_deps():
        return
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import api.tenant_seed_applications as router_mod
    except ImportError as e:
        try:
            import pytest
            pytest.skip(f"router imports unavailable: {e}")
        except ImportError:
            return
    from types import SimpleNamespace
    from api.auth import get_current_user
    from db.database import get_db

    with tempfile.TemporaryDirectory() as tmp:
        manager, db = _manager_and_db(tmp)
        router_mod.seed_manager = manager
        caller = SimpleNamespace(user_id="u1", tenant_id="11111111-2222-3333-4444-555555555555",
                                 role=SimpleNamespace(value="FLOW_DESIGNER"))
        app = FastAPI()
        app.include_router(router_mod.router)
        app.dependency_overrides[get_current_user] = lambda: caller
        app.dependency_overrides[get_db] = lambda: db
        http = TestClient(app)
        base = "/api/v1/tenant-seed-applications"

        assert http.put(f"{base}/other_key", json={"seed": _seed()}).status_code == 400
        r = http.put(f"{base}/acme_inventory", json={"seed": _seed(), "install": True}).json()
        assert r["success"] and r["install"]["created"] and r["status"]["status"] == "installed", r
        listed = http.get(f"{base}/").json()
        assert [a["key"] for a in listed["applications"]] == ["acme_inventory"], listed
        assert http.get(f"{base}/acme_inventory").json()["seed"]["metadata"]["tenant_id"] == caller.tenant_id
        assert http.post(f"{base}/validate", json={"seed": {"key": "x"}}).json()["valid"] is False

        other = SimpleNamespace(user_id="u2", tenant_id="99999999-0000-0000-0000-000000000000",
                                role=SimpleNamespace(value="TENANT_ADMIN"))
        app.dependency_overrides[get_current_user] = lambda: other
        assert http.get(f"{base}/").json()["applications"] == []
        assert http.get(f"{base}/acme_inventory").status_code == 404

        monitor = SimpleNamespace(user_id="u3", tenant_id=caller.tenant_id,
                                  role=SimpleNamespace(value="EXECUTION_MONITOR"))
        app.dependency_overrides[get_current_user] = lambda: monitor
        assert http.put(f"{base}/acme_inventory", json={"seed": _seed()}).status_code == 403
        assert http.delete(f"{base}/acme_inventory").status_code == 403

        app.dependency_overrides[get_current_user] = lambda: caller
        assert http.delete(f"{base}/acme_inventory").json()["success"] is True


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f"FAIL {name}: {e!r}")
    sys.exit(1 if failures else 0)
