from typing import Any

import pytest
from pydantic import ValidationError

from agents.analyst_agent import _evaluar_nodo, calculadora
from errors import IndiceIncompatibleError
from agents.research_agent import buscar_en_politicas_internas
from rag import construir_rag_local


def test_la_busqueda_encuentra_los_tramos_de_vacaciones() -> None:
    texto = buscar_en_politicas_internas.invoke({"pregunta": "días de vacaciones según antigüedad"})
    assert "[Fuente: politica_vacaciones.txt]" in texto
    assert "14 días" in texto and "21 días" in texto and "28 días" in texto


def test_pregunta_vacia_y_sin_resultados(monkeypatch: pytest.MonkeyPatch) -> None:
    vacia = buscar_en_politicas_internas.invoke({"pregunta": "   "})
    assert vacia.startswith("No se encontró información relevante en las políticas.")
    assert "días de vacaciones" in vacia

    from agents import research_agent

    class Vacio:
        def obtener_top_k(self, query: str) -> list[dict[str, str]]:
            return []

    monkeypatch.setattr(research_agent, "rag_system", Vacio())
    assert buscar_en_politicas_internas.invoke({"pregunta": "zzzz"}) == "No se encontró información relevante en las políticas."


def test_sin_clave_el_origen_dice_local() -> None:
    from rag import rag_system

    assert rag_system.origen.startswith("local")
    assert "Pinecone" not in rag_system.origen


def test_index_name_sale_del_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    from rag import nombre_indice

    monkeypatch.setenv("INDEX_NAME", "techcorp-rag-hibrido")
    assert nombre_indice() == "techcorp-rag-hibrido"
    monkeypatch.setenv("INDEX_NAME", "otro-indice")
    assert nombre_indice() == "otro-indice"


def test_indice_de_otro_ancho_no_se_reingesta() -> None:
    from rag import verificar_indice

    with pytest.raises(IndiceIncompatibleError, match=r"^Mismatch de dimensiones: el índice .+ es 384D y text-embedding-3-small usa 1536D"):
        verificar_indice({"dimension": 384, "metric": "cosine"})


def test_indice_con_otra_metrica_no_se_acepta() -> None:
    from rag import verificar_indice

    with pytest.raises(IndiceIncompatibleError, match=r"^Mismatch de métrica:"):
        verificar_indice({"dimension": 1536, "metric": "euclidean"})


def test_namespace_con_vectores_no_cuenta_como_vacio() -> None:
    from rag import NAMESPACE, vectores_en_namespace

    assert vectores_en_namespace({"namespaces": {NAMESPACE: {"vector_count": 12}}}) == 12
    assert vectores_en_namespace({"namespaces": {}}) == 0


def test_k_llega_a_los_dos_retrievers() -> None:
    sistema = construir_rag_local(k=2)
    bm25: Any = sistema.retriever.retrievers[0]
    vectorial: Any = sistema.retriever.retrievers[1]
    assert sistema.k == 2
    assert bm25.k == 2
    assert vectorial.search_kwargs["k"] == 2


def test_calculadora_resuelve_los_12_anos() -> None:
    assert calculadora.invoke({"expresion": "5*14 + 5*21 + 2*28"}) == "Resultado: 231"


@pytest.mark.parametrize(
    ("expresion", "mensaje"),
    [
        ("", "Error al calcular '': la expresión está vacía."),
        ("25.000 * 12", "separador de miles"),
        ("1/0", "división por cero"),
        ("__import__('os')", "Expresión no permitida"),
        ("2 ** 1000", "exponente fuera de rango"),
    ],
)
def test_calculadora_rechaza_y_dice_como_seguir(expresion: str, mensaje: str) -> None:
    salida = calculadora.invoke({"expresion": expresion})
    assert salida.startswith("Error al calcular")
    assert mensaje in salida
    assert "calculadora" in salida or "Pasá solo números" in salida


def test_evaluar_no_acepta_nombres() -> None:
    import ast

    with pytest.raises(ValueError, match="Expresión no permitida"):
        _evaluar_nodo(ast.parse("x * 2", mode="eval").body)


def test_la_herramienta_exige_el_argumento() -> None:
    with pytest.raises(ValidationError):
        calculadora.invoke({})
