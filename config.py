import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENTRIPMAP_API_KEY = os.environ.get("OPENTRIPMAP_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

# TBD: flight/hotel search API not yet integrated (Amadeus removed).

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")

REQUIRED_KEYS = {
    "GEMINI_API_KEY": GEMINI_API_KEY,
    "OPENTRIPMAP_API_KEY": OPENTRIPMAP_API_KEY,
    "TAVILY_API_KEY": TAVILY_API_KEY,
}


def missing_keys():
    return [name for name, value in REQUIRED_KEYS.items() if not value]
