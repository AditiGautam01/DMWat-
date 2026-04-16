"""
db2_watsonx_pipeline.py
=======================
Pipeline that connects to a local Db2 database, extracts data,
and sends it to IBM watsonx.ai for AI-powered analysis.

Capabilities:
  - Pull table data from Db2 and summarize it with an LLM
  - Ask natural-language questions about your Db2 data
  - Generate SQL from plain English using your schema as context

Usage:
  1. Copy .env.example to .env and paste your WATSONX_API_KEY
  2. pip install python-dotenv requests
  3. python db2_watsonx_pipeline.py
"""

import os
import sys
import json
import re
import requests
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Environment setup
# ---------------------------------------------------------------------------
# Load .env before anything else
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv not installed — rely on system env vars

# Db2 DLL path must be set BEFORE importing ibm_db on Windows
dll_path = os.getenv("DB2_DLL_PATH", r"C:\PROGRA~1\IBM\SQLLIB\BIN")
if sys.platform == "win32" and os.path.isdir(dll_path):
    os.add_dll_directory(dll_path)

import ibm_db

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WATSONX_API_KEY  = os.getenv("WATSONX_API_KEY", "")
WATSONX_PROJECT  = os.getenv("WATSONX_PROJECT_ID", "")
WATSONX_URL      = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
DB2_DATABASE     = os.getenv("DB2_DATABASE", "SAMPLE")

# watsonx.ai model — IBM Granite is a good default
MODEL_ID = "ibm/granite-3-8b-instruct"

# API version
API_VERSION = "2024-05-01"

SEPARATOR = "-" * 60


# ===========================================================================
# watsonx.ai Client
# ===========================================================================
class WatsonxClient:
    """Lightweight client for watsonx.ai text generation REST API."""

    IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"

    def __init__(self, api_key: str, project_id: str, url: str):
        self.api_key = api_key
        self.project_id = project_id
        self.base_url = url.rstrip("/")
        self._token = None
        self._token_time = None

    def _get_token(self) -> str:
        """Exchange API key for an IAM bearer token (cached for 30 min)."""
        now = datetime.now()
        if self._token and self._token_time and (now - self._token_time).seconds < 1800:
            return self._token

        resp = requests.post(
            self.IAM_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": self.api_key,
            },
            timeout=30,
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        self._token_time = now
        return self._token

    def generate(
        self,
        prompt: str,
        model_id: str = MODEL_ID,
        max_tokens: int = 500,
        temperature: float = 0.3,
    ) -> str:
        """Send a prompt to watsonx.ai and return the generated text."""
        token = self._get_token()
        url = f"{self.base_url}/ml/v1/text/generation?version={API_VERSION}"

        payload = {
            "input": prompt,
            "model_id": model_id,
            "project_id": self.project_id,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "stop_sequences": ["\n\n---", ";"],
            },
        }

        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()

        # Extract generated text from response
        return result["results"][0]["generated_text"].strip()


# ===========================================================================
# Db2 Helper Functions
# ===========================================================================
def db2_connect():
    """Connect to local Db2 using implicit Windows auth."""
    conn = ibm_db.connect(DB2_DATABASE, "", "")
    return conn


def db2_get_schema(conn, schema: str = None) -> list[dict]:
    """Get table and column metadata from the database."""
    if schema is None:
        stmt = ibm_db.exec_immediate(
            conn, "SELECT RTRIM(CURRENT USER) FROM SYSIBM.SYSDUMMY1"
        )
        row = ibm_db.fetch_tuple(stmt)
        schema = row[0].strip()

    sql = """
        SELECT t.TABNAME, c.COLNAME, c.TYPENAME, c.LENGTH
        FROM SYSCAT.TABLES t
        JOIN SYSCAT.COLUMNS c ON t.TABSCHEMA = c.TABSCHEMA AND t.TABNAME = c.TABNAME
        WHERE t.TABSCHEMA = ? AND t.TYPE = 'T'
        ORDER BY t.TABNAME, c.COLNO
    """
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, schema)
    ibm_db.execute(stmt)

    tables = {}
    row = ibm_db.fetch_assoc(stmt)
    while row:
        tname = row["TABNAME"]
        if tname not in tables:
            tables[tname] = {"name": tname, "columns": []}
        tables[tname]["columns"].append({
            "name": row["COLNAME"],
            "type": row["TYPENAME"],
            "length": row["LENGTH"],
        })
        row = ibm_db.fetch_assoc(stmt)

    return list(tables.values())


