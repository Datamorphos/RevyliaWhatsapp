"""Grafo LangGraph de SOLO LECTURA del copiloto del panel (§6 del contrato).

Bucle mínimo modelo <-> herramientas: el modelo Gemini (`REVYLIA_MODEL`) solo
dispone de las herramientas de consulta de `src/panel_agent/tools.py`.

MEMORIA SOLO EN PROCESO (§0.5): la conversación del panel es de sesión. Se usa
`MemorySaver` (en RAM), NUNCA `PostgresSaver`: no se toca `DATABASE_URL` ni se
reutilizan los checkpoints del agente de WhatsApp, y nada sobrevive al
reinicio del proceso.
"""

from typing import Any

from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.core.config import Settings, get_settings
from src.panel_agent.prompts import SYSTEM_PROMPT
from src.panel_agent.tools import PANEL_TOOLS


def build_panel_model(settings: Settings | None = None):
    """Modelo Gemini con las herramientas de solo lectura ya enlazadas."""
    settings = settings or get_settings()
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY no está configurada")
    modelo = ChatGoogleGenerativeAI(
        model=settings.revylia_model,
        google_api_key=settings.google_api_key,
        temperature=0.0,
        max_retries=2,
    )
    return modelo.bind_tools(PANEL_TOOLS)


def build_panel_graph(*, settings: Settings | None = None, model: Any = None):
    """Compila el grafo del copiloto.

    `model` permite inyectar un doble en pruebas sin llamar a Gemini.
    """
    modelo = model if model is not None else build_panel_model(settings)

    def copiloto(state: MessagesState) -> dict[str, Any]:
        mensajes = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [modelo.invoke(mensajes)]}

    builder = StateGraph(MessagesState)
    builder.add_node("copiloto", copiloto)
    builder.add_node("tools", ToolNode(PANEL_TOOLS))
    builder.add_edge(START, "copiloto")
    builder.add_conditional_edges("copiloto", tools_condition)
    builder.add_edge("tools", "copiloto")

    # §0.5 (revisado). La versión original compilaba sin `checkpointer=` y eso
    # rompía en ejecución: `ag_ui_langgraph` lee el estado del hilo con
    # `graph.aget_state(...)`, que sobre un grafo sin checkpointer lanza
    # `ValueError: No checkpointer set` — en la PRIMERA petición, no al
    # importar, así que no lo detectaba nada salvo levantar el servidor.
    #
    # El invariante que importa es una propiedad observable, no la ausencia de
    # una clase: *la conversación no sobrevive al reinicio del proceso y no
    # toca `DATABASE_URL`*. `MemorySaver` guarda en RAM del proceso y cumple
    # las dos cosas; `PostgresSaver` incumpliría ambas y sigue prohibido.
    return builder.compile(checkpointer=MemorySaver())
