"""Have Claude tag every downloaded story, and save the results as JSON.

Reads data/story_list.csv and library/<story_id>.txt, writes data/story_tags.json.
Safe to re-run: stories that are already tagged are skipped.

Usage:
    python tag_stories.py            tag everything not yet tagged
    python tag_stories.py --review 8 print 8 random tagged stories to spot-check
"""
import argparse
import csv
import json
import random

import config
import llm

TAG_SYSTEM = f"""You are cataloguing public-domain short stories for a reading-recommendation tool.
Read the story excerpt and reply with ONLY a JSON object with these keys:
  "genre": exactly one of {json.dumps(config.GENRES)}
  "subgenre": 2-4 words, e.g. "locked-room puzzle" or "gothic revenge"
  "mood": a list of 1 to 3 values chosen only from {json.dumps(config.MOODS)}
  "language_difficulty": one of {json.dumps(config.DIFFICULTY)} (how dense or old-fashioned the prose is for a modern reader)
  "ending": one of {json.dumps(config.ENDINGS)}
  "blurb": two sentences that describe the story WITHOUT revealing the ending
Judge by what is actually on the page, not by the author's reputation."""


def excerpt(text, head=1800, tail=500):
    """The start of the story plus its last lines (so the ending can be judged)."""
    words = text.split()
    if len(words) <= head + tail:
        return text
    return " ".join(words[:head]) + "\n\n[... middle of story omitted ...]\n\n" + " ".join(words[-tail:])


def validate(tags):
    problems = []
    if tags.get("genre") not in config.GENRES:
        problems.append(f"genre {tags.get('genre')!r}")
    if tags.get("language_difficulty") not in config.DIFFICULTY:
        problems.append(f"language_difficulty {tags.get('language_difficulty')!r}")
    if tags.get("ending") not in config.ENDINGS:
        problems.append(f"ending {tags.get('ending')!r}")
    moods = tags.get("mood")
    if not isinstance(moods, list) or not moods or any(m not in config.MOODS for m in moods):
        problems.append(f"mood {moods!r}")
    if not tags.get("blurb") or not tags.get("subgenre"):
        problems.append("missing blurb or subgenre")
    return problems


def load_tags():
    if config.TAGS_FILE.exists():
        return json.loads(config.TAGS_FILE.read_text(encoding="utf-8"))
    return {}


def save_tags(tags):
    config.DATA_DIR.mkdir(exist_ok=True)
    config.TAGS_FILE.write_text(json.dumps(tags, indent=2, ensure_ascii=False), encoding="utf-8")


def tag_all():
    tags = load_tags()
    with open(config.STORY_LIST, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    llm.reset_totals()
    for row in rows:
        sid = row["story_id"].strip()
        if sid in tags:
            continue
        path = config.LIBRARY_DIR / f"{sid}.txt"
        if not path.exists():
            print(f"missing file for {sid} ({row['title']}); run fetch_stories.py first")
            continue
        text = path.read_text(encoding="utf-8")
        words = len(text.split())
        user = f'Title: {row["title"]}\nAuthor: {row["author"]}\n\n{excerpt(text)}'
        for attempt in range(2):
            try:
                result = llm.extract_json(llm.ask(
                    config.TAGGING_MODEL, TAG_SYSTEM,
                    [{"role": "user", "content": user}], max_tokens=500, label="tag"))
                problems = validate(result)
            except ValueError as e:
                problems = [str(e)]
            if not problems:
                break
            print(f"  retrying {row['title']}: {problems}")
        else:
            print(f"  SKIPPED {row['title']}: could not get valid tags ({problems})")
            continue
        tags[sid] = {
            "title": row["title"], "author": row["author"],
            "genre": result["genre"], "subgenre": result["subgenre"],
            "mood": result["mood"], "language_difficulty": result["language_difficulty"],
            "ending": result["ending"], "blurb": result["blurb"],
            "word_count": words, "length": config.length_bucket(words),
        }
        save_tags(tags)
        print(f"tagged {sid}  {row['title']}  ->  {result['genre']} / {result['subgenre']}")
    print(f"\n{len(tags)} stories tagged. {llm.TOTALS['calls']} calls, "
          f"${llm.TOTALS['cost_usd']:.4f} this run.")


def review(n):
    tags = load_tags()
    for sid in random.sample(list(tags), min(n, len(tags))):
        t = tags[sid]
        print(f"\n{sid}  {t['title']} by {t['author']}  ({t['word_count']} words, {t['length']})")
        print(f"   {t['genre']} / {t['subgenre']} | mood: {', '.join(t['mood'])} | "
              f"language: {t['language_difficulty']} | ending: {t['ending']}")
        print(f"   {t['blurb']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", type=int, metavar="N", help="print N random tagged stories")
    args = parser.parse_args()
    review(args.review) if args.review else tag_all()
