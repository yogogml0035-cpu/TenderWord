import json
import logging
import os
from typing import Mapping, Any

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "tender_agent.log")

logger = logging.getLogger("TenderWord")
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def log_state_start(label: str, state: Mapping[str, Any]) -> None:
    logger.info("===== RUN START =====")

def log_state(label: str, state: Mapping[str, Any]) -> None:
    state_dict = dict(state)
    formatted_json = json.dumps(state_dict, ensure_ascii=False, indent=2)
    logger.info("%s state:\n%s", label, formatted_json)
