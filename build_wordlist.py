"""
build_wordlist.py — generate a clean words.txt for Q-Less.

Strategy
--------
Download ENABLE (a conservative Scrabble dictionary) from GitHub.
Cross-reference against a word-frequency list derived from real English text
(OpenSubtitles via hermitdave/FrequencyWords on GitHub, top 50 k entries).

* Words of 6+ letters: keep if they appear in the frequency list OR in the
  top-N entries (longer words are almost always legitimate).
* Words of 3–5 letters: only keep if they appear in the frequency list
  (short Scrabble obscurities like AALII, ZAX, QOPH disappear here).

Run:
    python build_wordlist.py
Writes the filtered list to words.txt.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

HERE = Path(__file__).parent

ENABLE_URL = (
    "https://raw.githubusercontent.com/dolph/dictionary/master/enable1.txt"
)

FREQ_URL = (
    "https://raw.githubusercontent.com/hermitdave/FrequencyWords"
    "/master/content/2016/en/en_50k.txt"
)
# How many of the top frequency entries to treat as "known"
FREQ_TOP_N = 50_000


def download_enable(url: str) -> list[str]:
    print(f"Downloading ENABLE word list from {url} …")
    with urllib.request.urlopen(url) as resp:
        text = resp.read().decode("utf-8", errors="ignore")
    words = [w.strip().lower() for w in text.splitlines() if w.strip()]
    print(f"  {len(words):,} ENABLE entries loaded.")
    return words


def download_freq_words(url: str, top_n: int) -> set[str]:
    print(f"Downloading frequency list from {url} …")
    with urllib.request.urlopen(url) as resp:
        text = resp.read().decode("utf-8", errors="ignore")
    words: set[str] = set()
    for line in text.splitlines()[:top_n]:
        parts = line.strip().split()
        if parts:
            words.add(parts[0].lower())
    print(f"  {len(words):,} frequency entries loaded.")
    return words


def build(out_path: Path) -> None:
    enable = download_enable(ENABLE_URL)
    freq   = download_freq_words(FREQ_URL, FREQ_TOP_N)

    kept: list[str] = []
    for word in enable:
        n = len(word)
        if n < 3:
            continue
        if n >= 6:
            # Longer words: keep if in frequency list; otherwise keep anyway
            # (6-letter+ words in ENABLE are overwhelmingly legitimate).
            kept.append(word)
        else:
            # Short words (3–5 letters): require frequency-list presence.
            if word in freq:
                kept.append(word)

    kept.sort()
    out_path.write_text("\n".join(kept) + "\n")

    removed = len(enable) - len(kept)
    print(
        f"\nOriginal ENABLE : {len(enable):>7,} words\n"
        f"Kept            : {len(kept):>7,} words\n"
        f"Removed (short) : {removed:>7,} words\n"
        f"Written to      : {out_path}"
    )

    # Spot-check
    check = ["aalii", "qoph", "zax", "aa", "cat", "dog", "hello", "beautiful", "the"]
    print("\nSpot check:")
    word_set = set(kept)
    for w in check:
        print(f"  {w:12s} {'✓ kept' if w in word_set else '✗ removed'}")


if __name__ == "__main__":
    build(HERE / "words.txt")
