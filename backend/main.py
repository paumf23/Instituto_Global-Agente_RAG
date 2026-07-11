"""
Punto de entrada del backend — FastAPI con streaming SSE.

Responsabilidades:
  - Levantar la app FastAPI con CORS.
  - Ejecutar la ingesta de documentos al arrancar (si ChromaDB está vacía).
  - Exponer POST /chat que invoca el grafo LangGraph y envía la respuesta
    token a token como Server-Sent Events (SSE).
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agente.graph import agente
from ingesta.procesar_pdfs import inicializar_vectorstore


STATUS_MESSAGES = {
    "clasificador": "Identificando tipo de pregunta...",
    "recuperador": "Buscando en la base de información...",
    "evaluador": "Definiendo información relevante...",
    "generador": "Elaborando respuesta..."
}

# ---------------------------------------------------------------------------
# Lifespan (arranque / cierre del servidor)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ejecuta la ingesta de documentos al arrancar el servidor."""
    print("🚀 Arrancando servidor...")
    await asyncio.to_thread(inicializar_vectorstore)
    print("✅ Servidor listo.")
    yield
    print("👋 Servidor apagándose.")


# ---------------------------------------------------------------------------
# App FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Agente RAG — Instituto Global",
    description="API del agente conversacional del Instituto Global de Educación Online.",
    lifespan=lifespan,
)

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Esquema de entrada
# ---------------------------------------------------------------------------

class PreguntaRequest(BaseModel):
    pregunta: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/chat")
async def chat(req: PreguntaRequest):

    estado_inicial = {
        "pregunta": req.pregunta,
        "tipo_pregunta": "consulta_academica",
        "chunks_candidatos": [],
        "chunks_relevantes": [],
        "tiene_contexto_util": False,
        "respuesta": "",
        "citas": [],
    }

    async def generar_eventos():
        tipo_pregunta = ""
        citas = []

        async for evento in agente.astream_events(estado_inicial, version="v2"):
            kind = evento["event"]

            # 1. ENVIAR MENSAJES DE STATUS (cuando un nodo comienza)
            if kind == "on_chain_start":
                node_name = evento.get("name")
                if node_name in STATUS_MESSAGES:
                    yield {
                        "event": "status",
                        "data": json.dumps({"message": STATUS_MESSAGES[node_name]}),
                    }

            # 2. STREAMING DE TOKENS (del nodo Generador)
            elif kind == "on_chat_model_stream":
                nodo = evento.get("metadata", {}).get("langgraph_node", "")
                if nodo == "generador":
                    token = evento["data"]["chunk"].content
                    if token:
                        yield {
                            "event": "token",
                            "data": json.dumps({"token": token}),
                        }

            # 3. CAPTURAR RESULTADOS FINALES (tipo_pregunta y citas)
            elif kind == "on_chain_end":
                output = evento["data"].get("output", {})
                if isinstance(output, dict):
                    if "tipo_pregunta" in output:
                        tipo_pregunta = output["tipo_pregunta"]
                    if "citas" in output:
                        citas = output["citas"]

        # 4. ENVIAR METADATA Y CERRAR STREAM
        yield {
            "event": "metadata",
            "data": json.dumps({
                "tipo_pregunta": tipo_pregunta,
                "citas": citas,
            }),
        }
        yield {"event": "done", "data": ""}

    return EventSourceResponse(generar_eventos())


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Endpoints de documentos
# ---------------------------------------------------------------------------

DOCS_DIR = Path(__file__).resolve().parent.parent / "documentos"


@app.get("/documentos")
async def listar_documentos():
    """Devuelve la lista de PDFs disponibles en la carpeta /documentos."""
    if not DOCS_DIR.exists():
        return {"documentos": []}
    pdfs = sorted(f.name for f in DOCS_DIR.iterdir() if f.suffix.lower() == ".pdf")
    return {"documentos": pdfs}


@app.get("/documentos/{nombre}")
async def servir_documento(nombre: str):
    """Sirve un PDF específico para visualización en el frontend."""
    ruta = DOCS_DIR / nombre
    if not ruta.exists() or not ruta.suffix.lower() == ".pdf":
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return FileResponse(
        path=str(ruta),
        media_type="application/pdf",
        filename=nombre,
    )