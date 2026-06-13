from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.config import load_config, resolve_project_path


def get_database_path(config: dict | None = None) -> Path:
    config = config or load_config()
    db_path = resolve_project_path(config["database"]["path"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_schema(db_path: str | Path | None = None) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    with get_connection(db_path) as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
