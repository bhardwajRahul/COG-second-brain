#!/usr/bin/env python3
"""voice-baseline: measure your own corpus so an agent stops amplifying your tics.

Usage
-----
    python3 census.py CORPUS_DIR [--ext .md] [--out voice-baseline.md]
    python3 census.py CORPUS_DIR --check DRAFT.md

An agent writing in your voice samples the median of *you*: it regresses toward the
words and sentence shapes that appear most in the corpus it has seen. A word that was
a choice at one use reads as a tic at five. This measures which ones you actually
over-use, so the watchlist is yours and not a generic ban list.

Two modes:
  (default) census  -- walk the corpus, write a baseline file
  --check DRAFT     -- compare one draft against the corpus rate, flag what is above it
"""
import argparse
import os
import re
import sys
from collections import Counter

# Words an agent reaches for as praise or emphasis. Counted, never banned: the census
# says which ones YOUR corpus over-uses. Add your own.
WATCH = [
    "actually", "just", "simply", "really", "quite", "very", "genuinely", "honestly",
    "quietly", "clean", "plain", "simple", "cheap", "small", "elegant", "powerful",
    "robust", "seamless", "leverage", "delve", "ship", "shipped", "earn", "earns",
    "the whole", "the real", "here's", "at the end of the day", "load-bearing",
]

# "The <noun> <past-tense verb> <short predicate>." parked at the end of a paragraph,
# where it lands like a verdict instead of carrying a fact.
VERDICT = re.compile(
    r"(?:^|\. )The [a-z][a-z-]{2,14} (?:was|were|is|are|went|took|did|does|fell|lives|sits|stays|goes|came|holds|catches|kills|works|stops|moves|breaks)\b[^.\n]{0,40}\.\s*$",
    re.M)
KICKER = re.compile(r"\bThat (?:is|was|'s) (?:the|all|it|what|why)\b[^.\n]{0,40}\.", re.I)
HEADING = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$", re.M)
SENTENCE = re.compile(r"[.!?](?:\s|$)")
OPENER = re.compile(r"(?:^|\. )([A-Z][a-z]+) ", re.M)
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
CODE = re.compile(r"^```.*?^```", re.M | re.S)


def load(path):
    text = open(path, encoding="utf-8", errors="ignore").read()
    text = FRONTMATTER.sub("", text)
    return CODE.sub(" ", text)


def count_phrase(text, phrase):
    if " " in phrase or "'" in phrase:
        return len(re.findall(re.escape(phrase), text, re.I))
    return len(re.findall(r"\b%s\b" % re.escape(phrase), text, re.I))


def census(paths):
    words = Counter()
    docs = Counter()
    sentences = verdicts = kickers = 0
    openers = Counter()
    headings = Counter()
    closers = {"question": 0, "kicker": 0}
    for p in paths:
        t = load(p)
        sentences += len(SENTENCE.findall(t))
        verdicts += len(VERDICT.findall(t))
        k = len(KICKER.findall(t))
        kickers += k
        for m in OPENER.finditer(t):
            openers[m.group(1)] += 1
        for h in HEADING.findall(t):
            first = h.split()[0] if h.split() else ""
            headings[first] += 1
        body = [ln for ln in t.strip().splitlines() if ln.strip()]
        if body:
            last = body[-1]
            if last.rstrip().endswith("?"):
                closers["question"] += 1
            if KICKER.search(last):
                closers["kicker"] += 1
        for w in WATCH:
            n = count_phrase(t, w)
            if n:
                words[w] += n
                docs[w] += 1
    return {"files": len(paths), "sentences": sentences, "words": words, "docs": docs,
            "verdicts": verdicts, "kickers": kickers, "openers": openers,
            "headings": headings, "closers": closers}


