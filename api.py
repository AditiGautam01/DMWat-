from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import os
import sys
import json
import asyncio
import requests
from pathlib import Path
from db2_watsonx_pipeline import (
    db2_connect, 
    db2_get_schema, 
    db2_query,
    format_table,
    WatsonxClient,
    summarize_table,
    ask_question,
    generate_sql,
    WATSONX_API_KEY,
    WATSONX_PROJECT,
    WATSONX_URL,
    MODEL_ID
)
import ibm_db
from maximo_client import MaximoClient
from maximo_mock import MockMaximoClient

app = FastAPI(title="Db2 + watsonx.ai Pipeline API")

# Mount the static directory for the frontend
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ---------------------------------------------------------------------------
# Maximo client factory — auto-detect mock vs real
# ---------------------------------------------------------------------------
_MAXIMO_BASE = os.getenv("MAXIMO_BASE_URL", "")
_MAXIMO_MOCK_MODE = (
    not _MAXIMO_BASE
    or "your-maximo" in _MAXIMO_BASE.lower()
    or os.getenv("MAXIMO_MOCK", "false").lower() in ("1", "true", "yes")
)

def get_maximo_client():
    """Return MockMaximoClient when Maximo isn't configured, else the real one."""
    if _MAXIMO_MOCK_MODE:
        return MockMaximoClient()
    return MaximoClient()

# Request Models
class SummarizeRequest(BaseModel):
    table_name: str

class QuestionRequest(BaseModel):
    table_name: str
    question: str

class SqlRequest(BaseModel):
    request: str

class MaximoAnalyzeRequest(BaseModel):
    data_type: str  # "workorders", "assets", "service_requests"
    question: str

class UnifiedPipelineRequest(BaseModel):
    table_name: str           # Db2 source table (e.g. "EMPLOYEE")
    maximo_entity: str = "workorders"  # "workorders", "assets", "service_requests"
    question: str             # NL question for watsonx.ai
    max_rows: int = 15        # Max Db2 rows to pull

# Dependency to get Db2 connection
def get_db2_conn():
    try:
        conn = db2_connect()
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

# Dependency to get watsonx client
def get_wx_client():
    if not WATSONX_API_KEY or WATSONX_API_KEY == "your-ibm-cloud-api-key-here":
        raise HTTPException(status_code=500, detail="WATSONX_API_KEY is not configured in .env")
    return WatsonxClient(WATSONX_API_KEY, WATSONX_PROJECT, WATSONX_URL)

@app.get("/")
async def root():
    return FileResponse(str(static_dir / "index.html"))

@app.get("/api/tables")
async def get_tables():
    conn = get_db2_conn()
    try:
        schema = db2_get_schema(conn)
        return {"tables": schema}
    finally:
        ibm_db.close(conn)

@app.post("/api/summarize")
async def api_summarize(req: SummarizeRequest):
    conn = get_db2_conn()
    wx = get_wx_client()
    try:
        result = summarize_table(conn, wx, req.table_name)
        return result
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Watsonx AI Error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        ibm_db.close(conn)

@app.post("/api/question")
async def api_question(req: QuestionRequest):
    conn = get_db2_conn()
    wx = get_wx_client()
    try:
        result = ask_question(conn, wx, req.question, req.table_name)
        return result
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Watsonx AI Error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        ibm_db.close(conn)

@app.post("/api/sql")
async def api_sql(req: SqlRequest):
    conn = get_db2_conn()
    wx = get_wx_client()
    try:
        result = generate_sql(conn, wx, req.request)
        if result["error"]:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Watsonx AI Error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        ibm_db.close(conn)

# ===========================================================================
# Maximo Integration Endpoints (batch)
# ===========================================================================

@app.get("/api/maximo/status")
async def maximo_status():
    """Return whether we're using live Maximo or synthetic mock data."""
    return {
        "mock_mode": _MAXIMO_MOCK_MODE,
        "source": "synthetic" if _MAXIMO_MOCK_MODE else "live",
        "message": (
            "Using synthetic Maximo data (no MAXIMO_BASE_URL configured)"
            if _MAXIMO_MOCK_MODE
            else f"Connected to {_MAXIMO_BASE}"
        ),
    }

