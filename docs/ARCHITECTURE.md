# Arquitectura V2

## Separación de responsabilidades

```text
Transport
└── src/webhooks + integrations/whatsapp

Application
└── services/message_processor.py

AI Runtime
└── agents/runtime.py + graph.py

Deterministic Tools
└── agents/tools.py + database/repository.py

Persistence
└── Supabase PostgreSQL

Observability
└── observability/langfuse.py
```

## Decisiones

1. El webhook no conoce la topología de agentes.
2. `invoke_revylia()` sigue siendo la interfaz pública del Brain.
3. Los agentes no escriben SQL directamente; invocan herramientas deterministas.
4. Todas las consultas de negocio incluyen `clinic_id`.
5. LangGraph y datos operativos comparten PostgreSQL, pero no las mismas tablas.
6. La memoria de conversación se identifica con un hash de `tenant_id + thread_id`.
7. Los mensajes de Meta se deduplican antes de invocar LangGraph.
8. La recuperación solo genera borradores con aprobación humana en esta V2.
