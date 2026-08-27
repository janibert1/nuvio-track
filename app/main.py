from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from . import db, recommend, stremio
from .auth import require_api_key
from .models import HistoryIn, RatingIn, WatchlistIn


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="NuvioTrack", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Tracking (authenticated) ----------

@app.post("/history", dependencies=[Depends(require_api_key)])
def post_history(item: HistoryIn):
    db.add_history(item.tmdb_id, item.media_type, item.title, item.season, item.episode, item.watched_at)
    return {"ok": True}


@app.get("/history", dependencies=[Depends(require_api_key)])
def get_history(limit: int = 200):
    return db.list_history(limit=limit)


@app.post("/ratings", dependencies=[Depends(require_api_key)])
def post_rating(item: RatingIn):
    if not 1 <= item.rating <= 10:
        raise HTTPException(400, "rating must be 1-10")
    db.upsert_rating(item.tmdb_id, item.media_type, item.title, item.rating)
    return {"ok": True}


@app.get("/ratings", dependencies=[Depends(require_api_key)])
def get_ratings(min_rating: int = 1):
    return db.list_ratings(min_rating=min_rating)


@app.post("/watchlist", dependencies=[Depends(require_api_key)])
def post_watchlist(item: WatchlistIn):
    db.add_watchlist(item.tmdb_id, item.media_type, item.title)
    return {"ok": True}


@app.delete("/watchlist/{media_type}/{tmdb_id}", dependencies=[Depends(require_api_key)])
def delete_watchlist(media_type: str, tmdb_id: int):
    db.remove_watchlist(tmdb_id, media_type)
    return {"ok": True}


@app.get("/watchlist", dependencies=[Depends(require_api_key)])
def get_watchlist():
    return db.list_watchlist()


# ---------- Recommendations ----------

@app.get("/recommendations", dependencies=[Depends(require_api_key)])
async def get_recommendations(
    media_type: str = Query(..., pattern="^(movie|tv)$"),
    limit: int = 20,
    refresh: bool = False,
):
    return await recommend.get_recommendations(media_type, limit=limit, force_refresh=refresh)


# ---------- Stremio addon surface (public - this is the installable catalog) ----------

@app.get("/manifest.json")
def manifest():
    return JSONResponse(stremio.MANIFEST)


@app.get("/catalog/{stremio_type}/{catalog_id}.json")
async def catalog(stremio_type: str, catalog_id: str):
    if catalog_id != "nuviotrack-recommended" or stremio_type not in ("movie", "series"):
        raise HTTPException(404, "unknown catalog")
    media_type = stremio.from_stremio_type(stremio_type)
    recs = await recommend.get_recommendations(media_type, limit=50)
    return JSONResponse({"metas": [stremio.to_meta_preview(r) for r in recs]})
