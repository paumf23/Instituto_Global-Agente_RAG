"""
Nodos del agente: Clasificador, Recuperador, Evaluador y Generador
"""

import os

import cohere
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from .state import Chunk, EstadoAgente, TipoPregunta

# ---------------------------------------------------------------------------
# Configuración compartida
# ---------------------------------------------------------------------------

MODELO_GENERACION = "gemini-2.5-flash"
MODELO_EMBEDDING = "models/gemini-embedding-001"
MODELO_RERANK = "rerank-multilingual-v3.0"

TOP_K_CANDIDATOS = 8   # chunks candidatos que trae el Recuperador (ChromaDB) 
TOP_N_RERANK = 3        # chunks que se quedan después del Evaluador (Cohere)
UMBRAL_COHERE = 0.25     # corte de seguridad sobre relevance_score de Cohere 

llm = ChatGoogleGenerativeAI(
    model=MODELO_GENERACION,
    google_api_key=os.environ["GOOGLE_API_KEY"],
)

embeddings = GoogleGenerativeAIEmbeddings(
    model=MODELO_EMBEDDING,
    google_api_key=os.environ["GOOGLE_API_KEY"],
)

CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "ingesta", "chroma_db")

vectorstore = Chroma(
    collection_name="instituto_global",
    embedding_function=embeddings,
    persist_directory=CHROMA_PERSIST_DIR,
    collection_metadata={"hnsw:space": "cosine"},
)

cohere_client = cohere.Client(api_key=os.environ["COHERE_API_KEY"])


# ---------------------------------------------------------------------------
# Nodo 1: Clasificador (Gemini)
# ---------------------------------------------------------------------------

PROMPT_CLASIFICADOR = """Clasificá la siguiente pregunta de un estudiante en \
UNA sola categoría. Respondé únicamente con la categoría, sin explicación.

Categorías posibles:
- charla_casual: saludos, agradecimientos, despedidas, chistes
- consulta_academica: preguntas sobre reglamento, becas, reembolsos, \
cursos o certificados del Instituto Global de Educación Online
- fuera_de_tema: cualquier otra cosa que no tenga que ver con el instituto

Pregunta: {pregunta}

Categoría:"""


def nodo_clasificador(estado: EstadoAgente) -> dict:
    mensaje = HumanMessage(content=PROMPT_CLASIFICADOR.format(pregunta=estado["pregunta"]))
    respuesta = llm.invoke([mensaje])
    tipo = respuesta.content.strip().lower()

    valores_validos: set[TipoPregunta] = {
        "charla_casual", "consulta_academica", "fuera_de_tema"
    }
    if tipo not in valores_validos:
        tipo = "fuera_de_tema"

    return {"tipo_pregunta": tipo}


# ---------------------------------------------------------------------------
# Nodo 2: Recuperador (ChromaDB + 1 llamada chica de embedding)
# ---------------------------------------------------------------------------

def nodo_recuperador(estado: EstadoAgente) -> dict:
    resultados = vectorstore.similarity_search_with_score(
        estado["pregunta"], k=TOP_K_CANDIDATOS
    )

    chunks: list[Chunk] = []
    for documento_langchain, distancia in resultados:
        score = 1 - distancia
        metadata = documento_langchain.metadata
        chunk: Chunk = {
            "texto": documento_langchain.page_content,
            "fuente": metadata["fuente"],
            "pagina": metadata["pagina"],
            "score": score,
        }
        if "seccion" in metadata:
            chunk["seccion"] = metadata["seccion"]
        chunks.append(chunk)

    return {"chunks_candidatos": chunks}


# ---------------------------------------------------------------------------
# Nodo 3: Evaluador (Cohere Rerank -- Cross-Encoder Multilingüe)
# ---------------------------------------------------------------------------

