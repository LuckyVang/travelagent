# Feature Status

Tracks the full capstone design (`docs/` checkpoints 1.1–6.1) against what's actually
implemented in this codebase today. Status values: ✅ Done, 🚧 Partial, ❌ Not started.
For action items that require your input rather than code (API sign-ups, decisions), see
[TODO.md](TODO.md).

## Core planning capabilities

| Feature | Status | Notes |
|---|---|---|
| Chat-based trip planning agent | ✅ Done | `agent.py`, Gemini (`gemini-flash-lite-latest`), ReAct-style tool-calling loop. |
| Geocoding (place name → coordinates) | ✅ Done | `tools/geocode.py`, Open-Meteo geocoding (free, no key). |
| Weather forecast | ✅ Done | `tools/weather.py`, Open-Meteo (free, no key). Limited to ~16 days ahead. |
| Attractions / POI search | ✅ Done | `tools/attractions.py`, OpenTripMap (free tier, single direct radius query). |
| Restaurant search | ✅ Done | `tools/restaurants.py`, OpenTripMap `foods` category. No dedicated restaurants *agent* yet (checkpoint 5.1) — folded into the single agent; no dietary-restriction filtering or cuisine precision (OpenTripMap has no reliable cuisine filter). |
| Flight search | ❌ Not started | Was Amadeus (free test tier); removed. `.env.example` has a `FLIGHTS_HOTELS_API_KEY` TBD placeholder — needs a free API decision. |
| Hotel search | ❌ Not started | Same as flights — TBD, no free API chosen yet. |
| Itinerary confirm-then-save | ✅ Done | `tools/save_itinerary.py`. Agent must present the itinerary as chat text and get explicit user confirmation in a later turn before saving; saved as markdown under `outputs/`. |
| User preference memory | 🚧 Partial | `memory.py`, flat key/value JSON persisted across runs (e.g. "likes hiking"). Design (checkpoint 2.1) also wants episodic recall of past trip *conversations*, not just static preferences. |
| Presession structured form | ✅ Done | `agent.py`'s `run_presession_form()`: asks 6 basic questions (destination, dates, budget, party size, interests, dietary restrictions) before free-form chat starts; every question can be skipped with Enter. Answers are synthesized into the first turn sent to the agent (`format_presession_message`), which then reasons over them normally (adaptive retrieval, ToT, autonomy inference, critic all apply to this first turn too). Skipping every question triggers the same "surprise me" path as fully-autonomous mode. Verified end-to-end both with answers filled in and with everything skipped. |

## Reasoning & retrieval architecture (checkpoints 2.1–4.1)

| Feature | Status | Notes |
|---|---|---|
| ReAct loop (reason → act → observe) | ✅ Done | Handled implicitly by Gemini's automatic function calling in `agent.py`. |
| Tree-of-Thought reasoning for exploratory requests | 🚧 Partial (lite version) | Prompt-driven, single-layer branching: for open-ended requests with no fixed destination, the agent proposes 2-4 candidate destinations, grounds each in real geocode/weather/attractions tool calls, prunes ones that conflict with stated constraints, and presents the survivor(s) with reasoning. No deeper per-day/activity branching layer, and no code-level tree/search data structure — it's the model's own multi-branch tool-calling, guided by the system prompt rather than an external orchestrator. Verified working (San Diego/Miami/Honolulu test case: all 3 branches grounded in real tool calls, Miami pruned, restaurant names in the final itinerary all traced back to actual API results). |
| Adaptive retrieval (specific vs. exploratory queries) | ✅ Done | The LLM classifies each request inline (per system prompt) and passes `result_mode="specific"` or `"exploratory"` to `search_attractions`/`search_restaurants`. Specific mode: tight radius, ~10 results, no narrowing. Exploratory mode: 2x radius, up to 25 candidates fetched, then reranked/narrowed to top 5. Verified both modes fire correctly in testing. |
| Web/forum retrieval (Reddit, travel blogs) for subjective quality signals | ✅ Done | `tools/web_search.py` via Tavily's free tier (needs a `TAVILY_API_KEY` — not yet supplied, tool degrades gracefully with an error message when missing). System prompt restricts the agent to only state web-search facts that actually appeared in results, and to cite the source. |
| Reranking / narrowing search results | ✅ Done | `tools/rerank.py`: sorts by OpenTripMap's `rate` (importance) field, then applies a per-category cap (max 2 of the same primary "kind") before filling remaining slots, so exploratory results aren't all one category. Used by both `search_attractions` and `search_restaurants` in exploratory mode. |

## Multi-agent architecture (checkpoint 5.1)

| Feature | Status | Notes |
|---|---|---|
| Single agent (MVP baseline) | ✅ Done | Deliberate scope choice for the MVP — one agent, one model, all tools. |
| Travel-arrangement agent (flights/hotels/cars) | ❌ Not started | Depends on flights/hotels API decision above. |
| Attractions agent | ❌ Not started | Currently folded into the single agent, not a separate specialized agent. |
| Restaurants agent | ❌ Not started | Restaurant *search tool* exists (`tools/restaurants.py`), but it's used by the single agent, not a separate specialized agent. |
| Hybrid sequential/graph-based agent coordination | ❌ Not started | No multi-agent orchestration exists yet (no CrewAI/LangChain/MCP layer). |

