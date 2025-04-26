import json
import os
from typing import Any, Dict, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def _get_path(name: str) -> str:
    return os.path.join(DATA_DIR, f"{name}.json")

def load_json(name: str) -> Dict[str, Any]:
    path = _get_path(name)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(name: str, data: Dict[str, Any]):
    path = _get_path(name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_collection(name: str) -> Dict[str, Any]:
    return load_json(name)

def set_collection(name: str, data: Dict[str, Any]):
    save_json(name, data)
