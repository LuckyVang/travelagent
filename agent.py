import sys

from google import genai
from google.genai import types

import config
import memory as memory_module
from critic import run_critic

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
from tools import (
    geocode_location,
    get_weather,
    save_itinerary,
    search_attractions,
    search_restaurants,
    web_search,
)
from tools.validate import validate_coordinates

SYSTEM_PROMPT_TEMPLATE = """You are a travel-planning assistant. You help the user research and build a \
personalized itinerary using attractions, restaurants, and weather data.

Rules you must always follow:
- You only SEARCH and PROPOSE. You never claim to book, purchase, or reserve anything on the user's \
behalf.
- Flight and hotel search is not yet available (TBD, pending a free API choice) -- if the user asks for \
flights or hotels, tell them clearly that this feature is coming soon and do not invent prices or options.
- Weather forecasts only cover ~16 days ahead. Mention this caveat when relevant.
- Restaurant and attraction data comes from OpenTripMap, which has limited coverage and no live info \
on prices, hours, or ratings -- remind the user to verify details before relying on them.
- NEVER recommend a specific restaurant or attraction by name unless it appeared in a search_restaurants \
or search_attractions tool result in this conversation. Do not fill in gaps with well-known places from \
your own general knowledge, even if they seem like an obvious fit. OpenTripMap has no reliable cuisine \
filter, so if the user asks for a specific cuisine (e.g. "seafood") and no result clearly matches, say so \
plainly and show the actual nearby results you did get instead of substituting known restaurants from memory.
- Ask clarifying questions (destination, dates, budget, party size, interests, dietary restrictions) \
before searching if the user's request is ambiguous or missing key details.
- Use geocode_location first to resolve any place name before calling get_weather, search_attractions, \
or search_restaurants, which need coordinates.
- When the user states a durable preference (e.g. preferred airline, seat type, dietary restriction, \
budget style), call remember_preference to save it for future sessions.

Adaptive retrieval -- classify every request before searching:
- SPECIFIC request: the user already named a fixed destination and knows roughly what they want (e.g. \
"restaurants near the Space Needle", "3-day trip to Denver in June"). Call search_attractions / \
search_restaurants with result_mode="specific" -- tight radius, precise results.
- EXPLORATORY request: the user is open-ended about destination or wants broad options (e.g. "plan me \
a trip somewhere warm", "surprise me", "$2000 trip anywhere in the US"). Call search_attractions / \
search_restaurants with result_mode="exploratory" -- casts a wider net and returns a diversity-reranked \
top set rather than everything found.
- For subjective questions structured APIs can't answer (which spot is more "authentic" or a "hidden \
gem", local recommendations, safety/customs info, or anything time-sensitive like current events), use \
web_search. Only state something as fact from web_search if it actually appeared in the results, and \
mention where it came from (e.g. "according to [source]").

Tree-of-Thought destination branching (only for EXPLORATORY requests with no fixed destination):
- Propose 2-4 candidate destinations ("branches") that plausibly fit the user's stated constraints \
(budget, season, interests, region).
- For EACH candidate, you must actually call geocode_location, get_weather, and search_attractions \
(result_mode="exploratory") for it -- do not evaluate a candidate from general knowledge alone, ground \
every branch in real tool results.
- Prune (drop) any candidate that clearly conflicts with a stated constraint (e.g. bad weather for the \
dates, no attractions matching stated interests).
- Present the surviving best 1-2 candidates to the user with your reasoning, and briefly note which \
candidates you considered and pruned and why. Cap this at 4 candidate branches to keep latency reasonable.
- Saving an itinerary is a strict two-step process across two separate turns:
  1. First, present the complete itinerary as normal chat text, then explicitly ask the user to \
confirm it (e.g. "Would you like me to save this itinerary?"). Do NOT call save_itinerary in this step.
  2. Only in a later turn, after the user explicitly confirms that exact itinerary (e.g. "yes", "save \
it", "looks good"), call save_itinerary. The content_markdown you pass must be the same itinerary you \
already showed the user -- never invent or draft a new itinerary at save time.
- If the user asks you to save before you have presented a complete itinerary in this conversation, tell \
them there's nothing finished to save yet, and continue gathering details or planning instead of saving \
anything.

Autonomy level -- infer this from how much detail the user's request already contains (don't ask which \
mode to use; judge it yourself each turn):
- FULLY AUTONOMOUS: the user gave very few constraints (e.g. "surprise me", "plan me a trip", no \
destination/dates specified). You have broad latitude to decide destination, dates, and activities \
yourself (grounded in real tool calls, using the Tree-of-Thought branching above where it's an open-ended \
destination choice). Briefly note that you're filling in the blanks since they didn't specify.
- PARTIALLY RESTRICTED: the user gave some constraints (e.g. a region, season, or budget) but left other \
details open. Strictly respect every constraint they did give, and use your own judgment to fill in \
anything they didn't specify without needing to ask about each gap.
- FULLY DETAILED: the user specified most/all key details (destination, dates, party size, etc.). Do \
NOT override or second-guess anything they explicitly stated. For anything they left unspecified, ask \
before deciding it yourself rather than assuming -- at this level of detail, the user wants control, not \
surprises.

Known context from previous sessions:
{memory_summary}
"""


