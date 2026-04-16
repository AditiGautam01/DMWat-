# Project Context — Db2 + watsonx.ai Pipeline

> **Last updated:** 2026-04-09

---

## 1. What This Project Is

An AI-powered data pipeline and web UI that connects a **local IBM Db2** database to **IBM watsonx.ai** for intelligent data analytics. Users can browse their database schema, summarise tables, ask natural-language questions about their data, and generate + execute SQL from plain English — all through a modern glassmorphism web interface.

**AI Model:** IBM Granite 3 8B Instruct (`ibm/granite-3-8b-instruct`)

---

## 2. Project Structure

```
local_pipeline/
│
├── api.py                    # FastAPI server (REST endpoints + static mount)
├── db2_watsonx_pipeline.py   # Core pipeline logic (Db2 ↔ watsonx.ai)
├── test_local_db2.py         # Driver validation script (4 tests)
├── .env.example              # Environment variable template
├── .env                      # Actual secrets (git-ignored)
├── context.md                # This file
│
└── static/
    ├── index.html            # Single-page frontend (glassmorphism UI)
    ├── style.css             # Dark-mode design system (CSS custom props)
    └── app.js                # Vanilla JS client (state → fetch → render)
```

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Browser (SPA)                         │
│  index.html + style.css + app.js                             │
│  ── Glassmorphism dark-mode UI ──                            │
│  State: { tables[], maximo[], activeTable, activeMaximo }    │
└─────────────────────────┬────────────────────────────────────┘
                          │ fetch()  (JSON over HTTP)
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                   FastAPI Server  (api.py)                   │
│  :8000                                                       │
│                                                              │
│  GET  /               → serves index.html                    │
│  GET  /api/tables     → list all user tables + columns       │
│  POST /api/summarize  → AI summary of a Db2 table            │
│  POST /api/question   → natural-language Q&A on a Db2 table  │
│  POST /api/sql        → NL→Db2 SQL generation + execution    │
│  GET  /api/maximo/*   → Fetch Maximo work orders, assets...  │
│  POST /api/maximo/analyze → NL Q&A on Maximo data            │
│                                                              │
│  Static mount: /static → ./static/                           │
└─────────┬────────────────────────────┬─────────────┬─────────┘
          │                            │             │
          ▼                            ▼             ▼
┌──────────────────┐     ┌─────────────────────┐  ┌────────────────┐
│   Local Db2      │     │ IBM watsonx.ai API  │  │ Maximo REST    │
│   SAMPLE DB      │     │ us-south.ml...      │  │ Remote API     │
│   (ibm_db)       │     │ Model: granite-3-8b │  │ OSLC Endpoint  │
│                  │     │ Auth: IAM bearer    │  │ Auth: API Key  │
│   Windows auth   │     │                     │  │                │
│   Port 50000     │     │                     │  │                │
└──────────────────┘     └─────────────────────┘  └────────────────┘
```

---

## 4. Key Files in Detail

### `db2_watsonx_pipeline.py` — Core Pipeline Logic (414 lines)

| Component | Description |
|---|---|
| **Environment setup** | Loads `.env` via `python-dotenv`, sets DLL path for Windows before importing `ibm_db`. |
| **`WatsonxClient`** | Lightweight REST client for watsonx.ai text generation. Handles IAM token exchange with 30-min caching. Calls `/ml/v1/text/generation` endpoint. |
| **`db2_connect()`** | Connects to the local SAMPLE database using Windows implicit auth (empty user/password). |
| **`db2_get_schema()`** | Queries `SYSCAT.TABLES` + `SYSCAT.COLUMNS` for the current user's schema. Returns `list[dict]` with table names and column metadata. |
| **`db2_query()`** | Executes arbitrary SQL, returns up to `max_rows` results as `list[dict]`. Strips whitespace from strings. |
| **`format_table()`** | Formats query results as readable ASCII text tables (for LLM prompts). |
| **`summarize_table()`** | Fetches 15 sample rows → builds a prompt → calls watsonx.ai → returns `{table_name, rows, summary}`. |
| **`ask_question()`** | Fetches 20 rows as context → asks the LLM to answer a user question → returns `{question, table_name, rows, answer}`. |
| **`generate_sql()`** | Sends full schema context + user request → LLM generates SQL → `_clean_sql()` strips markdown fences → executes against Db2 → returns `{request, sql, rows, error}`. |
| **`_clean_sql()`** | Post-processor that strips markdown fences and extracts the first SQL statement from raw LLM output. |
| **`main()`** | CLI demo: runs summarize → Q&A → SQL gen on the EMPLOYEE table. |

**Configuration (from `.env`):**

| Variable | Default | Description |
|---|---|---|
| `WATSONX_API_KEY` | *(required)* | IBM Cloud API key for watsonx.ai |
| `WATSONX_PROJECT_ID` | *(required)* | watsonx.ai project ID |
| `WATSONX_URL` | `https://us-south.ml.cloud.ibm.com` | watsonx.ai regional endpoint |
| `DB2_DATABASE` | `SAMPLE` | Local Db2 database name |
| `DB2_DLL_PATH` | `C:\PROGRA~1\IBM\SQLLIB\BIN` | Path to Db2 CLI DLLs (Windows) |

---

### `api.py` — FastAPI Server (115 lines)

| Endpoint | Method | Request Body | Response |
|---|---|---|---|
| `/` | GET | — | Serves `index.html` |
| `/api/tables` | GET | — | `{ tables: [{name, columns: [{name, type, length}]}] }` |
| `/api/summarize` | POST | `{ table_name }` | `{ table_name, rows, summary }` |
| `/api/question` | POST | `{ table_name, question }` | `{ question, table_name, rows, answer }` |
| `/api/sql` | POST | `{ request }` | `{ request, sql, rows, error }` |

Each endpoint opens a fresh Db2 connection, performs the operation, and closes it in a `finally` block. Watsonx client is validated for a configured API key before use.

**Pydantic request models:** `SummarizeRequest`, `QuestionRequest`, `SqlRequest`.

**Run command:** `python api.py` → starts Uvicorn on `127.0.0.1:8000` with hot-reload.

---

### `static/index.html` — Frontend (145 lines)

Single-page app with three view states:
- **Welcome** — landing screen with sparkle icon and instructions.
- **Table View** — operation cards (Summarize / Ask Question), Q&A input bar, results area with data preview table.
- **SQL Gen View** — textarea for natural-language requests, generated SQL display (monospace green), execution results table.

**External dependencies:**
- Google Fonts: **Inter** (weights 300–700)
- **Phosphor Icons** (via unpkg CDN) — modern line icons

---

### `static/style.css` — Design System (426 lines)

| Token | Value | Usage |
|---|---|---|
| `--bg-base` | `#0f172a` (Slate 900) | Page background |
| `--accent-primary` | `#3b82f6` (Blue 500) | Buttons, active states |
| `--accent-gradient` | Blue → Purple 135° | Sidebar title, icon backgrounds |
| `--success` | `#10b981` | Connection-status indicator |
| `--error` | `#ef4444` | Error messages |

Key design features:
- **Glassmorphism** panels (`backdrop-filter: blur(16px)` + semi-transparent backgrounds)
- **Animated background blobs** — 3 radial-gradient shapes with `blur(100px)`
- **Micro-animations** — `fadeIn` for view transitions, `spin` for loading indicators, hover `translateY(-4px)` on cards
- **Custom scrollbars** — thin 4–6px tracks with transparent background

---

### `static/app.js` — Frontend Logic (238 lines)

| Function | Purpose |
|---|---|
| `init()` | Fetches `/api/tables`, renders sidebar, sets up keyboard listeners. |
| `renderTableList()` | Builds sidebar table items with active-state highlighting. |
| `renderDataTable()` | Generates HTML `<table>` from JSON row data. |
| `app.switchView()` | Toggles between welcome / table / sql view states. |
| `app.selectTable()` | Sets active table, resets UI, switches to table view. |
| `app.summarizeTable()` | POST to `/api/summarize`, displays AI summary + data preview. |
| `app.askQuestion()` | POST to `/api/question`, displays AI answer + data context. |
| `app.generateSql()` | POST to `/api/sql`, displays generated SQL + execution results. |

**State model:** `{ tables: [], activeTable: null, currentView: 'welcome' }`

---

### `test_local_db2.py` — Driver Validation (159 lines)

Four sequential tests to validate the `ibm_db` driver against the local Db2 instance:

1. **`test_ibm_db_connection()`** — Low-level `ibm_db.connect()`, server/client info, quick query.
2. **`test_dbapi_connection()`** — DB-API 2.0 via `ibm_db_dbi`, cursor operations, table count.
3. **`test_context_manager()`** — `Db2connect` context manager (`with` block).
4. **`test_crud()`** — CREATE → INSERT (parameterised `execute_many`) → SELECT → DROP.

---

## 5. Technology Stack

| Component | Technology |
|---|---|
| **Database** | IBM Db2 for LUW (local install, SAMPLE database) |
| **Python Driver** | `ibm_db` (C extension) + `ibm_db_dbi` (DB-API 2.0) |
| **AI Service** | IBM watsonx.ai — `ibm/granite-3-8b-instruct` model |
| **Backend Framework** | FastAPI + Uvicorn |
| **Frontend** | Vanilla HTML/CSS/JS (no framework) |
| **Design** | Glassmorphism dark-mode, Inter font, Phosphor Icons |
| **Auth (watsonx)** | IBM IAM API key → bearer token exchange |
| **Auth (Db2)** | Windows implicit authentication (empty credentials) |
| **Environment** | `.env` file via `python-dotenv` |

---

## 6. Dependencies

### Python

| Package | Purpose |
|---|---|
| `ibm_db` | Db2 CLI/ODBC driver |
| `ibm_db_dbi` | DB-API 2.0 wrapper (used by test script) |
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `pydantic` | Request validation (via FastAPI) |
| `python-dotenv` | `.env` file loading |
| `requests` | HTTP client for watsonx.ai REST API |

### System

| Requirement | Details |
|---|---|
| **IBM Db2** | Local installation with SAMPLE database created |
| **Db2 CLI Driver** | DLLs at `C:\PROGRA~1\IBM\SQLLIB\BIN` (Windows) |
| **Python** | 3.9+ |
| **IBM Cloud Account** | API key + watsonx.ai project for AI features |

### Frontend (CDN)

| Library | CDN |
|---|---|
| Inter font | Google Fonts |
| Phosphor Icons | unpkg.com/@phosphor-icons/web |

---

## 7. Running the Project

```bash
# 1. Install Python dependencies
pip install ibm_db fastapi uvicorn python-dotenv requests

# 2. Configure environment
cp .env.example .env
# Edit .env — set WATSONX_API_KEY and WATSONX_PROJECT_ID

# 3. Validate Db2 connectivity
python test_local_db2.py

# 4. Run the pipeline CLI demo (optional)
python db2_watsonx_pipeline.py

# 5. Start the web server
python api.py
# → Open http://127.0.0.1:8000 in browser
```

---

## 8. Key Design Decisions

| Decision | Rationale |
|---|---|
| **Windows implicit auth** for Db2 | Simplifies local development — no credentials needed when the Windows user owns the database. |
| **30-min IAM token cache** | Avoids re-authenticating on every watsonx.ai call; tokens are valid for 60 min. |
| **Schema-aware SQL generation** | Full schema context is sent to the LLM so it only uses real tables/columns. Limited to 15 tables to fit the context window. |
| **`_clean_sql()` post-processing** | LLMs often wrap SQL in markdown fences or add explanations; this strips that down to executable SQL. |
| **Fresh Db2 connection per request** | Each API endpoint creates and closes its own connection. Simple and avoids connection-pool complexity. |
| **Vanilla JS frontend** | No build step, no framework overhead. The SPA is small enough that vanilla JS with a simple state object keeps things clean. |
| **Glassmorphism + dark mode** | Modern, premium aesthetic. Uses CSS custom properties for a maintainable design system. |

---

## 9. Known Constraints & Gotchas

- **Windows DLL path**: `os.add_dll_directory()` must be called **before** `import ibm_db` or import will fail with `ImportError: DLL load failed`.
- **SQL generation accuracy**: The Granite 3 8B model may occasionally generate invalid SQL. The pipeline handles this gracefully by catching execution errors and returning them to the user.
- **Context window limits**: Schema info is capped at 15 tables; data context is capped at 15–20 rows. Larger databases may need more sophisticated chunking.
- **No connection pooling**: Each request opens/closes a connection. Fine for single-user local use; would need pooling for production.
- **No authentication on the API**: The FastAPI server is intended for local development only — no auth middleware.
- **`.env.example` contains real-looking keys**: The example file ships with placeholder values that look like real credentials — always regenerate before use.
