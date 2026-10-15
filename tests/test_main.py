import os
import subprocess
import sys
from pathlib import Path

import pytest

import main

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = (RAIZ / "main.py").read_text(encoding="utf-8")


def test_main_muestra_la_delegacion(capsys: pytest.CaptureFixture[str]) -> None:
    main.main()
    salida = capsys.readouterr().out
    assert "Nodo: investigador" in salida
    assert "Nodo: analista" in salida
    assert "Nodo: sintesis" in salida
    assert "RESPUESTA FINAL:" in salida
    assert "231 días" in salida


def test_main_con_pregunta_vacia_sale_con_error() -> None:
    entorno = {
        **os.environ,
        "GOOGLE_API_KEY": "",
        "OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "PINECONE_API_KEY": "",
        "LLM_PROVIDER": "google",
        "PYTHONIOENCODING": "utf-8",
    }
    proceso = subprocess.run([sys.executable, "main.py", "   "], cwd=RAIZ, env=entorno, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert proceso.returncode == 1
    assert "Error controlado: Solicitud inválida: texto: String should have at least 1 character" in proceso.stdout


def test_main_no_arma_el_grafo_ni_pone_clave() -> None:
    for prohibido in ("StateGraph", "create_agent", "sk-", "api_key"):
        assert prohibido not in FUENTE
    assert 'stream_mode="updates"' in FUENTE
    assert "app.invoke(estado_inicial(texto))" in FUENTE
    assert "acumuló en total" in FUENTE
