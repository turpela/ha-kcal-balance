"""
store.py — SQLite persistence layer for Kcal Balance.

Replaces weekly_state.json with a proper queryable store.
Database lives at /data/kcal.db (persisted by HA across restarts).
"""

import sqlite3

DB_PATH = "/data/kcal.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS food_diary (
                user       TEXT NOT NULL,
                date       TEXT NOT NULL,
                calories   REAL NOT NULL DEFAULT 0,
                protein    REAL NOT NULL DEFAULT 0,
                fat        REAL NOT NULL DEFAULT 0,
                carbs      REAL NOT NULL DEFAULT 0,
                fetched_at TEXT,
                PRIMARY KEY (user, date)
            )
        """)


def upsert_day(user, date_str, totals):
    """Insert or update one day's totals for a user."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO food_diary (user, date, calories, protein, fat, carbs, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user, date) DO UPDATE SET
                calories   = excluded.calories,
                protein    = excluded.protein,
                fat        = excluded.fat,
                carbs      = excluded.carbs,
                fetched_at = excluded.fetched_at
            """,
            (
                user, date_str,
                totals["calories"], totals["protein"],
                totals["fat"],     totals["carbs"],
            ),
        )


def has_day(user, date_str):
    """Return True if a row exists for (user, date)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM food_diary WHERE user=? AND date=?",
            (user, date_str),
        ).fetchone()
        return row is not None


def get_day(user, date_str):
    """Return dict for one day, or None if missing."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM food_diary WHERE user=? AND date=?",
            (user, date_str),
        ).fetchone()
        return dict(row) if row else None


def get_range(user, start_str, end_str):
    """Return list of dicts for all days in [start, end] inclusive."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM food_diary
            WHERE user=? AND date BETWEEN ? AND ?
            ORDER BY date
            """,
            (user, start_str, end_str),
        ).fetchall()
        return [dict(r) for r in rows]


def aggregate(rows):
    """Sum calories/protein/fat/carbs across a list of row dicts."""
    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for r in rows:
        for k in totals:
            totals[k] += r.get(k, 0)
    return {k: round(v, 1) for k, v in totals.items()}