## Safety, evaluation, and autonomy (checkpoint 6.1)

| Feature | Status | Notes |
|---|---|---|
| No booking/purchase capability | ✅ Done | By design — no booking action exists anywhere in the codebase. System prompt reinforces search/propose-only behavior. |
| Critic / verification agent (double-checks outputs) | ✅ Done (lite version) | `critic.py`: after every reply, a second lightweight Gemini call (`run_critic`) checks the draft against the actual tool results from that turn and flags (a) place names not present in any tool result, (b) booking/purchase claims, (c) unsupported specific facts (price/hours/rating). Non-blocking (flag-only, per your direction) — a visible `[Verification notice]` is appended to the reply rather than forcing a revision loop. Verified catching a deliberately fabricated restaurant + fake booking claim in testing, and — unprompted — caught a real cross-branch hallucination during a live ToT run (the model borrowed a coffee shop name from a pruned candidate destination's tool results and misapplied it to the winning destination). Not a fully separate agent process — it's a second model call sharing the same client, and it fails open (no issues reported) if the critic call itself errors. |
| Three autonomy modes (fully autonomous / partially restricted / fully detailed) | ✅ Done (prompt-inferred) | System prompt instructs the agent to infer the mode from how much detail the user's request already contains (no explicit mode-selection UI), matching the design doc's actual framing. Verified: a vague "surprise me with a trip somewhere" request triggered fully-autonomous behavior (agent picked and branched over its own candidate destinations). Not independently tested against the partially-restricted and fully-detailed cases yet — no code-level enforcement exists, it's prompt-driven, so behavior isn't guaranteed as strictly as a hard-coded mode would be. |
| Evaluation harness (accuracy, robustness, calibration, bias, fairness, toxicity, efficiency) | 🚧 Partial (by design) | `eval/run_eval.py` (`python -m eval.run_eval`) automates 4 of the 7: groundedness/accuracy (reuses the critic pass — 0 issues = pass), safety (regex scan for booking-confirmation language), robustness (garbled/contradictory input must not crash), and efficiency (latency + tool-call count, reported not gated). Verified all 3 scenarios pass; robustness run also surfaced a real model reasoning slip (swapped lat/lon in one tool call) that didn't crash anything but is worth knowing about. Bias, fairness, toxicity, and calibration are intentionally NOT automated — they need labeled adversarial datasets and/or human judgment to produce a meaningful signal, which wasn't a fit for a free bare-minimum script; faking a pass/fail for them would be worse than admitting they're unaddressed. |
| Tool access restricted to search only (no purchasing tools exposed) | ✅ Done | Only search/geocode/weather/save/remember/web-search tools are exposed to the model; nothing purchase-capable exists to call. |
| Groundedness guardrail (no fabricated restaurant/attraction names) | ✅ Done | Two layers now: (1) prompt-level rule — agent must only name places that appeared in an actual tool result, and must say so plainly when nothing matches rather than substituting from training data; (2) the critic pass above independently re-checks this after the fact and has caught real violations in testing. |

## Engineering / polish

| Item | Status | Notes |
|---|---|---|
| Graceful handling of missing API keys | ✅ Done | `config.missing_keys()`, exits cleanly with a message instead of crashing. |
| `.env` / `.env.example` set up for Gemini + OpenTripMap + Tavily | 🚧 Partial | `TAVILY_API_KEY` field exists but is empty — sign up at tavily.com to enable web search. |
| README with setup instructions | ✅ Done | |
| Automated tests | 🚧 Partial | `eval/run_eval.py` covers 3 scripted scenarios (see above); no unit tests for individual tool functions yet. |
| Windows console encoding safety | ✅ Done | `agent.py` reconfigures stdout to UTF-8 on startup after a real crash was found: printing a non-cp1252 character (an emoji in a verification notice) raised `UnicodeEncodeError` and killed the CLI mid-conversation. |
| Coordinate validation guardrail (lat/lon mix-ups) | ✅ Fixed | `tools/validate.py`'s `validate_coordinates()` now runs before every `search_attractions`/`search_restaurants`/`get_weather` call in `agent.py`. It rejects out-of-range values and, specifically, `lat == lon` (the exact failure mode observed in testing, where the model copied latitude into the longitude slot while comparing candidate destinations) — the tool returns a clear error telling the model to re-call `geocode_location` instead of silently searching the wrong spot. What was previously logged as two separate issues ("coordinate sign dropped in print" and "occasional lat/lon mix-up") turned out to be the same root cause: the model passing a wrong coordinate value, not a print formatting bug. Verified the validator directly rejects a duplicated lat/lon pair and out-of-range values; the live model-reproduction case is nondeterministic so it wasn't re-triggered on demand, but the guardrail is unit-verified and will catch it whenever it recurs. |
