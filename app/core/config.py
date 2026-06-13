from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return get_project_root() / candidate


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    path = resolve_project_path(config_path or "config.yaml")
    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    return config
