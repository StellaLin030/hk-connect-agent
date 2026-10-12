import json
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "experiments.jsonl"


def save_event(event_type, experiment):
    """追加一条事件记录，不覆盖以前的实验。"""
    LOG_DIR.mkdir(exist_ok=True)

    event = {
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "experiment": experiment,
    }

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")