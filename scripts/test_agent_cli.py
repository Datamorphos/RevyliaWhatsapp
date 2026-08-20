from src.agents.runtime import invoke_revylia
from src.core.config import get_settings


def main():
    settings = get_settings()
    print("Revylia CLI V2")
    print("Escribe /salir para terminar.\n")
    thread_id = "cli:demo-user"

    while True:
        text = input("Tú: ").strip()
        if text.lower() in {"/salir", "exit", "quit"}:
            break
        if not text:
            continue
        output = invoke_revylia(
            text,
            thread_id=thread_id,
            tenant_id=settings.revylia_clinic_id,
            channel="cli",
            trace=True,
        )
        print("\nRevylia:", output["final_response"])
        print("Ruta:", output["executed_agents"])
        print("Acciones:", output["action_types"])
        print("Métricas:", output["metrics"])
        print()


if __name__ == "__main__":
    main()
