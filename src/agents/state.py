from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from src.domain.contracts import AgentName


class RevyliaState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    request_id: str
    tenant_id: str
    channel: str
    environment: str
    route_plan: list[AgentName]
    routing_reason: str
    router_fallback_used: bool
    agent_results: list[dict[str, Any]]
    executed_agents: list[AgentName]
    trajectory: list[str]
    agent_timings_ms: dict[str, float]
    errors: list[dict[str, Any]]
    safety_flags: list[str]
    step_count: int
    actions: list[dict[str, Any]]
    final_response: str
