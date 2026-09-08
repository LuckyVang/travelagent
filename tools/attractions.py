import requests

import config
from tools.rerank import rerank_and_narrow

_RADIUS_URL = "https://api.opentripmap.com/0.1/en/places/radius"

# Exploratory mode casts a wider net (larger radius, lower importance floor, more
# candidates) then narrows/reranks down to a diverse top set. Specific mode stays
# tight and precise since the user already knows roughly what they want.
_MODE_SETTINGS = {
    "specific": {"radius_multiplier": 1, "fetch_limit": 10, "min_rate": 2, "return_limit": 10},
    "exploratory": {"radius_multiplier": 2, "fetch_limit": 25, "min_rate": 1, "return_limit": 5},
}


def search_attractions(lat, lon, radius_m=5000, categories=None, result_mode="specific"):
    """Search points of interest near a coordinate using OpenTripMap."""
    if not config.OPENTRIPMAP_API_KEY:
        return {"error": "OPENTRIPMAP_API_KEY is not configured."}

    settings = _MODE_SETTINGS.get(result_mode, _MODE_SETTINGS["specific"])

    params = {
        "radius": radius_m * settings["radius_multiplier"],
        "lon": lon,
        "lat": lat,
        "limit": settings["fetch_limit"],
        "rate": settings["min_rate"],
        "format": "json",
        "apikey": config.OPENTRIPMAP_API_KEY,
    }
    if categories:
        params["kinds"] = categories

    try:
        resp = requests.get(_RADIUS_URL, params=params, timeout=15)
        if resp.status_code >= 400:
            return {"error": f"OpenTripMap API error {resp.status_code}: {resp.text[:500]}"}
        places = resp.json()
    except requests.RequestException as e:
        return {"error": f"OpenTripMap request failed: {e}"}

    if not places:
        return {"places": [], "note": "No points of interest found near this location."}

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

    narrowed = rerank_and_narrow(results, limit=settings["return_limit"])
    return {"places": narrowed, "candidates_found": len(results)}
