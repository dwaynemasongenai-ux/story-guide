"""The story guide.

It recommends one story at a time. When the reader drops a story, it asks a few
leading questions to work out why, then either adjusts within the same path or
switches to a different one.

Usage:  python guide.py            (a chat in the terminal; type quit to leave)
"""
import json

import config
import llm

MAX_QUESTIONS_IN_A_ROW = 3
PIVOT_TYPES = {None, "adjust_within_path", "switch_path", "continue_path"}


def load_tags():
    return json.loads(config.TAGS_FILE.read_text(encoding="utf-8"))


def load_prompt(path):
    return path.read_text(encoding="utf-8")


def catalog_text(tags):
    lines = []
    for sid, t in tags.items():
        lines.append(
            f'{sid} | "{t["title"]}" by {t["author"]} | {t["genre"]} / {t["subgenre"]} | '
            f'mood: {", ".join(t["mood"])} | language: {t["language_difficulty"]} | '
            f'length: {t["length"]} ({t["word_count"]} words) | ending: {t["ending"]}'
        )
    return "\n".join(lines)


def _log_problem(user_text, raw, problems):
    """Keep a record of every reply the guide gave that was rejected, so failures can be diagnosed."""
    try:
        config.LOG_DIR.mkdir(exist_ok=True)
        with open(config.LOG_DIR / "guide_problems.log", "a", encoding="utf-8") as f:
            f.write(f"--- reader said: {user_text!r}\nproblems: {problems}\nraw reply: {raw}\n\n")
    except OSError:
        pass


class GuideSession:
    def __init__(self, tags, prompt_text, model=None):
        self.tags = tags
        self.system = prompt_text.replace("{{CATALOG}}", catalog_text(tags))
        self.model = model or config.GUIDE_MODEL
        self.messages = []          # the conversation so far, in API format
        self.recommended = []       # story ids already recommended
        self.questions_in_a_row = 0

    def seed_recommendation(self, opening_text, story_id):
        """Start a session as if the guide had already recommended story_id (used by the tests)."""
        reply = {"action": "recommend", "message": "Here is one to start with.",
                 "story_id": story_id, "pivot_type": None, "diagnosis": None}
        self.messages = [{"role": "user", "content": opening_text},
                         {"role": "assistant", "content": json.dumps(reply)}]
        self.recommended = [story_id]

    def _validate(self, d):
        problems = []
        if d.get("action") not in ("recommend", "ask"):
            problems.append('"action" must be "recommend" or "ask"')
        if not isinstance(d.get("message"), str) or not d["message"].strip():
            problems.append('"message" must be non-empty text')
        if d.get("pivot_type") not in PIVOT_TYPES:
            problems.append('"pivot_type" is not an allowed value')
        if d.get("action") == "recommend":
            sid = d.get("story_id")
            if sid not in self.tags:
                problems.append(f"story_id {sid!r} is not in the catalog")
            elif sid in self.recommended:
                problems.append(f"story {sid} was already recommended")
        if d.get("action") == "ask" and self.questions_in_a_row >= MAX_QUESTIONS_IN_A_ROW:
            problems.append("you have asked enough questions; recommend a story now")
        return problems

    def send(self, user_text):
        """Give the guide the reader's message; returns its decision as a dict."""
        if not user_text.strip():
            user_text = "(no answer)"
        self.messages.append({"role": "user", "content": user_text})
        decision, problems = None, []
        for _ in range(3):
            raw = llm.ask(self.model, self.system, self.messages, max_tokens=600, label="guide")
            try:
                decision = llm.extract_json(raw)
                problems = self._validate(decision)
            except ValueError as e:
                decision, problems = None, [f"reply was not valid JSON ({e})"]
            self.messages.append({"role": "assistant", "content": raw})
            if not problems:
                break
            _log_problem(user_text, raw, problems)
            self.messages.append({"role": "user", "content": (
                "SYSTEM NOTE: your last reply was not accepted: " + "; ".join(problems) +
                ". Reply again with ONLY a valid JSON object.")})
        if problems:
            decision = {"action": "ask", "pivot_type": None, "story_id": None, "diagnosis": None,
                        "message": "Sorry, I lost my place. Could you say that another way?"}
        if decision["action"] == "ask":
            self.questions_in_a_row += 1
        else:
            self.questions_in_a_row = 0
            self.recommended.append(decision["story_id"])
        return decision


def main():
    tags = load_tags()
    session = GuideSession(tags, load_prompt(config.PROMPTS_DIR / "guide_v3.txt"))
    llm.reset_totals()
    print("Story Guide. Tell me what you're in the mood for. (Type quit to leave.)\n")
    user_text = input("You: ").strip()
    while user_text.lower() not in ("quit", "exit"):
        if not user_text:          # an accidental Enter should not end the chat
            user_text = input("(Type a reply, or quit to leave.)\nYou: ").strip()
            continue
        d = session.send(user_text)
        print(f"\nGuide: {d['message']}")
        if d["action"] == "recommend":
            s = tags[d["story_id"]]
            print(f'\n   >> "{s["title"]}" by {s["author"]}  ({s["genre"]}, {s["length"]})')
            print(f'   Read it: {config.LIBRARY_DIR / (d["story_id"] + ".txt")}')
            print("   Come back and tell me how it went.")
        user_text = input("\nYou: ").strip()
    print(f"\nSession cost: ${llm.TOTALS['cost_usd']:.4f} "
          f"({llm.TOTALS['input_tokens']} tokens in, {llm.TOTALS['output_tokens']} out)")


if __name__ == "__main__":
    main()
