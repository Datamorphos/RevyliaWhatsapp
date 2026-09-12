"""Grafo LangGraph de SOLO LECTURA del copiloto del panel (§6 del contrato).

Bucle mínimo modelo <-> herramientas: el modelo Gemini (`REVYLIA_MODEL`) solo
dispone de las herramientas de consulta de `src/panel_agent/tools.py`.

SIN CHECKPOINTER (§0.5): la conversación del panel es de sesión. No se crea
`PostgresSaver` ni se reutilizan los checkpoints del agente de WhatsApp.
"""

from typing import Any

from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
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

    # §0.5: se compila deliberadamente SIN `checkpointer=`. La conversación es
    # de sesión y no debe persistirse ni cruzarse con la de WhatsApp.
    # Advertencia para el orquestador: `ag_ui_langgraph` lee el estado del hilo
    # con `graph.aget_state(...)`, que sobre un grafo sin checkpointer lanza
    # `ValueError: No checkpointer set`. Si eso ocurre en ejecución, es una
    # decisión de contrato (§0.5), no un descuido: debe resolverla el
    # orquestador antes de añadir cualquier saver aquí.
    return builder.compile()
