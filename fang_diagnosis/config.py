from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "fang_diagnosis.yaml"


@lru_cache(maxsize=4)
def load_fang_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def threshold(config: dict[str, Any], path: tuple[str, ...]) -> float | None:
    current: Any = config.get("thresholds", {})
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise KeyError("Missing Fang threshold: " + ".".join(path))
        current = current[key]
    value = current.get("value") if isinstance(current, dict) else current
    return None if value is None else float(value)


def threshold_status(config: dict[str, Any], path: tuple[str, ...]) -> str:
    current: Any = config.get("thresholds", {})
    for key in path:
        current = current[key]
    return str(current.get("status", "provisional")) if isinstance(current, dict) else "provisional"

