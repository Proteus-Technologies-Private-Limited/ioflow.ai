# Node Error Handling

Flows can now decide, node by node, what happens when a step fails: retry it,
carry on with a fallback, or take a dedicated **error branch**. A flow can also
name an **error handler flow** that starts whenever a run fails with an error
no node handled.

The design follows n8n's per-node settings plus error output. Make's error
types are used to decide what to retry.

## Designer

Select any node except the trigger. The properties panel now has a collapsible
**Error Handling** section:

| Setting | Meaning |
|---|---|
| **On Error: Stop the flow** | Default. The failure fails the execution, the same as before this feature. |
| **On Error: Continue** | The node outputs `{success: false, error: {...}}` and its normal connections run. An optional **fallback output** (JSON) is merged in so later nodes find the fields they expect. |
| **On Error: Route to error branch** | Adds a red **on error** handle at the bottom right of the node. Only nodes connected to it run when the node fails; normal connections are skipped. |
| **Treat unsuccessful responses as errors** | Action nodes only. A result with `success: false` counts as a failure. |
| **Retry on failure** | Max attempts (1–10, including the first try), initial delay, fixed or exponential backoff, max delay, and which error types to retry (default: connection, timeout, rate limit, 5xx; or *Any error*). |

Error edges are drawn red and dashed with an "on error" label. When a node
stops using the error branch, its error connections are removed.
Nodes show a small badge (`↻ 3`, `on error: continue`) when a policy is active.

**Flow Settings → Error Handler Flow** picks the flow that starts when this flow
fails with an unhandled error.

## Flow JSON

```json
{
  "id": "call_api",
  "type": "action",
  "data": {
    "label": "Create order",
    "errorHandling": {
      "onError": "error_branch",
      "retry": {
        "enabled": true,
        "maxAttempts": 3,
        "initialDelayMs": 1000,
        "backoff": "exponential",
        "maxDelayMs": 30000,
        "jitter": true,
        "retryOn": ["connection", "timeout", "rate_limit", "server"]
      },
      "continueOutput": null,
      "failOnUnsuccessfulResponse": false
    }
  }
}
```

The error edge is a normal edge with `"sourceHandle": "error"`:

```json
{ "id": "e1", "source": "call_api", "target": "notify_ops", "sourceHandle": "error", "targetHandle": "top" }
```

Flow-level handler: `flow_definition.settings.error_handler_flow_id`.

A node without `errorHandling`, or with `errorHandling: null`, behaves exactly as before.

## Error object

A handled failure stores this as the node's output under `error`:

```json
{
  "message": "api_call execution failed: Service unavailable",
  "type": "server",
  "status_code": 503,
  "exception": "ServiceExecutionError",
  "node_id": "call_api",
  "node_type": "action",
  "node_label": "Create order",
  "attempts": 3,
  "retryable": true,
  "handled_by": "error_branch",
  "timestamp": "2026-09-30T09:50:43Z",
  "response": { "...": "error body when available" }
}
```

Referencing it:

- `{{call_api.error.message}}`, `{{node_outputs.call_api.error.type}}`, and so on
- `{{error.message}}`: the most recent handled error in this run
- inside transform scripts: the `error` object (`error.message`, `error.type`, and so on), or `node_outputs['call_api']['error']`

### Error types

| Type | Source |
|---|---|
| `connection` | connect/network errors |
| `timeout` | timeouts, HTTP 408 |
| `rate_limit` | HTTP 429, "rate limit" messages |
| `server` | HTTP 5xx |
| `auth` | HTTP 401/403, authentication failures |
| `not_found` | HTTP 404 |
| `validation` | HTTP 400/409/422, `ValueError`/`KeyError`/`TypeError` (includes transform script errors) |
| `client` | other HTTP 4xx |
| `billing` | insufficient balance and other billing errors: **never retried or handled** |
| `unknown` | anything else |

Service failures now raise `ServiceExecutionError`, which carries the HTTP status code. The status code drives the classification above.

## Execution semantics

- **Retry** re-runs only the node's own handler. Every attempt is logged as a
  warning and broadcast as a `node_retry` WebSocket event. Retry is ignored on
  `loop`, `parallel`, `human_in_loop` and `wait_for_event` nodes, because
  re-running them would repeat the nodes they control.
- A **handled failure** is logged as a warning with `execution_stage: node_error_handled`.
  It is broadcast as `node_complete` with a `handled_error` field, so existing
  UIs treat the run as still in progress.
- **Continue on a condition** takes the false branch. **Continue on a loop** runs the
  loop's Continue output.
- **Loops:** an unhandled failure inside the loop body is the loop's failure, so
  the loop's own policy applies. Failures on the loop's continue path, after the
  loop finished, are not.
- **Joins (fork-join):** when a node takes its error branch, its normal outgoing
  paths are marked dead (dead-path elimination). A node reached by both the normal
  path and the error branch, such as the single response node of a synchronous
  flow, runs as soon as the live path arrives, instead of waiting forever.
- **Error handler flow:** starts in the background with trigger type `error_handler`
  and these input variables:
  `input.error` (`message`, `type`, `status_code`, `exception`, `node_id`, `node_label`, `attempts`),
  `input.execution` (`execution_id`, `trigger_type`, `started_at`, `failed_at`) and
  `input.flow` (`flow_id`, `flow_name`). It is skipped for simulations, for a flow
  that names itself, and when the failing run is itself an error handler run,
  which prevents chains.

## Validation

`FlowValidator` warns when:

- `onError` is `error_branch` but nothing is connected to the error handle
- an error edge exists but the node's mode isn't `error_branch`, so the branch never runs
- retry is set on a node type that doesn't support it, max attempts is out of range, or `retryOn` has unknown types

An unknown `onError` value is an error.

The `/api/v1/flow-design/guidelines` response (MCP `get_flow_design_guideline`)
has an `error_handling` section, so AI flow designers can use the feature.

## Files

| Area | File |
|---|---|
| Policy, classification, error object | `backend/services/node_error_handling.py` |
| Engine integration (retry loop, routing, dead paths, error handler flow, `{{error.*}}`) | `backend/services/execution_engine.py` |
| `error` in transform scripts | `backend/services/transform_executor_v2.py` |
| Validation | `backend/services/flow_validator.py` (`_validate_error_handling`) |
| Designer guide | `backend/api/flow_design.py` (`error_handling` section) |
| Properties panel | `frontend/src/components/flow/NodeErrorHandlingConfig.js` |
| Error handle and badges on every node | `frontend/src/components/flow/ResizableNode.js` |
| Error edge styling | `frontend/src/components/flow/CustomEdge.js` |
| Designer wiring and error handler flow setting | `frontend/src/pages/FlowDesigner.js` |

## Tests

- `backend/tests/test_node_error_handling.py`: offline unit tests (policy, classification, retry, routing, dead paths, validator).
  Run with `venv/bin/python backend/tests/test_node_error_handling.py`.
- `test-script/test_node_error_handling_e2e.py`: creates temporary flows through the API,
  runs them in-process against the real database, then deletes them. Covers error branch with retry,
  continue with fallback, stop, and error handler flow.

## Known limitations

- Dead-path elimination applies to error branches only. A condition's untaken
  branch still doesn't release joins, so the existing fork-join behaviour for
  condition branches is unchanged.
- An error branch left unconnected ends that path. Inside a loop this ends the
  loop, which is existing behaviour for any path that doesn't return to the loop.
