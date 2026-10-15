"""Orquestador jerárquico: supervisor, investigador, analista y síntesis final."""

from requisitos import exigir_python_312

exigir_python_312()

from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field, ValidationError

import modelo
from agents.analyst_agent import nodo_analista
from agents.research_agent import nodo_investigador
from agents.texto import texto_de
from errors import DecisionInvalidaError, SolicitudInvalidaError
from state import AgentState, Solicitud

MAX_PASOS = 6

SUPERVISOR_PROMPT = """Sos el Supervisor de un equipo con dos especialistas:
- investigador: busca datos concretos en las políticas internas de TechCorp.
- analista: hace cálculos matemáticos a partir de datos ya obtenidos.

Rúbrica: no des por terminada la tarea hasta cumplir las cuatro reglas.
Reglas:
1. Si falta un dato de la empresa, mandá a 'investigador'.
2. Si ya se buscó el dato pero falta calcular, mandá a 'analista'.
3. Si ya se buscó Y se calculó lo necesario, respondé 'FINISH'.
4. Nunca repitas el mismo agente dos veces seguidas si ya cumplió su parte.

Contribuciones hasta ahora:
{contribuciones}
"""


class DecisionSupervisor(BaseModel):
    next: Literal["investigador", "analista", "FINISH"] = Field(
        description="Próximo agente a invocar, o FINISH si la tarea ya está completa"
    )
    razon: str = Field(description="Breve justificación de la decisión")


def nodo_supervisor(state: AgentState) -> dict[str, Any]:
    """Router: quién interviene ahora, o FINISH si la tarea ya está completa."""
    if state.get("pasos", 0) >= MAX_PASOS:
        return {"next_agent": "FINISH", "task_completed": True}

    contribuciones_texto = "\n".join(
        f"- {c['agente']}: {c['aporte'][:200]}" for c in state.get("contribuciones", [])
    ) or "(ninguna todavía)"
    pregunta_original = texto_de(state["messages"][0].content)
    prompt_sistema = SUPERVISOR_PROMPT.format(contribuciones=contribuciones_texto)
    llm_supervisor = modelo.obtener_llm().with_structured_output(DecisionSupervisor)
    decision = modelo.invocar(
        lambda: llm_supervisor.invoke(
            [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Tarea original: {pregunta_original}"},
            ]
        )
    )
    if not isinstance(decision, DecisionSupervisor):
        raise DecisionInvalidaError(
            f"Decisión inválida del supervisor: {decision!r}. No se adivina una ruta: revisá el modelo configurado en LLM_PROVIDER."
        )
    decision = aplicar_guardas(state, decision, pregunta_original)
    return {"next_agent": decision.next, "task_completed": decision.next == "FINISH"}


def _cumplio(state: AgentState, agente: str) -> bool:
    """True si ese agente ya dejó un aporte usable. Un error o un 'no encontrado' no cuenta."""
    return any(
        c["agente"] == agente and not c["aporte"].startswith(("ERROR", "No se encontró"))
        for c in state.get("contribuciones", [])
    )


def aplicar_guardas(state: AgentState, decision: DecisionSupervisor, pregunta: str) -> DecisionSupervisor:
    """FINISH solo después de buscar y, si la pregunta pide una cuenta, de calcular.

    Tampoco se repite un agente que ya cumplió su parte: es la regla 4 del prompt,
    hecha cumplir en el código.
    """
    hechos = {c["agente"] for c in state.get("contribuciones", [])}
    if decision.next == "investigador" and _cumplio(state, "investigador"):
        if "analista" not in hechos and _pide_calculo(pregunta):
            return DecisionSupervisor(next="analista", razon="[guarda] el investigador ya cumplió su parte: sigue el analista.")
        return DecisionSupervisor(next="FINISH", razon="[guarda] el investigador ya cumplió su parte.")
    if decision.next == "analista" and _cumplio(state, "analista"):
        return DecisionSupervisor(next="FINISH", razon="[guarda] el analista ya cumplió su parte.")
    if decision.next != "FINISH":
        return decision
    if "investigador" not in hechos:
        return DecisionSupervisor(next="investigador", razon="[guarda] FINISH sin datos de las políticas: primero el investigador.")
    if "analista" not in hechos and _pide_calculo(pregunta):
        return DecisionSupervisor(next="analista", razon="[guarda] FINISH sin el cálculo: primero el analista.")
    return decision


def _pide_calculo(pregunta: str) -> bool:
    texto = pregunta.lower()
    return any(palabra in texto for palabra in ("cuánto", "cuanto", "cuántos", "cuantos", "total", "acumul", "calcul"))


def enrutar(state: AgentState) -> Literal["investigador", "analista", "sintesis"]:
    if state["next_agent"] == "FINISH":
        return "sintesis"
    destino = state["next_agent"]
    if destino not in ("investigador", "analista"):
        raise DecisionInvalidaError(
            f"Decisión inválida del supervisor: {destino!r}. Tiene que ser investigador, analista o FINISH."
        )
    return destino  # type: ignore[return-value]


def nodo_sintesis(state: AgentState) -> dict[str, Any]:
    """Redacta la respuesta final con la pregunta y las contribuciones. No busca ni calcula."""
    contribuciones_texto = "\n".join(f"- [{c['agente']}] {c['aporte']}" for c in state.get("contribuciones", []))
    pregunta_original = texto_de(state["messages"][0].content)
    prompt = (
        f"Pregunta original: {pregunta_original}\n\nAportes del equipo:\n{contribuciones_texto}\n\n"
        "Redactá una respuesta final clara y breve combinando estos aportes."
    )
    llm = modelo.obtener_llm()
    respuesta_final = modelo.invocar(lambda: llm.invoke(prompt))
    return {"messages": [AIMessage(content=texto_de(respuesta_final.content), name="supervisor")]}


grafo = StateGraph(AgentState)
grafo.add_node("supervisor", nodo_supervisor)
grafo.add_node("investigador", nodo_investigador)
grafo.add_node("analista", nodo_analista)
grafo.add_node("sintesis", nodo_sintesis)

grafo.add_edge(START, "supervisor")
grafo.add_conditional_edges(
    "supervisor",
    enrutar,
    {
        "investigador": "investigador",
        "analista": "analista",
        "sintesis": "sintesis",
    },
)
grafo.add_edge("investigador", "supervisor")
grafo.add_edge("analista", "supervisor")
grafo.add_edge("sintesis", END)

type Orquestador = CompiledStateGraph[AgentState, None, AgentState, AgentState]
app: Orquestador = grafo.compile()


def validar_pregunta(texto: str) -> str:
    """Pydantic antes del grafo: una pregunta vacía no gasta llamadas."""
    try:
        return Solicitud(texto=texto).texto
    except ValidationError as exc:
        campos = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise SolicitudInvalidaError(f"Solicitud inválida: {campos}") from exc


def estado_inicial(pregunta: str) -> AgentState:
    return {
        "messages": [HumanMessage(content=validar_pregunta(pregunta))],
        "next_agent": None,
        "contribuciones": [],
        "pasos": 0,
        "task_completed": False,
    }
