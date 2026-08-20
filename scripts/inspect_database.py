import argparse
import json

from src.core.config import get_settings
from src.database.repository import ClinicRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "table",
        choices=[
            "patients", "appointments", "opportunities", "escalations",
            "recovery_messages", "whatsapp_inbound_events",
        ],
    )
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    settings = get_settings()
    repo = ClinicRepository(settings)
    rows = repo.read_table(settings.revylia_clinic_id, args.table, args.limit)
    print(json.dumps(rows, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
