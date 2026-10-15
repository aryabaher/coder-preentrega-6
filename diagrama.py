"""Genera el diagrama del grafo: grafo.mmd (Mermaid) y grafo.png (draw_mermaid_png)."""

from requisitos import exigir_python_312

exigir_python_312()

from pathlib import Path

from graph import app as graph

RAIZ = Path(__file__).resolve().parent


def generar(raiz: Path = RAIZ, png: bool = True) -> str:
    """Escribe grafo.mmd y, si `png`, grafo.png. Devuelve el Mermaid."""
    dibujo = graph.get_graph()
    mermaid = dibujo.draw_mermaid()
    (raiz / "grafo.mmd").write_text(mermaid, encoding="utf-8")
    if png:
        # draw_mermaid_png renderiza con la API de mermaid.ink: necesita red.
        (raiz / "grafo.png").write_bytes(dibujo.draw_mermaid_png())
    return mermaid


if __name__ == "__main__":
    print(generar())
    print("Escrito grafo.mmd y grafo.png")
