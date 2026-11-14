# Agent pack, tenant seed applications and assistant hardening

## Agent pack: one definition of IOFlow's design agents

`backend/agent_pack/agents/<name>.md` is the ONE definition of each IOFlow
design agent: a small front matter (`name`, `adk_id`, `description`, `tools`)
followed by the prompt.

| Pack agent | ADK agent | Plugin agent |
|---|---|---|
| `seed-app-designer` | `seed_application_designer` | `ioflow-plugin/agents/seed-app-designer.md` |
| `flow-designer` | `flow_designer` | `ioflow-plugin/agents/flow-designer.md` |
| `flow-editor` | `flow_design_editor` | `ioflow-plugin/agents/flow-editor.md` |

Every surface that runs one reads it from the pack:

- **IOFlow Assistant, Google ADK mode:** `agent/*/agent.py` uses
  `instruction=agent_prompt("<name>")`.
- **IOFlow Assistant, Claude Code mode:** the prompt comes from the pack;
  `agent.py` is no longer regex-scraped.
- **Claude Code plugin:** `ioflow-plugin/agents/*.md` are GENERATED. Edit the
  pack, then run `python backend/scripts/build_plugin_agents.py`.
  `tests/test_agent_pack.py` fails if a generated copy is stale.
- **External agents (Twasta's Ask-AI):** they call `GET /api/mcp/agent-pack`,
  which returns `{schema, version, tool_surface, agents: [...]}`. `version` is a
  content hash, so callers can cache on it.

### One tool surface

Every tool an agent lists is a tool of the MCP bridge (`/api/mcp/tools`). The
test fails if a pack agent names a tool the bridge lacks, or if a prompt calls a
tool missing from its own `tools` list.

The assistant's agents now reach the bridge through
`backend/mcp_server/bridge_proxy.py`, a stdlib stdio proxy and the Python twin of
`ioflow-plugin/mcp-proxy.mjs`. It is limited to the agent's own tools by
`IOFLOW_TOOL_ALLOWLIST`, so the assistant, the plugin and external agents all see
the same tools under the same names.

## Tenant seed applications

A global seed application is one JSON file every tenant shares, so writing one
stays INSTANCE_ADMIN only. A tenant's own connectors live in a separate catalog:

- **Storage:** `backend/seed-applications/tenants/<tenant_id>/<key>.json`.
  This is a sub-folder, so global discovery never sees it.
- **REST:** `/api/v1/tenant-seed-applications`, served by
  `api/tenant_seed_applications.py`:
  - `GET /` lists the catalog;
  - `GET /{key}` returns one seed;
  - `POST /validate` checks a seed without saving;
  - `PUT /{key}` takes `{seed, install}` and saves (and optionally installs);
  - `POST /{key}/install` installs or updates;
  - `DELETE /{key}` deletes.
- **Who may write:** any role that may manage applications, which is everyone
  except EXECUTION_MONITOR and FLOW_EXECUTOR. The tenant always comes from the
  caller, never from the request.
- **Validation:** the same schema validator plus the installer's field checks,
  all run before anything is written. A key already used by a global seed
  application is refused.
- **Install** (`JsonSeedManager.install_tenant_application`) creates an
  `app_scope='tenant'` application owned by the tenant. Re-installing updates it
  IN PLACE:
  - application, service and event ids are kept, matched by name;
  - subscriptions are never touched;
  - a service or event that was removed is deactivated, not deleted.
- **Bridge tools:** `list_`, `get_`, `validate_`, `save_`, `install_` and
  `delete_tenant_seed_application`.

The global install paths now ignore tenant applications (`app_scope != 'tenant'`).

## Permission fixes in the bridge

- **Global catalog writes need an instance admin.** These tools all write the
  GLOBAL catalog: `create_seed_application`, `edit_application_metadata`,
  `add_service_to_application`, `add_event_to_application`,
  `update_auth_configuration`, `delete_seed_application`,
  `duplicate_application`, install / uninstall / update / rollback, and
  `load_seed_application`. They now require INSTANCE_ADMIN.
  - The registry tools used to let a TENANT_ADMIN rewrite shared files.
  - TENANT_ADMIN also lost `create_seed_applications` / `edit_seed_applications`
    in the MCP auth permission maps.
- **Each request keeps its own identity.** `MCPBridgeService` is a singleton,
  and each request used to hand its auth handler to shared tool objects by
  assignment, so concurrent requests could swap identities. The handler now
  lives in a ContextVar, and the shared objects' `auth` / `auth_handler`
  attributes read it from there (`_RequestScopedAuth`).
- `create_seed_application` now forwards `auth_config`.

## Assistant hardening

- **Tokens no longer travel through `os.environ['IOFLOW_API_KEY']`.**
  - The caller's token used to be written there, which made it process-wide:
    concurrent sessions raced and one tenant's agent could act as another.
  - It now travels in a ContextVar (`agent_pack/runtime.py`), set per request
    and read when the agent builds its toolset.
  - The LLM provider key is no longer copied into `IOFLOW_API_KEY`.
- **The assistant requires a signed-in caller.**
  - `/api/assistant/execute` used to run anonymously when the request carried
    its own LLM key.
  - WebSocket messages now have their token VERIFIED, not just decoded.
  - The user and tenant ids the agent uses are the verified caller's, not the
    ones in the message.
- **Claude Code agent API:**
  - `/ws/{session_id}` needs `?token=` belonging to the session's user.
  - `/permission/{session_id}` needs the session's `hook_secret`. It is written
    (mode 0600) to the session file the hook reads.
  - The hook denies when the backend refuses it.
- MCP config files that carry a token are written with mode 0600.

## Not done (deliberately)

- **API-key scopes are still not enforced.** Every key defaults to `["read"]`,
  so enforcing scopes would break every existing plugin key that writes. That
  needs a migration of existing keys first.

## Tests

`backend/tests/test_agent_pack.py`, run from `backend/` with
`pytest tests/test_agent_pack.py` or `python tests/test_agent_pack.py`. It
covers:

- the pack, its tools and plugin parity;
- the ADK agents reading the pack;
- the bridge proxy against a fake bridge;
- the tenant seed lifecycle on SQLite;
- the tenant router over HTTP.
