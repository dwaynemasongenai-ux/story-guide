"""Run the scripted reader scenarios against the guide and report a pass rate.

For each scenario the test:
  1. picks a first story that matches the scenario (so the setup is the same every run),
  2. has a simulated reader say the story isn't for them,
  3. lets the guide ask its leading questions (a simulated reader answers from a hidden persona),
  4. checks the guide's next recommendation against what a good guide should do.

Run it before and after changing a prompt to see whether the change helped.

Usage:
    python run_tests.py                                  uses prompts/guide_v1.txt
    python run_tests.py --prompt prompts/guide_v2.txt    try another version
    python run_tests.py --repeats 3                      run every scenario 3 times (answers vary)
    python run_tests.py --only mystery_too_long          run one scenario
"""
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import config
import guide
import llm

MAX_QUESTIONS = 4
LENGTH_RANK = {"short": 0, "medium": 1, "long": 2}
DIFF_RANK = {"easy": 0, "moderate": 1, "challenging": 2}

SIM_SYSTEM = """You are role-playing a person who is trying a story recommendation tool. Stay in character.
Your profile: {persona}
Rules: reply in one or two short, casual sentences. Reveal your real reason for disliking a story only when the question touches it. If the question is off-target, answer honestly from your profile but do not volunteer more. Never mention that you are a simulation."""


def pick_first_story(tags, wanted):
    for sid, t in tags.items():
        ok = True
        for key, value in wanted.items():
            have = t.get(key)
            if (value not in have) if isinstance(have, list) else (have != value):
                ok = False
                break
        if ok:
            return sid
    return None


def sim_reply(persona, guide_message, transcript):
    history = "\n".join(transcript) or "(nothing yet)"
    user = (f"Conversation so far:\n{history}\n\nThe guide just said: {guide_message}\n"
            "Reply as the reader.")
    for _ in range(2):
        reply = llm.ask(config.SIM_MODEL, SIM_SYSTEM.format(persona=persona),
                        [{"role": "user", "content": user}], max_tokens=150, label="sim_reader").strip()
        if reply:
            return reply
    return "Hmm, I'm not sure, honestly."   # the simulated reader sometimes returns nothing


def evaluate(expect, first, second, decision, asked, tags):
    t1, t2 = tags[first], tags[second]
    fails = []
    if "pivot_type" in expect and decision.get("pivot_type") != expect["pivot_type"]:
        fails.append(f"pivot_type was {decision.get('pivot_type')}, expected {expect['pivot_type']}")
    if expect.get("genre_same") and t2["genre"] != t1["genre"]:
        fails.append(f"genre changed ({t1['genre']} -> {t2['genre']})")
    if expect.get("genre_different") and t2["genre"] == t1["genre"]:
        fails.append("genre did not change")
    if "genre_in" in expect and t2["genre"] not in expect["genre_in"]:
        fails.append(f"genre {t2['genre']} not in {expect['genre_in']}")
    if expect.get("length_shorter") and LENGTH_RANK[t2["length"]] >= LENGTH_RANK[t1["length"]]:
        fails.append(f"length not shorter ({t1['length']} -> {t2['length']})")
    if expect.get("difficulty_easier") and DIFF_RANK[t2["language_difficulty"]] >= DIFF_RANK[t1["language_difficulty"]]:
        fails.append(f"language not easier ({t1['language_difficulty']} -> {t2['language_difficulty']})")
    if "ending_in" in expect and t2["ending"] not in expect["ending_in"]:
        fails.append(f"ending {t2['ending']} not in {expect['ending_in']}")
    if "mood_includes_any" in expect and not set(t2["mood"]) & set(expect["mood_includes_any"]):
        fails.append(f"mood {t2['mood']} has none of {expect['mood_includes_any']}")
    if "mood_excludes" in expect and set(t2["mood"]) & set(expect["mood_excludes"]):
        fails.append(f"mood {t2['mood']} includes something to avoid {expect['mood_excludes']}")
    if "min_questions" in expect and asked < expect["min_questions"]:
        fails.append(f"asked {asked} questions, expected at least {expect['min_questions']}")
    if "max_questions" in expect and asked > expect["max_questions"]:
        fails.append(f"asked {asked} questions, expected at most {expect['max_questions']}")
    return fails


