"""Stremio addon protocol surface. This is what makes NuvioTrack installable
as a catalog source in Nuvio (and any other Stremio-protocol client) without
needing any app-specific integration code - confirmed against Nuvio's own
source that it accepts "tmdb:<id>" prefixed catalog item ids natively
(composeApp/src/commonMain/kotlin/com/nuvio/app/DetailsDestinations.kt)."""

MANIFEST = {
    "id": "nl.jdries.nuviotrack",
    "version": "0.1.0",
    "name": "NuvioTrack Recommendations",
    "description": "Self-hosted, open-source personalized recommendations "
    "based on your own watch history and ratings (TMDB similarity + Gemini "
    "personalization). github.com/janibert1/nuvio-track",
    "resources": ["catalog"],
    "types": ["movie", "series"],
    "catalogs": [
        {"type": "movie", "id": "nuviotrack-recommended", "name": "Recommended For You"},
        {"type": "series", "id": "nuviotrack-recommended", "name": "Recommended For You"},
    ],
    "behaviorHints": {"configurable": False},
}

_STREMIO_TYPE = {"movie": "movie", "tv": "series"}
_MEDIA_TYPE_FROM_STREMIO = {"movie": "movie", "series": "tv"}


def to_stremio_type(media_type: str) -> str:
    return _STREMIO_TYPE[media_type]


def from_stremio_type(stremio_type: str) -> str:
    return _MEDIA_TYPE_FROM_STREMIO[stremio_type]


def to_meta_preview(rec: dict) -> dict:
    return {
        "id": f"tmdb:{rec['tmdb_id']}",
        "type": to_stremio_type(rec["media_type"]),
        "name": rec["title"],
        "poster": rec.get("poster_url"),
        "description": rec.get("reason") or rec.get("overview"),
        "releaseInfo": rec.get("year"),
    }
