from tools.attractions import search_attractions
from tools.geocode import geocode_location
from tools.restaurants import search_restaurants
from tools.save_itinerary import save_itinerary
from tools.weather import get_weather
from tools.web_search import web_search

# TBD: flight/hotel search tools removed (Amadeus dropped). Add back once a free
# flights/hotels API is chosen -- see FLIGHTS_HOTELS_API_KEY placeholder in .env.example.

__all__ = [
    "geocode_location",
    "search_attractions",
    "search_restaurants",
    "get_weather",
    "save_itinerary",
    "web_search",
]
