from langchain_core.messages import AIMessage, HumanMessage

import main
from agents.analyst_agent import nodo_analista
from agents.research_agent import nodo_investigador
from graph import (
    MAX_PASOS,
    DecisionSupervisor,
    app,
    enrutar,
    estado_inicial,
    grafo,
)
from tests.conftest import EspecialistaFalso, LLMFalso

PREGUNTA = main.pregunta


def test_topologia() -> None:
    dibujo = app.get_graph()
    assert set(dibujo.nodes) == {"__start__", "supervisor", "investigador", "analista", "sintesis", "__end__"}
    aristas = {(a.source, a.target) for a in dibujo.edges}
    assert ("__start__", "supervisor") in aristas
    assert ("supervisor", "investigador") in aristas
    assert ("supervisor", "analista") in aristas
    assert ("supervisor", "sintesis") in aristas
    assert ("investigador", "supervisor") in aristas
    assert ("analista", "supervisor") in aristas
    assert ("sintesis", "__end__") in aristas
    assert ("investigador", "analista") not in aristas
    assert grafo is not None


def test_enrutar_manda_finish_a_sintesis() -> None:
    assert enrutar({"next_agent": "FINISH"}) == "sintesis"  # type: ignore[typeddict-item]
    assert enrutar({"next_agent": "investigador"}) == "investigador"  # type: ignore[typeddict-item]
    assert enrutar({"next_agent": "analista"}) == "analista"  # type: ignore[typeddict-item]


def test_el_especialista_recibe_solo_el_ultimo_mensaje(dobles: tuple[LLMFalso, EspecialistaFalso, EspecialistaFalso]) -> None:
    _, investigador, analista = dobles
    estado = estado_inicial(PREGUNTA)
    estado["messages"] = [HumanMessage(content=PREGUNTA), AIMessage(content="instruccion puntual", name="supervisor")]
    nodo_investigador(estado)
    mensajes = investigador.entradas[0]["messages"]
    assert len(mensajes) == 1
    assert mensajes[0].content == "instruccion puntual"
    nodo_analista(estado)
    assert analista.entradas[0]["messages"][0].content == "instruccion puntual"


def test_delega_busca_calcula_y_sintetiza(dobles: tuple[LLMFalso, EspecialistaFalso, EspecialistaFalso]) -> None:
    llm, investigador, analista = dobles
    salida = app.invoke(estado_inicial(PREGUNTA))
    assert [c["agente"] for c in salida["contribuciones"]] == ["investigador", "analista"]
    assert salida["contribuciones"][0]["aporte"].startswith("14 días")
    assert salida["contribuciones"][1]["aporte"] == "Resultado: 231"
    assert salida["task_completed"] is True
    assert salida["pasos"] == 2
    assert salida["messages"][-1].content == "En 12 años acumuló 231 días de vacaciones."
    assert salida["messages"][-1].name == "supervisor"
    assert investigador.entradas[0]["messages"][0].content == PREGUNTA
    assert "14 días" in analista.entradas[0]["messages"][0].content
    assert "Pregunta original:" in str(llm.prompts[0])
    assert "investigador" in str(llm.prompts[0]) and "analista" in str(llm.prompts[0])


def test_finish_sin_datos_no_cierra(dobles: tuple[LLMFalso, EspecialistaFalso, EspecialistaFalso]) -> None:
    llm, _, _ = dobles

    def siempre_finish(mensajes: list[dict[str, str]], *args: object, **kwargs: object) -> DecisionSupervisor:
        return DecisionSupervisor(next="FINISH", razon="ya está")

    llm.supervisor.invoke = siempre_finish  # type: ignore[method-assign]
    salida = app.invoke(estado_inicial(PREGUNTA))
    assert [c["agente"] for c in salida["contribuciones"]] == ["investigador", "analista"]
    assert salida["task_completed"] is True


def test_max_pasos_corta_aunque_el_supervisor_insista(dobles: tuple[LLMFalso, EspecialistaFalso, EspecialistaFalso]) -> None:
    llm, investigador, _ = dobles
    investigador.texto = "No se encontró información relevante en las políticas."

    def siempre_investigador(mensajes: list[dict[str, str]], *args: object, **kwargs: object) -> DecisionSupervisor:
        llm.supervisor.llamadas += 1
        return DecisionSupervisor(next="investigador", razon="otra vez")

    llm.supervisor.invoke = siempre_investigador  # type: ignore[method-assign]
    llm.supervisor.llamadas = 0
    salida = app.invoke(estado_inicial(PREGUNTA))
    assert len(investigador.entradas) == MAX_PASOS
    assert salida["pasos"] == MAX_PASOS
    assert salida["task_completed"] is True
    assert llm.supervisor.llamadas == MAX_PASOS


def test_no_repite_al_agente_que_ya_cumplio(dobles: tuple[LLMFalso, EspecialistaFalso, EspecialistaFalso]) -> None:
    llm, investigador, analista = dobles

    def siempre_investigador(mensajes: list[dict[str, str]], *args: object, **kwargs: object) -> DecisionSupervisor:
        return DecisionSupervisor(next="investigador", razon="otra vez")

    llm.supervisor.invoke = siempre_investigador  # type: ignore[method-assign]
    salida = app.invoke(estado_inicial(PREGUNTA))
    assert len(investigador.entradas) == 1
    assert len(analista.entradas) == 1
    assert salida["task_completed"] is True


def test_las_contribuciones_no_se_pisan_entre_corridas() -> None:
    una = app.invoke(estado_inicial(PREGUNTA))
    otra = app.invoke(estado_inicial(PREGUNTA))
    assert len(una["contribuciones"]) == len(otra["contribuciones"]) == 2


def test_respuesta_truncada_no_se_toma_como_dato(dobles: tuple[LLMFalso, EspecialistaFalso, EspecialistaFalso]) -> None:
    _, investigador, _ = dobles

    def cortada(entrada: dict[str, object], *args: object, **kwargs: object) -> dict[str, list[AIMessage]]:
        return {"messages": [AIMessage(content="14 días y", response_metadata={"finish_reason": "length"})]}

    investigador.invoke = cortada  # type: ignore[method-assign]
    salida = nodo_investigador(estado_inicial(PREGUNTA))
    assert salida["contribuciones"][0]["aporte"].startswith("ERROR: output truncado: investigador cortó la respuesta por max_tokens.")


def test_contenido_en_bloques_se_lee_como_texto(dobles: tuple[LLMFalso, EspecialistaFalso, EspecialistaFalso]) -> None:
    _, investigador, _ = dobles
    investigador.invoke = lambda entrada, *a, **k: {  # type: ignore[method-assign]
        "messages": [AIMessage(content=[{"type": "text", "text": "28 días."}, {"type": "text", "text": " [Fuente: politica_vacaciones.txt]", "extras": {"signature": "x"}}])]
    }
    salida = nodo_investigador(estado_inicial(PREGUNTA))
    assert salida["contribuciones"][0]["aporte"] == "28 días. [Fuente: politica_vacaciones.txt]"
    assert "signature" not in salida["contribuciones"][0]["aporte"]
