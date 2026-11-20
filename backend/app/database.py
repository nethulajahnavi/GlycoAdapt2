"""Small local SQLite store for GlucoRAG prediction history.

By default the database lives in backend/data/glucorag_history.db. Set
GLUCORAG_DB_PATH to use another persistent location.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def database_path() -> Path:
    configured = os.getenv("GLUCORAG_DB_PATH")
    if configured:
        path = Path(configured).expanduser().resolve()
    else:
        path = Path(__file__).resolve().parents[1] / "data" / "glucorag_history.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path(), timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                latest_glucose REAL NOT NULL,
                risk_label TEXT NOT NULL,
                six_step REAL NOT NULL,
                twelve_step REAL NOT NULL,
                request_json TEXT NOT NULL,
                response_json TEXT NOT NULL
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_prediction_created ON prediction_history(created_at DESC)")


def save_prediction(request_data: dict[str, Any], response_data: dict[str, Any]) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        cursor = connection.execute(
            """INSERT INTO prediction_history
               (created_at, latest_glucose, risk_label, six_step, twelve_step, request_json, response_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                created_at,
                float(response_data["latest_glucose"]),
                str(response_data["risk_analysis"]["overall_label"]),
                float(response_data["predictions"]["six_step"]["glucose_mg_dl"]),
                float(response_data["predictions"]["twelve_step"]["glucose_mg_dl"]),
                json.dumps(request_data, default=str),
                json.dumps(response_data, default=str),
            ),
        )
        record_id = cursor.lastrowid
    return {"id": record_id, "created_at": created_at}


def list_predictions(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, created_at, latest_glucose, risk_label, six_step, twelve_step FROM prediction_history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_prediction(record_id: int) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute("SELECT * FROM prediction_history WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "request": json.loads(row["request_json"]),
        "result": json.loads(row["response_json"]),
    }
