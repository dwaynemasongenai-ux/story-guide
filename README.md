# Story Guide

An adaptive reading-path recommender built on the Claude API. It recommends a classic short story, and when the reader says "this one isn't for me," it asks a few leading questions to work out *why*, then decides whether to adjust within the path or switch to a different one.

It is a small, public-domain stand-in for a recommender I built at work (Conscious Guide), rebuilt from scratch so the design, the tests and the numbers can be shown openly.

## What it does

- Recommends one public-domain short story at a time from a curated library of 30 stories.
- When a story is dropped, asks one to three leading questions instead of guessing why.
- Chooses between three pivots: adjust within the same path (lighter, shorter, easier language), switch to a different path, or keep asking.
- Logs tokens and cost for every call.

## How it works

1. **Library.** 30 public-domain short stories from Wikisource: 8 horror and gothic, 5 mystery, 4 each of humor, adventure and literary, 3 science fiction and fantasy, 2 romance and drama. 10 short, 15 medium and 5 long; 6 with challenging language.
2. **Tagging.** Claude (Haiku) reads the opening and closing of each story and tags genre, subgenre, mood, language difficulty and type of ending, and writes a spoiler-free blurb. Length comes from the word count. Output is validated JSON, with a retry if a tag is invalid.
3. **Guide loop.** Claude (Sonnet) gets the tagged catalog and the conversation so far, and replies with JSON: ask a question, or recommend a story with a pivot type. Replies are validated (real story id, no repeats, at most three questions in a row) and retried if they fail.
4. **Tests.** 15 scripted reader scenarios. Each starts from a fixed first story, has a simulated reader (a cheap model playing a hidden persona) drop it, lets the guide ask its questions, then checks the next recommendation against what a good guide should do: the right kind of pivot, the right change in genre, length, language, ending or mood, and the right number of questions.

## Results

Each prompt version was run 3 times over all 15 scenarios (45 scenario runs), because the guide's answers vary from run to run: the same prompt scored 12/13, 13/15 and 11/15 in single runs.

| Prompt | Passed | Cost of the run |
|---|---|---|
| v1: original | 36 / 45 (80%) | $1.16 |
| v2: adds a rule for telling "adjust within the genre" from "switch genre" | 40 / 45 (89%) | $0.98 |

What changed: in v1 the guide kept readers inside a genre when the real complaint was about what the genre offers ("the jokes feel shallow, I want depth"). v2 adds one rule separating a complaint about a dimension of the story (too long, too dark, too slow) from a complaint about the genre's core pleasure. `humor_wants_depth` went from 0/3 to 3/3, and three other scenarios that were flaky became 3/3.

What did not improve, or got worse:
- `literary_too_slow` went from 1/3 to 0/3. The guide treats "too slow" as a complaint about one dimension and picks a faster literary story. That is a defensible answer, so this may be a scenario whose expectation is too strict, not a bug.
- `scifi_too_farfetched` went from 2/3 to 1/3. The guide moves readers to humor, which the scenario does not list as an acceptable destination.

I left both scenarios unchanged so the numbers are not tuned to the guide. Fifteen scenarios, three runs each, is a small test: the gain is clearest on the one scenario the prompt change was aimed at.

## Cost

Tagging all 30 stories cost about 2 cents. A scripted conversation (guide plus simulated reader) costs about 2 to 3 cents. Each full 45-run test costs about $1.

## Known limitations

- Tags are written by Claude and have not been hand-verified. Some are debatable (for example, *The Gift of the Magi* gets a "tragic" mood tag).
- The library has no stories tagged "easy" language, and only one thin pocket of romance. Some pivots have few good destinations.
- The reader in the tests is simulated, so the tests check consistency with a persona, not how real readers react.

## Setup (Windows)

1. Install Python. There are no other packages to install: everything uses the standard library, which also means it runs on locked-down Windows PCs that block compiled add-ons.
2. Set your API key as an environment variable (it is never stored in this project):
   `setx ANTHROPIC_API_KEY "paste-your-key-here"`
   Then close Command Prompt and open a new one.
3. In this folder, check the setup: `python check_setup.py`
4. Run the scripts in order: `python fetch_stories.py` (downloads the stories), `python tag_stories.py` (tags them), then `python guide.py` to chat. To run the tests: `python run_tests.py --repeats 3`, or `python run_tests.py --prompt prompts/guide_v2.txt --repeats 3` to compare prompt versions.

## Notes

Built with AI assistance (Claude). Stories are public domain, via Wikisource.
