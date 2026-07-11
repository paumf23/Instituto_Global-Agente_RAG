"""
Script de prueba para el endpoint POST /chat.
"""

import httpx
import json
import sys

URL = "http://localhost:8000/chat"

PREGUNTAS_TEST = [
    "¿Cuántos días tengo para pedir un reembolso?",
    "Hola, ¿cómo estás?",
    "¿Cuál es la capital de Francia?",
]


def test_pregunta(pregunta: str):
    print(f"\n{'='*60}")
    print(f"📝 Pregunta: {pregunta}")
    print(f"{'='*60}\n")

    with httpx.Client(timeout=120.0) as client:
        with client.stream("POST", URL, json={"pregunta": pregunta}) as response:
            if response.status_code != 200:
                print(f"❌ Error HTTP {response.status_code}")
                for line in response.iter_lines():
                    print(line)
                return

            for linea in response.iter_lines():
                linea = linea.strip()
                if not linea:
                    continue

                # Parsear líneas SSE: "event: token", "data: {...}"
                if linea.startswith("event:"):
                    # Guarda el tipo de evento para la próxima línea de data
                    test_pregunta._evento_actual = linea[len("event:"):].strip()

                elif linea.startswith("data:"):
                    raw_data = linea[len("data:"):].strip()
                    evento = getattr(test_pregunta, "_evento_actual", "")

                    # 1. Manejo de mensajes de estado (los mensajes amigables)
                    if evento == "status":
                        try:
                            payload = json.loads(raw_data)
                            print(f"⚙️ {payload['message']}")
                        except json.JSONDecodeError:
                            print(f"⚙️ {raw_data}")

                    # 2. Manejo de los tokens de la respuesta
                    elif evento == "token":
                        try:
                            payload = json.loads(raw_data)
                            print(payload["token"], end="", flush=True)
                        except json.JSONDecodeError:
                            print(raw_data, end="", flush=True)

                    # 3. Manejo de metadatos (tipo de pregunta y citas)
                    elif evento == "metadata":
                        try:
                            payload = json.loads(raw_data)
                            print(f"\n\n📊 Tipo: {payload.get('tipo_pregunta', '?')}")
                            if payload.get("citas"):
                                print("📚 Citas:")
                                for cita in payload["citas"]:
                                    texto = f"  - {cita['fuente']}, pág. {cita['pagina']}"
                                    if "seccion" in cita:
                                        texto += f" ({cita['seccion']})"
                                    print(texto)
                        except json.JSONDecodeError:
                            print(f"\n📊 Metadata (raw): {raw_data}")

                    # 4. Finalización del stream
                    elif evento == "done":
                        print("\n✅ Stream finalizado.")

    print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_pregunta(" ".join(sys.argv[1:]))
    else:
        print("🧪 Testeando 3 tipos de pregunta...\n")
        for pregunta in PREGUNTAS_TEST:
            test_pregunta(pregunta)