# Travel Planning Agent

A single Gemini-powered agent that researches real attractions, restaurants, and weather —
and web sources for anything a structured API can't answer — then proposes a personalized
trip itinerary. It only searches and proposes; it never books or purchases anything, and
every reply is fact-checked by a second, non-blocking critic pass before it reaches you.

This is a bare-minimum-viable build of a larger multi-agent travel-planning design (see
`docs/` for the original capstone checkpoints). It runs entirely on free-tier APIs and
establishes the core reasoning loop before adding full multi-agent orchestration, flight/hotel
search, or deeper Tree-of-Thought planning. See [`FEATURES.md`](FEATURES.md) for a detailed,
honest status of every feature against the original design, and [`TODO.md`](TODO.md) for the
handful of things that need a human (API sign-ups, decisions) rather than code.

## The problem

Planning a trip today means hours of scattered research — flight sites, hotel listings, review
blogs, weather forecasts — followed by manually checking that everything actually fits together
(does the hotel's dates match the flight? is it raining on the day you planned to hike?). This
agent is for travelers who want a researched, grounded itinerary without doing all of that
research themselves.

## What it does — and deliberately doesn't

- ✅ Researches attractions, restaurants, and weather for one or more candidate destinations
- ✅ Proposes a day-by-day itinerary, grounded in real tool results
- ✅ Remembers durable preferences (e.g. "I like hiking") across runs
- ✅ Saves an itinerary to a file, but only after you've seen it and confirmed it
- ❌ **Never books, purchases, or reserves anything.** No such tool exists in the codebase —
  this is an architectural guarantee, not a prompt instruction the model could ignore.
- ❌ Doesn't search flights or hotels yet (see [Limitations](#limitations--roadmap))

## Architecture

A single agent (not the three-agent split from the original design — see `FEATURES.md`) built
around Google Gemini's automatic function-calling loop: a ReAct-style reason → act → observe
cycle. One turn looks like this:

```
 You ──► Presession form (first turn only)
              │
              ▼
        ┌───────────────────────────────────────────────┐
        │  Agent  (gemini-flash-lite-latest)             │
        │  reasons, then calls tools as needed           │
        └───────────────────────────────────────────────┘
              │                              ▲
              ▼                              │ tool results
        ┌───────────────────────────────────────────────┐
        │  Tools                                         │
        │  geocode_location · get_weather                │
        │  search_attractions · search_restaurants       │
        │  web_search · save_itinerary                   │
        │  remember_preference                           │
        └───────────────────────────────────────────────┘
              │
              ▼
        ┌───────────────────────────────────────────────┐
        │  Critic pass (critic.py)                       │
        │  independent model call fact-checks the draft  │
        │  against this turn's real tool results         │
        └───────────────────────────────────────────────┘
              │
              ▼
        Reply (+ visible notice if the critic found an issue)
```

**Key reasoning behaviors, layered on top of the base loop:**

- **Adaptive retrieval** — the agent classifies each request as *specific* (fixed destination,
  tight/precise search) or *exploratory* (open-ended, broader search + reranked/diversity-capped
  results) and passes that mode to the search tools itself.
- **Tree-of-Thought (lite)** — for open-ended requests with no fixed destination, the agent
  proposes a few candidate destinations, grounds *each one* in real geocode/weather/attraction
  tool calls (never evaluated from general knowledge alone), prunes candidates that conflict with
  your stated constraints, and presents the best surviving option(s) with its reasoning.
- **Inferred autonomy level** — judged from how much detail your request already contains: a
  vague ask ("surprise me") gives the agent latitude to decide destination/dates itself; a
  detailed ask means it won't override anything you specified, and will ask before filling gaps.
- **Critic pass** (`critic.py`) — a second, independent Gemini call checks the draft reply
  against the real tool results gathered that turn, and flags (non-blocking) any place name that
  wasn't actually returned by a tool, or any claim of having booked/purchased something.
- **Coordinate validation** (`tools/validate.py`) — rejects malformed or duplicated lat/lon
  values before they reach an external API, catching a real failure mode where the model copied
  one coordinate into both arguments.

### Free APIs used

| Purpose | Provider | Key required? |
|---|---|---|
| Weather forecast + geocoding | [Open-Meteo](https://open-meteo.com/) | No |
| Attractions & restaurants | [OpenTripMap](https://opentripmap.io/) | Yes (free) |
| Web/forum search | [Tavily](https://tavily.com/) | Yes (free tier) |
| Reasoning model | [Google Gemini](https://ai.google.dev/) | Yes (free tier) |

### Project structure

```
agent.py          CLI entry point: chat loop, presession form, tool wrappers, system prompt
config.py         Loads API keys and settings from .env
memory.py         Load/save data/memory.json (persisted user preferences)
critic.py         Independent fact-checking pass over each draft reply
tools/
  geocode.py        Place name → lat/lon (Open-Meteo)
  weather.py         Daily forecast (Open-Meteo)
  attractions.py       Attraction search (OpenTripMap) + adaptive mode
  restaurants.py        Restaurant search (OpenTripMap) + adaptive mode
  rerank.py              Diversity-aware narrowing for exploratory search results
  web_search.py           Web/forum search (Tavily)
  save_itinerary.py        Writes a confirmed itinerary to outputs/
  validate.py               Lat/lon sanity checks
eval/
  run_eval.py        Automated evaluation harness (see Evaluation below)
data/memory.json    Persisted user preferences (created at runtime, gitignored)
outputs/            Saved itineraries, one markdown file per confirmed trip (gitignored)
docs/               Original capstone design checkpoints (the aspirational full design)
FEATURES.md         Status of every designed feature vs. what's actually built
TODO.md             Action items that need you (API sign-ups, decisions)
```

## Setup

1. **Get free API keys:**
   - **Google Gemini**: https://aistudio.google.com/apikey — create a free API key.
   - **OpenTripMap** (attractions/restaurants): https://opentripmap.io/product — sign up for a
     free API key.
   - **Tavily** (web/forum search): https://tavily.com/ — sign up for a free API key.
   - Weather and geocoding use Open-Meteo, which needs no key at all.

2. **Configure environment:**
   ```bash
   cp .env.example .env
   ```
   Fill in `GEMINI_API_KEY`, `OPENTRIPMAP_API_KEY`, and `TAVILY_API_KEY` in `.env`.

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the agent:

```bash
python agent.py
```

It opens with a short presession form — destination, dates, budget, party size, interests,
dietary restrictions — and every question can be skipped by pressing Enter. Leaving everything
blank tells the agent you're open to suggestions, which puts it in fully-autonomous mode.

```
=== Travel Planning Agent (MVP) ===
...
Before we start, a few quick questions (press Enter to skip any of them):

  Where would you like to go? (leave blank if you're open to suggestions)
  > Seattle, WA
  What dates or timeframe are you thinking? (leave blank if unsure)
  > Sept 20-22 2026
  ...

Agent: Here is a 3-day weekend itinerary tailored to your interests in hiking and coffee...
...
Would you like me to save this itinerary?

You: yes, save it
Agent: I have successfully saved your itinerary! You can find it in outputs/.
```

From there it's a normal chat — ask follow-up questions, ask it to adjust the plan, or start
over with a new request. Type `exit` or `quit` to leave; your stated preferences are saved to
`data/memory.json` and picked back up next time you run it.

### Evaluation

```bash
python -m eval.run_eval
```

Runs a small automated harness covering four of the seven metrics named in the course's
evaluation framework:

- **Groundedness/accuracy** — reuses the critic pass; a scenario passes if the critic finds zero
  issues.
- **Safety** — regex scan of the reply for booking/purchase-confirmation language.
- **Robustness** — garbled or contradictory input must not crash the agent.
- **Efficiency** — latency and tool-call count per scenario, reported rather than gated.

Bias, fairness, toxicity, and calibration are **intentionally not automated** — producing a
meaningful signal for them needs labeled adversarial datasets and/or human judgment, which
wasn't achievable in a free, bare-minimum script. See `FEATURES.md` for the full reasoning.

## Limitations & roadmap

- Flight and hotel search are not implemented yet — an earlier Amadeus free-tier prototype was
  removed; see `TODO.md` for picking a replacement.
- Single agent rather than the three-agent (travel arrangement / attractions / restaurants)
  architecture from the original design.
- Tree-of-Thought only branches one layer deep, over candidate destinations — not per-day or
  per-activity.
- Memory is flat user preferences, not episodic recall of past trip conversations.
- Weather forecasts (Open-Meteo) only cover roughly the next 16 days.

Full detail, including every deliberate scope trade-off and every bug found and fixed along the
way, is in [`FEATURES.md`](FEATURES.md).
