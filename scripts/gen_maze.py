#!/usr/bin/env python3
"""
gen_maze.py — generate & validate the "alimagine // odyssey" ASCII maze
for the GitHub profile README (repo: NurHabibAssolihudin).

Maze rules (fixed, deterministic, verifiable):
  * Grid = WIDTH x HEIGHT cells, walls '#', paths '·' (middle dot).
  * ENTRANCE on the left edge, EXIT on the right edge, both open to the outside.
  * The maze is solvable (a path exists from ENTRANCE to EXIT).
  * Cell (1,1) is marked '@' (Nur's mark, the start).
  * Optional quest marks: exactly one '@' inside the maze (contribution cells
    are the remaining '·' path cells).
  * Every path cell is reachable from the start cell (no trapped islands).

Usage:
  python scripts/gen_maze.py                    # print the maze (and verify it)
  python scripts/gen_maze.py --check            # verify only (exit 0/1)
  python scripts/gen_maze.py --validate-pr      # validate a maze PR (used in CI)
  python scripts/gen_maze.py --validate-pr --file=README.md   # against a specific file
"""

from __future__ import annotations

import random
import sys

# --- fixed maze parameters (locked for the quest) ---
WIDTH = 27
HEIGHT = 17
SEED = 20260723

# --- cell glyphs ---
WALL = "#"
PATH = "\u00b7"  # '·' middle dot
MARK = "@"


