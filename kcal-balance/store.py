"""
store.py — SQLite persistence layer for Kcal Balance.

Database lives at /data/kcal.db (persisted by HA across restarts).
"""

import sqlite3

DB_PATH = "/data/kcal.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist; migrate existing schema."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS food_diary (
                user       TEXT NOT NULL,
                date       TEXT NOT NULL,
                calories   REAL NOT NULL DEFAULT 0,
                protein    REAL NOT NULL DEFAULT 0,
                fat        REAL NOT NULL DEFAULT 0,
                carbs      REAL NOT NULL DEFAULT 0,
                burned     REAL          DEFAULT 0,
                fetched_at TEXT,
                PRIMARY KEY (user, date)
            )
        """)
        # Migration: add burned column for installs that existed before v2.3.0
        try:
            conn.execute("ALTER TABLE food_diary ADD COLUMN burned REAL DEFAULT 0")
        except Exception:
            pass  # column already exists — safe to ignore
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)


def upsert_day(user, date_str, totals, burned=None):
    """
    Insert or update one day's totals for a user.

    burned is optional: if None or 0 the existing stored value is preserved
    (backfill calls don't have Garmin data and must not clobber live data).
    """
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO food_diary (user, date, calories, protein, fat, carbs, burned, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user, date) DO UPDATE SET
                calories   = excluded.calories,
                protein    = excluded.protein,
                fat        = excluded.fat,
                carbs      = excluded.carbs,
                burned     = CASE
                               WHEN excluded.burned > 0 THEN excluded.burned
                               ELSE food_diary.burned
                             END,
                fetched_at = excluded.fetched_at
            """,
            (
                user, date_str,
                totals["calories"], totals["protein"],
                totals["fat"],      totals["carbs"],
                burned if burned is not None else 0,
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


def get_setting(key, default=None):
    """Return a settings value, or default if not set."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    """Upsert a setting."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def update_burned(user, date_str, burned):
    """
    Update the burned value for an existing day using MAX(new, existing).

    Used for day-boundary carry-over: after midnight the Garmin sensor may
    still show yesterday's final reading; we push it here without touching
    the food columns.  No-op if the row doesn't exist yet.
    """
    if not burned or burned <= 0:
        return
    with _connect() as conn:
        conn.execute(
            "UPDATE food_diary SET burned = MAX(burned, ?) WHERE user=? AND date=?",
            (burned, user, date_str),
        )


def aggregate(rows):
    """Sum calories/protein/fat/carbs/burned across a list of row dicts."""
    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0, "burned": 0.0}
    for r in rows:
        for k in totals:
            totals[k] += r.get(k, 0) or 0
    return {k: round(v, 1) for k, v in totals.items()}
