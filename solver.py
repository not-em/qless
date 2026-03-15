# This is going to be the solver for q-less problems
# Eventually will be implemented as an API call for a "solve for me" button
from __future__ import annotations

import time
import logging
import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import TypedDict

# Logger with no handlers by default — callers (CLI or API) configure it themselves.
log = logging.getLogger("qless")
log.addHandler(logging.NullHandler())

_HERE = Path(__file__).parent

with open(_HERE / 'words.txt') as f:
    ENGLISH_WORDS = set(w.lower() for w in f.read().splitlines() if len(w) >= 3)

# Cache: tuple(sorted(letters)) → filtered valid_words list
_word_cache: dict[tuple[str, ...], list[str]] = {}

# Type used by Grid.find_placements — (orientation, start_position)
Placement = tuple[str, tuple[int, int]]


class GridResult(TypedDict):
    """Serialisable result returned by Grid.to_dict() and the future API endpoint."""
    solved: bool
    words: list[str]
    grid: dict[str, str]


class Solver:
    def __init__(self) -> None:
        self.letters: list[str] = []
        self.valid_words: list[str] = []
        self._word_score: dict[str, int] = {}   # word → connectivity score for first-word ordering
        self.grid: Grid | None = None
        # Diagnostic counters reset each solve() call
        self._bt_calls: int = 0
        self._fp_calls: int = 0

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def get_words_from_letters(self) -> None:
        key = tuple(sorted(self.letters))
        if key in _word_cache:
            self.valid_words = _word_cache[key]
            log.debug(f"  get_words_from_letters: cache hit ({len(self.valid_words)} words)")
            return
        valid_words = [w for w in ENGLISH_WORDS if set(w).issubset(set(self.letters))]
        valid_words = [w for w in valid_words if all(w.count(l) <= self.letters.count(l) for l in set(w))]
        n = len(self.letters)
        # Exclude words that would leave 1 or 2 tiles unplaceable,
        # but allow a word that uses all tiles exactly.
        self.valid_words = [w for w in valid_words if len(w) <= n - 3 or len(w) == n]
        _word_cache[key] = self.valid_words

    def get_word_scores(self) -> None:
        """
        Score each valid word by how many other valid words share at least one letter.
        Uses an inverted index (letter → word set) so this is O(n*k) not O(n³).
        """
        letter_to_words = defaultdict(set)
        for word in self.valid_words:
            for letter in set(word):
                letter_to_words[letter].add(word)

        self._word_score = {
            word: sum(len(letter_to_words[l]) - 1 for l in set(word))
            for word in self.valid_words
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _remaining_letters(self, grid: Grid) -> list[str]:
        """Return the multiset of letters not yet placed on the grid."""
        remaining = list(self.letters)
        for letter in grid.placements.values():
            remaining.remove(letter)
        return remaining

    def _ordered_first_words(self) -> list[str]:
        """
        Return valid_words sorted for use as the first word.
        Prefer words containing the rarest letter, then by highest connectivity score.
        """
        letter_counts = {
            l: sum(1 for w in self.valid_words if l in w)
            for l in set(self.letters)
        }
        rarest = min(letter_counts, key=lambda l: letter_counts[l])
        log.debug(f"  Rarest letter: '{rarest}' (appears in {letter_counts[rarest]} words)")
        rarest_words = sorted(
            [w for w in self.valid_words if rarest in w],
            key=lambda w: -self._word_score.get(w, 0)
        )
        other_words = [w for w in self.valid_words if rarest not in w]
        return rarest_words + other_words

    # ------------------------------------------------------------------
    # Backtracking search
    # ------------------------------------------------------------------

    def _backtrack(self, grid: Grid, candidates: set[str], letter_counts: dict[str, int]) -> bool:
        self._bt_calls += 1
        remaining = self._remaining_letters(grid)

        if self._bt_calls % 2000 == 0:
            log.debug(f"  [{self._bt_calls} backtracks, {self._fp_calls} find_placements] "
                      f"remaining={remaining!r}  candidates={len(candidates)}")

        if not remaining:
            valid, bad = grid.validate(ENGLISH_WORDS)
            if not valid:
                log.debug(f"  Solution rejected by validate(): {bad}")
            return valid

        # MRV: letter_counts is kept current, so this is now O(|unique remaining|).
        target = min(set(remaining), key=lambda l: letter_counts.get(l, 0))
        word_candidates = [w for w in candidates if target in w]
        if not word_candidates:
            log.debug(f"  Dead end: no candidate contains '{target}'")
            return False

        # Fix 1: only try words that share at least one letter with the current grid —
        # anything else cannot form a valid intersection.
        grid_letters = set(grid.placements.values())
        placeable = [w for w in word_candidates if any(l in grid_letters for l in w)]

        for word in placeable:
            self._fp_calls += 1
            for orientation, start in grid.find_placements(word, remaining):
                grid.place_word(word, orientation, start)

                # Fix 2: mutate candidates set and letter_counts in-place;
                # restore both on backtrack instead of rebuilding the list each call.
                candidates.discard(word)
                for l in set(word):
                    letter_counts[l] -= 1

                if self._backtrack(grid, candidates, letter_counts):
                    return True

                candidates.add(word)
                for l in set(word):
                    letter_counts[l] += 1

                grid.unplace_word(word)

        return False

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def solve(self, tiles: list[str]) -> Grid | None:
        self._bt_calls = 0
        self._fp_calls = 0
        t_total = time.perf_counter()

        self.letters = [t.lower() for t in tiles]
        self.grid = None

        t0 = time.perf_counter()
        self.get_words_from_letters()
        log.info(f"get_words_from_letters: {len(self.valid_words)} candidates  "
                 f"({time.perf_counter() - t0:.3f}s)")

        t0 = time.perf_counter()
        self.get_word_scores()
        log.info(f"get_word_scores:         scored {len(self._word_score)} words  "
                 f"({time.perf_counter() - t0:.3f}s)")

        if not self.valid_words:
            log.warning("No valid words found for these letters.")
            return None

        t0 = time.perf_counter()
        ordered = self._ordered_first_words()
        log.info(f"_ordered_first_words:    top candidate = '{ordered[0]}'  "
                 f"({time.perf_counter() - t0:.3f}s)")

        for attempt, first_word in enumerate(ordered, 1):
            log.debug(f"  Attempt {attempt}: first_word='{first_word}'  "
                      f"(score={self._word_score.get(first_word, 0)})")
            t0 = time.perf_counter()
            grid = Grid()
            grid.place_first_word(first_word)

            # candidates is a mutable set; letter_counts tracks how many candidates
            # contain each letter so MRV lookups are O(1) instead of O(n).
            candidates = {w for w in self.valid_words if w != first_word}
            letter_counts: dict[str, int] = defaultdict(int)
            for w in candidates:
                for l in set(w):
                    letter_counts[l] += 1

            if self._backtrack(grid, candidates, letter_counts):
                elapsed = time.perf_counter() - t0
                log.info(f"  Solved with first_word='{first_word}' on attempt {attempt}  "
                         f"({elapsed:.3f}s,  {self._bt_calls} backtracks,  "
                         f"{self._fp_calls} find_placements calls)")
                self.grid = grid
                log.info(f"Total solve time: {time.perf_counter() - t_total:.3f}s")
                return grid

        log.warning("No solution found.")
        return None


class Grid:
    def __init__(self) -> None:
        self.placements: dict[tuple[int, int], str] = {}    # (x, y) → letter
        self.placed_words: dict[str, dict[int, tuple[int, int]]] = {}  # word → {index: (x, y)}

    def place_first_word(self, word: str) -> None:
        self.placed_words[word] = {}
        for i, letter in enumerate(word):
            self.placements[(i, 0)] = letter
            self.placed_words[word][i] = (i, 0)

    def can_place(self, word_str: str, orientation: str, start: tuple[int, int]) -> bool:
        """Return True if word_str can legally be placed at start with the given orientation."""
        x, y = start
        n = len(word_str)

        # Reject if a tile immediately before or after would merge this word into a longer one
        if orientation == "H":
            if (x - 1, y) in self.placements or (x + n, y) in self.placements:
                return False
        else:
            if (x, y - 1) in self.placements or (x, y + n) in self.placements:
                return False

        for i, letter in enumerate(word_str):
            pos = (x + i, y) if orientation == "H" else (x, y + i)
            existing = self.placements.get(pos)

            # Conflict: cell is occupied by a different letter
            if existing is not None and existing != letter:
                return False

            # For cells that would be newly placed, check the perpendicular run length.
            # A run of exactly 2 would form an invalid short word.
            if existing is None:
                perp_dirs = [(0, -1), (0, 1)] if orientation == "H" else [(-1, 0), (1, 0)]
                run = 1
                for dx, dy in perp_dirs:
                    nx_, ny_ = pos[0] + dx, pos[1] + dy
                    while (nx_, ny_) in self.placements:
                        run += 1
                        nx_ += dx
                        ny_ += dy
                if run == 2:
                    return False

        return True

    def place_word(self, word_str: str, orientation: str, start: tuple[int, int]) -> bool:
        """Place word_str on the grid. Returns True on success, False if placement is invalid."""
        if not self.can_place(word_str, orientation, start):
            return False
        x, y = start
        self.placed_words[word_str] = {}
        for i, letter in enumerate(word_str):
            pos = (x + i, y) if orientation == "H" else (x, y + i)
            self.placements[pos] = letter
            self.placed_words[word_str][i] = pos
        return True

    def unplace_word(self, word_str: str) -> None:
        """Remove word_str from the grid, preserving cells shared with other placed words."""
        if word_str not in self.placed_words:
            return
        owned = set(self.placed_words[word_str].values())
        shared = {pos for w, coords in self.placed_words.items()
                  if w != word_str for pos in coords.values()}
        for pos in owned - shared:
            del self.placements[pos]
        del self.placed_words[word_str]

    def find_placements(self, word_str: str, remaining_letters: list[str]) -> list[Placement]:
        """
        Return all (orientation, start) pairs where word_str can legally be placed
        such that it intersects at least one existing grid tile and only consumes
        letters available in remaining_letters for new (non-intersecting) cells.
        """
        seen = set()
        results = []
        for (cx, cy), cell_letter in self.placements.items():
            for i, letter in enumerate(word_str):
                if letter != cell_letter:
                    continue
                for orientation in ("H", "V"):
                    start = (cx - i, cy) if orientation == "H" else (cx, cy - i)
                    if start in seen:
                        continue
                    # Collect letters needed from the remaining pool (new cells only)
                    needed = []
                    for j, wl in enumerate(word_str):
                        pos = (start[0] + j, start[1]) if orientation == "H" else (start[0], start[1] + j)
                        if pos not in self.placements:
                            needed.append(wl)
                    # Multiset availability check
                    avail = list(remaining_letters)
                    ok = True
                    for nl in needed:
                        if nl in avail:
                            avail.remove(nl)
                        else:
                            ok = False
                            break
                    if ok and self.can_place(word_str, orientation, start):
                        seen.add((orientation, start))
                        results.append((orientation, start))
        return results

    def display(self) -> None:
        """Print an ASCII representation of the current grid state."""
        if not self.placements:
            print("(empty grid)")
            return
        xs = [x for x, y in self.placements]
        ys = [y for x, y in self.placements]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        for y in range(min_y, max_y + 1):
            print("".join(self.placements.get((x, y), ".").upper()
                          for x in range(min_x, max_x + 1)))

    def to_dict(self) -> GridResult:
        """
        Return a serialisable summary of the grid, suitable for the CLI --json flag
        and the future API response.  Coordinates are normalised so the top-left
        occupied cell is always (0, 0).
        """
        if not self.placements:
            return {"solved": False, "words": [], "grid": {}}
        xs = [x for x, y in self.placements]
        ys = [y for x, y in self.placements]
        min_x, min_y = min(xs), min(ys)
        return {
            "solved": True,
            "words": sorted(self.placed_words.keys()),
            "grid": {
                f"{x - min_x},{y - min_y}": letter.upper()
                for (x, y), letter in self.placements.items()
            },
        }

    def validate(self, word_set: set[str]) -> tuple[bool, list[str]]:
        """
        Scan every horizontal and vertical run of 2+ consecutive tiles and verify
        each is a valid word of ≥3 letters in word_set.
        Returns (True, []) if all runs are valid, or (False, [invalid_words]) otherwise.
        """
        if not self.placements:
            return True, []

        xs = [x for x, y in self.placements]
        ys = [y for x, y in self.placements]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        invalid = []

        def check_runs(cells):
            run = []
            for cell in cells:
                if cell in self.placements:
                    run.append(self.placements[cell])
                else:
                    if len(run) >= 2:
                        word = ''.join(run)
                        if len(word) < 3 or word not in word_set:
                            invalid.append(word)
                    run = []
            if len(run) >= 2:
                word = ''.join(run)
                if len(word) < 3 or word not in word_set:
                    invalid.append(word)

        for y in range(min_y, max_y + 1):
            check_runs([(x, y) for x in range(min_x, max_x + 1)])
        for x in range(min_x, max_x + 1):
            check_runs([(x, y) for y in range(min_y, max_y + 1)])

        return len(invalid) == 0, invalid


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="solver",
        description="Q-Less puzzle solver — place all tiles in a valid crossword.",
    )
    parser.add_argument(
        "letters", nargs="*",
        help="Tile letters, e.g.  A B C D E F G H I J K L  or  ABCDEFGHIJKL",
    )
    parser.add_argument("--test", action="store_true", help="Run built-in test cases.")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging.")
    parser.add_argument("--quiet", action="store_true", help="Suppress all log output.")
    parser.add_argument("--json", action="store_true", help="Print result as JSON (implies --quiet).")
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Logging — configured here so importing the module elsewhere is clean.
    # ------------------------------------------------------------------
    if not args.quiet and not args.json:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S"
        ))
        log.addHandler(handler)
        log.setLevel(logging.DEBUG if args.debug else logging.INFO)
    log.propagate = False  # never fall through to the root logger

    # ------------------------------------------------------------------
    # Runner — shared by both --test and single-puzzle modes.
    # ------------------------------------------------------------------
    def run_case(label, tiles):
        if not args.json:
            print(f"\n{'=' * 44}")
            print(f"  {label}:  {' '.join(t.upper() for t in tiles)}")
            print(f"{'=' * 44}")
        solver = Solver()
        grid = solver.solve(tiles)
        if args.json:
            result = grid.to_dict() if grid else {"solved": False, "words": [], "grid": {}}
            print(json.dumps(result, indent=2))
        elif grid:
            grid.display()
        else:
            print("No solution found.")
        return grid

    # ------------------------------------------------------------------
    # Dispatch.
    # ------------------------------------------------------------------
    if args.test:
        from tests import TEST_CASES
        for name, tiles in TEST_CASES.items():
            run_case(name, tiles)

    elif args.letters:
        # Accept either space-separated tiles  (A B C …)  or one run  (ABC…)
        raw = args.letters
        if len(raw) == 1:
            raw = list(raw[0])
        run_case("puzzle", raw)

    else:
        parser.print_help()
        sys.exit(1)
