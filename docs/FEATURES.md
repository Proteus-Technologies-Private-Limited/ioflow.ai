# IOFlow feature tour

Everything IOFlow does, area by area. Each section ends with what is **not there yet**, so you can judge fit before you install. For setup, see [Getting started](GETTING_STARTED.md).

**Contents**

1. [Flow designer](#1-flow-designer)
2. [Triggers](#2-triggers)
3. [Nodes](#3-nodes)
4. [Variables, templates and transforms](#4-variables-templates-and-transforms)
5. [Error handling and retries](#5-error-handling-and-retries)
6. [Human review and waiting for events](#6-human-review-and-waiting-for-events)
7. [Connectors and service types](#7-connectors-and-service-types)
8. [Authentication and webhook security](#8-authentication-and-webhook-security)
9. [Debugging and monitoring](#9-debugging-and-monitoring)
10. [AI agents and MCP](#10-ai-agents-and-mcp)
11. [Publishing flows](#11-publishing-flows)
12. [Usage, cost and billing](#12-usage-cost-and-billing)
13. [Teams, tenants and access](#13-teams-tenants-and-access)
14. [Architecture and extensibility](#14-architecture-and-extensibility)

---

## 1. Flow designer

The designer is a React Flow canvas where a flow is a graph of nodes connected by edges.

- **Canvas.** Add nodes from the Add Node panel, drag them into place, and connect them. A minimap, zoom controls, and an overlap indicator keep large flows readable.
- **Schema-driven forms.** Each connector service declares its parameters as JSON Schema, and the designer generates the form: nested objects, arrays of objects, tables, file inputs, and lookups that fetch options from the connected application.
- **Variable picker.** Insert values from the trigger or from earlier nodes without typing paths. Variables appear as pills inside text fields.
- **Condition builder.** Build simple conditions visually and switch to a text expression for complex ones.
- **Transform editor.** Write Python in a code editor with variable autocomplete and templates, or describe the transform in plain language and let the AI assistant write it.
- **Live validation.** The flow is validated on the server as you edit, with errors listed in a panel and shown on the nodes.
- **Undo and redo.** 50 steps of history with the usual keyboard shortcuts.
- **Import and export.** Export a flow as JSON and import it elsewhere. On import, IOFlow checks which connectors the flow needs and walks you through installing the missing ones.
- **Co-editing.** Invite someone with a link and edit together, with live cursors, selection highlights, a participant list, and chat.
- **Guided tour.** A walkthrough introduces the designer on first use.

**Not there yet:** dragging nodes from the palette onto the canvas (nodes are added by click), automatic layout, flow version history, a run button inside the designer (flows are run from the Flows list or the debugger), and the visual drag-and-drop transform builder.

## 2. Triggers

| Trigger | What starts the flow |
|---|---|
| **Application event** | A webhook from a connected application, such as a new Shopify order or a Slack message. IOFlow verifies the request and answers provider handshakes. |
| **Polling** | For APIs without webhooks: IOFlow calls a service on a schedule and starts the flow when it sees new IDs, a newer timestamp, a changed hash, or a changed count. |
| **Schedule** | An interval, a cron expression, or a daily, weekly or monthly time, with timezone support. |
| **API call** | An HTTP request to the flow's endpoint, either asynchronous (returns an execution ID) or synchronous (returns the flow's Response node output). |
| **MQTT** | A message on a topic. A bounded queue, worker pool, batching, rate limiting and deduplication protect the server from bursts. |
| **File change** | A file created or modified in a watched folder on the server. |
| **Chat input** | A message in a conversation, for flows that behave like a chat assistant. |
| **Manual** | A person starts the run and fills in typed inputs. |

Email-driven flows are built with the IMAP and POP3 connectors' events.

## 3. Nodes

| Node | Purpose |
|---|---|
| **Trigger** | The start of the flow; defines its input. |
| **Action** | Calls a service of a connected application. |
| **Condition** | Branches on an expression. |
| **Loop** | Repeats a section with `forEach`, `while`, or `for`. |
| **Transform** | Runs Python over the data. |
| **Human Review** | Pauses the run and creates a task for a person. |
| **Wait for Event** | Pauses until a matching application event arrives, or a timeout passes. |
| **Response** | Sets the body and status code returned by a synchronous flow. |

A flow can call another flow: publish the inner flow as a reusable connector (see [Publishing flows](#11-publishing-flows)) and use it from an Action node. AI agents are used the same way, through the AI Agent connector.

**Not there yet:** the Parallel node (the handler exists but the validator does not accept it yet) and a dedicated delay node.

## 4. Variables, templates and transforms

- **Variables.** `input.*` holds the trigger data, `node_outputs.<node>.*` the result of each earlier node, `loop.*` the current item and index, `global.*` values you set from a transform, and `flow.*` metadata about the run.
- **Templates.** Any parameter can contain `{{ ... }}` expressions. Request and response templates in connectors use sandboxed Jinja2 with filters such as `tojson`, `from_json`, `to_int`, `to_float`, `iso8601`, `money` and `csv_list`.
- **Transforms.** A Transform node is a Python script with access to the flow's variables and to reusable helper functions.
- **AI-written transforms.** Describe the result you want and the assistant writes the script, then refine it in conversation. Works with OpenAI, Anthropic, Google Gemini, Azure OpenAI, DeepSeek, and local models through Ollama or LM Studio.

**Important:** transforms run inside the backend process with a module allowlist and a 30-second timeout. That limits accidents, but it is not a security sandbox. Treat anyone who can edit flows as trusted.

## 5. Error handling and retries

Each node can define what happens when it fails. See [Node error handling](node-error-handling.md).

- **Retries** with fixed or exponential backoff and jitter, up to 10 attempts.
- **Retry by cause:** connection errors, timeouts, rate limits, server errors, or any error.
- **On failure:** stop the flow, continue with a fallback output, or follow a dedicated error branch.
- **Error-handler flow:** a flow-level setting that runs another flow when this one fails.

## 6. Human review and waiting for events

**Human Review** puts a person in the middle of an automated process: approve an invoice, correct extracted data, sign off on a message before it is sent.

- Assign a task to specific users or to a role, with a title, description, priority, and the data the reviewer should see.
- Reviewers work from the **Task Inbox**, filtered by pending, completed, escalated, expired and cancelled. A bell in the header and an email announce new tasks.
- Tasks can be reassigned or cancelled, and can be completed through a tokenized link without signing in.
- On timeout, a task can be approved automatically, rejected automatically, escalated to someone else (several levels), or failed.

**Wait for Event** pauses a run until an application event arrives that matches a token or correlation value, such as a payment confirmation for the order the flow is processing. A timeout decides what happens if it never comes.

## 7. Connectors and service types

A connector (a "seed application") is a JSON file that describes an application: how to authenticate, which services it offers, and which events it sends. 50+ connectors ship in [`backend/seed-applications/`](../backend/seed-applications/); the [README](../README.md#connectors) lists them.

Connectors are installed per installation from Admin → Seed Applications, and each tenant connects its own accounts. Connectors are versioned, so an upgrade keeps existing connections.

A service in a connector uses one of these service types:

| Service type | What it can do |
|---|---|
| **REST / HTTP** | Any HTTP API, with JSON, form, XML and multipart bodies, request and response templates, and custom success rules (for example, treating a 404 as a valid answer). |
| **GraphQL** | Queries and mutations against GraphQL APIs. |
| **Outbound webhook** | Post an event to another system. |
| **Database query** | SQL against PostgreSQL, MySQL, Oracle, SQL Server and SQLite, with connection pooling, and Arrow Flight sources such as Dremio. |
| **File systems** | Read, write, list and move files on local disk, FTP, SFTP and SMB shares. |
| **PDF processing** | Merge, split, rotate, extract text, images and tables, OCR, encrypt and decrypt, watermark, compress, fill forms, and convert HTML, text or images to PDF. |
| **Image processing** | Resize, crop, rotate, convert, overlay, watermark, OCR, and read QR codes and barcodes. |
| **Web scraping** | Static pages and JavaScript-rendered pages (Playwright), screenshots, form filling, clicking and scrolling, multi-page crawls, sitemaps, and change monitoring. |
| **SSH command** | Run a command on a remote server. |
| **Email** | Send through SMTP; receive through IMAP and POP3. |
| **AI agent** | Run a Google ADK agent (Gemini models) with tools as a step in a flow. |

**Not there yet:** NFS and S3 in the file systems connector, and PDF signing. Some features need extra software on the server; see [optional dependencies](GETTING_STARTED.md#optional-dependencies).

## 8. Authentication and webhook security

**Connecting applications**

- **OAuth2:** authorization code (with PKCE), client credentials, refresh tokens, and provider quirks such as custom token headers.
- **API key:** in a header, query parameter or body, with a configurable name and prefix (this covers bearer tokens).
- **Basic auth,** including application passwords.
- **Token exchange:** sign in with a username and password to obtain a token, refreshed automatically.
- **Custom:** any combination of headers and parameters.

Stored credentials are encrypted with a key you control.

**Verifying incoming webhooks**

- **HMAC signatures** with SHA-256, SHA-1 or SHA-512, a configurable header and signing string, and a timestamp tolerance against replays.
- **Challenge handshakes,** both the POST-body style and the GET query style.
- **Tokens** in a bearer header, a custom header, or a query parameter.

## 9. Debugging and monitoring

- **Step debugger.** Run a flow one node at a time, see each node's variables, change a node's configuration or variables mid-run, then resume or stop.
- **Transform debugger.** Step into a Transform node and run its Python line by line, with breakpoints and a variables view.
- **Executions.** A filterable history with live status updates, input and output data, and a hierarchical log of every node.
- **Log levels.** Record everything, a per-node summary, or errors only, with sampling for high-volume flows.
- **Polling logs.** See when each polling trigger last ran, what it found, and any errors.
- **Dashboard.** Seven-day execution statistics and workspace counts.
- **Health.** A `/health` endpoint, plus an optional watchdog (systemd timer and scripts in `scripts/`) that restarts an unresponsive server and sends an email alert. See [Health monitoring](health-monitoring.md).

**Not there yet:** node-level breakpoints in the step debugger.

## 10. AI agents and MCP

IOFlow treats AI agents as builders with the same reach as a person in the UI.

**MCP tools.** The backend exposes more than 90 tools through an HTTP bridge at `/api/mcp`:

| Group | Examples |
|---|---|
| Explore | Search connectors, services and events; read schemas and samples |
| Build connectors | Create and edit a connector, add or remove services and events, set up authentication |
| Test | Validate a connector, test an endpoint, authentication and parameters, generate a test report |
| Deploy | Install, update, verify and roll back connectors; create connections |
| Design flows | Create a flow, add trigger and action nodes, validate, save |
| Edit flows | Add, remove and replace nodes, update edges |
| Inspect | List flows, read execution details and logs |
| Guides | On-demand guidance for conditions, transforms, loops, human review, triggers and parameter mapping |

Clients connect through a small stdio proxy (Node or Python, both included) and authenticate with an IOFlow API key or a user token. The **MCP Services** page in the UI lets you browse and run the tools by hand.

**Claude Code plugin.** [`ioflow-plugin/`](../ioflow-plugin/) adds three agents and four skills to Claude Code:

- `flow-designer` creates and validates new flows.
- `flow-editor` changes existing flows and diagnoses failed runs.
- `seed-app-designer` writes, installs and tests connectors.
- Skills: `/ioflow:design-flow`, `/ioflow:edit-flow`, `/ioflow:create-seed-app`, `/ioflow:list-apps`.

**Built-in assistant.** A chat panel inside IOFlow designs flows and connectors and answers questions about your workspace. It runs on Google ADK with Gemini, or on a Claude Code installation on the server. "Create Flow with AI" and "Create Connector with AI" on the dashboard start it with a prompt.

**Agent pack.** Each design agent is defined once, as a Markdown file with its prompt and its allowed tools. The same definition drives the built-in assistant, the Claude Code plugin, and any external agent that fetches it from `/api/mcp/agent-pack`. See [Agent pack](AGENT_PACK_AND_TENANT_SEED_APPS.md).

**Not there yet:** a native MCP HTTP transport (today, remote use goes through the stdio proxy) and OAuth for MCP clients.

## 11. Publishing flows

A finished flow can be offered to others in three forms.

- **As an API.** Every flow with an API trigger gets generated documentation: authentication, endpoints, parameters, responses, error codes, and samples in cURL, Python, JavaScript and PHP. An organization-wide page indexes all flow APIs.
- **As a reusable connector.** Publish a flow as an application and it appears in the designer like any other connector, with its inputs as parameters. This is how flows call other flows.
- **As a hosted app.** Turn a flow into a web app at its own URL: an input form, live progress, and a result view. Each app has:
  - visibility settings (public, private, or access granted per user) and rate limits
  - usage analytics, subscribers, and optional per-run billing
  - its own documentation pages and related flows
  - a **landing page builder** with 16 block types (hero, rich text, images and galleries, input form, progress, results, features, pricing, call to action and more) and theme colors
  - embed code as an iframe, a widget, or a modal

**Marketplace (beta).** A catalog where published applications can be listed with categories, ratings and reviews, behind an approval queue for administrators.

## 12. Usage, cost and billing

- **Third-party cost metering.** A connector can declare what a call costs: per call or per unit consumed (such as tokens), optionally priced by model. IOFlow records usage per flow run, so you can see what each flow spends on external APIs. Prices can be overridden per connection. Metering currently ships for the Anthropic and X (Twitter) connectors. See [Flow usage and cost](FLOW_USAGE_AND_COST.md).
- **Daily budgets.** Set a daily cap per flow; IOFlow checks it before a run starts and before each metered call.
- **Usage dashboard.** Trends, cost breakdowns by application and service type, and free versus paid executions.
- **Prepaid balances.** For installations that charge tenants: a balance per tenant, top-ups, automatic top-up, usage limits, low-balance warnings, transaction history, and per-application pricing.

**Not there yet:** online payment in the top-up screen. The backend integrates Razorpay, but the UI records top-ups manually.

## 13. Teams, tenants and access

- **Multi-tenant.** Each organization is a tenant. Connectors and connections live in a PostgreSQL schema per tenant; flows and executions live in shared tables scoped by tenant.
- **Roles.** Instance admin, tenant admin, flow designer, flow executor, execution monitor, and application provider. Executors and monitors see flows read-only.
- **Flow visibility.** A flow can be private to its author, shared with the tenant, or global.
- **Sign-in.** Email and password, Google sign-in, password reset, and invitations by email.
- **API keys.** Created per user for scripts and agents, stored hashed, with optional expiry.
- **Onboarding.** A setup wizard walks a new administrator through AI settings, connecting applications, and balances.

**Not there yet:** enforced API key scopes, audit logging, and built-in rate limiting for the main API.

## 14. Architecture and extensibility

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy, APScheduler |
| Database | PostgreSQL (TimescaleDB optional, for MQTT time series) |
| Cache and coordination | Redis when available, with database and in-memory fallbacks |
| Frontend | React 18, Vite, React Flow, Tailwind CSS, TanStack Query, CodeMirror |
| Agents | MCP bridge, Google ADK, optional Claude Code |

- **One process to run.** Schedules, polling, the MQTT listener, the file watcher and review timeouts run as background tasks inside the API server. There is no separate worker or queue to operate.
- **Plugin registry.** Node types, service executors, authentication types and webhook verifiers register with a decorator and are discovered at startup. The UI renders their configuration forms from the schemas they publish. See the [contributing guide](CONTRIBUTING.md).
- **Connectors as data.** Most integrations need no backend code at all, only a JSON file.
- **Performance.** Pooled database connections per connection, a cache of flow definitions invalidated on change, and a shared HTTP client. See [Pooling and caching](performance-pooling-and-caching.md).
- **Theming.** Brand colors are CSS variables. See the [theming guide](THEMING_GUIDE.md).

**Not there yet:** multi-worker deployment (leader election and a shared message queue are in place, but the server starts a single worker), loading plugins from external packages, and a dark theme.
