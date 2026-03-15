"""
Q-Less solver API.

Serves the static game files (index.html, words.txt) and exposes a single
endpoint:

    POST /api/solve   {"tiles": ["a", "b", ...]}
                   → GridResult (see solver.py)

Run locally:
    uvicorn api:app --reload

Deploy (Render / Railway):
    start command: uvicorn api:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from solver import Solver, GridResult

_HERE = Path(__file__).parent

# ---------------------------------------------------------------------------
# Logging — reuse the same "qless" logger the solver already emits to.
# ---------------------------------------------------------------------------
log = logging.getLogger("qless")
if not log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S"
    ))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Q-Less Solver",
    description="Solve a Q-Less puzzle given a set of letter tiles.",
    version="1.0.0",
)

# CORS — allows the HTML to call the API from any origin (e.g. during local dev
# or if the front-end is ever served from a different host in the future).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class SolveRequest(BaseModel):
    tiles: list[str]

    @field_validator("tiles")
    @classmethod
    def validate_tiles(cls, v: list[str]) -> list[str]:
        if len(v) < 5 or len(v) > 19:
            raise ValueError(f"expected 5–19 tiles, got {len(v)}")
        for t in v:
            if len(t) != 1 or not t.isalpha():
                raise ValueError(f"each tile must be a single letter; got {t!r}")
        return [t.upper() for t in v]


class SolveResponse(BaseModel):
    solved: bool
    words: list[str]
    grid: dict[str, str]


# ---------------------------------------------------------------------------
# Endpoints  (must be registered BEFORE the static-file catch-all mount)
# ---------------------------------------------------------------------------
@app.post("/api/solve", response_model=SolveResponse, summary="Solve a Q-Less puzzle")
async def solve(request: SolveRequest) -> SolveResponse:
    """
    Accept a list of letter tiles and return a solved crossword layout.

    - **tiles**: list of 5–19 single-letter strings (case-insensitive)

    On success, **grid** maps `"x,y"` coordinate strings to uppercase letters,
    with the top-left occupied cell normalised to `"0,0"`.
    """
    log.info(f"POST /api/solve  tiles={''.join(request.tiles)}")
    solver = Solver()
    grid = solver.solve(request.tiles)

    if grid is None:
        return SolveResponse(solved=False, words=[], grid={})

    result: GridResult = grid.to_dict()
    return SolveResponse(**result)


# ---------------------------------------------------------------------------
# Static files — served last so API routes always take priority.
# html=True makes StaticFiles serve index.html for "/" automatically.
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory=str(_HERE), html=True), name="static")

