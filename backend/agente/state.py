"""
Estado compartido del agente 
(la "memoria" que fluye entre los nodos de LangGraph).
"""

from typing import Any, Dict, List, Literal, NotRequired, TypedDict

# ---------------------------------------------------------------------------
# Tipos auxiliares
# ---------------------------------------------------------------------------

TipoPregunta = Literal["charla_casual", "consulta_academica", "fuera_de_tema"]


class Chunk(TypedDict):
    texto: str
    fuente: str          
    pagina: int          
    seccion: NotRequired[str] 
    score: float           # similitud coseno (Recuperador) O relevance_score de
                             # Cohere rerank (Evaluador), si el reranking está activo
                             # -- se sobreescribe en nodo_evaluador


class Cita(TypedDict):
    fuente: str
    pagina: int
    seccion: NotRequired[str]


# ---------------------------------------------------------------------------
# Estado principal del grafo
# ---------------------------------------------------------------------------

class EstadoAgente(TypedDict):
    # 1. Lo que ingresa el usuario
    pregunta: str

    # 2. La decisión del Clasificador (Nodo 1)
    tipo_pregunta: TipoPregunta

    # 3. Lo que encuentra ChromaDB (Nodo 2)
    chunks_candidatos: List[Chunk]

    # 4. Lo que aprueba el Evaluador Matemático (Nodo 3)
    # Solo los chunks que superaron el umbral de similitud (ej: > 0.75)
    chunks_relevantes: List[Chunk]

    # 5. Bandera para saber si quedó algo útil después de evaluar
    tiene_contexto_util: bool

    # 6. Lo que escribe Gemini al final (Nodo 4)
    respuesta: str

    # 7. Metadata para el frontend (fuentes clickeables + highlight de sidebar)
    citas: List[Dict[str, Any]]