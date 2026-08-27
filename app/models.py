from typing import Literal, Optional

from pydantic import BaseModel


class HistoryIn(BaseModel):
    tmdb_id: int
    media_type: Literal["movie", "tv"]
    title: str
    season: Optional[int] = None
    episode: Optional[int] = None
    watched_at: Optional[int] = None  # unix seconds; defaults to now


class RatingIn(BaseModel):
    tmdb_id: int
    media_type: Literal["movie", "tv"]
    title: str
    rating: int  # 1-10


class WatchlistIn(BaseModel):
    tmdb_id: int
    media_type: Literal["movie", "tv"]
    title: str
