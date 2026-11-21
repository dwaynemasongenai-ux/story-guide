"""Quick check that your API key, billing and model name all work.

Usage:  python check_setup.py
Costs a tiny fraction of a cent.
"""
import config
import llm

try:
    reply = llm.ask(config.TAGGING_MODEL, "You are a friendly assistant.",
                    [{"role": "user", "content": "Say hi in five words."}],
                    max_tokens=30, label="check_setup")
except llm.ApiError as e:
    message = str(e)
    print("\nSomething went wrong:\n  " + message + "\n")
    lower = message.lower()
    if "not set" in lower or "401" in message or "authentication" in lower or "x-api-key" in lower:
        print("Hint: the key was not picked up. Open a NEW Command Prompt and try again.")
    elif "credit" in lower or "billing" in lower:
        print("Hint: add credit under Billing in Console.")
    elif "404" in message or "model" in lower:
        print("Hint: the model name may need changing in config.py. Tell Claude what this says.")
    raise SystemExit(1)

print(f"\nIt works! Claude says: {reply}")
print(f"Cost of this check: ${llm.TOTALS['cost_usd']:.6f}")