def nodo_evaluador(estado: EstadoAgente) -> dict:
    candidatos = estado["chunks_candidatos"]

    if not candidatos:
        return {"chunks_relevantes": [], "tiene_contexto_util": False}

    textos_candidatos = [chunk["texto"] for chunk in candidatos]

    try:
        respuesta_rerank = cohere_client.rerank(
            model=MODELO_RERANK,
            query=estado["pregunta"],
            documents=textos_candidatos,
            top_n=TOP_N_RERANK,
            return_documents=False,
        )
    except Exception as error:
        # Si Cohere falla se degrada usando los candidatos del Recuperador
        # sin reordenar, para no afectar el resultado final.
        print(f"[Evaluador] Cohere rerank falló ({error}); usando fallback sin reranking.")
        chunks_relevantes = candidatos[:TOP_N_RERANK]
        return {
            "chunks_relevantes": chunks_relevantes,
            "tiene_contexto_util": len(chunks_relevantes) > 0,
        }

    chunks_relevantes: list[Chunk] = []
    for resultado in respuesta_rerank.results:
        if resultado.relevance_score >= UMBRAL_COHERE:
            chunk_original = dict(candidatos[resultado.index])
            chunk_original["score"] = resultado.relevance_score  # sobreescribe: coseno -> Cohere
            chunks_relevantes.append(chunk_original)

    return {
        "chunks_relevantes": chunks_relevantes,
        "tiene_contexto_util": len(chunks_relevantes) > 0,
    }


# ---------------------------------------------------------------------------
# Nodo 4: Generador (Gemini, con streaming)
# ---------------------------------------------------------------------------

PROMPT_GENERADOR_CON_CONTEXTO = """Sos el asistente virtual del Instituto \
Global de Educación Online. Respondé la pregunta del estudiante en tono \
claro y empático, usando ÚNICAMENTE la información del contexto de abajo. \
Si citás una regla puntual, indicá de qué documento sale.

Contexto:
{contexto}

Pregunta: {pregunta}

Respuesta:"""

PROMPT_GENERADOR_SIN_CONTEXTO = """Sos el asistente virtual del Instituto \
Global de Educación Online. No encontraste información en los documentos \
oficiales que responda esta pregunta. Redactá una disculpa breve y amable, \
sugiriendo que contacte a soporte para más detalles.

Pregunta: {pregunta}

Respuesta:"""

PROMPT_GENERADOR_CHARLA_CASUAL = """Sos el asistente virtual del Instituto \
Global de Educación Online. El estudiante te escribió lo siguiente, que es \
charla casual (no una consulta académica). Respondé de forma breve, cálida \
y natural.

Mensaje: {pregunta}

Respuesta:"""

PROMPT_GENERADOR_FUERA_DE_TEMA = """Sos el asistente virtual del Instituto \
Global de Educación Online. El estudiante preguntó algo que no tiene que \
ver con el instituto. Explicale amablemente que solo podés ayudar con \
temas del instituto (reglamento, becas, reembolsos, cursos).

Pregunta: {pregunta}

Respuesta:"""


def _armar_contexto(chunks: list[Chunk]) -> str:
    partes = []
    for c in chunks:
        if "seccion" in c:
            referencia = f"{c['fuente']}, {c['seccion']}"
        else:
            referencia = f"{c['fuente']}, página {c['pagina']}"
        partes.append(f"[Fuente: {referencia}]\n{c['texto']}")
    return "\n\n".join(partes)


def nodo_generador(estado: EstadoAgente) -> dict:
    tipo = estado["tipo_pregunta"]

    if tipo == "charla_casual":
        prompt = PROMPT_GENERADOR_CHARLA_CASUAL.format(pregunta=estado["pregunta"])
        citas = []
    elif tipo == "fuera_de_tema":
        prompt = PROMPT_GENERADOR_FUERA_DE_TEMA.format(pregunta=estado["pregunta"])
        citas = []
    elif estado["tiene_contexto_util"]:
        contexto = _armar_contexto(estado["chunks_relevantes"])
        prompt = PROMPT_GENERADOR_CON_CONTEXTO.format(
            contexto=contexto, pregunta=estado["pregunta"]
        )
        citas = []
        for c in estado["chunks_relevantes"]:
            cita: dict = {"fuente": c["fuente"], "pagina": c["pagina"]}
            if "seccion" in c:
                cita["seccion"] = c["seccion"]
            citas.append(cita)
    else:
        prompt = PROMPT_GENERADOR_SIN_CONTEXTO.format(pregunta=estado["pregunta"])
        citas = []

    mensaje = HumanMessage(content=prompt)
    respuesta = llm.invoke([mensaje])

    return {"respuesta": respuesta.content, "citas": citas}