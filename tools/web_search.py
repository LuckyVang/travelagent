import requests

import config

_SEARCH_URL = "https://api.tavily.com/search"


def web_search(query, max_results=5):
    """Search the web (including forums/blogs) via Tavily for subjective or current information
    not covered by the structured attraction/restaurant/weather APIs -- e.g. "hidden gem" spots,
    local recommendations, or general travel advice.
    """
    if not config.TAVILY_API_KEY:
        return {"error": "TAVILY_API_KEY is not configured."}

    try:
        resp = requests.post(
            _SEARCH_URL,
            json={
                "api_key": config.TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
            },
            timeout=20,
        )
        if resp.status_code >= 400:
            return {"error": f"Tavily API error {resp.status_code}: {resp.text[:500]}"}
        data = resp.json()
    except requests.RequestException as e:
        return {"error": f"Tavily request failed: {e}"}

    results = [
        {
            "title": r.get("title"),
            "url": r.get("url"),
            "snippet": r.get("content"),
        }
        for r in data.get("results", [])
    ]
    if not results:
        return {"results": [], "note": "No web results found for this query."}
    return {"results": results}
