from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.config import settings
from src.graph.neo4j_client import Neo4jClient
from src.gemini.service import ask as gemini_ask
from src.config import settings
import google.generativeai as genai


app = FastAPI(title="MCP-like Bridge: Neo4j Cypher Executor")


class CypherRequest(BaseModel):
    query: str
    params: dict | None = None


class CypherResponse(BaseModel):
    results: list[dict]


def get_client() -> Neo4jClient:
    return Neo4jClient(
        settings.NEO4J_URI or "bolt://localhost:7687",
        settings.NEO4J_USERNAME or "neo4j",
        settings.NEO4J_PASSWORD or "",
        database=settings.NEO4J_DATABASE,
    )


@app.post("/execute_cypher_query", response_model=CypherResponse)
def execute_cypher_query(body: CypherRequest):
    client = get_client()
    try:
        results = client.run_query(body.query, body.params, readonly=settings.MCP_READ_ONLY)
        return CypherResponse(results=results)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Execution error") from e
    finally:
        client.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"status": "ok", "message": "MCP-like Bridge online", "docs": "/docs"}


class AskRequest(BaseModel):
    question: str
    server: str | None = None


@app.post("/ask")
def ask(body: AskRequest):
    try:
        server_url = body.server or "http://localhost:8000"
        answer = gemini_ask(body.question, server_url)
        return {"answer": answer}
    except Exception as e:
        # Return more explicit error detail to help diagnose API key or network issues
        raise HTTPException(status_code=500, detail={"error": str(e), "type": e.__class__.__name__})


@app.get("/diag/gemini")
def diag_gemini():
    try:
        if not settings.GEMINI_API_KEY:
            return {"ok": False, "reason": "GEMINI_API_KEY missing"}
        genai.configure(api_key=settings.GEMINI_API_KEY)
        # lightweight check: list models or get a specific one
        models = [m.name for m in genai.list_models()][:5]
        return {"ok": True, "models_sample": models}
    except Exception as e:
        return {"ok": False, "error": str(e), "type": e.__class__.__name__}


@app.get("/ui", response_class=HTMLResponse)
def ui():
    return """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Graph Assistant UI</title>
  <style>
    body { font-family: Segoe UI, sans-serif; margin: 24px; }
    #answer { white-space: pre-wrap; margin-top: 16px; padding: 12px; background: #f5f5f5; border-radius: 8px; }
    input, button { font-size: 16px; }
    input { width: 70%; padding: 8px; }
    button { padding: 8px 12px; }
  </style>
  <script>
    async function ask() {
      const q = document.getElementById('q').value;
      const res = await fetch('/ask', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({question:q})});
      const data = await res.json();
      document.getElementById('answer').textContent = data.answer || JSON.stringify(data);
    }
  </script>
  </head>
<body>
  <h2>Graph Assistant</h2>
  <p>Örnek: auth.py modülünü kim yazdı?</p>
  <input id=\"q\" placeholder=\"Sorunuzu yazın...\" />
  <button onclick=\"ask()\">Sor</button>
  <div id=\"answer\"></div>
</body>
</html>
"""


