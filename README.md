# NuvioTrack

A self-hosted, open-source alternative to Trakt/Simkl for personal watch
tracking + recommendations — built because Trakt now requires a paid VIP
subscription just to register a new API application at all (as of 2026),
and Simkl (free) has no recommendation engine.

**What it does:**
- Stores your own watch history, ratings, and watchlist (the same kind of
  data Trakt collects) in a local SQLite database — single user, API-key
  authenticated.
- Generates personalized recommendations using TMDB's free `/recommendations`
  and `/similar` endpoints as a content-similarity base signal, re-ranked
  and explained by Gemini using your actual watch/rating history.
- Exposes itself as a **Stremio-protocol addon** (`manifest.json` +
  `catalog/*` endpoints) so it can be installed directly into Nuvio,
  Stremio, or any other app that supports generic addons — no app-specific
  integration code needed on the client side.

**What it deliberately does NOT try to do:** replicate Trakt's real
collaborative-filtering recommendation engine, which is built on aggregate
behavior across millions of users. This can't be bootstrapped from one
person's data. The Gemini-based approach here is content-similarity +
LLM reasoning over your own history, not true collaborative filtering —
good enough for real personal use, not a drop-in algorithmic replacement.

## Architecture

```
app/
  main.py          - FastAPI app, routes
  db.py            - SQLite schema + access
  auth.py          - simple API-key auth dependency
  tmdb.py          - TMDB client (similar/recommendations/details)
  recommend.py     - recommendation engine (TMDB base + Gemini re-rank)
  stremio.py       - Stremio addon manifest/catalog formatting
  models.py        - pydantic request/response models
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in TMDB_API_KEY, GOOGLE_API_KEY, NUVIOTRACK_API_KEY
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8420
```

## Endpoints

### Tracking (require `X-API-Key` header)
- `POST /history` — log a watched item `{tmdb_id, media_type, title, watched_at?, rating?}`
- `GET /history` — list watch history
- `POST /ratings` — rate an item `{tmdb_id, media_type, rating}` (1-10)
- `GET /ratings`
- `POST /watchlist` / `DELETE /watchlist/{tmdb_id}` / `GET /watchlist`

### Recommendations
- `GET /recommendations?media_type=movie|tv&limit=20` — personalized, based on history+ratings

### Stremio addon (no auth — this is the public catalog surface)
- `GET /manifest.json`
- `GET /catalog/{type}/nuviotrack-recommended.json`

## License

MIT
