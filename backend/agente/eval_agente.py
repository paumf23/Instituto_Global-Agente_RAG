"""
Evaluación del agente contra el eval set.
"""

import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from .graph import agente
from .state import EstadoAgente

# ---------------------------------------------------------------------------
# Eval set: incluye casos trampa diseñados para poner a prueba el
# threshold de similitud y el guardrail anti-alucinación.
# ---------------------------------------------------------------------------

CASOS_DE_PRUEBA = [
#   {
#       "pregunta": "¿Cuántos días tengo para pedir un reembolso completo desde que empieza el curso?",
#       "tipo_esperado": "consulta_academica",
#       "fuente_esperada": "Politica_de_Reembolsos.pdf",
#       "nota": "Caso simple, sin ambigüedad",
#   },
 #  {
#       "pregunta": "¿Qué nota necesito para aprobar un curso?",
#       "tipo_esperado": "consulta_academica",
#       "fuente_esperada": "FAQ_Cursos_y_Certificados.pdf",
#       "nota": "TRAMPA vs. la siguiente: 70% (aprobar) no es lo mismo que 80% (mantener beca)",
#  },
#   {
#       "pregunta": "¿Qué promedio necesito para no perder mi beca?",
#       "tipo_esperado": "consulta_academica",
#       "fuente_esperada": "Programa_Becas_y_Afiliados.pdf",
#       "nota": "TRAMPA vs. la anterior: 80% (becas), no 70% (aprobación general)",
#   },
  {
        "pregunta": "Si me voy de vacaciones un mes, ¿puedo pausar el tiempo de mi curso y retomarlo a la vuelta?",
        "tipo_esperado": "consulta_academica",
        "fuente_esperada": None,
        "nota": "TEST DE ALUCINACIÓN 2: Concepto de 'pausar' cursos. Chroma traerá info de duración, Cohere debe descartarlo.",
    },
#    {
#        "pregunta": "Si me expulsan por plagio, ¿tengo derecho a reembolso?",
#        "tipo_esperado": "consulta_academica",
#        "fuente_esperada": "Reglamento_del_Estudiante.pdf",
#        "nota": "TRAMPA: la respuesta correcta sale del Reglamento (no), no de la Política de Reembolsos",
#    },
#    {
#        "pregunta": "¿Puedo autocomprarme un curso con mi propio link de afiliado?",
#        "tipo_esperado": "consulta_academica",
#        "fuente_esperada": "Programa_Becas_y_Afiliados.pdf",
#        "nota": "Caso simple, respuesta explícita en el documento",
#    },
#    {
#        "pregunta": "Si pierdo la beca por bajo rendimiento, ¿me reembolsan lo que pagué de más?",
#        "tipo_esperado": "consulta_academica",
#        "fuente_esperada": None,  # ningún documento lo cubre
#        "nota": "TEST DE ALUCINACIÓN: no hay respuesta en los documentos, el agente NO debe inventarla",
#    },
#   {
#       "pregunta": "Hola, ¿cómo estás?",
#       "tipo_esperado": "charla_casual",
#       "fuente_esperada": None,
#       "nota": "No debería tocar ChromaDB en absoluto",
#   },
#   {
#       "pregunta": "¿Cuál es la capital de Francia?",
#       "tipo_esperado": "fuera_de_tema",
#       "fuente_esperada": None,
#       "nota": "No debería tocar ChromaDB en absoluto",
#   },
]


def _estado_inicial(pregunta: str) -> EstadoAgente:
    return {
        "pregunta": pregunta,
        "tipo_pregunta": "consulta_academica",  
        "chunks_candidatos": [],
        "chunks_relevantes": [],
        "tiene_contexto_util": False,
        "respuesta": "",
        "citas": [],
    }


def correr_evaluacion() -> None:
    print(f"Evaluando {len(CASOS_DE_PRUEBA)} casos...\n")
    print("=" * 80)

    for i, caso in enumerate(CASOS_DE_PRUEBA, start=1):
        resultado = agente.invoke(_estado_inicial(caso["pregunta"]))

        print(f"\n[{i}] {caso['pregunta']}")
        print(f"    Nota: {caso['nota']}")
        print(f"    Tipo esperado:   {caso['tipo_esperado']}")
        print(f"    Tipo detectado:  {resultado['tipo_pregunta']}", end="")
        print(" ✅" if resultado["tipo_pregunta"] == caso["tipo_esperado"] else " ❌")

        if resultado["tipo_pregunta"] == "consulta_academica":
            print(f"    Candidatos recuperados (ChromaDB): {len(resultado['chunks_candidatos'])}")
            print(f"    Chunks Relevantes (Cohere Rerank): {len(resultado['chunks_relevantes'])}")
            for c in resultado["chunks_relevantes"]:
                print(f"      [✓] score_cohere={c['score']:.3f}  {c['fuente']}"
                      f"{', ' + c.get('seccion', '') if c.get('seccion') else ', pág. ' + str(c['pagina'])}")


            fuentes_citadas = {c["fuente"] for c in resultado["citas"]}
            if caso["fuente_esperada"] is None:
                estado_ok = len(resultado["citas"]) == 0
                print(f"    Se esperaba SIN citas (alucinación test): "
                      f"{'✅ correcto, no citó nada' if estado_ok else '❌ citó algo cuando no debía'}")
            else:
                estado_ok = caso["fuente_esperada"] in fuentes_citadas
                print(f"    Fuente esperada: {caso['fuente_esperada']} -> "
                      f"{'✅' if estado_ok else '❌ no está entre las citas: ' + str(fuentes_citadas)}")

        print(f"    Respuesta: {resultado['respuesta'][:200]}"
              f"{'...' if len(resultado['respuesta']) > 200 else ''}")
        print("-" * 80)


if __name__ == "__main__":
    correr_evaluacion()