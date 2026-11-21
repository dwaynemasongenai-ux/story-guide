"""Shared settings for the story guide project."""
from pathlib import Path

ROOT = Path(__file__).parent
LIBRARY_DIR = ROOT / "library"            # downloaded story text files (not committed)
DATA_DIR = ROOT / "data"
STORY_LIST = DATA_DIR / "story_list.csv"
TAGS_FILE = DATA_DIR / "story_tags.json"
SCENARIOS_FILE = DATA_DIR / "scenarios.json"
PROMPTS_DIR = ROOT / "prompts"
RESULTS_DIR = ROOT / "results"
LOG_DIR = ROOT / "logs"

# A fast, low-cost model for bulk tagging, the simulated readers and test runs,
# and a stronger model for the live guide conversation. Swap these to experiment.
TAGGING_MODEL = "claude-haiku-5-5"
GUIDE_MODEL = "claude-sonnet-5-5"
SIM_MODEL = "claude-haiku-5-5"

# Dollars per million tokens (input, output). Source: Anthropic's pricing page,
# October 2026. Check the pricing page for changes before quoting cost numbers.
PRICES = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50},   # prompts up to 100K tokens
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
}

# The "paths" a reader can walk down (stand-ins for course categories).
GENRES = [
    "Horror & Gothic",
    "Mystery & Detective",
    "Humor & Satire",
    "Adventure & Action",
    "Romance & Drama",
    "Science Fiction & Fantasy",
    "Literary & Reflective",
]

# Allowed tag values (the tagging script enforces these).
MOODS = ["dark", "eerie", "suspenseful", "funny", "whimsical", "warm",
         "tragic", "thoughtful", "thrilling", "romantic"]
DIFFICULTY = ["easy", "moderate", "challenging"]   # how dense / old-fashioned the language is
ENDINGS = ["happy", "tragic", "twist", "ambiguous", "resolved"]
LENGTHS = ["short", "medium", "long"]               # computed from word count


def length_bucket(word_count):
    if word_count < 3000:
        return "short"
    if word_count < 8000:
        return "medium"
    return "long"