def build_maze(width: int = WIDTH, height: int = HEIGHT, seed: int = SEED) -> list[list[str]]:
    rng = random.Random(seed)
    grid = [[WALL] * width for _ in range(height)]

    # internal cells are odd-indexed; standard recursive backtracker
    def carve(x: int, y: int) -> None:
        grid[y][x] = PATH
        dirs = [(0, -2), (0, 2), (-2, 0), (2, 0)]
        rng.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 1 <= nx < width - 1 and 1 <= ny < height - 1 and grid[ny][nx] == WALL:
                grid[y + dy // 2][x + dx // 2] = PATH
                carve(nx, ny)

    carve(1, 1)

    # ENTRANCE / EXIT openings
    grid[1][0] = PATH
    grid[height - 2][width - 1] = PATH

    # Nur's mark at the start cell
    grid[1][1] = MARK

    return grid


def solve(grid: list[list[str]]) -> list[tuple[int, int]] | None:
    """BFS shortest path from start '@' to the exit opening on the right edge."""
    height, width = len(grid), len(grid[0])
    start = (1, 1)
    targets = [(y, width - 1) for y in range(height) if grid[y][width - 1] == PATH]
    queue: list[tuple[tuple[int, int], list[tuple[int, int]]]] = [(start, [start])]
    seen = {start}
    while queue:
        (y, x), path = queue.pop(0)
        if (y, x) in targets:
            return path
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            ny, nx = y + dy, x + dx
            if (
                0 <= ny < height
                and 0 <= nx < width
                and grid[ny][nx] in (PATH, MARK)
                and (ny, nx) not in seen
            ):
                seen.add((ny, nx))
                queue.append(((ny, nx), path + [(ny, nx)]))


def reachable_count(grid: list[list[str]]) -> int:
    """Number of path cells reachable from the start (no trapped islands)."""
    height, width = len(grid), len(grid[0])
    seen = {(1, 1)}
    stack = [(1, 1)]
    while stack:
        y, x = stack.pop()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            ny, nx = y + dy, x + dx
            if (
                0 <= ny < height
                and 0 <= nx < width
                and grid[ny][nx] in (PATH, MARK)
                and (ny, nx) not in seen
            ):
                seen.add((ny, nx))
                stack.append((ny, nx))
    return len(seen)


def render(grid: list[list[str]]) -> str:
    return "\n".join("".join(row) for row in grid)


def verify(grid: list[list[str]], expect_single_mark: bool = True) -> list[str]:
    problems: list[str] = []
    height, width = len(grid), len(grid[0])
    if grid[1][0] != PATH:
        problems.append("ENTRANCE is not open on the left edge (row 1).")
    if grid[height - 2][width - 1] != PATH:
        problems.append("EXIT is not open on the right edge.")
    if grid[1][1] != MARK:
        problems.append("Start cell (1,1) is not marked '@'.")
    marks = sum(row.count(MARK) for row in grid)
    if expect_single_mark and marks != 1:
        problems.append(f"Expected exactly 1 mark '@', found {marks}.")
    path = solve(grid)
    if path is None:
        problems.append("Maze is UNSOLVABLE (no path from ENTRANCE to EXIT).")
    path_count = len(path) if path else 0
    total_paths = sum(row.count(PATH) for row in grid)
    if total_paths == 0:
        problems.append("No path cells — nothing to contribute to.")
    return problems, path, path_count, total_paths


def _load_readme_maze(path: str = "README.md") -> list[list[str]] | None:
    """Extract the maze grid from the README (between the ``` code fences)."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print(f"error: cannot read README.md: {exc}", file=sys.stderr)
        return None

    marker = "## §4"
    idx = text.find(marker)
    if idx == -1:
        idx = text.find("odyssey maze")
    # find the code fence that directly precedes a full-wall row (# only),
    # which is the maze itself — this avoids picking up the ```txt fences
    # in the "Cara bermain" section.
    start = idx
    fence = -1
    while True:
        fence = text.find("```", fence + 1)
        if fence == -1:
            break
        after = text[fence + 3:]
        # skip blank/whitespace lines after the fence, then inspect first non-empty line
        lines_after = after.splitlines()
        nxt_line = next((ln for ln in lines_after if ln.strip()), "")
        if nxt_line.strip().startswith("#") and set(nxt_line.strip()) == {"#"}:
            break
    if fence == -1:
        print("error: maze code fence not found in README", file=sys.stderr)
        return None
    end = text.find("```", fence + 3)
    if end == -1:
        print("error: maze closing fence not found in README", file=sys.stderr)
        return None
    block = text[fence + 3:end]
    lines = [line for line in block.splitlines() if line.strip()]
    grid = [list(line) for line in lines]
    if not grid:
        print("error: empty maze block", file=sys.stderr)
        return None
    return grid


def validate_contribution(readme_path: str = "README.md") -> int:
    """Validate that a PR modifies the maze correctly:
    exactly one path cell '·' -> '@', no other walls/marks changed."""
    base = build_maze()  # the pristine maze (what main should look like)
    contrib = _load_readme_maze(readme_path)
    if contrib is None:
        return 1

    if len(contrib) != len(base) or any(len(r) != len(b) for r, b in zip(contrib, base)):
        print("error: maze dimensions changed — do not resize the maze", file=sys.stderr)
        return 1

    changes: list[tuple[tuple[int, int], str, str]] = []
    for y, (crow, brow) in enumerate(zip(contrib, base)):
        for x, (cc, bc) in enumerate(zip(crow, brow)):
            if cc != bc:
                changes.append(((y, x), bc, cc))

    if len(changes) != 1:
        print(
            f"error: expected exactly 1 changed cell, found {len(changes)}. "
            "Change exactly one path cell '·' into '@'.",
            file=sys.stderr,
        )
        return 1

    (y, x), before, after = changes[0]
    if before != "\u00b7" or after != "@":
        print(
            f"error: invalid change at ({x},{y}) — must be '·' -> '@', "
            f"got '{before}' -> '{after}'",
            file=sys.stderr,
        )
        return 1

    # verify the edited maze is still solvable & connected
    # (a contribution legitimately adds a 2nd '@' mark, so skip the single-mark check)
    problems, path, path_count, total_paths = verify(contrib, expect_single_mark=False)
    if problems:
        for p in problems:
            print(f"error: {p}", file=sys.stderr)
        return 1
    if path_count == 0:
        print("error: no path found", file=sys.stderr)
        return 1

    # the placed mark must be on a reachable path cell (not an isolated pocket)
    seen = {(1, 1)}
    stack = [(1, 1)]
    while stack:
        cy, cx = stack.pop()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            ny, nx = cy + dy, cx + dx
            if (
                0 <= ny < len(contrib)
                and 0 <= nx < len(contrib[0])
                and contrib[ny][nx] in (PATH, MARK)
                and (ny, nx) not in seen
            ):
                seen.add((ny, nx))
                stack.append((ny, nx))
    if (y, x) not in seen:
        print(f"error: mark at ({x},{y}) is not reachable from the start — pick a connected path cell.", file=sys.stderr)
        return 1

    print(f"OK — mark placed at ({x},{y}); maze still solvable ({path_count} steps).", file=sys.stderr)
    return 0


def main() -> int:
    check_only = "--check" in sys.argv
    validate_pr = "--validate-pr" in sys.argv

    if validate_pr:
        # optional: --file=<path> for testing
        fpath = "README.md"
        for arg in sys.argv[1:]:
            if arg.startswith("--file="):
                fpath = arg.split("=", 1)[1]
        return validate_contribution(fpath)

    grid = build_maze()
    text = render(grid)
    problems, path, path_count, total_paths = verify(grid)

    if not check_only:
        print(text)
    print("\n# diagnostics", file=sys.stderr)
    print(f"# size           : {WIDTH}x{HEIGHT} (inner path region)", file=sys.stderr)
    print(f"# path cells     : {total_paths}", file=sys.stderr)
    print(f"# solution length: {path_count} cells (shortest BFS)", file=sys.stderr)
    print(f"# reachable      : {reachable_count(grid)}/{total_paths} (no islands)", file=sys.stderr)
    if problems:
        print("# PROBLEMS:", file=sys.stderr)
        for p in problems:
            print(f"#   - {p}", file=sys.stderr)
        return 1
    print("# OK — maze is solvable and safe to ship.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
