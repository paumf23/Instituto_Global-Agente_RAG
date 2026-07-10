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

from dotenv import load_dotenv

# Cargar .env ANTES de importar módulos que leen variables de entorno
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agente.graph import agente
from ingesta.procesar_pdfs import inicializar_vectorstore


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
    """Recibe una pregunta y responde con streaming SSE token a token."""

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

            # Streamear tokens SOLO del nodo Generador (no del Clasificador)
            if kind == "on_chat_model_stream":
                nodo = evento.get("metadata", {}).get("langgraph_node", "")
                if nodo == "generador":
                    token = evento["data"]["chunk"].content
                    if token:
                        yield {
                            "event": "token",
                            "data": json.dumps({"token": token}),
                        }

            # Capturar tipo_pregunta y citas a medida que los nodos terminan
            elif kind == "on_chain_end":
                output = evento["data"].get("output", {})
                if isinstance(output, dict):
                    if "tipo_pregunta" in output:
                        tipo_pregunta = output["tipo_pregunta"]
                    if "citas" in output:
                        citas = output["citas"]

        # Enviar metadata al final (tipo de pregunta + citas de fuentes)
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
    """Endpoint de verificación: confirma que el servidor está corriendo."""
    return {"status": "ok"}