def db2_query(conn, sql: str, max_rows: int = 20) -> list[dict]:
    """Execute a SQL query and return results as a list of dicts."""
    stmt = ibm_db.exec_immediate(conn, sql)
    rows = []
    row = ibm_db.fetch_assoc(stmt)
    while row and len(rows) < max_rows:
        # Strip whitespace from string values
        clean = {}
        for k, v in row.items():
            clean[k] = v.strip() if isinstance(v, str) else v
        rows.append(clean)
        row = ibm_db.fetch_assoc(stmt)
    return rows


def format_table(rows: list[dict]) -> str:
    """Format query results as a readable text table."""
    if not rows:
        return "(no rows)"

    cols = list(rows[0].keys())
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}

    header = " | ".join(c.ljust(widths[c]) for c in cols)
    sep = "-+-".join("-" * widths[c] for c in cols)
    lines = [header, sep]
    for r in rows:
        lines.append(" | ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))

    return "\n".join(lines)


# ===========================================================================
# Pipeline Operations
# ===========================================================================
def summarize_table(conn, wx: WatsonxClient, table_name: str):
    """Pull data from a Db2 table and ask watsonx.ai to summarize it."""
    print(f"\n{SEPARATOR}")
    print(f"  SUMMARIZE TABLE: {table_name}")
    print(SEPARATOR)

    # Fetch sample data
    rows = db2_query(conn, f'SELECT * FROM {table_name} FETCH FIRST 15 ROWS ONLY')
    table_text = format_table(rows)
    print(f"\n  Fetched {len(rows)} rows from {table_name}")

    prompt = f"""You are a data analyst. Below is a sample of data from the Db2 table "{table_name}".

DATA:
{table_text}

Provide a concise summary of this data. Include:
1. What this table appears to store
2. Key patterns or observations
3. The data types and ranges you see

Summary:"""

    print("  Sending to watsonx.ai...")
    response = wx.generate(prompt)
    print(f"\n  --- watsonx.ai Response ---\n{response}")
    return {
        "table_name": table_name,
        "rows": rows,
        "summary": response
    }


def ask_question(conn, wx: WatsonxClient, question: str, table_name: str):
    """Ask a natural-language question about data in a Db2 table."""
    print(f"\n{SEPARATOR}")
    print(f"  QUESTION: {question}")
    print(f"  TABLE:    {table_name}")
    print(SEPARATOR)

    rows = db2_query(conn, f'SELECT * FROM {table_name} FETCH FIRST 20 ROWS ONLY')
    table_text = format_table(rows)

    prompt = f"""You are an expert data analyst assistant. You must answer the user's question accurately based ONLY on the data provided below. Do not generate fake data. Provide ONLY the answer to the single question asked, and do not generate any additional questions or conversation.

TABLE: {table_name}
DATA:
{table_text}

QUESTION: {question}

ANSWER:"""

    print("  Sending to watsonx.ai...")
    response = wx.generate(prompt)
    print(f"\n  --- watsonx.ai Response ---\n{response}")
    return {
        "question": question,
        "table_name": table_name,
        "rows": rows,
        "answer": response
    }


def _clean_sql(raw: str) -> str:
    """Strip markdown fences and extract the first SQL statement from LLM output."""
    import re
    sql = raw.strip()

    # Remove ```sql ... ``` or ``` ... ``` markdown fences
    sql = re.sub(r"^```(?:sql)?\s*\n?", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\n?```\s*$", "", sql)

    # Take only the first complete statement (stop at first semicolon)
    if ";" in sql:
        sql = sql[: sql.index(";")]

    return sql.strip()


def generate_sql(conn, wx: WatsonxClient, request: str):
    """Generate SQL from a natural-language request using the DB schema as context."""
    print(f"\n{SEPARATOR}")
    print(f"  GENERATE SQL: {request}")
    print(SEPARATOR)

    # Get schema context
    schema_info = db2_get_schema(conn)
    
    # Smart Selection: Prioritize tables mentioned in the request string
    words = set(re.findall(r'\b\w+\b', request.upper()))
    prioritized = [t for t in schema_info if t["name"].upper() in words]
    others = [t for t in schema_info if t["name"].upper() not in words]
    
    # Combine and limit to 50 tables (plenty for Granite 8k context window)
    tokens_limit = 50
    selected_tables = (prioritized + others)[:tokens_limit]
    
    schema_text = ""
    for table in selected_tables:
        cols = ", ".join(f'{c["name"]} {c["type"]}({c["length"]})' for c in table["columns"])
        schema_text += f'  {table["name"]}({cols})\n'

    prompt = f"""You are an expert Db2 SQL developer. Write a single SQL query for the request below.

DATABASE SCHEMA:
{schema_text}

IMPORTANT NOTES:
- EMPLOYEE table uses WORKDEPT (not DEPTNO) for department code
- DEPARTMENT table uses DEPTNO for department code
- EMPLOYEE.WORKDEPT = DEPARTMENT.DEPTNO for joins
- Prefer the simplest query with fewest JOINs
- If a single table has all needed columns, do NOT join other tables

USER REQUEST: {request}

Rules:
- Standard Db2 SQL syntax only
- Only use tables and columns that exist in the schema above
- Return ONLY the SQL, no explanation, no markdown fences
- ONE query only, ending with a semicolon

SQL:"""

    print("  Sending to watsonx.ai...")
    response = wx.generate(prompt, temperature=0.1, max_tokens=300)

    # Clean up LLM output — strip markdown fences, take first statement only
    sql = _clean_sql(response)
    print(f"\n  --- Generated SQL ---\n  {sql}")

    # Execute the cleaned SQL against Db2
    print(f"\n  Executing against Db2...")
    result_rows = []
    error = None
    try:
        result_rows = db2_query(conn, sql)
        print(f"  Returned {len(result_rows)} rows:")
        print(format_table(result_rows))
    except Exception as e:
        error = str(e)
        print(f"  [WARN] Could not execute: {e}")
        
    return {
        "request": request,
        "sql": sql,
        "rows": result_rows,
        "error": error
    }


# ===========================================================================
# Main
# ===========================================================================
def main():
    print("=" * 60)
    print("  Db2 -> watsonx.ai Pipeline")
    print("=" * 60)

    # --- Validate config ---
    if not WATSONX_API_KEY or WATSONX_API_KEY == "your-ibm-cloud-api-key-here":
        print("\n  [ERROR] WATSONX_API_KEY is not set!")
        print("  Edit the .env file and paste your IBM Cloud API key.")
        print("  You can create one at: https://cloud.ibm.com/iam/apikeys")
        sys.exit(1)

    if not WATSONX_PROJECT:
        print("\n  [ERROR] WATSONX_PROJECT_ID is not set!")
        sys.exit(1)

    # --- Connect to Db2 ---
    print(f"\n  Connecting to Db2 [{DB2_DATABASE}]...", end=" ")
    conn = db2_connect()
    info = ibm_db.server_info(conn)
    print(f"OK ({info.DBMS_NAME} {info.DBMS_VER})")

    # --- Initialize watsonx.ai client ---
    print(f"  Connecting to watsonx.ai [{WATSONX_URL}]...", end=" ")
    wx = WatsonxClient(WATSONX_API_KEY, WATSONX_PROJECT, WATSONX_URL)
    print(f"OK (model: {MODEL_ID})")

    # ============================
    # Pipeline Demo
    # ============================

    # 1. Summarize a table
    summarize_table(conn, wx, "EMPLOYEE")

    # 2. Ask a question about data
    ask_question(
        conn, wx,
        question="Who is the highest-paid employee and what department are they in?",
        table_name="EMPLOYEE",
    )

    # 3. Generate SQL from natural language
    generate_sql(
        conn, wx,
        request="Show me the average salary by department, ordered from highest to lowest",
    )

    # --- Cleanup ---
    ibm_db.close(conn)
    print(f"\n{'=' * 60}")
    print("  Pipeline complete.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
