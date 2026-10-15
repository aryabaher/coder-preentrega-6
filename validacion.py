"""Chequeo offline: cadenas del orquestador, repo sin claves y la demo con dobles (sin API)."""

from requisitos import exigir_python_312

exigir_python_312()

import io
import re
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import modelo
from tests.conftest import EspecialistaFalso, LLMFalso

modelo.obtener_llm = lambda: LLMFalso()  # type: ignore[assignment]

import agents.analyst_agent as analista  # noqa: E402
import agents.research_agent as investigador  # noqa: E402
import main  # noqa: E402
from graph import app  # noqa: E402

investigador.agente_investigador = EspecialistaFalso("14 días, 21 días y 28 días. [Fuente: politica_vacaciones.txt]")
analista.agente_analista = EspecialistaFalso("Resultado: 231")

RAIZ = Path(__file__).resolve().parent

CADENAS = {
    "state.py": [
        "class AgentState(MessagesState):",
        "contribuciones: Annotated[List[Dict[str, str]], operator.add]",
        "next_agent: Optional[str]",
        "task_completed: bool",
    ],
    "agents/research_agent.py": [
        "def buscar_en_politicas_internas(pregunta: str) -> str:",
        "agente_investigador = create_agent(",
        "def nodo_investigador(state: AgentState) -> dict[str, Any]:",
        'state["messages"][-1].content  # contexto acotado, no todo el historial',
        'name="investigador"',
    ],
    "agents/analyst_agent.py": [
        "def calculadora(expresion: str) -> str:",
        "def _evaluar_nodo(nodo: ast.expr) -> int | float:",
        "agente_analista = create_agent(",
        "def nodo_analista(state: AgentState) -> dict[str, Any]:",
    ],
    "graph.py": [
        "MAX_PASOS = 6",
        "class DecisionSupervisor(BaseModel):",
        'next: Literal["investigador", "analista", "FINISH"]',
        "def nodo_supervisor(state: AgentState) -> dict[str, Any]:",
        "with_structured_output(DecisionSupervisor)",
        'def enrutar(state: AgentState) -> Literal["investigador", "analista", "sintesis"]:',
        "def nodo_sintesis(state: AgentState) -> dict[str, Any]:",
        "grafo = StateGraph(AgentState)",
        'grafo.add_node("supervisor", nodo_supervisor)',
        'grafo.add_node("investigador", nodo_investigador)',
        'grafo.add_node("analista", nodo_analista)',
        'grafo.add_node("sintesis", nodo_sintesis)',
        'grafo.add_conditional_edges(',
        "app: Orquestador = grafo.compile()",
    ],
    "rag.py": [
        'INDEX_NAME = "techcorp-rag-hibrido"',
        'os.getenv("INDEX_NAME")',
        'NAMESPACE = "politicas-internas"',
        'EMBEDDING_MODEL = "text-embedding-3-small"',
        "EMBEDDING_DIM = 1536",
        "class RAGSystem:",
        "def obtener_top_k(self, query: str)",
        "EnsembleRetriever",
        "No se reingesta.",
    ],
    "main.py": [
        "acumuló en total",
        'stream_mode="updates"',
        "app.invoke(estado_inicial(texto))",
        "RESPUESTA FINAL:",
    ],
    "README.md": ["Requisito: Python 3.12 o superior", "py -3.12 -m venv .venv", "```mermaid", "![Grafo del orquestador](grafo.png)"],
}


def _ok(nombre: str, condicion: bool, detalle: str = "") -> None:
    print(f"[{'OK' if condicion else 'FALLO'}] {nombre}{f' - {detalle}' if detalle else ''}")
    if not condicion:
        raise SystemExit(1)


def chequear_repo() -> None:
    _ok("Python 3.12+", sys.version_info >= (3, 12), sys.version.split()[0])
    for archivo, cadenas in CADENAS.items():
        fuente = (RAIZ / archivo).read_text(encoding="utf-8")
        for cadena in cadenas:
            _ok(f"{archivo}: {cadena}", cadena in fuente)
    codigo = [p for p in RAIZ.rglob("*.py") if not {".venv", "tests"} & set(p.relative_to(RAIZ).parts)]
    armados = [p.name for p in codigo for linea in p.read_text(encoding="utf-8").splitlines() if re.match(r"\w+ = StateGraph\(", linea)]
    _ok("un solo StateGraph", armados == ["graph.py"], ", ".join(armados))
    clave = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
    _ok("sin claves en el código", not any(clave.search(p.read_text(encoding="utf-8")) for p in [*codigo, RAIZ / ".env.example"]))
    _ok(".gitignore excluye .env", ".env" in (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines())
    _ok("grafo.mmd es el del grafo", (RAIZ / "grafo.mmd").read_text(encoding="utf-8").strip() == app.get_graph().draw_mermaid().strip())
    git = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
    if git.returncode == 0:
        versionables = git.stdout.splitlines()
        prohibidos = [f for f in versionables if Path(f).name == ".env" or f.startswith(".venv/")]
        _ok("git ls-files sin .env ni .venv", not prohibidos, ", ".join(prohibidos) or f"{len(versionables)} archivos")


def chequear_demo() -> None:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main.main()
    salida = buffer.getvalue()
    print(salida, end="")
    _ok("demo: investigador, analista y sintesis", all(f"Nodo: {n}" in salida for n in ("investigador", "analista", "sintesis")))
    _ok("demo: respuesta final", "RESPUESTA FINAL:" in salida and "231" in salida)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    chequear_repo()
    chequear_demo()
    print("[OK] validacion")