def run_scenario(scn, tags, prompt_text):
    first = pick_first_story(tags, scn["first_story"])
    if first is None:
        return {"id": scn["id"], "skipped": f"no story in the library matches {scn['first_story']}"}
    session = guide.GuideSession(tags, prompt_text)
    session.seed_recommendation(scn["opening"], first)
    transcript = [f"Reader: {scn['drop_line']}"]
    decision = session.send(scn["drop_line"])
    asked = 0
    while decision["action"] == "ask" and asked < MAX_QUESTIONS:
        asked += 1
        transcript.append(f"Guide: {decision['message']}")
        reply = sim_reply(scn["persona"], decision["message"], transcript)
        transcript.append(f"Reader: {reply}")
        decision = session.send(reply)
    result = {"id": scn["id"], "first_story": f"{first} {tags[first]['title']}",
              "questions_asked": asked, "transcript": transcript}
    if decision["action"] != "recommend":
        result.update(passed=False, fails=["never made a recommendation"])
        return result
    second = decision["story_id"]
    fails = evaluate(scn["expect"], first, second, decision, asked, tags)
    result.update(second_story=f"{second} {tags[second]['title']}",
                  pivot_type=decision.get("pivot_type"), diagnosis=decision.get("diagnosis"),
                  guide_message=decision["message"], passed=not fails, fails=fails)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default=str(config.PROMPTS_DIR / "guide_v1.txt"))
    parser.add_argument("--only", nargs="*", help="scenario ids to run")
    parser.add_argument("--repeats", type=int, default=1,
                        help="run every scenario this many times (the guide's answers vary a little)")
    args = parser.parse_args()

    tags = guide.load_tags()
    prompt_path = Path(args.prompt)
    prompt_text = guide.load_prompt(prompt_path)
    scenarios = json.loads(config.SCENARIOS_FILE.read_text(encoding="utf-8"))
    if args.only:
        scenarios = [s for s in scenarios if s["id"] in args.only]

    llm.reset_totals()
    results = []
    for scn in scenarios:
        trials = []
        for i in range(args.repeats):
            try:
                r = run_scenario(scn, tags, prompt_text)
            except Exception as e:           # one bad call should not stop the whole run
                r = {"id": scn["id"], "error": str(e)}
            r["trial"] = i + 1
            trials.append(r)
            results.append(r)
        if "skipped" in trials[0]:
            print(f"SKIP  {scn['id']}: {trials[0]['skipped']}")
            continue
        good = [r for r in trials if r.get("passed")]
        errors = [r for r in trials if "error" in r]
        status = "PASS" if len(good) == len(trials) else ("FAIL" if not good else "MIXED")
        extra = f", {len(errors)} errored" if errors else ""
        print(f"{status}  {scn['id']}  {len(good)}/{len(trials)}{extra}")
        shown = set()
        for r in trials:
            for why in r.get("fails", []) + ([f"error: {r['error']}"] if "error" in r else []):
                if why not in shown:
                    shown.add(why)
                    print(f"        - {why}")

    ran = [r for r in results if "skipped" not in r and "error" not in r]
    passed = sum(1 for r in ran if r["passed"])
    skipped = sum(1 for r in results if "skipped" in r)
    errored = sum(1 for r in results if "error" in r)
    cost = llm.TOTALS["cost_usd"]
    print(f"\n{passed}/{len(ran)} scenario runs passed ({skipped} skipped, {errored} errored). "
          f"Cost of this run: ${cost:.4f}")

    config.RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (config.RESULTS_DIR / f"run_{stamp}_{prompt_path.stem}.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = config.RESULTS_DIR / "summary.csv"
    new_file = not summary.exists()
    with open(summary, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["time", "prompt", "passed", "ran", "skipped", "cost_usd"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), f"{prompt_path.name} x{args.repeats}",
                    passed, len(ran), skipped, f"{cost:.4f}"])


if __name__ == "__main__":
    main()
