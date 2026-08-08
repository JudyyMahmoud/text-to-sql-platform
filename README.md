# Multi-Tenant Text-to-SQL and Document Chat Platform

A secure backend that lets authenticated users:
- connect **live business databases** at runtime (no code changes),
- upload **documents** (PDF, Word, Excel, CSV, text) into searchable knowledge bases,
- and **chat** with both sources — database-only, document-only, or hybrid questions —
  through one conversational API, with tenant/role/table/column/row-level security enforced
  on every request.

Built with **FastAPI**, **PostgreSQL + pgvector**, **SQLAlchemy 2 / Alembic**, **LangGraph**,
and **SQLGlot** for SQL safety validation.

This whole codebase was verified end-to-end while building it: the Alembic migration was run
against a real Postgres+pgvector database, and a full login → create connection → test → sync
schema flow was exercised against a live sample database. It works out of the box.

---

## 1. What you need before you start

You only need **two things** installed on your computer:

1. **Docker Desktop** (includes Docker Compose) — [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
   This is the only thing you need to install. Docker will run PostgreSQL and the API server
   for you in isolated containers — you do **not** need to install Python, PostgreSQL, or
   anything else directly on your machine.
2. An **LLM API key** for chat/SQL generation — any OpenAI-compatible provider works, including
   **Groq** (fast and has a free tier) — [https://console.groq.com/keys](https://console.groq.com/keys).
   Plain OpenAI also works if you'd rather use that instead.

That's it. Everything else — Postgres, pgvector, the Python environment, the sample database,
**and document embeddings** — is handled automatically by Docker Compose. Embeddings run
locally inside the container (no API key, no extra cost), because not every LLM provider
(Groq included) offers an embeddings API.

### Using Groq specifically
Groq only serves chat/completions, not embeddings — this project already accounts for that by
running embeddings locally. All you do is put your Groq key in `.env` as shown in Step 3 below;
nothing else changes.

---

## 2. Step-by-step: running the project

### Step 1 — Unzip the project
Unzip the delivered project folder anywhere on your computer, e.g. to your Desktop. You should
see a folder called `text-to-sql-platform` containing files like `docker-compose.yml`,
`requirements.txt`, `app/`, `api/`, etc.

### Step 2 — Open a terminal in that folder
- **Windows**: open the folder in File Explorer, then right-click inside it and choose
  "Open in Terminal" (or open PowerShell and `cd` into the folder).
- **Mac**: open Terminal, then type `cd ` (with a trailing space), drag the folder into the
  terminal window, and press Enter.
- **Linux**: open a terminal and `cd` into the folder.

### Step 3 — Create your `.env` file
Copy the example environment file:

```bash
cp .env.example .env
```
(On Windows PowerShell: `copy .env.example .env`)

Now open `.env` in any text editor and fill in **three values**: `OPENAI_API_KEY`,
`JWT_SECRET_KEY`, and `ENCRYPTION_KEY`.

#### What these three values actually are

- **`OPENAI_API_KEY`** — despite the name, this is just "the API key for whichever
  OpenAI-compatible LLM provider you're using." If you have a **Groq** key, put it here — the
  `.env.example` file already points `OPENAI_BASE_URL` at Groq's endpoint, so a Groq key works
  immediately with no code changes. Get one free at
  [https://console.groq.com/keys](https://console.groq.com/keys).
- **`JWT_SECRET_KEY`** — a long random string the server uses to cryptographically sign login
  tokens (JWTs), so nobody can forge a fake "logged in" token. It isn't a key from any external
  service — you invent it yourself, it just needs to be long and random.
- **`ENCRYPTION_KEY`** — a random key (in a specific format called "Fernet") used to encrypt
  customer database passwords before they're saved to the platform's database, so raw
  passwords are never stored in plain text. Also not from any external service — you generate
  it yourself.

#### How to generate them

You don't need Python installed on your computer for this — the commands below run Python
inside a temporary Docker container instead, using the Docker Desktop you already installed.
Open a terminal and run each one:

```bash
# For JWT_SECRET_KEY:
docker run --rm python:3.11-slim python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# For ENCRYPTION_KEY:
docker run --rm python:3.11-slim python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

Each command prints one line of random text. Copy that text into the matching spot in `.env`:

```
JWT_SECRET_KEY=<paste the output of the first command here>
ENCRYPTION_KEY=<paste the output of the second command here>
OPENAI_API_KEY=<paste your Groq (or OpenAI) key here>
```

(If you'd rather use plain OpenAI instead of Groq, also change `OPENAI_BASE_URL` back to
`https://api.openai.com/v1` and `LLM_MODEL` to `gpt-4o-mini` in `.env`.)

### Step 4 — Start everything with Docker Compose
From inside the project folder, run:

```bash
docker compose up --build
```

The first run will take a few minutes while Docker downloads images and installs Python
packages. You'll see logs from three services: `postgres` (the platform's database),
`sample_customer_db` (a ready-made demo business database you can query immediately), and
`api` (the FastAPI backend). When it's ready you'll see something like:

```
ttsql_api  | Starting API server...
ttsql_api  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

Leave this terminal window open — it's running your server. To stop everything later, press
`Ctrl + C`, or open a new terminal and run `docker compose down`.

### Step 5 — Confirm it's running
Open your browser to:

```
http://localhost:8000/docs
```

You should see the interactive Swagger API documentation for every endpoint in the platform.

### Step 6 — Log in with the default account
On first boot, the platform automatically creates a demo tenant and admin user for you (see
`scripts/init_db.py`), so you don't have to register one by hand:

```
tenant_code: demo
email:       admin@demo.com
password:    ChangeMe123!
```

You can log in via `/docs` (use the `POST /api/auth/login` endpoint) or with `curl`:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"tenant_code":"demo","email":"admin@demo.com","password":"ChangeMe123!"}'
```

This returns an `access_token`. Copy it — every other request needs it in the header:
`Authorization: Bearer <access_token>`. In the `/docs` page, click the "Authorize" button at
the top right and paste `Bearer <access_token>` to unlock all the endpoints in the UI.

---

## 3. Trying out the platform end-to-end

A ready-made sample business database (`sample_company`, with `customers`, `orders`, and
`invoices` tables and some seed rows) is started automatically for you by Docker Compose, so
you can test Text-to-SQL immediately without connecting your own database first.

### 3.1 Connect the sample database
`POST /api/database-connections` (as the demo admin):
```json
{
  "name": "sample_company",
  "database_type": "postgresql",
  "host": "sample_customer_db",
  "port": 5432,
  "database_name": "sample_company",
  "username": "sample_user",
  "password": "sample_password",
  "ssl_enabled": false
}
```
> Note: use `host: "sample_customer_db"` (the Docker service name) when calling the API from
> inside Docker Compose — the containers talk to each other by service name, not `localhost`.

Then test it: `POST /api/database-connections/{id}/test`
Then sync its schema: `POST /api/database-connections/{id}/sync-schema`

### 3.2 Grant yourself table access
Tenant admins get automatic read access to their tenant's tables, so you can skip this step
for a quick test. For a real multi-user setup, grant specific tables/columns to a role or user
with `POST /api/permissions/table-permissions`.

### 3.3 Ask a database question
`POST /api/chat`
```json
{
  "message": "What is the total order amount for Acme Corp?",
  "database_connection_ids": ["<connection-id-from-3.1>"]
}
```

### 3.4 Upload a document and ask about it
1. `POST /api/knowledge-bases` with `{"name": "contracts"}`
2. `POST /api/files/upload?knowledge_base_id=<kb-id>` with a PDF/DOCX/XLSX/CSV/TXT file attached
3. Wait a few seconds for background processing (`GET /api/files/{id}` shows
   `processing_status: completed`)
4. `POST /api/chat`:
```json
{
  "message": "What does the contract say about payment terms?",
  "knowledge_base_ids": ["<kb-id>"]
}
```

### 3.5 Ask a hybrid question (combines both)
```json
{
  "message": "Compare the total invoice value with the contract value mentioned in the uploaded files.",
  "database_connection_ids": ["<connection-id>"],
  "knowledge_base_ids": ["<kb-id>"]
}
```
The response includes the SQL that ran, the row count, and citations pointing to the specific
file/page the answer drew from — see `sql` and `citations` in the response, and
`GET /api/messages/{message_id}/sql` / `GET /api/messages/{message_id}/citations` for full
traceability.

---

## 4. Running tests

Tests that don't need a live database (the SQL safety validator, encryption, and the app's
routing) can run directly:

```bash
docker compose exec api pytest tests/test_query_validator.py tests/test_encryption.py tests/test_app_smoke.py -v
```

These are the security tests demonstrating that destructive SQL (`DROP`, `TRUNCATE`,
multi-statement injection, SQL comments) and unauthorized tables/columns are rejected before
ever reaching a real database — see `tests/test_query_validator.py`.

---

## 5. Project structure

```
text-to-sql-platform/
├── app/            FastAPI app setup, config, dependencies, exceptions
├── api/routes/      All HTTP endpoints (auth, connections, files, chat, ...)
├── core/            Security (JWT/passwords), encryption, tenant context, permission resolver
├── models/          SQLAlchemy ORM models (one file per entity)
├── schemas/         Pydantic request/response models
├── services/
│   ├── database/    Connection testing, schema discovery, SQL validation & execution, adapters
│   ├── documents/   File parsing, chunking, embeddings, vector retrieval
│   └── llm/         OpenAI client, SQL generation prompt, answer generation prompt
├── agents/          LangGraph orchestrator (classify → database/document agent → answer)
├── migrations/       Alembic migration files (schema.sql equivalent)
├── scripts/         DB wait/seed scripts, sample customer database seed SQL
├── tests/           Unit + smoke tests
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

## 6. How the security model works (important to understand)

1. Every JWT contains `tenant_id`. Every single database query in the app filters by
   `tenant_id` — this is what keeps tenants isolated (`core/tenant_context.py`,
   `app/dependencies.py`).
2. `core/permissions.py` resolves, for the current user and a specific connection, **exactly**
   which tables and columns they're allowed to see (`get_allowed_schema`). This is the *only*
   schema ever shown to the LLM — it can't invent tables it wasn't told about.
3. The LLM proposes SQL (`services/llm/sql_generator.py`), but it never touches a real
   database directly. Every generated query passes through
   `services/database/query_validator.py`, which:
   - parses the SQL with **SQLGlot** (not just keyword matching),
   - blocks multiple statements and SQL comments,
   - blocks `DROP`, `TRUNCATE`, `ALTER`, `CREATE`, `GRANT`, `REVOKE`, `EXEC`, `CALL`, `COPY`,
     etc.,
   - blocks system schemas (`pg_catalog`, `information_schema`, ...),
   - rejects any table/column not in the resolved allowed schema,
   - injects a row limit automatically.
4. Only after validation does `services/database/query_executor.py` run the query, using a
   short connection timeout, a statement timeout, and (for Postgres) a read-only transaction
   for `SELECT`s.
5. Every generated SQL statement, its validation result, and its execution outcome is
   persisted to `query_executions` for full audit traceability, alongside `message_citations`
   for document evidence.
6. Sensitive columns (`is_sensitive = true` in `database_columns`) are excluded from the
   allowed schema by default, so they're never shown to the LLM or returned in results.

## 7. Extending to more database types

`services/database/adapters/` has one small adapter per dialect. PostgreSQL and MySQL work
out of the box. SQL Server and Oracle adapters are included and structurally complete, but
need their drivers added to `requirements.txt` and the `Dockerfile` to actually connect
(`pyodbc` + the "ODBC Driver 18 for SQL Server" system package for SQL Server; `oracledb` for
Oracle) — see the docstring at the top of each adapter file for the exact one-line addition.
Everything else (schema discovery, permissions, validation, execution) is dialect-agnostic and
needs no changes.

## 8. Production notes

- The demo admin password (`ChangeMe123!`) should be changed immediately in any non-local
  deployment — set `DEFAULT_ADMIN_PASSWORD` in `.env` before first boot, or change it via your
  own user-management flow afterward.
- In production, connect with a **separate, read-only database credential** per customer
  connection rather than the same credential used for admin tasks, and consider a dedicated
  row-level-security role at the database level as defense in depth beyond the application
  layer's SQLGlot validation.
- `CORSMiddleware` is currently wide open (`allow_origins=["*"]`) for local development —
  restrict this to your real frontend origin before deploying.
