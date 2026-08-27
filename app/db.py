"""SQLite storage for NuvioTrack. Single-user by design (one API key =
one household account) - this mirrors what a self-hosted personal tracker
actually needs, not a multi-tenant SaaS."""
import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "./nuviotrack.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tmdb_id INTEGER NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('movie', 'tv')),
    title TEXT NOT NULL,
    season INTEGER,
    episode INTEGER,
    watched_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ratings (
    tmdb_id INTEGER NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('movie', 'tv')),
    title TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 10),
    rated_at INTEGER NOT NULL,
    PRIMARY KEY (tmdb_id, media_type)
);

CREATE TABLE IF NOT EXISTS watchlist (
    tmdb_id INTEGER NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('movie', 'tv')),
    title TEXT NOT NULL,
    added_at INTEGER NOT NULL,
    PRIMARY KEY (tmdb_id, media_type)
);

-- Small cache so the recommendation engine doesn't re-call
-- TMDB/Gemini on every request within the same window.
CREATE TABLE IF NOT EXISTS recommendation_cache (
    media_type TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    generated_at INTEGER NOT NULL
);
"""


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_history(tmdb_id: int, media_type: str, title: str, season=None, episode=None, watched_at=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO history (tmdb_id, media_type, title, season, episode, watched_at) VALUES (?, ?, ?, ?, ?, ?)",
            (tmdb_id, media_type, title, season, episode, watched_at or int(time.time())),
        )


def list_history(limit: int = 200):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM history ORDER BY watched_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_rating(tmdb_id: int, media_type: str, title: str, rating: int):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO ratings (tmdb_id, media_type, title, rating, rated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(tmdb_id, media_type) DO UPDATE SET rating=excluded.rating, rated_at=excluded.rated_at""",
            (tmdb_id, media_type, title, rating, int(time.time())),
        )


def list_ratings(min_rating: int = 1):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM ratings WHERE rating >= ? ORDER BY rating DESC, rated_at DESC", (min_rating,)
        ).fetchall()
        return [dict(r) for r in rows]


def add_watchlist(tmdb_id: int, media_type: str, title: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO watchlist (tmdb_id, media_type, title, added_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(tmdb_id, media_type) DO NOTHING""",
            (tmdb_id, media_type, title, int(time.time())),
        )


def remove_watchlist(tmdb_id: int, media_type: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM watchlist WHERE tmdb_id = ? AND media_type = ?", (tmdb_id, media_type))


def list_watchlist():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM watchlist ORDER BY added_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_cached_recommendations(media_type: str, max_age_seconds: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT payload_json, generated_at FROM recommendation_cache WHERE media_type = ?", (media_type,)
        ).fetchone()
        if row and (int(time.time()) - row["generated_at"]) < max_age_seconds:
            return row["payload_json"]
        return None


def set_cached_recommendations(media_type: str, payload_json: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO recommendation_cache (media_type, payload_json, generated_at) VALUES (?, ?, ?)
               ON CONFLICT(media_type) DO UPDATE SET payload_json=excluded.payload_json, generated_at=excluded.generated_at""",
            (media_type, payload_json, int(time.time())),
        )
