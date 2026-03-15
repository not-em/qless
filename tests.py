"""
Test cases for the Q-Less solver.

Run directly to exercise all cases with INFO logging:
    python tests.py

Or via the solver CLI:
    python solver.py --test
"""
from __future__ import annotations

import logging
import sys

TEST_CASES: dict[str, list[str]] = {
    # Original test case
    "baskdangtntt":  ["b", "a", "s", "k", "d", "a", "n", "g", "t", "n", "t", "t"],
    # Common letters — several short crossing words expected
    "catsdogripen":  ["c", "a", "t", "s", "d", "o", "g", "r", "i", "p", "e", "n"],
    # Mix of vowel-heavy and consonant tiles
    "helpstoneric":  ["h", "e", "l", "p", "s", "t", "o", "n", "e", "r", "i", "c"],
}

if __name__ == "__main__":
    from solver import Solver

    log = logging.getLogger("qless")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S"
    ))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False

    passed = 0
    for label, tiles in TEST_CASES.items():
        print(f"\n{'=' * 44}")
        print(f"  {label}:  {' '.join(t.upper() for t in tiles)}")
        print(f"{'=' * 44}")
        grid = Solver().solve(tiles)
        if grid:
            grid.display()
            passed += 1
        else:
            print("  ✗  No solution found.")

    print(f"\n{passed}/{len(TEST_CASES)} test cases solved.")

