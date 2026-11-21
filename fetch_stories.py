"""Download the stories listed in data/story_list.csv from Wikisource.

story_list.csv columns: story_id, title, author, wikisource_page
  - story_id is a short name you choose (it becomes the file name).
  - wikisource_page is the exact page title on en.wikisource.org. If a story is
    split across several pages (chapters), separate them with " || ".

Each story is saved as library/<story_id>.txt as plain text (page furniture such
as headers, navigation and footnote markers is removed). The script prints the
word count and the opening words of every story so you can eyeball the result,
and flags anything that looks wrong (too short, or a menu page instead of a story).

Uses only Python's standard library (no add-on packages).

Usage:
    python fetch_stories.py            download anything not yet downloaded
    python fetch_stories.py --force    download everything again
"""
import argparse
import csv
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

import config

API = os.environ.get("STORY_API_BASE", "https://en.wikisource.org/w/api.php")
HEADERS = {"User-Agent": "story-guide-portfolio-project/1.0 (personal, non-commercial learning project)"}
MIN_WORDS = 400          # anything shorter is probably not a whole story
PAGE_SEPARATOR = "||"

# Wikisource page furniture that is not part of the story itself.
SKIP_TAGS = {"style", "script", "sup", "noscript"}
SKIP_CLASSES = {"ws-noexport", "ws-header", "noprint", "headertemplate", "searchaux",
                "mw-editsection", "reference", "pagenum", "navbox", "toc", "licenseContainer"}
VOID_TAGS = {"br", "hr", "img", "meta", "link", "input", "wbr"}
BLOCK_TAGS = {"p", "div", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "pre"}


class _TextExtractor(HTMLParser):
    """Turns the rendered HTML of a Wikisource page into plain paragraphs."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.stack = []        # one entry per open tag: (tag, is_skipped)
        self.skip_depth = 0

    def _should_skip(self, tag, attrs):
        if tag in SKIP_TAGS:
            return True
        classes = set((dict(attrs).get("class") or "").split())
        return bool(classes & SKIP_CLASSES)

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            if tag == "br" and not self.skip_depth:
                self.parts.append("\n")
            return
        skipped = self._should_skip(tag, attrs)
        if tag in BLOCK_TAGS and not self.skip_depth and not skipped:
            self.parts.append("\n\n")     # text before a new block starts a new paragraph
        self.stack.append((tag, skipped))
        if skipped:
            self.skip_depth += 1

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and not self.skip_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        # close back to the matching open tag (tolerates sloppy HTML)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for _, skipped in self.stack[i:]:
                    if skipped:
                        self.skip_depth -= 1
                del self.stack[i:]
                break
        if tag in BLOCK_TAGS and not self.skip_depth:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)


def html_to_text(html):
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts)
    text = text.replace("​", "").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # stray layout labels that some pages leave behind, e.g. "Layout 2"
    text = re.sub(r"^(Layout \d+\s*)+", "", text).strip()
    return text


def api_get(page):
    params = urllib.parse.urlencode({
        "action": "parse", "page": page, "prop": "text", "format": "json",
        "formatversion": "2", "redirects": "1",
    })
    request = urllib.request.Request(f"{API}?{params}", headers=HEADERS)
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}"
            if e.code not in (429, 500, 502, 503, 504):
                break
        except urllib.error.URLError as e:
            last_error = f"network problem: {e.reason}"
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(last_error or "unknown error")


def fetch_page_text(page):
    data = api_get(page)
    if "error" in data:
        raise RuntimeError(f"Wikisource says: {data['error'].get('info', data['error'])}")
    return html_to_text(data["parse"]["text"])


def fetch_story(pages_field):
    pages = [p.strip() for p in pages_field.split(PAGE_SEPARATOR) if p.strip()]
    chunks = []
    for page in pages:
        chunks.append(fetch_page_text(page))
        time.sleep(1.0)    # be polite to Wikisource
    return "\n\n".join(chunks)


def looks_wrong(text):
    words = len(text.split())
    if words < MIN_WORDS:
        return f"only {words} words (a menu or edition-list page instead of the story?)"
    if re.search(r"\b(disambiguation|this page lists|versions of this work)\b", text[:600], re.I):
        return "looks like a list of editions, not a story"
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="download everything again")
    args = parser.parse_args()

    config.LIBRARY_DIR.mkdir(exist_ok=True)
    with open(config.STORY_LIST, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    problems = []
    for row in rows:
        sid, title = row["story_id"].strip(), row["title"].strip()
        out = config.LIBRARY_DIR / f"{sid}.txt"
        if out.exists() and not args.force:
            print(f"skip   {sid}  (already downloaded)")
            continue
        print(f"fetch  {sid}  {title}")
        try:
            text = fetch_story(row["wikisource_page"])
        except RuntimeError as e:
            print(f"   FAILED: {e}")
            problems.append((sid, title, str(e)))
            continue
        why = looks_wrong(text)
        if why:
            problems.append((sid, title, why))
            continue          # do not save it, so the next run tries again
        out.write_text(text, encoding="utf-8")
        opening = " ".join(text.split()[:12])
        print(f"   {len(text.split())} words | starts: {opening}")
    print(f"\nDone. {len(rows) - len(problems)} ok, {len(problems)} to check.")
    for sid, title, why in problems:
        print(f"  CHECK {sid} ({title}): {why}")


if __name__ == "__main__":
    main()
