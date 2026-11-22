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
4. **Tests.** 16 scripted reader scenarios. Each starts from a fixed first story, has a simulated reader (a cheap model playing a hidden persona) drop it, lets the guide ask its questions, then checks the next recommendation against what a good guide should do: the right kind of pivot, the right change in genre, length, language, ending or mood, and the right number of questions.

## Example session

A real session, with the file-path lines the tool prints left out. The reader asks for a story and drops it with a vague answer, so the guide asks what went wrong instead of guessing. The answer is about what the genre offers, so the guide switches genre. A later complaint about content makes it adjust within the new path.

```
You: I would love something where a pair of individuals go on a journey together and
     discover something about themselves while looking for answers from their past

Guide: Companions setting out together to decode a message from the past is the heart
       of this tale. It's not deeply introspective, but it's a gripping quest where the
       trio's trust is tested. If you want more inner discovery, I can steer you elsewhere.
   >> "The Gold-Bug" by Edgar Allan Poe  (Mystery & Detective, long)

You: meh

Guide: Fair enough, that one was more treasure hunt than self-discovery. What fell flat
       for you: the puzzle-and-codes plot, the length, or the lack of any emotional
       journey for the characters?

You: lack of any emotional journey

Guide: Since puzzles left you cold, I've switched to a more emotional path. A statue and
       a little swallow work together, and the Prince looks back on his sheltered past,
       so both of them are changed by what they find.
   >> "The Happy Prince" by Oscar Wilde  (Literary & Reflective, medium)

You: I would prefer no animals at all

Guide: No animals, noted. I've kept the emotional, reflective path and changed only that.
       A husband and wife face years of hardship together, and Mathilde finally learns the
       truth about a past mistake and who she really is.
   >> "The Necklace" by Guy de Maupassant  (Literary & Reflective, short)
```

What happened: a vague drop got one clarifying question (ask), "no emotional journey" was a complaint about the genre so it switched path (mystery to literary), and "no animals" was a complaint about one dimension so it adjusted within the path.

## Results

Each prompt version was run 3 times over every scenario, because the guide's answers vary from run to run: the same prompt scored 12/13, 13/15 and 11/15 in single runs.

| Prompt | Original 15 scenarios (3 runs each) | Cost of the run |
|---|---|---|
| v1: original | 36 / 45 (80%) | $1.16 |
| v2: adds a rule for telling "adjust within the genre" from "switch genre" | 40 / 45 (89%) | $0.98 |
| v3: v2 plus a rule to stop asking questions after two vague answers | 38 / 45 (84%) | $1.28 (16 scenarios, 48 runs) |

**v1 to v2.** In v1 the guide kept readers inside a genre when the real complaint was about what the genre offers ("the jokes feel shallow, I want depth"). v2 separates a complaint about one dimension of a story (too long, too dark, too slow) from a complaint about the genre's core pleasure. `humor_wants_depth` went from 0/3 to 3/3, and three other flaky scenarios became 3/3.

### A weakness found in real use

While trying the guide myself, I gave vague answers ("meh", "it was forgettable", "nothing really happened") and the guide asked three questions in a row, drifting toward options I had not asked about. I turned that into a test, `vague_all_the_way`: a simulated reader who gives abstract answers that point to no fix. The guide passes only if it asks at most two questions.

| Prompt | `vague_all_the_way` (10 runs each) |
|---|---|
| v2 | 4 / 10 |
| v3 | 9 / 10 |

My first version of this test passed 3 out of 3 with v2, so it proved nothing: the simulated reader said "I can't put my finger on it," which made the guide stop on its own. I rewrote the reader to answer the way I really had and ran 10 trials per prompt, which is what exposed the problem. With only 10 runs each, I treat the improvement as likely real, not certain.

**Side effects of v3.** On the original 15 scenarios v3 scored 38/45 against v2's 40/45. The difference comes from `scifi_too_farfetched` (1/3 to 0/3) and `switch_path_and_keep_it_short` (3/3 to 2/3). That is inside the run-to-run noise seen above, but it may be a small real cost. `vague_drop_needs_a_question`, which requires the guide to ask, stayed at 3/3.

**Still failing.** `literary_too_slow` (0/3 on v2 and v3): the guide treats "too slow" as one dimension of the story and picks a faster literary story, which is defensible, so the scenario's expectation may be too strict. `scifi_too_farfetched` also fails because the guide moves readers to genres the scenario does not list as acceptable. I left both scenarios unchanged so the numbers are not tuned to the guide.

Fifteen-plus scenarios at three runs each is a small test, so these results show a direction, not proof.

## Cost

Tagging all 30 stories cost about 2 cents. A scripted conversation (guide plus simulated reader) costs about 2 to 3 cents. Each full 45-run test costs about $1.

## Known limitations

- Tags are written by Claude and have not been hand-verified. Some are debatable (for example, *The Gift of the Magi* gets a "tragic" mood tag).
- The library has no stories tagged "easy" language, and only a thin pocket of romance. Some pivots have few good destinations.
- The reader in the tests is simulated, so the tests check consistency with a persona, not how real readers react.
- Even with v3, the guide occasionally asks one question too many with a very vague reader (1 run in 10 asked four).
- Once in real use the guide replied "Sorry, I lost my place" (its fallback after three rejected replies). It did not happen again; rejected replies are now logged to `logs/guide_problems.log`, but I have not found the cause.
- Each turn sends the whole 30-story catalog, so a short chat costs about 8 cents. Trimming the catalog sent per turn would cut that.

## Setup (Windows)

1. Install Python. There are no other packages to install: everything uses the standard library, which also means it runs on locked-down Windows PCs that block compiled add-ons.
2. Set your API key as an environment variable (it is never stored in this project):
   `setx ANTHROPIC_API_KEY "paste-your-key-here"`
   Then close Command Prompt and open a new one.
3. In this folder, check the setup: `python check_setup.py`
4. Run the scripts in order: `python fetch_stories.py` (downloads the stories), `python tag_stories.py` (tags them), then `python guide.py` to chat (it uses the v3 prompt). To run the tests: `python run_tests.py --repeats 3`, or `python run_tests.py --prompt prompts/guide_v2.txt --repeats 3` to compare prompt versions.

## Notes

Built with AI assistance (Claude). Stories are public domain, via Wikisource.
