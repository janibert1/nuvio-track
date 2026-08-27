"""Thin TMDB v3 client - just what the recommendation engine needs.
Uses the v3 API key (query param), not the v4 read access token, matching
what Nuvio itself asks for in its own settings screen."""
import os
import httpx

BASE = "https://api.themoviedb.org/3"


def _key():
    key = os.environ.get("TMDB_API_KEY", "")
    if not key:
        raise RuntimeError("TMDB_API_KEY not set")
    return key


async def get_details(tmdb_id: int, media_type: str) -> dict | None:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BASE}/{media_type}/{tmdb_id}", params={"api_key": _key()})
        if r.status_code != 200:
            return None
        return r.json()


async def get_similar(tmdb_id: int, media_type: str, page: int = 1) -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{BASE}/{media_type}/{tmdb_id}/similar", params={"api_key": _key(), "page": page}
        )
        if r.status_code != 200:
            return []
        return r.json().get("results", [])


async def get_recommendations_for(tmdb_id: int, media_type: str, page: int = 1) -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{BASE}/{media_type}/{tmdb_id}/recommendations", params={"api_key": _key(), "page": page}
        )
        if r.status_code != 200:
            return []
        return r.json().get("results", [])


async def get_trending(media_type: str, window: str = "week") -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BASE}/trending/{media_type}/{window}", params={"api_key": _key()})
        if r.status_code != 200:
            return []
        return r.json().get("results", [])


async def search(title: str, media_type: str) -> dict | None:
    """Used to resolve a Gemini-suggested title back to a real TMDB id."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{BASE}/search/{media_type}", params={"api_key": _key(), "query": title}
        )
        if r.status_code != 200:
            return None
        results = r.json().get("results", [])
        return results[0] if results else None


def poster_url(poster_path: str | None, size: str = "w342") -> str | None:
    if not poster_path:
        return None
    return f"https://image.tmdb.org/t/p/{size}{poster_path}"
