"""Real coordinate lookup — deterministic code, not an LLM guess.

The Geolocator agent only names a PLACE (e.g. "Sidi Fredj, Algeria"); an LLM recalling
lat/lng from memory is accurate for famous cities but silently collapses smaller/specific
sites to "the nearest big place it remembers" (verified live: it placed the Sidi Fredj
landing at Algiers' own coordinates, 15km off). A real geocoder looks the name up instead
of recalling it — same principle as the Fetcher being code, not judgment.
"""
from __future__ import annotations

import time
from typing import Optional, Protocol

from .schema import Location


class GeocodeClient(Protocol):
    def lookup(self, place: str) -> Optional[Location]:
        ...


class NominatimGeocode:
    """OpenStreetMap's free geocoder. No API key. Usage policy caps requests at ~1/sec
    and requires a descriptive User-Agent — both honored here."""

    _URL = "https://nominatim.openstreetmap.org/search"

    def __init__(self, min_interval: float = 1.0):
        self._min_interval = min_interval
        self._last_call = 0.0

    def lookup(self, place: str) -> Optional[Location]:
        if not place or not place.strip():
            return None
        import httpx

        wait = self._min_interval - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()

        try:
            resp = httpx.get(
                self._URL,
                params={"q": place, "format": "json", "limit": 1},
                headers={"User-Agent": "conflict-atlas-ai-updater/1.0"},
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json()
        except Exception:
            return None
        if not results:
            return None
        r = results[0]
        try:
            return Location(lat=float(r["lat"]), lng=float(r["lon"]), label=place)
        except (KeyError, ValueError, TypeError):
            return None


class NullGeocode:
    """No-op backend — geocoding disabled, the LLM's own guess (if any) is kept as-is."""

    def lookup(self, place: str) -> Optional[Location]:
        return None


def get_geocode(settings) -> GeocodeClient:
    if getattr(settings, "geocode_backend", "nominatim") == "nominatim":
        return NominatimGeocode()
    return NullGeocode()
