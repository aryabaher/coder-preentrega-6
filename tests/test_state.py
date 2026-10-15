import operator
import typing

import pytest
from langgraph.graph import MessagesState
from pydantic import ValidationError

from state import AgentState, Solicitud


def test_agent_state_hereda_messages_y_suma_contribuciones() -> None:
    assert MessagesState in AgentState.__orig_bases__
    campos = typing.get_type_hints(AgentState, include_extras=True)
    assert set(campos) >= {"messages", "next_agent", "contribuciones", "pasos", "task_completed"}
    assert typing.get_args(campos["contribuciones"])[1] is operator.add


def test_operator_add_suma_contribuciones_sin_pisarlas() -> None:
    primera = [{"agente": "investigador", "aporte": "14 días"}]
    segunda = [{"agente": "analista", "aporte": "Resultado: 231"}]
    assert operator.add(primera, segunda) == primera + segunda
    assert primera == [{"agente": "investigador", "aporte": "14 días"}]


def test_solicitud_vacia_no_pasa() -> None:
    with pytest.raises(ValidationError, match="String should have at least 1 character"):
        Solicitud(texto="   ")
