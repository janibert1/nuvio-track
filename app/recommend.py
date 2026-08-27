"""The actual recommendation engine.

Honest about what this is: TMDB's /similar and /recommendations endpoints
give content-based candidates (people who liked THIS title also liked...)
seeded from your own top-rated/recently-watched titles. Gemini then acts
as a personalization layer on top - it sees your whole rated history and
picks/ranks/explains which candidates actually fit your taste, instead of
just returning TMDB's generic per-title similarity list untouched.

This is NOT Trakt's real collaborative filtering (which needs aggregate
behavior across millions of accounts - not reproducible from one person's
data). It's a legitimate, useful approximation, not a drop-in replacement -
see README for the full explanation.
"""
import json
import os
import time

from google import genai

from . import db, tmdb

GEMINI_MODEL = "gemini-2.5-flash"
CACHE_SECONDS = 6 * 3600  # recompute at most every 6h per media_type


async def build_candidate_pool(media_type: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (candidates, top_rated, recent_history) - candidates are
    deduped TMDB result dicts, excluding anything already watched/rated."""
    ratings = [r for r in db.list_ratings(min_rating=6) if r["media_type"] == media_type]
    history = [h for h in db.list_history(limit=100) if h["media_type"] == media_type]
    seen_ids = {r["tmdb_id"] for r in ratings} | {h["tmdb_id"] for h in history}

    seed_items = ratings[:8] if ratings else history[:8]

    candidates: dict[int, dict] = {}
    for item in seed_items:
        for source_call in (tmdb.get_similar, tmdb.get_recommendations_for):
            results = await source_call(item["tmdb_id"], media_type)
            for r in results:
                if r["id"] in seen_ids or r["id"] in candidates:
                    continue
                candidates[r["id"]] = r

    if not candidates:
        # Cold start - nothing watched/rated yet for this media_type.
        for r in await tmdb.get_trending(media_type):
            if r["id"] not in seen_ids:
                candidates[r["id"]] = r

    return list(candidates.values()), ratings, history


def _gemini_prompt(media_type: str, ratings: list[dict], history: list[dict], candidates: list[dict]) -> str:
    kind = "movies" if media_type == "movie" else "TV shows"
    rated_lines = "\n".join(f"- {r['title']}: {r['rating']}/10" for r in ratings[:30]) or "(none rated yet)"
    history_lines = "\n".join(f"- {h['title']}" for h in history[:30]) or "(no watch history yet)"
    candidate_lines = "\n".join(
        f"{c['id']}. {c.get('title') or c.get('name')} "
        f"({(c.get('release_date') or c.get('first_air_date') or '????')[:4]}) - "
        f"{(c.get('overview') or '')[:200]}"
        for c in candidates[:60]
    )
    return f"""You are picking personalized {kind} recommendations for one person based on their actual watch/rating history. Be genuinely selective, not generic.

Their ratings (out of 10):
{rated_lines}

Their recent watch history:
{history_lines}

Candidate pool (numbered by TMDB id) - pick ONLY from this list, do not invent titles:
{candidate_lines}

Return the best 15 candidates for this specific person, ranked best-first, as a JSON array like:
[{{"tmdb_id": 12345, "reason": "one short sentence on why this fits their taste"}}]

Only return the JSON array, nothing else."""


def _call_gemini(prompt: str) -> list[dict]:
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    text = response.text.strip()
    # Gemini sometimes wraps JSON in ```json fences despite instructions.
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


async def get_recommendations(media_type: str, limit: int = 20, force_refresh: bool = False) -> list[dict]:
    if not force_refresh:
        cached = db.get_cached_recommendations(media_type, CACHE_SECONDS)
        if cached:
            return json.loads(cached)[:limit]

    candidates, ratings, history = await build_candidate_pool(media_type)
    if not candidates:
        return []

    by_id = {c["id"]: c for c in candidates}

    if ratings or history:
        try:
            picks = _call_gemini(_gemini_prompt(media_type, ratings, history, candidates))
        except Exception:
            # Gemini call/parse failed - fall back to raw TMDB candidate
            # order rather than erroring the whole recommendations request.
            picks = [{"tmdb_id": c["id"], "reason": None} for c in candidates]
    else:
        picks = [{"tmdb_id": c["id"], "reason": "Trending right now"} for c in candidates]

    result = []
    for pick in picks:
        item = by_id.get(pick.get("tmdb_id"))
        if not item:
            continue
        result.append(
            {
                "tmdb_id": item["id"],
                "media_type": media_type,
                "title": item.get("title") or item.get("name"),
                "overview": item.get("overview"),
                "poster_url": tmdb.poster_url(item.get("poster_path")),
                "year": (item.get("release_date") or item.get("first_air_date") or "")[:4] or None,
                "reason": pick.get("reason"),
            }
        )

    db.set_cached_recommendations(media_type, json.dumps(result))
    return result[:limit]
