import json
import os

MEMORY_PATH = os.path.join(os.path.dirname(__file__), "data", "memory.json")

_DEFAULT = {"preferences": {}, "past_trips": []}


def load_memory():
    if not os.path.exists(MEMORY_PATH):
        return dict(_DEFAULT)
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("preferences", {})
        data.setdefault("past_trips", [])
        return data
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT)


def save_memory(memory):
    os.makedirs(os.path.dirname(MEMORY_PATH), exist_ok=True)
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)


def remember_preference(memory, key, value):
    memory["preferences"][key] = value
    save_memory(memory)
    return memory


def memory_summary(memory):
    if not memory["preferences"] and not memory["past_trips"]:
        return "No stored preferences or past trips yet."
    lines = []
    if memory["preferences"]:
        lines.append("Known user preferences:")
        for k, v in memory["preferences"].items():
            lines.append(f"- {k}: {v}")
    if memory["past_trips"]:
        lines.append("Past trips:")
        for trip in memory["past_trips"]:
            lines.append(f"- {trip}")
    return "\n".join(lines)
