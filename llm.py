"""Thin wrapper around the Claude API, using only Python's standard library.

It calls the Messages API over plain HTTPS, so there are no add-on packages to
install (some Windows security policies block the compiled parts of add-ons).

Every call is logged (tokens and cost) to logs/usage.csv, and a running total is
kept in TOTALS so a script can report what a whole session or test run cost.
"""
import csv
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

import config

API_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com") + "/v1/messages"
API_VERSION = "2023-06-01"
TOTALS = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}


class ApiError(RuntimeError):
    """Raised when the API cannot be reached or rejects a request."""


def reset_totals():
    TOTALS.update({"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})


def cost_usd(model, input_tokens, output_tokens):
    price = config.PRICES.get(model)
    if not price:
        return 0.0
    return input_tokens / 1_000_000 * price["input"] + output_tokens / 1_000_000 * price["output"]


def _error_message(body):
    try:
        return json.loads(body)["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return body[:300]


def _post(payload):
    # The key comes from the environment. It is never stored in this project.
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ApiError("ANTHROPIC_API_KEY is not set. Set it with setx, then open a new Command Prompt.")
    request = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"x-api-key": key, "anthropic-version": API_VERSION,
                 "content-type": "application/json"})
    delay = 2
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503, 529) and attempt < 3:
                time.sleep(delay)
                delay *= 2
                continue
            raise ApiError(f"API error {e.code}: {_error_message(body)}") from None
        except urllib.error.URLError as e:
            if attempt < 3:
                time.sleep(delay)
                delay *= 2
                continue
            raise ApiError(f"Could not reach the API: {e.reason}") from None


def _log(label, model, input_tokens, output_tokens, cost):
    config.LOG_DIR.mkdir(exist_ok=True)
    path = config.LOG_DIR / "usage.csv"
    new_file = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["time", "label", "model", "input_tokens", "output_tokens", "cost_usd"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"), label, model,
                         input_tokens, output_tokens, f"{cost:.6f}"])


def ask(model, system, messages, max_tokens=800, label=""):
    """Send one request and return the reply text. Logs tokens and cost."""
    data = _post({"model": model, "max_tokens": max_tokens, "system": system, "messages": messages})
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    inp = data["usage"]["input_tokens"]
    out = data["usage"]["output_tokens"]
    cost = cost_usd(model, inp, out)
    TOTALS["calls"] += 1
    TOTALS["input_tokens"] += inp
    TOTALS["output_tokens"] += out
    TOTALS["cost_usd"] += cost
    _log(label, model, inp, out, cost)
    return text


def extract_json(text):
    """Pull a JSON object out of a model reply (tolerates code fences and stray text)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in reply")
    return json.loads(text[start:end + 1])
