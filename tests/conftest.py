from requisitos import exigir_python_312

exigir_python_312()

import os

# Los tests usan el RAG en memoria. La clave real no tiene que disparar Pinecone al importar.
os.environ.pop("PINECONE_API_KEY", None)

import pytest
from typing import Any

from langchain_core.messages import AIMessage

import modelo
from agents import analyst_agent, research_agent
from graph import DecisionSupervisor


class SupervisorGuion:
    """Sin contribuciones manda al investigador; con el dato, al analista; con los dos, FINISH."""

    def __init__(self) -> None:
        self.llamadas = 0

    def invoke(self, mensajes: list[dict[str, str]], *args: object, **kwargs: object) -> DecisionSupervisor:
        self.llamadas += 1
        sistema = mensajes[0]["content"]
        if "- investigador:" not in sistema:
            return DecisionSupervisor(next="investigador", razon="falta un dato de la empresa")
        if "- analista:" not in sistema:
            return DecisionSupervisor(next="analista", razon="falta calcular")
        return DecisionSupervisor(next="FINISH", razon="ya se buscó y se calculó")


class LLMFalso:
    def __init__(self) -> None:
        self.supervisor = SupervisorGuion()
        self.prompts: list[object] = []

    def invoke(self, prompt: object, *args: object, **kwargs: object) -> AIMessage:
        self.prompts.append(prompt)
        return AIMessage(content="En 12 años acumuló 231 días de vacaciones.")

    def with_structured_output(self, schema: object, **kwargs: object) -> SupervisorGuion:
        return self.supervisor


class EspecialistaFalso:
    def __init__(self, texto: str) -> None:
        self.texto = texto
        self.entradas: list[dict[str, Any]] = []

    def invoke(self, entrada: dict[str, Any], *args: object, **kwargs: object) -> dict[str, Any]:
        self.entradas.append(entrada)
        return {"messages": [AIMessage(content=self.texto)]}


@pytest.fixture(autouse=True)
def dobles(monkeypatch: pytest.MonkeyPatch) -> tuple[LLMFalso, EspecialistaFalso, EspecialistaFalso]:
    """El grafo no llama al LLM real. El backoff no espera."""
    llm = LLMFalso()
    investigador = EspecialistaFalso("14 días, 21 días y 28 días. [Fuente: politica_vacaciones.txt]")
    analista = EspecialistaFalso("Resultado: 231")
    monkeypatch.setattr(modelo, "obtener_llm", lambda: llm)
    monkeypatch.setattr(modelo, "ESPERA_INICIAL_S", 0)
    monkeypatch.setattr(research_agent, "agente_investigador", investigador)
    monkeypatch.setattr(analyst_agent, "agente_analista", analista)
    return llm, investigador, analista
