import re
from datetime import datetime
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from src.agents.llm import LLMClients
from src.agents.safety import apply_clinical_claim_guard, detect_critical_risk
from src.agents.state import RevyliaState
from src.agents.tools import ClinicTools
from src.core.config import Settings
from src.domain.contracts import AgentName
from src.domain.knowledge import CLINIC_KNOWLEDGE, clinic_context_text


BOGOTA_TZ = ZoneInfo("America/Bogota")


def today_bogota():
    return datetime.now(BOGOTA_TZ).date()


def extract_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
                continue
            if isinstance(block, dict):
                text = block.get("text")
                if text:
                    text_parts.append(str(text))
                continue
            text = getattr(block, "text", None)
            if text:
                text_parts.append(str(text))
        return "\n".join(text_parts).strip()
    return str(content or "").strip()


def last_user_text(state: RevyliaState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return extract_message_text(message.content)
    return ""


def compact_history(state: RevyliaState, max_messages: int = 8) -> str:
    history = []
    for message in state.get("messages", [])[-max_messages:]:
        role = "Paciente" if isinstance(message, HumanMessage) else "Revylia"
        history.append(f"{role}: {extract_message_text(message.content)}")
    return "\n".join(history)


def build_revylia_graph(
    *,
    settings: Settings,
    llms: LLMClients,
    tools: ClinicTools,
    checkpointer,
):
    max_agent_steps = settings.revylia_max_agent_steps

    def keyword_router(user_text: str) -> list[AgentName]:
        text = user_text.lower()
        selected: list[AgentName] = []
        if any(word in text for word in [
            "cita", "agendar", "agenda", "horario", "disponibilidad", "reprogram", "cancelar"
        ]):
            selected.append("agenda")
        if any(word in text for word in [
            "precio", "cuánto", "cuanto", "servicio", "horario de atención", "política",
            "politica", "regla", "blanqueamiento", "limpieza", "ortodoncia"
        ]):
            selected.append("clinic_brain")
        if any(word in text for word in [
            "recuperar", "inactivos", "campaña", "campana", "reactivar", "seguimiento"
        ]):
            selected.append("recovery")
        if any(word in text for word in [
            "humano", "asesor", "queja", "dolor", "sangrado", "urgente", "emergencia",
            "respirar", "alérgica", "alergica"
        ]):
            selected.insert(0, "reception")
        return list(dict.fromkeys(selected))[:max_agent_steps] or ["reception"]

    def supervisor_node(state: RevyliaState) -> dict[str, Any]:
        started = perf_counter()
        user_text = last_user_text(state)
        system_prompt = f"""
Eres el orquestador principal de Revylia para una clínica.

Selecciona solo los especialistas estrictamente necesarios:
- reception: saludo, primera atención, calificación de oportunidad, quejas,
  solicitud de humano o riesgo clínico.
- agenda: consultar disponibilidad, crear o reprogramar citas.
- recovery: pacientes inactivos, campañas y borradores de reactivación.
- clinic_brain: servicios, precios, horarios, reglas y conocimiento de la clínica.

Reglas:
1. Selecciona máximo {max_agent_steps} agentes.
2. En una solicitud mixta de información y agenda, ejecuta primero clinic_brain y luego agenda.
3. No selecciones agentes por precaución si no son necesarios.
4. No diagnostiques.
5. Fecha actual en Colombia: {today_bogota().isoformat()}.
"""
        fallback_used = False
        errors: list[dict[str, Any]] = []
        try:
            decision = llms.router.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_text),
            ])
            plan = list(decision.agents)[:max_agent_steps]
            reason = decision.reason
        except Exception as exc:
            plan = keyword_router(user_text)
            reason = f"Ruta de respaldo por palabras clave: {type(exc).__name__}"
            fallback_used = True
            errors.append({
                "component": "supervisor",
                "type": "router_fallback",
                "error_class": type(exc).__name__,
            })

        timings = dict(state.get("agent_timings_ms", {}))
        timings["supervisor"] = round((perf_counter() - started) * 1000, 2)
        return {
            "route_plan": plan,
            "routing_reason": reason,
            "router_fallback_used": fallback_used,
            "agent_results": [],
            "executed_agents": [],
            "trajectory": ["supervisor"],
            "agent_timings_ms": timings,
            "errors": errors,
            "safety_flags": [],
            "step_count": 0,
            "actions": [],
        }

    def finish_agent(
        state: RevyliaState,
        agent_name: AgentName,
        reply: str,
        started: float,
        actions: list[dict[str, Any]] | None = None,
        safety_flags: list[str] | None = None,
    ) -> dict[str, Any]:
        actions = actions or []
        remaining = list(state.get("route_plan", []))
        if remaining and remaining[0] == agent_name:
            remaining = remaining[1:]
        elif agent_name in remaining:
            remaining.remove(agent_name)

        results = list(state.get("agent_results", []))
        results.append({"agent": agent_name, "reply": reply, "actions": actions})
        executed = list(state.get("executed_agents", []))
        executed.append(agent_name)
        trajectory = list(state.get("trajectory", []))
        trajectory.append(agent_name)
        timings = dict(state.get("agent_timings_ms", {}))
        timings[agent_name] = round((perf_counter() - started) * 1000, 2)
        errors = list(state.get("errors", []))
        for action in actions:
            action_type = str(action.get("type", ""))
            if action_type.endswith("_error") or action_type == "agent_error":
                errors.append({
                    "component": agent_name,
                    "type": action_type,
                    "error": action.get("error", "unknown"),
                })
        flags = list(state.get("safety_flags", []))
        flags.extend(safety_flags or [])
        return {
            "route_plan": remaining,
            "agent_results": results,
            "executed_agents": executed,
            "trajectory": trajectory,
            "agent_timings_ms": timings,
            "errors": errors,
            "safety_flags": list(dict.fromkeys(flags)),
            "step_count": int(state.get("step_count", 0)) + 1,
        }

    def reception_node(state: RevyliaState) -> dict[str, Any]:
        started = perf_counter()
        user_text = last_user_text(state)
        clinic_id = state["tenant_id"]
        critical_risk = detect_critical_risk(user_text)
        prompt = f"""
Eres el agente de Recepción IA de Revylia.

Objetivos:
- Responder de forma cálida, breve y profesional.
- Detectar interés comercial real.
- Crear oportunidad solo cuando exista intención concreta.
- Escalar solicitudes explícitas de humano, quejas sensibles o riesgos clínicos.
- Nunca diagnosticar ni prometer resultados médicos.
- Ante sangrado abundante, dificultad para respirar, reacción alérgica o una emergencia,
  indicar atención inmediata y escalar como urgente.

Fecha actual: {today_bogota().isoformat()}.
Conversación reciente:
{compact_history(state)}

Devuelve una decisión estructurada.
"""
        actions: list[dict[str, Any]] = []
        flags: list[str] = []
        try:
            decision = llms.reception.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=user_text),
            ])
            reply = decision.reply
            if decision.intent == "clinical_risk" or critical_risk:
                flags.append("clinical_risk")
            if decision.create_opportunity and not critical_risk:
                reason = decision.opportunity_reason or f"Interés detectado: {user_text}"
                opportunity = tools.create_opportunity(
                    clinic_id,
                    patient_name=decision.patient_name,
                    phone=decision.phone,
                    reason=reason,
                    score=decision.lead_score,
                )
                actions.append({"type": "opportunity_created", "data": opportunity})
            if decision.escalate:
                priority = "urgent" if critical_risk else decision.escalation_priority
                reason = decision.escalation_reason or user_text
                escalation = tools.create_escalation(
                    clinic_id,
                    reason=reason,
                    priority=priority,
                    patient_name=decision.patient_name,
                    phone=decision.phone,
                )
                actions.append({"type": "human_escalation_created", "data": escalation})
                flags.append(f"escalation:{priority}")
            if critical_risk:
                already_escalated = any(
                    action.get("type") == "human_escalation_created" for action in actions
                )
                if not already_escalated:
                    escalation = tools.create_escalation(
                        clinic_id,
                        reason=user_text,
                        priority="urgent",
                        patient_name=decision.patient_name,
                        phone=decision.phone,
                    )
                    actions.append({"type": "human_escalation_created", "data": escalation})
                flags.append("escalation:urgent")
                immediate = (
                    "Busca atención de urgencias inmediatamente o comunícate con el "
                    "servicio local de emergencias. También dejaré el caso escalado como urgente."
                )
                if not any(term in reply.lower() for term in ["urgencias", "emergencia", "inmediata"]):
                    reply = f"{immediate} {reply}"
        except Exception as exc:
            if critical_risk:
                try:
                    escalation = tools.create_escalation(
                        clinic_id,
                        reason=user_text,
                        priority="urgent",
                    )
                    actions.append({"type": "human_escalation_created", "data": escalation})
                except Exception as escalation_exc:
                    actions.append({"type": "escalation_error", "error": repr(escalation_exc)})
                flags.extend(["clinical_risk", "escalation:urgent", "llm_failure_safe_path"])
                reply = (
                    "Busca atención de urgencias inmediatamente o comunícate con el "
                    "servicio local de emergencias. El caso fue marcado para escalamiento urgente."
                )
            else:
                reply = (
                    "Puedo ayudarte con información, agendamiento o comunicarte con una persona. "
                    "No pude interpretar completamente la solicitud; por favor indícame qué necesitas."
                )
                actions.append({"type": "agent_error", "error": repr(exc)})

        reply, diagnosis_guard_triggered = apply_clinical_claim_guard(reply)
        if diagnosis_guard_triggered:
            flags.append("diagnosis_claim_blocked")
        return finish_agent(state, "reception", reply, started, actions, flags)

    def resolve_service(service: str | None, user_text: str) -> str | None:
        if service in CLINIC_KNOWLEDGE["services"]:
            return service
        text = f"{service or ''} {user_text}".lower()
        aliases = {
            "limpieza": "Limpieza dental",
            "valoración": "Valoración general",
            "valoracion": "Valoración general",
            "blanqueamiento": "Blanqueamiento",
            "ortodoncia": "Ortodoncia - valoración",
        }
        for alias, canonical in aliases.items():
            if alias in text:
                return canonical
        return None

    def agenda_node(state: RevyliaState) -> dict[str, Any]:
        started = perf_counter()
        user_text = last_user_text(state)
        clinic_id = state["tenant_id"]
        prompt = f"""
Eres el agente de Agenda y Confirmación de Revylia.

Tu función es extraer datos y elegir una acción:
- check: consultar disponibilidad.
- create: crear una cita si están nombre, teléfono, servicio, fecha y hora.
- reschedule: cambiar la próxima cita futura; requiere nombre, nueva fecha y hora.
- clarify: pedir solo los datos faltantes.

Reglas:
- Fecha actual en Colombia: {today_bogota().isoformat()}.
- Convierte expresiones relativas a fecha ISO YYYY-MM-DD.
- Usa hora 24 horas HH:MM y solo horas exactas.
- No inventes nombre, teléfono, servicio, fecha ni hora.
- Servicios válidos: {list(CLINIC_KNOWLEDGE['services'].keys())}.
- La respuesta debe explicar brevemente qué se hará o qué falta.

Conversación reciente:
{compact_history(state)}
"""
        actions: list[dict[str, Any]] = []
        try:
            decision = llms.agenda.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=user_text),
            ])
            service = resolve_service(decision.service, user_text)
            reply = decision.reply
            if decision.action == "check":
                if not decision.appointment_date:
                    reply = "¿Para qué fecha deseas consultar disponibilidad?"
                else:
                    slots = tools.list_available_slots(clinic_id, decision.appointment_date)
                    actions.append({
                        "type": "availability_checked",
                        "date": decision.appointment_date,
                        "slots": slots,
                    })
                    reply = (
                        f"Para el {decision.appointment_date} hay disponibilidad en: "
                        f"{', '.join(slots) if slots else 'ningún horario'}."
                    )
            elif decision.action == "create":
                missing = [
                    field for field, value in {
                        "nombre": decision.patient_name,
                        "teléfono": decision.phone,
                        "servicio": service,
                        "fecha": decision.appointment_date,
                        "hora": decision.appointment_time,
                    }.items() if not value
                ]
                if missing:
                    reply = f"Para confirmar la cita necesito: {', '.join(missing)}."
                else:
                    appointment = tools.create_appointment(
                        clinic_id,
                        patient_name=decision.patient_name,
                        phone=decision.phone,
                        service=service,
                        appointment_date=decision.appointment_date,
                        appointment_time=decision.appointment_time,
                    )
                    actions.append({"type": "appointment_created", "data": appointment})
                    reply = (
                        f"Cita confirmada para {appointment['patient_name']}: "
                        f"{appointment['service']} el {appointment['appointment_date']} "
                        f"a las {str(appointment['appointment_time'])[:5]}."
                    )
            elif decision.action == "reschedule":
                missing = [
                    field for field, value in {
                        "nombre": decision.patient_name,
                        "nueva fecha": decision.appointment_date,
                        "nueva hora": decision.appointment_time,
                    }.items() if not value
                ]
                if missing:
                    reply = f"Para reprogramar necesito: {', '.join(missing)}."
                else:
                    appointment = tools.reschedule_appointment(
                        clinic_id,
                        patient_name=decision.patient_name,
                        new_date=decision.appointment_date,
                        new_time=decision.appointment_time,
                    )
                    actions.append({"type": "appointment_rescheduled", "data": appointment})
                    reply = (
                        f"La cita de {appointment['patient_name']} quedó reprogramada "
                        f"para el {appointment['appointment_date']} "
                        f"a las {str(appointment['appointment_time'])[:5]}."
                    )
        except Exception as exc:
            reply = "No fue posible completar la operación de agenda."
            actions.append({"type": "agenda_error", "error": repr(exc)})
        return finish_agent(state, "agenda", reply, started, actions)

    def recovery_node(state: RevyliaState) -> dict[str, Any]:
        started = perf_counter()
        user_text = last_user_text(state)
        clinic_id = state["tenant_id"]
        prompt = f"""
Eres el agente de Recuperación de Pacientes de Revylia.

Decide:
- list: listar pacientes recuperables.
- draft: listar pacientes y crear borradores personalizados.
- clarify: pedir precisión.

Reglas:
- Solo se consideran pacientes con consentimiento.
- Por defecto, inactividad mínima de 180 días.
- Los borradores SIEMPRE requieren aprobación humana en esta V2.
- No uses presión ni afirmaciones clínicas.
- Fecha actual: {today_bogota().isoformat()}.

Solicitud: {user_text}
"""
        actions: list[dict[str, Any]] = []
        try:
            decision = llms.recovery.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=user_text),
            ])
            reply = decision.reply
            if decision.action in {"list", "draft"}:
                patients = tools.list_recoverable_patients(
                    clinic_id,
                    days_inactive=decision.days_inactive,
                    limit=decision.limit,
                )
                actions.append({"type": "recoverable_patients_listed", "data": patients})
                if not patients:
                    reply = "No encontré pacientes recuperables con los criterios actuales."
                elif decision.action == "list":
                    lines = [
                        f"- {p['name']} — última visita: {p['last_visit_date']} — {p['last_service']}"
                        for p in patients
                    ]
                    reply = "Pacientes recuperables:\n" + "\n".join(lines)
                else:
                    drafts = []
                    for patient in patients:
                        message_prompt = f"""
Redacta un mensaje de WhatsApp breve, cálido y no invasivo para {patient['name']}.
Último servicio: {patient['last_service']}.
La clínica es {CLINIC_KNOWLEDGE['clinic_name']}.
Invita a retomar contacto o solicitar una valoración. No inventes descuentos.
Devuelve solo el mensaje.
"""
                        generated = extract_message_text(llms.llm.invoke(message_prompt).content)
                        saved = tools.save_recovery_message(
                            clinic_id,
                            patient_id=patient["id"],
                            message=generated,
                            approval_required=True,
                        )
                        drafts.append({
                            "patient": patient["name"],
                            "message": generated,
                            "record": saved,
                        })
                    actions.append({"type": "recovery_drafts_created", "data": drafts})
                    reply = f"Creé {len(drafts)} borradores de recuperación pendientes de aprobación."
        except Exception as exc:
            reply = "No fue posible preparar la recuperación de pacientes."
            actions.append({"type": "recovery_error", "error": repr(exc)})
        return finish_agent(state, "recovery", reply, started, actions)

    def clinic_brain_node(state: RevyliaState) -> dict[str, Any]:
        started = perf_counter()
        user_text = last_user_text(state)
        prompt = f"""
Eres Clinic Brain, la fuente de conocimiento estructurado de Revylia.

Responde únicamente con base en el contexto suministrado.
- Sé breve, claro y comercial sin ser agresivo.
- Los precios son informativos.
- No diagnostiques.
- Cuando la pregunta sea clínica o presente riesgo, recomienda valoración o atención profesional.
- No afirmes que realizaste una cita o una escritura en base de datos.

CONTEXTO:
{clinic_context_text()}

PREGUNTA:
{user_text}
"""
        actions: list[dict[str, Any]] = []
        try:
            response = llms.llm.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=user_text),
            ])
            reply = extract_message_text(response.content)
        except Exception as exc:
            reply = "No pude consultar el conocimiento de la clínica en este momento."
            actions.append({"type": "clinic_brain_error", "error": repr(exc)})
        return finish_agent(state, "clinic_brain", reply, started, actions)

    def build_specialist_subgraph(node_fn):
        specialist_builder = StateGraph(RevyliaState)
        specialist_builder.add_node("execute", node_fn)
        specialist_builder.add_edge(START, "execute")
        specialist_builder.add_edge("execute", END)
        return specialist_builder.compile()

    specialist_graphs = {
        "reception": build_specialist_subgraph(reception_node),
        "agenda": build_specialist_subgraph(agenda_node),
        "recovery": build_specialist_subgraph(recovery_node),
        "clinic_brain": build_specialist_subgraph(clinic_brain_node),
    }

    def next_parent_node(state: RevyliaState) -> str:
        plan = list(state.get("route_plan", []))
        step_count = int(state.get("step_count", 0))
        if plan and step_count < max_agent_steps:
            return f"{plan[0]}_subgraph"
        return "finalizer"

    def flatten_actions(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        flattened = []
        for result in results:
            for action in result.get("actions", []):
                flattened.append({"agent": result.get("agent"), **action})
        return flattened

    def finalizer_node(state: RevyliaState) -> dict[str, Any]:
        started = perf_counter()
        results = state.get("agent_results", [])
        if not results:
            final_response = "No pude procesar la solicitud."
        elif len(results) == 1:
            final_response = results[0]["reply"]
        else:
            formatted = "\n\n".join(
                f"Agente {item['agent']}: {item['reply']}\nAcciones: {item['actions']}"
                for item in results
            )
            synthesis_prompt = f"""
Eres el supervisor final de Revylia.
Combina los resultados en una sola respuesta breve, natural y coherente.
No inventes acciones. Si una operación falló, dilo con claridad.
No muestres JSON, nombres internos de agentes ni detalles técnicos.

RESULTADOS:
{formatted}
"""
            try:
                response = llms.llm.invoke(synthesis_prompt)
                final_response = extract_message_text(response.content)
            except Exception:
                final_response = "\n".join(item["reply"] for item in results)

        final_response, guard_triggered = apply_clinical_claim_guard(final_response)
        final_flags = list(state.get("safety_flags", []))
        if guard_triggered:
            final_flags.append("diagnosis_claim_blocked")
        trajectory = list(state.get("trajectory", []))
        trajectory.append("finalizer")
        timings = dict(state.get("agent_timings_ms", {}))
        timings["finalizer"] = round((perf_counter() - started) * 1000, 2)
        return {
            "final_response": final_response,
            "messages": [AIMessage(content=final_response)],
            "trajectory": trajectory,
            "agent_timings_ms": timings,
            "actions": flatten_actions(results),
            "safety_flags": list(dict.fromkeys(final_flags)),
        }

    builder = StateGraph(RevyliaState)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("reception_subgraph", specialist_graphs["reception"])
    builder.add_node("agenda_subgraph", specialist_graphs["agenda"])
    builder.add_node("recovery_subgraph", specialist_graphs["recovery"])
    builder.add_node("clinic_brain_subgraph", specialist_graphs["clinic_brain"])
    builder.add_node("finalizer", finalizer_node)
    builder.add_edge(START, "supervisor")

    mapping = {
        "reception_subgraph": "reception_subgraph",
        "agenda_subgraph": "agenda_subgraph",
        "recovery_subgraph": "recovery_subgraph",
        "clinic_brain_subgraph": "clinic_brain_subgraph",
        "finalizer": "finalizer",
    }
    builder.add_conditional_edges("supervisor", next_parent_node, mapping)
    for subgraph_node in [
        "reception_subgraph", "agenda_subgraph", "recovery_subgraph", "clinic_brain_subgraph"
    ]:
        builder.add_conditional_edges(subgraph_node, next_parent_node, mapping)
    builder.add_edge("finalizer", END)
    return builder.compile(checkpointer=checkpointer)
