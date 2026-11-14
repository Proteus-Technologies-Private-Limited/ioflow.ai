# Getting started with IOFlow

This guide takes you from a fresh clone to a running IOFlow with your first flow. It replaces the older startup and run guides in this folder.

There are two ways to run IOFlow:

- **[Option A: everything in Docker](#option-a-everything-in-docker)**. One command, nothing else to install. Best for trying IOFlow.
- **[Option B: run from source](#option-b-run-from-source)**. The backend and frontend run from your terminal. Best for development.

Either way, start with the code:

```bash
git clone https://github.com/Proteus-Technologies-Private-Limited/ioflow.ai.git
cd ioflow.ai
```

## Option A: everything in Docker

You need Docker with Compose.

```bash
docker compose --profile app up -d --build
```

The first build takes several minutes. It starts three containers: PostgreSQL, Redis, and IOFlow itself, which serves the UI and the API together. Open **http://localhost:7001** and continue with [Create your account](#create-your-account).

What to know:

- **Keys are generated for you.** On first start the container creates the key that signs logins and the key that encrypts stored credentials, and keeps both in the `ioflow_secrets` volume. To supply your own, set `SECRET_KEY` and `ENCRYPTION_KEY` in your shell or in a `.env` file next to `docker-compose.yml`.
- **Running on a server?** Set `IOFLOW_PUBLIC_URL` (for example `https://ioflow.example.com`) so webhook URLs, OAuth callbacks and email links point at the right address.
- **A different port:** set `IOFLOW_PORT`.
- **Data** lives in named volumes. `docker compose --profile app down` keeps it; adding `-v` deletes it, including the generated keys.
- **Logs:** `docker compose logs -f ioflow`.
- **Optional features** such as OCR, HTML to PDF and browser-based scraping need system packages that the image does not include. See [optional dependencies](#optional-dependencies).

## Option B: run from source

| Requirement | Notes |
|---|---|
| Python 3.11 or newer | The backend. A virtual environment is created in the repository root. |
| Node.js 18 or newer | Builds the React frontend (Vite 5). |
| PostgreSQL | Required. The bundled Docker Compose file starts PostgreSQL 17 with TimescaleDB. |
| Redis | Optional. Used for locks, live-update fan-out and caching when reachable; IOFlow falls back to the database and memory without it. |
| Docker | Optional. The simplest way to run PostgreSQL and Redis locally. |

### 1. Start PostgreSQL and Redis

```bash
docker compose up -d postgres redis
```

This starts PostgreSQL on host port **5433** (user `ioflow`, password `ioflow_local_pass`, database `ioflow`) and Redis on 6379. Data is kept in named volumes; `docker compose down -v` deletes it.

To use your own PostgreSQL instead, create a database and a user that owns it, and put that connection string in `backend/.env` in step 3. If the database user is not named `ioflow`, append `?options=-csearch_path%3Dioflow` to the URL.

### 2. Build the UI and install dependencies

```bash
./build.sh
```

This builds the frontend, creates the virtual environment in `venv/`, installs the backend dependencies, and copies the built UI into `backend/static/` so the backend can serve it. The script ends with a note about editing `main.py`; you can ignore it, the backend already serves the built UI.

### 3. Configure the backend

```bash
cp backend/.env.example backend/.env
```

The defaults match the Docker Compose database from step 1, so for a local trial there is nothing to edit. `SECRET_KEY` and `ENCRYPTION_KEY` are left empty on purpose: `./start_backend.sh` generates both on first start and writes them into `backend/.env`.

Keep the encryption key safe. Connection credentials stored in IOFlow cannot be read without it.

Settings worth knowing:

| Setting | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string. |
| `SERVER_URL`, `BASE_URL`, `APP_URL` | The public URL of your IOFlow server. Used in webhook URLs and links. |
| `OAUTH_CALLBACK_BASE_URL` | Where OAuth2 providers redirect back to. Must be reachable by the provider for OAuth connectors. |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins, if the UI is served from a different origin than the API. |
| `REDIS_URL` | Redis connection. Leave as is for the Compose Redis. |
| `POSTMARK_API_KEY`, `FROM_EMAIL` | Outgoing email (activation, invitations, review notifications). SMTP can also be configured in the UI under Settings. |
| `IOFLOW_PORT` | Port the server listens on. Defaults to 7001. |

### 4. Start IOFlow

```bash
./start_backend.sh
```

Open **http://localhost:7001**. The backend serves both the UI and the API there, and creates its database tables on first start. Logs are written to `logs/ioflow.log`.

## After it starts

Useful endpoints:

- `http://localhost:7001/docs` for interactive API documentation
- `http://localhost:7001/health` for a health check

### Create your account

Register from the login page. **The first account registered on a new installation becomes the instance administrator** and is activated immediately. Accounts registered afterwards get their own organization (tenant) and are activated with a code sent by email, so configure outgoing email before inviting others.

### Install connectors

Connectors are not installed automatically. Go to **Admin → Seed Applications**, pick the ones you want, and install them. They are read from the JSON files in `backend/seed-applications/`.

Then open **Applications**, choose a connector, and connect it with your credentials (an API key, or an OAuth2 sign-in).

### Build your first flow

Three ways to start:

- **From an example.** Open **Flow Examples** and import one. The simplest is `ask-chatgpt.json`: a manual trigger, one OpenAI call, and a response. The example files live in `flow-design-src/`.
- **From the designer.** Create a flow, choose a trigger, and add nodes from the **Add Node** panel.
- **With an AI agent.** Set an AI provider under Settings → AI Settings and use "Create Flow with AI" on the dashboard, or connect Claude Code as described in the [README](../README.md#build-with-ai-agents).

Run a flow from the Flows list with **Trigger Flow**, and follow it under **Executions**. To step through a run node by node, use the flow debugger.

## Developing the frontend

For hot reload while working on the UI, run the Vite dev server in a second terminal:

```bash
./start_frontend.sh
```

It serves the UI on **http://localhost:5173** and proxies `/api` to the backend on 7001. Live execution updates and the debugger connect over WebSockets that the dev server does not proxy yet, so check those features against the built UI on port 7001 (`./build.sh` again after your changes).

For backend hot reload, set `IOFLOW_DEV_MODE=true` before running `./start_backend.sh`.

## Optional dependencies

Some connectors need software that pip does not install:

| Feature | Needs |
|---|---|
| Oracle Database connector | Oracle Instant Client. `start_backend.sh` detects it under `/opt/oracle/` or from `ORACLE_HOME`. |
| SQL Server queries | An ODBC driver for SQL Server |
| OCR in PDF and image processing | Tesseract and Poppler |
| HTML to PDF | wkhtmltopdf |
| Dynamic web scraping and screenshots | Playwright browsers (`venv/bin/playwright install chromium`) |
| Weaviate examples | `docker compose -f docker-compose-weaviate.yml up -d` |
| Built-in assistant in Claude Code mode | The `claude` command-line tool on the server |

IOFlow starts without any of these; the related services report an error when called.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `relation "users" does not exist` or similar | The database user is not named `ioflow`. Append `?options=-csearch_path%3Dioflow` to `DATABASE_URL`. |
| Connection refused to PostgreSQL | `DATABASE_URL` points at the wrong port. The Compose database listens on 5433. |
| Error about an invalid Fernet key | `ENCRYPTION_KEY` is not a Fernet key. Clear its value in `backend/.env` and restart with `./start_backend.sh` to generate one. |
| The page at `localhost:7001` is blank or returns JSON | Running from source and the UI has not been built. Run `./build.sh`. |
| OAuth sign-in for a connector fails on redirect | `OAUTH_CALLBACK_BASE_URL` is not reachable by the provider, or is not registered in the provider's app settings. |
| Activation email never arrives | Outgoing email is not configured. Set Postmark or SMTP. |
| `Too many open files` | Start with `./start_backend.sh`, which raises the open-file limit. |

If you are stuck, open an [issue](https://github.com/Proteus-Technologies-Private-Limited/ioflow.ai/issues) with the relevant lines from `logs/ioflow.log`.
