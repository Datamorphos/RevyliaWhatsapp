import uuid
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver

from src.agents.graph import build_revylia_graph
from src.agents.llm import LLMClients
from src.agents.tools import ClinicTools
from src.core.config import Settings, get_settings
from src.core.security import stable_hash
from src.database.connection import checkpoint_connection
from src.database.repository import ClinicRepository
from src.observability.langfuse import LangfuseTracer


def _safe_thread_id(tenant_id: str, thread_id: str) -> str:
    return stable_hash(f"{tenant_id}:{thread_id}")


def _safe_user_id(tenant_id: str, thread_id: str) -> str:
    return stable_hash(f"user:{tenant_id}:{thread_id}")


def _action_types(actions: list[dict[str, Any]]) -> list[str]:
    return [str(action.get("type", "unknown")) for action in actions]


class RevyliaRuntime:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.settings.require_agent_runtime()
        self.tracer = LangfuseTracer(self.settings)
        self.repository = ClinicRepository(self.settings)
        self.llms = LLMClients(self.settings)
        self.tools = ClinicTools(self.repository, self.tracer, self.settings)

    @contextmanager
    def _graph(self):
        with checkpoint_connection(self.settings) as conn:
            checkpointer = PostgresSaver(conn)
            graph = build_revylia_graph(
                settings=self.settings,
                llms=self.llms,
                tools=self.tools,
                checkpointer=checkpointer,
            )
            yield graph

    def _invoke_impl(
        self,
        *,
        message: str,
        thread_id: str,
        tenant_id: str,
        channel: str,
        request_id: str,
        callbacks: list | None = None,
    ) -> dict[str, Any]:
        safe_thread_id = _safe_thread_id(tenant_id, thread_id)
        started = perf_counter()
        config = {
            "configurable": {"thread_id": safe_thread_id},
            "run_name": "revylia.orchestrator",
            "tags": [
                f"environment:{self.settings.revylia_env}",
                f"channel:{channel}",
                f"provider:{self.settings.llm_provider}",
                f"model:{self.settings.revylia_model}",
                f"graph_version:{self.settings.graph_version}",
            ],
            "metadata": {
                "environment": self.settings.revylia_env,
                "tenant_hash": stable_hash(tenant_id),
                "channel": channel,
                "provider": self.settings.llm_provider,
                "model": self.settings.revylia_model,
                "graph_version": self.settings.graph_version,
                "prompt_version": self.settings.prompt_version,
                "request_id": request_id,
                "thread_hash": safe_thread_id,
            },
            "recursion_limit": 12,
        }
        if callbacks:
            config["callbacks"] = callbacks

        with self._graph() as graph:
            state = graph.invoke(
                {
                    "messages": [HumanMessage(content=message)],
                    "request_id": request_id,
                    "tenant_id": tenant_id,
                    "channel": channel,
                    "environment": self.settings.revylia_env,
                },
                config=config,
            )

        latency_ms = round((perf_counter() - started) * 1000, 2)
        actions = list(state.get("actions", []))
        errors = list(state.get("errors", []))
        action_types = _action_types(actions)
        tool_errors = [
            action_type for action_type in action_types
            if action_type.endswith("_error") or action_type == "agent_error"
        ]
        return {
            "request_id": request_id,
            "final_response": state.get("final_response", ""),
            "routing_reason": state.get("routing_reason", ""),
            "router_fallback_used": bool(state.get("router_fallback_used", False)),
            "executed_agents": list(state.get("executed_agents", [])),
            "trajectory": list(state.get("trajectory", [])),
            "actions": actions,
            "action_types": action_types,
            "errors": errors,
            "safety_flags": list(state.get("safety_flags", [])),
            "agent_timings_ms": dict(state.get("agent_timings_ms", {})),
            "metrics": {
                "latency_ms": latency_ms,
                "agent_steps": int(state.get("step_count", 0)),
                "action_count": len(actions),
                "tool_error_count": len(tool_errors),
                "error_count": len(errors),
                "router_fallback": int(bool(state.get("router_fallback_used", False))),
            },
        }

    def invoke(
        self,
        message: str,
        *,
        thread_id: str = "patient-demo-001",
        tenant_id: str | None = None,
        channel: str | None = None,
        request_id: str | None = None,
        trace: bool = True,
    ) -> dict[str, Any]:
        tenant_id = tenant_id or self.settings.revylia_clinic_id
        channel = channel or self.settings.revylia_channel
        request_id = request_id or str(uuid.uuid4())
        safe_thread_id = _safe_thread_id(tenant_id, thread_id)

        if not (self.tracer.enabled and trace):
            return self._invoke_impl(
                message=message,
                thread_id=thread_id,
                tenant_id=tenant_id,
                channel=channel,
                request_id=request_id,
            )

        from langfuse import propagate_attributes

        tags = [
            "application:revylia",
            "architecture:multiagent",
            f"channel:{channel}",
            f"provider:{self.settings.llm_provider}",
            f"model:{self.settings.revylia_model}",
            f"graph_version:{self.settings.graph_version}",
        ]
        metadata = {
            "tenant_hash": stable_hash(tenant_id),
            "channel": channel,
            "provider": self.settings.llm_provider,
            "model": self.settings.revylia_model,
            "graph_version": self.settings.graph_version,
            "prompt_version": self.settings.prompt_version,
            "request_id": request_id,
            "thread_hash": safe_thread_id,
        }
        root_input = self.tracer.trace_payload({
            "message": message,
            "request_id": request_id,
            "channel": channel,
            "tenant_hash": stable_hash(tenant_id),
            "thread_hash": safe_thread_id,
        })

        try:
            with self.tracer.client.start_as_current_observation(
                as_type="agent",
                name="revylia.request",
                input=root_input,
                version=self.settings.graph_version,
                metadata={**metadata, "privacy_mode": self.settings.revylia_trace_content_mode},
            ) as root_observation:
                with propagate_attributes(
                    trace_name="revylia.request",
                    user_id=_safe_user_id(tenant_id, thread_id),
                    session_id=safe_thread_id,
                    tags=tags,
                    version=self.settings.graph_version,
                    environment=self.settings.revylia_env,
                    metadata=metadata,
                ):
                    trace_id = self.tracer.client.get_current_trace_id()
                    try:
                        output = self._invoke_impl(
                            message=message,
                            thread_id=thread_id,
                            tenant_id=tenant_id,
                            channel=channel,
                            request_id=request_id,
                            callbacks=[self.tracer.handler],
                        )
                        output["langfuse_trace_id"] = trace_id
                        root_observation.update(
                            output=self.tracer.trace_payload(output),
                            metadata={
                                **metadata,
                                "privacy_mode": self.settings.revylia_trace_content_mode,
                                "evaluation_payload": self.tracer.trace_payload(output),
                            },
                        )
                        return output
                    except Exception as exc:
                        root_observation.update(
                            level="ERROR",
                            status_message=type(exc).__name__,
                            output={"error_type": type(exc).__name__},
                        )
                        raise
        finally:
            self.tracer.flush()


_runtime: RevyliaRuntime | None = None


def get_runtime() -> RevyliaRuntime:
    global _runtime
    if _runtime is None:
        _runtime = RevyliaRuntime()
    return _runtime


def invoke_revylia(
    message: str,
    thread_id: str = "patient-demo-001",
    tenant_id: str | None = None,
    channel: str | None = None,
    request_id: str | None = None,
    trace: bool = True,
) -> dict[str, Any]:
    return get_runtime().invoke(
        message,
        thread_id=thread_id,
        tenant_id=tenant_id,
        channel=channel,
        request_id=request_id,
        trace=trace,
    )
