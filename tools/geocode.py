import requests

_OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


def geocode_location(place_name):
    """Resolve a free-text place name into latitude/longitude coordinates using Open-Meteo's free
    geocoding API. (IATA city/airport code lookup is TBD, pending a free flights/hotels API choice.)
    """
    result = {"place_name": place_name, "lat": None, "lon": None}

    try:
        resp = requests.get(
            _OPEN_METEO_GEOCODE_URL,
            params={"name": place_name, "count": 1, "language": "en", "format": "json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        matches = data.get("results") or []
        if matches:
            match = matches[0]
            result["lat"] = match["latitude"]
            result["lon"] = match["longitude"]
            result["resolved_name"] = ", ".join(
                filter(None, [match.get("name"), match.get("admin1"), match.get("country")])
            )
        else:
            result["error"] = f"No coordinates found for '{place_name}'."
    except requests.RequestException as e:
        result["error"] = f"Geocoding request failed: {e}"

    return result