def render(c, corpus):
    n = max(c["files"], 1)
    lines = ["# Voice baseline", "",
             "Measured from %d files in `%s`, about %d sentences." % (c["files"], corpus, c["sentences"]),
             "Counted, not banned. A word above its baseline in a new draft is a tic to check, not an error.",
             "", "## Words", "", "| Word or phrase | Uses | Files | Per file |", "|---|---|---|---|"]
    for w, total in c["words"].most_common():
        lines.append("| %s | %d | %d | %.1f |" % (w, total, c["docs"][w], total / n))
    lines += ["", "## Sentence shapes", "",
              "| Shape | Count | Share |", "|---|---|---|",
              "| Paragraph-ending verdict (\"The X was one line.\") | %d | %.1f%% of sentences |"
              % (c["verdicts"], 100.0 * c["verdicts"] / max(c["sentences"], 1)),
              "| \"That is the point\" kicker | %d | %.1f per file |" % (c["kickers"], c["kickers"] / n),
              "| Files ending on a question to the reader | %d | %.0f%% of files |"
              % (c["closers"]["question"], 100.0 * c["closers"]["question"] / n),
              "| Files ending on a kicker | %d | %.0f%% of files |"
              % (c["closers"]["kicker"], 100.0 * c["closers"]["kicker"] / n), ""]
    lines += ["## Sentence openers", "", "| Opener | Count |", "|---|---|"]
    for w, total in c["openers"].most_common(8):
        lines.append("| %s | %d |" % (w, total))
    lines += ["", "## Heading first words", "", "| First word | Headings |", "|---|---|"]
    for w, total in c["headings"].most_common(8):
        lines.append("| %s | %d |" % (w, total))
    lines += ["", "## How to use this", "",
              "1. Before publishing, run `census.py CORPUS --check DRAFT` and read what sits above the per-file rate.",
              "2. For each flagged word, decide: does the sentence need it, or is it decoration? Remove the adjective; if the reader would do nothing differently, it was decoration.",
              "3. Cap the shapes. One paragraph-ending verdict per piece at most, and only when it carries a fact. No kicker closers. Do not end on a question by default.",
              "4. Re-run the census after ten new pieces. A tic you fixed should fall; a new one will have appeared.", ""]
    return "\n".join(lines)


def check(c, draft):
    n = max(c["files"], 1)
    t = load(draft)
    sentences = max(len(SENTENCE.findall(t)), 1)
    print("%s: %d sentences" % (draft, sentences))
    flagged = 0
    for w, total in c["words"].most_common():
        rate = total / n
        here = count_phrase(t, w)
        if here and here > max(rate, 1):
            flagged += 1
            print("  ABOVE BASELINE  %-18s %d uses here vs %.1f per file in the corpus" % (w, here, rate))
    v = len(VERDICT.findall(t))
    if v > 1:
        print("  SHAPE           %d paragraph-ending verdict sentences (cap: 1)" % v)
        flagged += 1
    k = len(KICKER.findall(t))
    if k:
        print("  SHAPE           %d \"That is the point\" kicker(s) (cap: 0)" % k)
        flagged += 1
    body = [ln for ln in t.strip().splitlines() if ln.strip()]
    if body and body[-1].rstrip().endswith("?"):
        print("  SHAPE           ends on a question to the reader")
        flagged += 1
    if not flagged:
        print("  nothing above baseline")
    return 1 if flagged else 0


def main():
    ap = argparse.ArgumentParser(description="Measure a writing corpus for over-used words and shapes.")
    ap.add_argument("corpus", help="directory of your own writing")
    ap.add_argument("--ext", default=".md", help="file extension to include (default .md)")
    ap.add_argument("--out", default="", help="write the baseline to this file instead of stdout")
    ap.add_argument("--check", default="", help="compare one draft against the corpus rate")
    a = ap.parse_args()

    paths = []
    for root, _, files in os.walk(a.corpus):
        for f in files:
            if f.endswith(a.ext):
                paths.append(os.path.join(root, f))
    if not paths:
        print("no %s files under %s" % (a.ext, a.corpus), file=sys.stderr)
        return 2

    c = census(sorted(paths))
    if a.check:
        return check(c, a.check)
    out = render(c, a.corpus)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out)
        print("wrote %s (%d files, %d sentences)" % (a.out, c["files"], c["sentences"]))
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
