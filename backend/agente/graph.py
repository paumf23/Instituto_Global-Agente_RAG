"""
Ensamblado del grafo del agente.

Conecta los 4 nodos (Clasificador -> Recuperador -> Evaluador ->
Generador) con la bifurcación: si la pregunta es
charla casual o está fuera de tema, el Clasificador salta directo al
Generador sin pasar por Recuperador ni Evaluador -- no tiene sentido
buscar en ChromaDB si el usuario solo dijo "Hola".
"""

from langgraph.graph import END, StateGraph

from .nodes import nodo_clasificador, nodo_evaluador, nodo_generador, nodo_recuperador
from .state import EstadoAgente


def _decidir_tras_clasificar(estado: EstadoAgente) -> str:
    """Determina el siguiente nodo según lo que decidió el Clasificador."""
    if estado["tipo_pregunta"] == "consulta_academica":
        return "recuperador"
    return "generador"  # charla_casual o fuera_de_tema -> atajo directo


def construir_grafo() -> StateGraph:
    grafo = StateGraph(EstadoAgente)

    grafo.add_node("clasificador", nodo_clasificador)
    grafo.add_node("recuperador", nodo_recuperador)
    grafo.add_node("evaluador", nodo_evaluador)
    grafo.add_node("generador", nodo_generador)

    grafo.set_entry_point("clasificador")

    # Única bifurcación real del grafo: decide si el "EstadoAgente" pasa por los
    # nodos 2 y 3 o si va directo al nodo 4.
    grafo.add_conditional_edges(
        "clasificador",
        _decidir_tras_clasificar,
        {
            "recuperador": "recuperador",
            "generador": "generador",
        },
    )

    # Nodo 2 -> 3 -> 4 siempre en línea recta (elimina el loop: si el 
    # Evaluador no encuentra nada útil, no vuelve a buscar, sigue directo 
    # al Generador para que redacte el "no sé").
    grafo.add_edge("recuperador", "evaluador")
    grafo.add_edge("evaluador", "generador")

    grafo.add_edge("generador", END)

    return grafo


# Grafo compilado, listo para usar desde FastAPI (main.py) con
# agente.invoke(estado_inicial) o agente.astream(estado_inicial) para
# el modo streaming.
agente = construir_grafo().compile()


if __name__ == "__main__":
    from dotenv import load_dotenv
    import os
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    estado_inicial: EstadoAgente = {
        "pregunta": "¿Cuántos días tengo para pedir un reembolso?",
        "tipo_pregunta": "consulta_academica",
        "chunks_candidatos": [],
        "chunks_relevantes": [],
        "tiene_contexto_util": False,
        "respuesta": "",
        "citas": [],
    }

    resultado = agente.invoke(estado_inicial)
    print("Tipo detectado:", resultado["tipo_pregunta"])
    print("Respuesta:", resultado["respuesta"])
    print("Citas:", resultado["citas"])