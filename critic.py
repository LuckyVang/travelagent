import json
import re

from google.genai import types

_CRITIC_PROMPT_TEMPLATE = """You are a strict fact-checker reviewing a travel-planning assistant's draft \
reply before it reaches the user. You are NOT the assistant -- you only verify its work.

User's message:
{user_message}

Tool calls made while producing this reply (this is the ONLY real, verified data available):
{tool_log}

Assistant's draft reply:
{draft_reply}

Check the draft reply for these problems ONLY:
1. It names a specific restaurant, attraction, or place that does NOT appear anywhere in the tool call \
results above (a fabricated/hallucinated recommendation not grounded in real data).
2. It claims to have booked, purchased, reserved, paid for, or confirmed a booking/reservation on the \
user's behalf (this assistant must only search and propose, never book).
3. It states a specific fact (price, hours, rating, weather figure) that isn't supported by any tool \
result and isn't clearly flagged as a general estimate/caveat.

Do not flag stylistic issues, missing details, or anything not covered by rules 1-3 above.

Respond with ONLY a single JSON object, no other text, no markdown code fences:
{{"ok": true, "issues": []}}
or
{{"ok": false, "issues": ["short description of problem 1", "short description of problem 2"]}}
"""


def _format_tool_log(tool_log):
    if not tool_log:
        return "(no tools were called for this reply)"
    lines = []
    for entry in tool_log:
        lines.append(f"- {entry['name']}({entry['args']}) -> {json.dumps(entry['result'])[:4000]}")
    return "\n".join(lines)


def _parse_json_response(text):
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def run_critic(client, model, user_message, draft_reply, tool_log):
    """Run a lightweight, non-blocking fact-check pass over a draft reply. Returns a list of
    issue strings (empty if none found or if the critic call itself fails -- fails open so a
    critic hiccup never blocks the user from getting their answer).
    """
    prompt = _CRITIC_PROMPT_TEMPLATE.format(
        user_message=user_message,
        tool_log=_format_tool_log(tool_log),
        draft_reply=draft_reply,
    )
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            ),
        )
        parsed = _parse_json_response(response.text)
        if not parsed:
            return []
        if parsed.get("ok", True):
            return []
        return list(parsed.get("issues", []))
    except Exception:
        return []
