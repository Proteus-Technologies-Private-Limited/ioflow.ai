# Contributing to IOFlow

Thank you for considering a contribution. IOFlow was developed in-house and open sourced recently, so there is plenty of useful work at every size, from a one-file connector to core engine features.

## Where help is most useful

| Area | Good first step |
|---|---|
| **Connectors** | Add a connector for an API you use, or widen one that covers only a few operations. One JSON file, no backend code. |
| **Setup experience** | A WebSocket proxy in the Vite dev server, a Docker image variant with the optional system packages (OCR, browser scraping), and schema migrations managed by a tool instead of one-off scripts. |
| **Example flows** | Add a flow to `flow-design-src/` that shows a real use case end to end. |
| **Documentation** | Screenshots and short recordings for the README, corrections to older guides in `docs/`, and tutorials. |
| **Designer** | Drag-and-drop from the node palette, automatic layout, a dark theme. |
| **Engine** | Finishing the Parallel node, a delay node, multi-worker deployment. |
| **Platform** | Enforcing API key scopes, audit logging, rate limiting, a native MCP HTTP transport. |

The [feature tour](FEATURES.md) lists what is not there yet in each area. If you plan something larger, open an issue first so we can agree on the approach before you invest time.

## Set up a development environment

Follow [Getting started](GETTING_STARTED.md), then:

- Run the backend with hot reload: `IOFLOW_DEV_MODE=true ./start_backend.sh`
- Run the frontend dev server: `./start_frontend.sh` (http://localhost:5173, proxies `/api` to the backend)
- Keep the virtual environment in the repository root (`venv/`); the scripts expect it there.

## Add a connector

A connector is a JSON file in `backend/seed-applications/` with this top-level shape:

```json
{
  "key": "unique_key",
  "application": { },
  "events": [],
  "services": []
}
```

1. Copy the structure from the [connector template](../backend/seed-applications/SEED_APPLICATION_TEMPLATE.md) and read the [JSON structure reference](../backend/docs/seed-application-json-structure.md). An existing connector of similar shape (for example `sendgrid.json` for an API-key REST API) is a good model.
2. Define service arguments in `parameter_schema` (JSON Schema). The designer builds its forms from it.
3. To treat specific HTTP status codes as valid answers, use `response_config.success_check.success_status_codes`.
4. Install it from Admin → Seed Applications, connect an account, and run each service from a test flow.
5. **Increase `application.version` whenever you change an existing connector.** Installations upgrade by version, and existing connections are kept.

Rules for connector files:

- No real credentials, tokens, account IDs, phone numbers or personal data, including in examples and sample payloads. Use obviously fake values.
- No application-specific logic in the execution engine or service executors. If an API needs behavior the generic executors lack, add a general capability or a plugin.

You can also let an agent do the first draft: the `seed-app-designer` agent in the [Claude Code plugin](../ioflow-plugin/) writes, installs and tests connectors through the MCP tools.

## Add a plugin

Plugins live under `backend/plugins/builtin/` and are discovered at startup: every Python file in the four folders below is imported, and registration happens through `PluginRegistry`. Base classes are in `backend/plugins/base.py`.

### Service executor

A service executor implements a `service_type` that connectors can use.

```python
# backend/plugins/builtin/service_executors/my_protocol.py
from plugins.registry import PluginRegistry
from services.service_executors import ServiceExecutor


@PluginRegistry.executor("my_protocol")
class MyProtocolExecutor(ServiceExecutor):
    async def execute(self, parameters, context):
        host = parameters.get("host")
        if not host:
            return {"error": True, "message": "Host is required."}
        try:
            return await self._call_remote(host, parameters)  # your implementation
        except Exception as exc:
            return {"error": True, "message": f"My protocol call failed: {exc}"}
```

The executor receives the service's configuration and the connection's credentials as `self.service_config` and `self.auth_credentials`. `backend/services/ssh_command_executor.py` is a compact, complete example.

### Node type

```python
# backend/plugins/builtin/node_handlers/my_node.py
from plugins.registry import PluginRegistry
from plugins.base import NodeHandlerPlugin


@PluginRegistry.node("my_node")
class MyNodeHandler(NodeHandlerPlugin):
    async def execute(self, node_data, context, engine_ctx):
        # node_data: this node's configuration from the flow definition
        # context: variables and earlier node outputs
        # engine_ctx: callbacks into the engine (child nodes, templates, logging)
        return {"result": "value stored as this node's output"}
```

A new node type also needs:

- an entry in `VALID_NODE_TYPES` in `backend/services/flow_validator.py`
- a node component and a palette entry in the designer (`frontend/src/pages/FlowDesigner.js` and `frontend/src/components/flow/`)
- a section in `docs/flow-design-guide.md`, so both people and the design agents know how to use it

### Authentication type

Subclass `AuthHandlerPlugin`, register it with `@PluginRegistry.auth("my_auth")`, and implement `credential_schema`, `config_schema`, `validate_credentials` and `validate_config`. Add a `ui_schema` property and the UI renders the configuration form for you. `backend/plugins/builtin/auth_handlers/none_auth.py` is the smallest example.

### Webhook verifier

Implement `async verify(request, config, credentials)` returning `(is_valid, optional_response)` and register an instance with `PluginRegistry.register_webhook_verifier("my_method", MyVerifier())`. See `backend/services/webhook_verification.py`.

## Change the design agents

The three design agents (`flow-designer`, `flow-editor`, `seed-app-designer`) are defined once in `backend/agent_pack/agents/`. The copies in `ioflow-plugin/agents/` are generated, so do not edit them by hand:

```bash
venv/bin/python backend/scripts/build_plugin_agents.py
```

MCP tools must stay thin: the bridge in `backend/api/mcp_bridge.py` routes a tool call to an API call and holds no business logic.

## Code guidelines

- **Handle errors.** Validate input, catch failures, and return a message a user can act on. Do not let errors pass silently.
- **Log, do not simplify.** When something fails, add logging to find the cause instead of replacing the feature with a reduced version.
- **Change files in place.** Do not add `_v2` or `_new` copies of a file.
- **Keep the engine generic.** No connector-specific branches in execution code.
- **Migrations** go in `migrations/` as idempotent scripts.
- **Dependencies must be MIT-compatible.** Do not add GPL, AGPL, SSPL or source-available packages as requirements. If one is unavoidable for an optional feature, make it an optional import with a fallback.
- **No secrets or personal data** anywhere in the repository: use environment variables and fake sample values.

## Tests

Backend tests live in `backend/tests/`. Several run offline, without a database or network, and can be run directly from `backend/`:

```bash
cd backend
../venv/bin/python tests/test_node_error_handling.py
```

They also run under pytest if you install it. Add or extend a test when you change engine behavior, and describe in the pull request how you tested anything that needs a live service.

## Pull requests

1. Fork the repository and create a branch from `main`.
2. Keep each pull request to one topic, with a description of what changed and why.
3. Update the documentation for anything a user would notice.
4. Confirm the change contains no credentials or personal data.

How changes land: this repository is published from the maintainers' development tree. An accepted pull request is applied there and appears in the next publish, so it may be closed with a reference to the published commit instead of being merged with the merge button.

## Reporting bugs and asking questions

Open an [issue](https://github.com/Proteus-Technologies-Private-Limited/ioflow.ai/issues) with:

- what you did, what you expected, and what happened
- the relevant lines from `logs/ioflow.log`
- for flow problems, the exported flow JSON with credentials removed

Please do not describe a security vulnerability in a public issue. Open an issue that asks for a private contact, without the details, and a maintainer will follow up.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](../LICENSE).