def build_system_prompt(memory):
    return SYSTEM_PROMPT_TEMPLATE.format(memory_summary=memory_module.memory_summary(memory))


def geocode_location_tool(place_name: str) -> dict:
    """Resolve a free-text place name (city, region, landmark) into latitude/longitude coordinates.
    Call this first for any place mentioned by the user before calling get_weather or search_attractions.

    Args:
        place_name: Free-text place name, e.g. 'Seattle, WA'.
    """
    print(f"  [calling tool: geocode_location({place_name!r})]")
    return geocode_location(place_name)


def search_attractions_tool(
    lat: float,
    lon: float,
    radius_m: int = 5000,
    categories: str = "",
    result_mode: str = "specific",
) -> dict:
    """Search points of interest (attractions, sights) near a coordinate using OpenTripMap.

    Args:
        lat: Latitude.
        lon: Longitude.
        radius_m: Search radius in meters.
        categories: Optional OpenTripMap category filter, e.g. 'interesting_places,foods'. Empty for all.
        result_mode: 'specific' for a tight, precise search, or 'exploratory' to cast a wider net and
            return a diversity-reranked top set. See the adaptive retrieval rules in your instructions.
    """
    print(f"  [calling tool: search_attractions(lat={lat}, lon={lon}, radius_m={radius_m}, mode={result_mode})]")
    error = validate_coordinates(lat, lon)
    if error:
        print(f"  [rejected: {error}]")
        return {"error": error}
    return search_attractions(lat, lon, radius_m, categories or None, result_mode)


def search_restaurants_tool(
    lat: float,
    lon: float,
    radius_m: int = 3000,
    cuisine: str = "",
    result_mode: str = "specific",
) -> dict:
    """Search restaurants, cafes, and other eateries near a coordinate using OpenTripMap.

    Args:
        lat: Latitude.
        lon: Longitude.
        radius_m: Search radius in meters.
        cuisine: Optional OpenTripMap food-category filter, e.g. 'cafes', 'fast_food', 'bars'.
            Leave empty to search all food-related places.
        result_mode: 'specific' for a tight, precise search, or 'exploratory' to cast a wider net and
            return a diversity-reranked top set. See the adaptive retrieval rules in your instructions.
    """
    print(f"  [calling tool: search_restaurants(lat={lat}, lon={lon}, radius_m={radius_m}, mode={result_mode})]")
    error = validate_coordinates(lat, lon)
    if error:
        print(f"  [rejected: {error}]")
        return {"error": error}
    return search_restaurants(lat, lon, radius_m, cuisine or None, result_mode)


def web_search_tool(query: str, max_results: int = 5) -> dict:
    """Search the web (including forums/blogs) for subjective or current information not covered by
    the structured attraction/restaurant/weather APIs, e.g. "hidden gem" spots, local recommendations,
    or general travel advice. Only state something as fact if it actually appeared in the results.

    Args:
        query: The search query.
        max_results: Maximum number of results to return.
    """
    print(f"  [calling tool: web_search({query!r})]")
    return web_search(query, max_results)


def get_weather_tool(lat: float, lon: float, start_date: str, end_date: str) -> dict:
    """Get a daily weather forecast (high/low temp, precipitation) for a coordinate and date range.
    Forecasts only cover roughly the next 16 days.

    Args:
        lat: Latitude.
        lon: Longitude.
        start_date: Start date as YYYY-MM-DD.
        end_date: End date as YYYY-MM-DD.
    """
    print(f"  [calling tool: get_weather(lat={lat}, lon={lon}, {start_date} to {end_date})]")
    error = validate_coordinates(lat, lon)
    if error:
        print(f"  [rejected: {error}]")
        return {"error": error}
    return get_weather(lat, lon, start_date, end_date)


def save_itinerary_tool(title: str, content_markdown: str) -> dict:
    """Save a user-confirmed itinerary as a markdown file under outputs/. Only call this after the
    user has explicitly confirmed the itinerary -- never for unconfirmed drafts.

    Args:
        title: Short trip title, e.g. 'Seattle Hiking & Coffee Trip'. Used to name the file.
        content_markdown: The full itinerary, formatted as markdown.
    """
    print(f"  [calling tool: save_itinerary({title!r})]")
    result = save_itinerary(title, content_markdown)
    print(f"  [itinerary saved to {result.get('path')}]")
    return result


def make_remember_preference_tool(memory):
    def remember_preference_tool(key: str, value: str) -> dict:
        """Persist a durable user preference (e.g. preferred airline, seat type, budget style, dietary
        need) to local memory so it's recalled in future sessions. Only for durable preferences, not
        one-off trip details.

        Args:
            key: Short preference name, e.g. 'seat_preference'.
            value: The preference value, e.g. 'aisle seat'.
        """
        print(f"  [calling tool: remember_preference({key!r}, {value!r})]")
        memory_module.remember_preference(memory, key, value)
        return {"status": "saved", "key": key, "value": value}

    return remember_preference_tool


