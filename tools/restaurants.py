import requests

import config
from tools.rerank import rerank_and_narrow

_RADIUS_URL = "https://api.opentripmap.com/0.1/en/places/radius"

_DEFAULT_KINDS = "foods"

# See tools/attractions.py for the rationale behind these two modes.
_MODE_SETTINGS = {
    "specific": {"radius_multiplier": 1, "fetch_limit": 10, "return_limit": 10},
    "exploratory": {"radius_multiplier": 2, "fetch_limit": 25, "return_limit": 5},
}


def search_restaurants(lat, lon, radius_m=3000, cuisine=None, result_mode="specific"):
    """Search restaurants/cafes/eateries near a coordinate using OpenTripMap's 'foods' category."""
    if not config.OPENTRIPMAP_API_KEY:
        return {"error": "OPENTRIPMAP_API_KEY is not configured."}

    settings = _MODE_SETTINGS.get(result_mode, _MODE_SETTINGS["specific"])

    params = {
        "radius": radius_m * settings["radius_multiplier"],
        "lon": lon,
        "lat": lat,
        "kinds": cuisine or _DEFAULT_KINDS,
        "limit": settings["fetch_limit"],
        "rate": 1,
        "format": "json",
        "apikey": config.OPENTRIPMAP_API_KEY,
    }

    try:
        resp = requests.get(_RADIUS_URL, params=params, timeout=15)
        if resp.status_code >= 400:
            return {"error": f"OpenTripMap API error {resp.status_code}: {resp.text[:500]}"}
        places = resp.json()
    except requests.RequestException as e:
        return {"error": f"OpenTripMap request failed: {e}"}

    if not places:
        return {"restaurants": [], "note": "No restaurants found near this location."}

    results = [
        {
            "name": p.get("name") or "(unnamed)",
            "kinds": p.get("kinds"),
            "distance_m": round(p.get("dist", 0)),
            "rate": p.get("rate", 0),
            "xid": p.get("xid"),
        }
        for p in places
        if p.get("name")
    ]
    if not results:
        return {
            "restaurants": [],
            "note": "Places were found nearby but none had names in OpenTripMap's data.",
        }

    narrowed = rerank_and_narrow(results, limit=settings["return_limit"])
    return {"restaurants": narrowed, "candidates_found": len(results)}
