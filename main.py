"""Demo: una pregunta que necesita el dato de la política y un cálculo."""

from requisitos import exigir_python_312

exigir_python_312()

import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

from errors import OrquestadorError  # noqa: E402
from graph import app, estado_inicial  # noqa: E402
from rag import rag_system  # noqa: E402

pregunta = (
    "Un empleado va a cumplir 12 años en TechCorp. Tuvo 14 días de vacaciones los primeros "
    "5 años, 21 los siguientes 5, y ahora tiene derecho a 28. ¿Cuántos días de vacaciones "
    "acumuló en total en esos 12 años?"
)


def main(texto: str = pregunta) -> None:
    """Muestra la delegación nodo por nodo y, al final, la respuesta."""
    print(f"RAG: {rag_system.origen}\n")
    estado = estado_inicial(texto)
    print("Flujo de delegación:\n")
    for evento in app.stream(estado, stream_mode="updates"):
        for nodo, actualizacion in evento.items():
            print(f"Nodo: {nodo}")
            if "next_agent" in actualizacion:
                print(f"   next_agent: {actualizacion['next_agent']}")
            if "messages" in actualizacion:
                for mensaje in actualizacion["messages"]:
                    print(f"   [{getattr(mensaje, 'name', 'sistema')}] {mensaje.content[:250]}")
            print()
    resultado_final = app.invoke(estado_inicial(texto))
    print("RESPUESTA FINAL:\n")
    print(resultado_final["messages"][-1].content)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else pregunta)
    except OrquestadorError as exc:
        print(f"Error controlado: {exc}")
        raise SystemExit(1)