def build_tools(memory):
    return [
        geocode_location_tool,
        search_attractions_tool,
        search_restaurants_tool,
        get_weather_tool,
        web_search_tool,
        save_itinerary_tool,
        make_remember_preference_tool(memory),
    ]


def create_client():
    return genai.Client(api_key=config.GEMINI_API_KEY)


def create_chat(client, memory):
    return client.chats.create(
        model=config.MODEL,
        config=types.GenerateContentConfig(
            system_instruction=build_system_prompt(memory),
            tools=build_tools(memory),
        ),
    )


def _extract_tool_log(history, start_index):
    """Pull the (name, args, result) of every tool call made since `start_index` in the chat
    history, by pairing function_call parts with the function_response parts that follow them.
    """
    calls = []
    responses = []
    for content in history[start_index:]:
        for part in content.parts:
            if part.function_call is not None:
                calls.append({"name": part.function_call.name, "args": dict(part.function_call.args or {})})
            if part.function_response is not None:
                responses.append(part.function_response.response)

    tool_log = []
    for call, response in zip(calls, responses):
        tool_log.append({"name": call["name"], "args": call["args"], "result": response})
    return tool_log


def send_and_verify(client, chat, user_input):
    """Send a message, then run a non-blocking critic pass over the draft reply using the real
    tool results gathered this turn. Returns (reply_text, issues, tool_log).
    """
    history_len_before = len(chat.get_history())
    response = chat.send_message(user_input)
    tool_log = _extract_tool_log(chat.get_history(), history_len_before)

    issues = run_critic(client, config.MODEL, user_input, response.text, tool_log)
    return response.text, issues, tool_log


PRESESSION_QUESTIONS = [
    ("destination", "Where would you like to go? (leave blank if you're open to suggestions)"),
    ("dates", "What dates or timeframe are you thinking? (leave blank if unsure)"),
    ("budget", "Roughly what's your budget? (leave blank if none)"),
    ("party_size", "How many people are traveling? (leave blank if just you)"),
    ("interests", "What are you interested in? (e.g. hiking, coffee, museums, relaxation)"),
    ("dietary", "Any dietary restrictions? (leave blank if none)"),
]


def run_presession_form():
    """Ask a short set of basic questions up front (checkpoint 1.1's presession form) so the
    agent has a baseline before free-form chat starts. Any question can be left blank -- a
    mostly-blank form is itself a signal for fully-autonomous mode.
    """
    print("Before we start, a few quick questions (press Enter to skip any of them):\n")
    answers = {}
    for key, prompt_text in PRESESSION_QUESTIONS:
        value = input(f"  {prompt_text}\n  > ").strip()
        if value:
            answers[key] = value
    print()
    return answers


def format_presession_message(answers):
    if not answers:
        return (
            "I didn't provide any trip details up front -- I'm open to whatever you'd suggest. "
            "Surprise me!"
        )
    lines = ["Here's what I have in mind for this trip so far:"]
    labels = dict(PRESESSION_QUESTIONS)
    for key, value in answers.items():
        lines.append(f"- {labels[key].split('(')[0].strip().rstrip('?')}: {value}")
    lines.append("Please help me plan based on this.")
    return "\n".join(lines)


def _send_and_print(client, chat, user_input):
    try:
        reply_text, issues, tool_log = send_and_verify(client, chat, user_input)
        if issues:
            print("  [critic flagged issues: " + "; ".join(issues) + "]")
            reply_text += (
                "\n\n[Verification notice] An automated fact-check flagged possible issues with "
                "this reply (" + "; ".join(issues) + "). Please double-check before relying on it."
            )
        print(f"\nAgent: {reply_text}\n")
        return tool_log
    except Exception as e:
        print(f"\nAgent error: {e}\n")
        return []


def chat_loop():
    missing = config.missing_keys()
    if missing:
        print(f"Warning: missing environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in your free API keys before continuing.\n")
    if not config.GEMINI_API_KEY:
        print("Cannot start without GEMINI_API_KEY. Exiting.")
        return

    client = create_client()
    memory = memory_module.load_memory()
    chat = create_chat(client, memory)

    print("=== Travel Planning Agent (MVP) ===")
    print("This agent searches attractions, restaurants, and weather to help plan a trip.")
    print("Flight/hotel search is TBD (not yet available).")
    print("It never books anything -- always verify and book directly with the provider.")
    print("Type 'exit' or 'quit' at any point to leave.\n")

    try:
        presession_answers = run_presession_form()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye!")
        memory_module.save_memory(memory)
        return

    _send_and_print(client, chat, format_presession_message(presession_answers))

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        _send_and_print(client, chat, user_input)

    memory_module.save_memory(memory)


if __name__ == "__main__":
    chat_loop()
