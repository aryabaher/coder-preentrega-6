"""MAX_PASOS corta al supervisor que insiste, sin llamar a la API."""

from requisitos import exigir_python_312

exigir_python_312()

import modelo
from graph import MAX_PASOS, DecisionSupervisor, app, estado_inicial
from main import pregunta
from tests.conftest import EspecialistaFalso, LLMFalso

llm = LLMFalso()
investigador = EspecialistaFalso("No se encontró información relevante en las políticas.")
modelo.obtener_llm = lambda: llm  # type: ignore[assignment]
modelo.ESPERA_INICIAL_S = 0

import agents.analyst_agent as analista  # noqa: E402
import agents.research_agent as investigacion  # noqa: E402

investigacion.agente_investigador = investigador
analista.agente_analista = EspecialistaFalso("Resultado: 0")


def siempre_investigador(mensajes: list[dict[str, str]], *args: object, **kwargs: object) -> DecisionSupervisor:
    llm.supervisor.llamadas += 1
    return DecisionSupervisor(next="investigador", razon="otra vez")


llm.supervisor.invoke = siempre_investigador  # type: ignore[method-assign]
llm.supervisor.llamadas = 0

salida = app.invoke(estado_inicial(pregunta))
print(f"MAX_PASOS = {MAX_PASOS}")
print(f"veces que el supervisor pidió al investigador: {llm.supervisor.llamadas}")
print(f"veces que el investigador corrió: {len(investigador.entradas)}")
print(f"pasos en el estado: {salida['pasos']}")
print(f"task_completed: {salida['task_completed']}")
print(f"cierre: {salida['messages'][-1].name}")
