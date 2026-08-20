from langchain_google_genai import ChatGoogleGenerativeAI

from src.core.config import Settings, get_settings
from src.domain.contracts import AgendaDecision, ReceptionDecision, RecoveryDecision, RouteDecision


class LLMClients:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        if not self.settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY no está configurada")

        self.llm = ChatGoogleGenerativeAI(
            model=self.settings.revylia_model,
            google_api_key=self.settings.google_api_key,
            temperature=0.0,
            max_retries=2,
        )
        self.router = self.llm.with_structured_output(RouteDecision)
        self.reception = self.llm.with_structured_output(ReceptionDecision)
        self.agenda = self.llm.with_structured_output(AgendaDecision)
        self.recovery = self.llm.with_structured_output(RecoveryDecision)