@app.get("/api/maximo/workorders")
async def maximo_work_orders():
    try:
        client = get_maximo_client()
        orders = client.get_work_orders(limit=50)
        return {"work_orders": orders, "count": len(orders), "source": "synthetic" if _MAXIMO_MOCK_MODE else "live"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/maximo/assets")
async def maximo_assets():
    try:
        client = get_maximo_client()
        assets = client.get_assets(limit=50)
        return {"assets": assets, "count": len(assets), "source": "synthetic" if _MAXIMO_MOCK_MODE else "live"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/maximo/service_requests")
async def maximo_service_requests():
    try:
        client = get_maximo_client()
        requests_data = client.get_service_requests(limit=50)
        return {"service_requests": requests_data, "count": len(requests_data), "source": "synthetic" if _MAXIMO_MOCK_MODE else "live"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===========================================================================
# Maximo Streaming Endpoints (Server-Sent Events)
# ===========================================================================

async def _sse_stream(generator):
    """Wrap an async generator into an SSE text/event-stream."""
    try:
        count = 0
        async for record in generator:
            count += 1
            payload = json.dumps(record, default=str)
            yield f"event: record\ndata: {payload}\n\n"
        # Send a final "done" event with summary
        yield f"event: done\ndata: {{\"total\": {count}}}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {{\"error\": \"{str(e)}\"}}\n\n"


@app.get("/api/maximo/stream/workorders")
async def stream_work_orders(limit: int = 30):
    """Stream synthetic work orders via Server-Sent Events."""
    client = get_maximo_client()
    if not hasattr(client, "stream_work_orders"):
        # Fallback: batch as single SSE burst
        data = client.get_work_orders(limit)
        async def _batch():
            for r in data:
                yield r
        return StreamingResponse(_sse_stream(_batch()), media_type="text/event-stream")
    return StreamingResponse(
        _sse_stream(client.stream_work_orders(limit=limit)),
        media_type="text/event-stream",
    )


@app.get("/api/maximo/stream/assets")
async def stream_assets(limit: int = 30):
    """Stream synthetic assets via Server-Sent Events."""
    client = get_maximo_client()
    if not hasattr(client, "stream_assets"):
        data = client.get_assets(limit)
        async def _batch():
            for r in data:
                yield r
        return StreamingResponse(_sse_stream(_batch()), media_type="text/event-stream")
    return StreamingResponse(
        _sse_stream(client.stream_assets(limit=limit)),
        media_type="text/event-stream",
    )


@app.get("/api/maximo/stream/service_requests")
async def stream_service_requests(limit: int = 30):
    """Stream synthetic service requests via Server-Sent Events."""
    client = get_maximo_client()
    if not hasattr(client, "stream_service_requests"):
        data = client.get_service_requests(limit)
        async def _batch():
            for r in data:
                yield r
        return StreamingResponse(_sse_stream(_batch()), media_type="text/event-stream")
    return StreamingResponse(
        _sse_stream(client.stream_service_requests(limit=limit)),
        media_type="text/event-stream",
    )


# ===========================================================================
# Maximo AI Analysis
# ===========================================================================

@app.post("/api/maximo/analyze")
async def maximo_analyze(req: MaximoAnalyzeRequest):
    """Fetch Maximo data, send to watsonx.ai for AI analysis."""
    try:
        client = get_maximo_client()
        
        # Fetch the right data
        if req.data_type == "workorders":
            data = client.get_work_orders(limit=20)
        elif req.data_type == "assets":
            data = client.get_assets(limit=20)
        elif req.data_type == "service_requests":
            data = client.get_service_requests(limit=20)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown data type: {req.data_type}")
        
        if not data:
             return {
                 "data_type": req.data_type,
                 "question": req.question,
                 "records_analyzed": 0,
                 "answer": f"No data found for {req.data_type}.",
                 "rows": []
             }
        
        # Format for LLM context
        context = json.dumps(data[:15], indent=2, default=str)
        
        # Build prompt
        source_note = " (synthetic demo data)" if _MAXIMO_MOCK_MODE else ""
        prompt = f"""You are an expert IBM Maximo analyst. 
        
Given the following Maximo {req.data_type} data{source_note}:

{context}

Question: {req.question}

Provide a clear, actionable answer based on the data above."""

        # Use existing watsonx client wrapper
        wx = get_wx_client()
        answer = wx.generate(prompt, max_tokens=500)
        
        return {
            "data_type": req.data_type,
            "question": req.question,
            "records_analyzed": len(data),
            "answer": answer,
            "rows": data[:15],  # send rows back for frontend preview
            "source": "synthetic" if _MAXIMO_MOCK_MODE else "live",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Unified Pipeline: Db2 → Maximo → watsonx.ai
# ===========================================================================

@app.post("/api/pipeline/unified")
async def unified_pipeline(req: UnifiedPipelineRequest):
    """
    Full pipeline: pull data from Db2 → enrich through Maximo → analyze with watsonx.ai.
    
    Flow:
      1. Query the specified Db2 table
      2. Feed Db2 rows through the Maximo layer to generate correlated EAM records
      3. Combine both datasets as context and send to watsonx.ai with the user's question
    """
    conn = get_db2_conn()
    try:
        # Step 1: Pull data from Db2
        sql = f'SELECT * FROM {req.table_name} FETCH FIRST {req.max_rows} ROWS ONLY'
        db2_rows = db2_query(conn, sql, max_rows=req.max_rows)
        
        if not db2_rows:
            return {
                "pipeline": "db2 → maximo → watsonx",
                "error": f"No data found in Db2 table '{req.table_name}'",
                "db2_rows": [],
                "maximo_records": [],
                "answer": None,
            }
        
        # Step 2: Enrich through Maximo
        maximo_client = get_maximo_client()
        maximo_records = maximo_client.enrich_from_db2(db2_rows, req.maximo_entity)
        
        # Step 3: Build combined context for watsonx.ai
        db2_context = format_table(db2_rows[:req.max_rows])
        maximo_context = json.dumps(maximo_records[:req.max_rows], indent=2, default=str)
        
        source_label = "synthetic" if _MAXIMO_MOCK_MODE else "live"
        prompt = f"""You are an expert data analyst working with IBM Db2 and IBM Maximo.

Below is data from TWO connected systems:

=== SOURCE: Db2 Table "{req.table_name}" ===
{db2_context}

=== ENRICHED: Maximo {req.maximo_entity} (correlated to Db2 records, {source_label} data) ===
{maximo_context}

The Maximo records are linked to the Db2 rows above. Each Maximo record has a "db2_source" field showing which Db2 employee/entity it came from.

Question: {req.question}

Provide a clear, insightful answer that considers BOTH the Db2 source data and the Maximo operational data together."""
        
        wx = get_wx_client()
        answer = wx.generate(prompt, max_tokens=600)
        
        return {
            "pipeline": "db2 → maximo → watsonx",
            "table_name": req.table_name,
            "maximo_entity": req.maximo_entity,
            "question": req.question,
            "db2_row_count": len(db2_rows),
            "maximo_record_count": len(maximo_records),
            "answer": answer,
            "db2_rows": db2_rows[:10],
            "maximo_records": maximo_records[:10],
            "source": source_label,
        }
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Watsonx AI Error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        ibm_db.close(conn)


@app.get("/api/pipeline/unified/stream")
async def unified_pipeline_stream(
    table_name: str = "EMPLOYEE",
    maximo_entity: str = "workorders",
    max_rows: int = 15,
):
    """
    Stream the unified pipeline: Db2 rows → Maximo enrichment records via SSE.
    
    Emits 3 event types:
      - event: db2_row     — each source row from Db2
      - event: maximo      — each enriched Maximo record
      - event: done        — summary with counts
    """
    conn = get_db2_conn()
    try:
        sql = f'SELECT * FROM {table_name} FETCH FIRST {max_rows} ROWS ONLY'
        db2_rows = db2_query(conn, sql, max_rows=max_rows)
    finally:
        ibm_db.close(conn)

    maximo_client = get_maximo_client()

    async def _generate():
        # Phase 1: Stream Db2 source rows
        for row in db2_rows:
            payload = json.dumps(row, default=str)
            yield f"event: db2_row\ndata: {payload}\n\n"
            await asyncio.sleep(0.05)  # slight delay between Db2 rows

        # Phase 2: Stream enriched Maximo records
        count = 0
        async for record in maximo_client.stream_enriched(db2_rows, maximo_entity):
            count += 1
            payload = json.dumps(record, default=str)
            yield f"event: maximo\ndata: {payload}\n\n"

        # Done
        summary = {"db2_rows": len(db2_rows), "maximo_records": count}
        yield f"event: done\ndata: {json.dumps(summary)}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
