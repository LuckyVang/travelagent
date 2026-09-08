from datetime import date, datetime

import requests

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_MAX_FORECAST_DAYS = 16


def get_weather(lat, lon, start_date, end_date):
    """Get a daily weather forecast for a coordinate and date range via Open-Meteo (free, no key)."""
    notes = []
    try:
        days_out = (datetime.strptime(start_date, "%Y-%m-%d").date() - date.today()).days
        if days_out > _MAX_FORECAST_DAYS:
            notes.append(
                f"Start date is {days_out} days away; Open-Meteo's forecast only covers "
                f"~{_MAX_FORECAST_DAYS} days ahead, so results may be incomplete or unavailable."
            )
    except ValueError:
        return {"error": f"Invalid date format, expected YYYY-MM-DD: {start_date}"}

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "temperature_unit": "fahrenheit",
        "timezone": "auto",
    }

    try:
        resp = requests.get(_FORECAST_URL, params=params, timeout=15)
        if resp.status_code >= 400:
            return {"error": f"Open-Meteo API error {resp.status_code}: {resp.text[:500]}", "notes": notes}
        data = resp.json()
    except requests.RequestException as e:
        return {"error": f"Open-Meteo request failed: {e}", "notes": notes}

    daily = data.get("daily")
    if not daily:
        return {"forecast": [], "notes": notes + ["No forecast data returned for this range."]}

    forecast = [
        {
            "date": d,
            "high_f": daily["temperature_2m_max"][i],
            "low_f": daily["temperature_2m_min"][i],
            "precipitation_mm": daily["precipitation_sum"][i],
        }
        for i, d in enumerate(daily["time"])
    ]
    return {"forecast": forecast, "notes": notes}
