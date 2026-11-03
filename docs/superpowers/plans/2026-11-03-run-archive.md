# Run Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish each desk run as its own directory and show it on a public page after it is merged to `main`.

**Architecture:** `run-dir` allocates `.tradingagents/<TICKER>/<YYYY-MM-DD>/<time>/` and never deletes an older run. The workflow records the `rating.md` paths that existed before the agent, checks the single new directory, and opens a pull request with only that directory. `docs/index.html` is a static shell: it lists runs from the GitHub tree API and fetches the markdown from `main` when the page opens.

**Tech Stack:** Python 3.12, pytest, GitHub Actions, one HTML file, `marked@15.0.12`, DOMPurify `3.2.6`.

## Global Constraints

- Work on branch `run-archive`. Do not commit on `main`.
- A run directory is `.tradingagents/<TICKER>/<YYYY-MM-DD>/<time>/`. `<time>` is `HHMMSS`, then `HHMMSS-2` through `HHMMSS-99`. A full second exits 1 and creates nothing.
- The date and the time come from one clock. A provided clock is read as its wall time, with no timezone conversion. The real command passes no clock.
- The workflow checks out `main` with `persist-credentials: false`. The agent step sets `GITHUB_TOKEN` and `GH_TOKEN` to empty.
- Workflow permissions are `contents: write`, `pull-requests: write`, and `actions: write`.
- The branch is `tradingagents/{branch_ticker(ticker)}/{YYYY-MM-DD}-{time}` where `branch_ticker` in `tradingagents.run_result` returns `ticker.encode("ascii").hex()` so ref names stay valid when the run directory ticker is `^GSPC`, `A..B`, or similar. The commit subject and pull request title are `tradingagents: <TICKER> <YYYY-MM-DD> <time>` with the real ticker. The body is the rating line, a blank line, and the run path under `.tradingagents/<TICKER>/…`.
- The commit author on the runner is `github-actions[bot]` (`41898282+github-actions[bot]@users.noreply.github.com`).
- The workflow does not push `main`, does not approve, and does not merge.
- The page names `kevinkantkode/TradingAgents` and `main`. It makes anonymous reads. It has no button that starts the workflow.
- The ledger stays at `~/.tradingagents/ledger.jsonl` and is not on the page.
- Notes, in order: `market.md`, `fundamentals.md`, `news.md`, `sentiment.md`, `bull.md`, `bear.md`, `omissions.md`, `plan.md`, `proposal.md`, `aggressive.md`, `conservative.md`, `neutral.md`, `rating.md`.
- `marked` and DOMPurify load from jsDelivr. The script URLs are `https://cdn.jsdelivr.net/npm/marked@15.0.12/marked.min.js` and `https://cdn.jsdelivr.net/npm/dompurify@3.2.6/dist/purify.min.js`.

---

### Task 1: Unique run directories

**Files:**
- Modify: `tradingagents/data/rundir.py`
- Modify: `tradingagents/cli.py:29-32`
- Modify: `README.md:13`
- Modify: `.cursor/skills/tradingagents/SKILL.md:16`
- Modify: `.gitignore:230-231`
- Test: `tests/test_rundir.py`
- Test: `tests/test_tradingagents_contract.py`

**Interfaces:**
- Consumes: `ticker_path_segment(raw: str) -> str` and `TradingAgentsError`.
- Produces: `prepare_run_dir(ticker: str, *, base: Path | None = None, now: datetime | None = None) -> Path`. The returned path is absolute. A second call with the same ticker and clock returns a different directory and leaves the first directory's files in place.

- [ ] **Step 1: Branch and commit the spec**

```bash
git checkout -b run-archive
git add docs/superpowers/specs/2026-11-03-run-archive-design.md
git commit -m "$(cat <<'EOF'
docs: specify the public run archive

EOF
)"
```

Expected: `main` is unchanged and the new commit is on `run-archive`.

- [ ] **Step 2: Write the failing directory tests**

Replace `tests/test_rundir.py` with:

```python
import re
from datetime import date, datetime
from pathlib import Path

import pytest

from tradingagents.cli import main
from tradingagents.data.errors import TradingAgentsError
from tradingagents.data.rundir import prepare_run_dir, ticker_path_segment


def test_ticker_path_segment_uppercases_ascii_letters_only():
    assert ticker_path_segment("nvda") == "NVDA"
    assert ticker_path_segment("0700.HK") == "0700.HK"


def test_prepare_run_dir_keeps_the_earlier_run(tmp_path):
    moment = datetime(2026, 11, 3, 23, 1, 55)
    first = prepare_run_dir("nvda", base=tmp_path, now=moment)
    (first / "bull.md").write_text("old", encoding="utf-8")

    second = prepare_run_dir("nvda", base=tmp_path, now=moment)

    assert first == (tmp_path / ".tradingagents" / "NVDA" / "2026-11-03" / "230155").resolve()
    assert (first / "bull.md").read_text(encoding="utf-8") == "old"
    assert second == first.parent / "230155-2"
    assert second.is_dir()
    assert not any(second.iterdir())


def test_prepare_run_dir_third_call_uses_the_next_suffix(tmp_path):
    moment = datetime(2026, 11, 3, 23, 1, 55)
    prepare_run_dir("NVDA", base=tmp_path, now=moment)
    prepare_run_dir("NVDA", base=tmp_path, now=moment)
    third = prepare_run_dir("NVDA", base=tmp_path, now=moment)
    assert third.name == "230155-3"


def test_prepare_run_dir_stops_at_suffix_99(tmp_path):
    moment = datetime(2026, 11, 3, 23, 1, 55)
    day = tmp_path / ".tradingagents" / "NVDA" / "2026-11-03"
    day.mkdir(parents=True)
    (day / "230155").mkdir()
    for n in range(2, 100):
        (day / f"230155-{n}").mkdir()

    with pytest.raises(TradingAgentsError, match="230155-99"):
        prepare_run_dir("NVDA", base=tmp_path, now=moment)

    assert not (day / "230155-100").exists()


def test_run_dir_cli_prints_absolute_path(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = main(["run-dir", "NVDA"])
    assert code == 0
    line = capsys.readouterr().out.strip()
    path = Path(line)
    assert path.is_absolute()
    assert path.parent.parent == (tmp_path / ".tradingagents" / "NVDA").resolve()
    assert path.parent.name == date.today().isoformat()
    assert re.fullmatch(r"\d{6}", path.name)


def test_run_dir_rejects_unsafe_ticker():
    assert main(["run-dir", ".."]) == 1
```

Append to `tests/test_tradingagents_contract.py`:

```python
def test_tradingagents_skill_uses_a_unique_run_directory():
    text = SKILL.read_text(encoding="utf-8")
    assert "<local-date>/<HHMMSS>/" in text
    assert "wipe" not in text.lower()


def test_run_directory_is_not_gitignored():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".tradingagents/" not in text
```

- [ ] **Step 3: Run the new tests and confirm they fail**

Run: `pytest tests/test_rundir.py tests/test_tradingagents_contract.py::test_tradingagents_skill_uses_a_unique_run_directory tests/test_tradingagents_contract.py::test_run_directory_is_not_gitignored -v`

Expected: FAIL. `prepare_run_dir` does not accept `now`, the skill has no `<HHMMSS>/` segment, and `.gitignore` still contains `.tradingagents/`.

- [ ] **Step 4: Implement the directory allocator**

Replace `tradingagents/data/rundir.py` with:

```python
"""Prepare one run directory."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from tradingagents.data.errors import TradingAgentsError
from tradingagents.data.symbols import safe_ticker_component


def ticker_path_segment(raw: str) -> str:
    """Path segment for ``.tradingagents/<segment>/``: validate, uppercase ASCII letters only."""
    stripped = raw.strip()
    try:
        safe_ticker_component(stripped)
    except ValueError as exc:
        raise TradingAgentsError(str(exc)) from exc
    return "".join(c.upper() if c.isascii() and c.isalpha() else c for c in stripped)


def prepare_run_dir(
    ticker: str,
    *,
    base: Path | None = None,
    now: datetime | None = None,
) -> Path:
    """Create ``.tradingagents/<ticker>/<local-date>/<HHMMSS>/`` under *base*.

    A provided *now* is read as its wall time, with no timezone conversion.
    An existing directory is left in place. The next free suffix is ``-2``
    through ``-99``.
    """
    segment = ticker_path_segment(ticker)
    moment = now if now is not None else datetime.now()
    day = moment.date().isoformat()
    stamp = f"{moment.hour:02d}{moment.minute:02d}{moment.second:02d}"
    root = (base or Path.cwd()).resolve() / ".tradingagents" / segment / day
    names = [stamp, *[f"{stamp}-{n}" for n in range(2, 100)]]
    for name in names:
        run_dir = root / name
        if not run_dir.exists():
            run_dir.mkdir(parents=True)
            return run_dir.resolve()
    raise TradingAgentsError(
        f"no free run directory for {segment} on {day} from {stamp} through {stamp}-99"
    )
```

In `tradingagents/cli.py`, change the `run-dir` help to:

```python
        help="create an empty .tradingagents/<TICKER>/<local-date>/<HHMMSS>/ run directory",
```

- [ ] **Step 5: Run the directory tests**

Run: `pytest tests/test_rundir.py -v`

Expected: PASS.

- [ ] **Step 6: Update the words and stop ignoring the directory**

In `README.md`, replace the `run-dir` sentence with:

```markdown
`tradingagents run-dir TICKER` creates an empty `.tradingagents/<TICKER>/<local-date>/<HHMMSS>/` run folder and prints its absolute path. A second run in that same second uses `HHMMSS-2`, then `HHMMSS-3`, through `HHMMSS-99`. An older run is left in place.
```

In `.cursor/skills/tradingagents/SKILL.md`, replace the run-directory paragraph with:

```markdown
Before step 1, run `tradingagents run-dir TICKER` with the user's ticker. Stdout is one line: the absolute path to an empty run directory (`.tradingagents/<TICKER>/<local-date>/<HHMMSS>/` under the current working directory). A taken name gets the next suffix, `-2` through `-99`. Use the printed path. Exit non-zero stops the run. All deliverable paths below are files in that directory.
```

Delete these two lines from `.gitignore`:

```gitignore
# Cursor desk run deliverables (local-date folders under .tradingagents/<TICKER>/)
.tradingagents/
```

- [ ] **Step 7: Run the contract tests**

Run: `pytest tests/test_rundir.py tests/test_tradingagents_contract.py -v`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tradingagents/data/rundir.py tradingagents/cli.py tests/test_rundir.py tests/test_tradingagents_contract.py README.md .cursor/skills/tradingagents/SKILL.md .gitignore
git commit -m "$(cat <<'EOF'
feat: keep every desk run directory

EOF
)"
```

### Task 2: Find the new run

**Files:**
- Modify: `tradingagents/run_result.py`
- Test: `tests/test_tradingagents_workflow.py`

**Interfaces:**
- Consumes: `TradingAgentsError` and `assert_run_result(run_root: Path) -> str`. `assert_run_result` stays as it is.
- Produces: `new_run_directory(before: set[Path], after: set[Path]) -> Path`. Both sets are `rating.md` paths. The same file given once as a relative path and once as an absolute path is one path. The return value is the parent of the single new file. Zero new files, or more than one, raises `TradingAgentsError`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tradingagents_workflow.py`:

```python
def test_new_run_directory_returns_the_one_new_parent(tmp_path: Path):
    old = tmp_path / "NVDA" / "2026-11-03" / "120000" / "rating.md"
    new = tmp_path / "NVDA" / "2026-11-03" / "120001" / "rating.md"
    old.parent.mkdir(parents=True)
    new.parent.mkdir(parents=True)
    old.write_text("Hold\n", encoding="utf-8")
    new.write_text("Buy\n", encoding="utf-8")
    assert new_run_directory({old}, {old, new}) == new.parent


def test_new_run_directory_rejects_none_or_two(tmp_path: Path):
    first = tmp_path / "a" / "rating.md"
    second = tmp_path / "b" / "rating.md"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("Buy\n", encoding="utf-8")
    second.write_text("Hold\n", encoding="utf-8")
    with pytest.raises(TradingAgentsError, match="found 0"):
        new_run_directory({first}, {first})
    with pytest.raises(TradingAgentsError, match="found 2"):
        new_run_directory(set(), {first, second})


def test_new_run_directory_treats_one_file_as_one_path(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    old = Path(".tradingagents/NVDA/2026-11-03/120000/rating.md")
    new = Path(".tradingagents/NVDA/2026-11-03/120001/rating.md")
    old.parent.mkdir(parents=True)
    new.parent.mkdir(parents=True)
    old.write_text("Buy\n", encoding="utf-8")
    new.write_text("Sell\n", encoding="utf-8")
    found = new_run_directory({old}, {old.resolve(), new.resolve()})
    assert found == new.resolve().parent
```

Add `new_run_directory` to the import from `tradingagents.run_result`.

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `pytest tests/test_tradingagents_workflow.py::test_new_run_directory_returns_the_one_new_parent tests/test_tradingagents_workflow.py::test_new_run_directory_rejects_none_or_two tests/test_tradingagents_workflow.py::test_new_run_directory_treats_one_file_as_one_path -v`

Expected: FAIL with `ImportError` because `new_run_directory` is not defined.

- [ ] **Step 3: Implement the helper**

Append to `tradingagents/run_result.py`:

```python
def new_run_directory(before: set[Path], after: set[Path]) -> Path:
    before_resolved = {path.resolve() for path in before}
    new = sorted(path.resolve() for path in after if path.resolve() not in before_resolved)
    if len(new) != 1:
        raise TradingAgentsError(f"expected one new rating.md, found {len(new)}: {new}")
    return new[0].parent
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_tradingagents_workflow.py -v`

Expected: PASS. The older `assert_run_result` tests still pass.

- [ ] **Step 5: Commit**

```bash
git add tradingagents/run_result.py tests/test_tradingagents_workflow.py
git commit -m "$(cat <<'EOF'
feat: identify the rating file created by one run

EOF
)"
```

### Task 3: Open a pull request

**Files:**
- Modify: `.github/workflows/tradingagents.yml`
- Modify: `tests/test_tradingagents_workflow.py` (the workflow text test)
- Delete: `scripts/fetch-tradingagents.sh`
- Delete: `.cursor/skills/fetch-tradingagents/SKILL.md`

**Interfaces:**
- Consumes: `new_run_directory(before: set[Path], after: set[Path]) -> Path` and `assert_run_result(run_root: Path) -> str`.
- Produces: a `workflow_dispatch` job that writes `$RUNNER_TEMP/tradingagents/run_dir.txt` after a valid new rating, copies that directory aside, and opens a pull request. A failed rating check does not copy the directory.

- [ ] **Step 1: Replace the workflow text test**

Replace `test_workflow_is_dispatch_only_and_publishes_the_run_folder` in `tests/test_tradingagents_workflow.py` with:

```python
def test_workflow_is_dispatch_only_and_opens_a_pull_request():
    text = Path(".github/workflows/tradingagents.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "schedule:" not in text
    assert "ROBINHOOD" not in text.upper()
    assert "CURSOR_API_KEY" in text
    assert "contents: write" in text
    assert "pull-requests: write" in text
    assert "actions: write" in text
    assert "persist-credentials: false" in text
    assert 'GITHUB_TOKEN: ""' in text
    assert "new_run_directory" in text
    assert "tradingagents/" in text
    assert "gh pr create" in text
    assert "if: failure()" in text
    assert "HEAD:main" not in text
    assert "git push origin main" not in text
    assert "ledger.jsonl" not in text
    assert "name: tradingagents" in text
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `pytest tests/test_tradingagents_workflow.py::test_workflow_is_dispatch_only_and_opens_a_pull_request -v`

Expected: FAIL because the workflow still says `contents: read` and does not call `gh pr create`.

- [ ] **Step 3: Replace the workflow**

Replace `.github/workflows/tradingagents.yml` with:

```yaml
# One ticker, dispatched by hand. A passed run opens a pull request.
name: tradingagents

on:
  workflow_dispatch:
    inputs:
      ticker:
        description: Ticker
        required: true
        type: string

permissions:
  contents: write
  pull-requests: write
  actions: write

concurrency:
  group: tradingagents-${{ inputs.ticker }}
  cancel-in-progress: false

jobs:
  run:
    name: run
    runs-on: ubuntu-latest
    timeout-minutes: 180
    steps:
      - uses: actions/checkout@v7
        with:
          ref: main
          persist-credentials: false

      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"

      - name: Install tradingagents
        run: |
          python -m pip install --upgrade pip
          pip install .

      - name: Install Cursor CLI
        run: |
          curl https://cursor.com/install -fsS | bash
          if [ -x "$HOME/.cursor/bin/agent" ]; then
            echo "$HOME/.cursor/bin" >> "$GITHUB_PATH"
          elif [ -x "$HOME/.local/bin/agent" ]; then
            echo "$HOME/.local/bin" >> "$GITHUB_PATH"
          else
            echo "agent binary not found after install" >&2
            exit 1
          fi

      - name: Record existing ratings
        run: |
          set -euo pipefail
          mkdir -p "$RUNNER_TEMP/tradingagents"
          if [ -d .tradingagents ]; then
            find .tradingagents -name rating.md -type f | sort > "$RUNNER_TEMP/tradingagents/before.txt"
          else
            : > "$RUNNER_TEMP/tradingagents/before.txt"
          fi

      - name: Run
        env:
          CURSOR_API_KEY: ${{ secrets.CURSOR_API_KEY }}
          TICKER: ${{ inputs.ticker }}
          GH_TOKEN: ""
          GITHUB_TOKEN: ""
        run: |
          set -euo pipefail
          if [ -f .cursor/mcp.json ]; then
            mv .cursor/mcp.json .cursor/mcp.json.off
          fi
          python -c 'import os; from pathlib import Path; from tradingagents.run_result import dispatcher_prompt; Path("run-prompt.txt").write_text(dispatcher_prompt(os.environ["TICKER"]), encoding="utf-8")'
          agent -p --force --model composer-2.5 --output-format text "$(cat run-prompt.txt)"

      - name: Check rating
        run: |
          python << 'PY'
          import os
          from pathlib import Path
          from tradingagents.run_result import assert_run_result, branch_ticker, new_run_directory

          meta = Path(os.environ["RUNNER_TEMP"]) / "tradingagents"
          before = {Path(line) for line in (meta / "before.txt").read_text(encoding="utf-8").splitlines() if line.strip()}
          root = Path(".tradingagents")
          after = set(root.rglob("rating.md")) if root.is_dir() else set()
          run_dir = new_run_directory(before, after)
          rating = assert_run_result(run_dir)
          rel = run_dir.resolve().relative_to(Path.cwd().resolve())
          if len(rel.parts) != 4 or rel.parts[0] != ".tradingagents":
              raise SystemExit(f"unexpected run path: {rel}")
          ticker, day, time = rel.parts[1], rel.parts[2], rel.parts[3]
          (meta / "run_dir.txt").write_text(str(run_dir.resolve()), encoding="utf-8")
          (meta / "rel.txt").write_text(rel.as_posix(), encoding="utf-8")
          (meta / "branch.txt").write_text(f"tradingagents/{branch_ticker(ticker)}/{day}-{time}", encoding="utf-8")
          (meta / "title.txt").write_text(f"tradingagents: {ticker} {day} {time}", encoding="utf-8")
          (meta / "body.txt").write_text(f"{rating}\n\n{rel.as_posix()}/\n", encoding="utf-8")
          print(rating)
          PY

      - name: Keep the run directory
        if: success()
        run: |
          set -euo pipefail
          run_dir="$(cat "$RUNNER_TEMP/tradingagents/run_dir.txt")"
          rm -rf "$RUNNER_TEMP/tradingagents/saved"
          mkdir -p "$RUNNER_TEMP/tradingagents/saved/run"
          cp -a "$run_dir/." "$RUNNER_TEMP/tradingagents/saved/run/"

      - name: Open pull request
        if: success()
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -euo pipefail
          meta="$RUNNER_TEMP/tradingagents"
          rel="$(cat "$meta/rel.txt")"
          branch="$(cat "$meta/branch.txt")"
          title="$(cat "$meta/title.txt")"
          git fetch origin main
          git checkout --force -B "$branch" origin/main
          git reset --hard origin/main
          git clean -fd
          mkdir -p "$rel"
          cp -a "$meta/saved/run/." "$rel/"
          git add -- "$rel"
          git -c user.name='github-actions[bot]' -c user.email='41898282+github-actions[bot]@users.noreply.github.com' commit -m "$title"
          git push "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" "HEAD:refs/heads/${branch}"
          gh pr create --base main --head "$branch" --title "$title" --body-file "$meta/body.txt"

      - name: Upload failed run
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: tradingagents-run
          path: ${{ runner.temp }}/tradingagents/saved/run
          if-no-files-found: ignore
          retention-days: 90
```

The fetch of `origin/main` has no token because the checkout does not persist credentials. This repository is public, so that fetch works. Do not turn `persist-credentials` back on. The agent step would then be able to push.

- [ ] **Step 4: Delete the fetch path**

Delete `scripts/fetch-tradingagents.sh` and `.cursor/skills/fetch-tradingagents/SKILL.md`.

Run: `rg -n "fetch-tradingagents" -g '!docs/superpowers/**'`

Expected: no matches.

- [ ] **Step 5: Run the workflow tests**

Run: `pytest tests/test_tradingagents_workflow.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/tradingagents.yml tests/test_tradingagents_workflow.py
git add -u scripts/fetch-tradingagents.sh .cursor/skills/fetch-tradingagents/SKILL.md
git commit -m "$(cat <<'EOF'
feat: open a pull request for a finished desk run

EOF
)"
```

### Task 4: The page

**Files:**
- Create: `docs/index.html`
- Create: `docs/.nojekyll`
- Test: `tests/test_snapshot.py`

**Interfaces:**
- Consumes: the `| Date | Close |` table printed by `snapshot_text`. The header row is `| Date | Close |` and the separator is `|---|---:|`. A body row is `| YYYY-MM-DD | <close> |`.
- Produces: `docs/index.html`, which lists `.tradingagents/<TICKER>/<YYYY-MM-DD>/<time>/rating.md` from `main` and renders one run. No Python function is added.

- [ ] **Step 1: Lock the close table**

In `tests/test_snapshot.py`, extend `test_marker_uses_the_last_closed_row_and_matches_the_table` with:

```python
    assert "| Date | Close |" in text
    assert "|---|---:|" in text
    assert "| 2026-11-02 | 187.25 |" in text
```

- [ ] **Step 2: Run the snapshot test**

Run: `pytest tests/test_snapshot.py::test_marker_uses_the_last_closed_row_and_matches_the_table -v`

Expected: PASS. The table is already printed. This assertion locks it.

- [ ] **Step 3: Write the page**

Create an empty `docs/.nojekyll`.

Create `docs/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TradingAgents</title>
<script src="https://cdn.jsdelivr.net/npm/marked@15.0.12/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/dompurify@3.2.6/dist/purify.min.js"></script>
<style>
  body { font: 16px/1.45 system-ui, sans-serif; margin: 0; color: #1a1a1a; }
  main { display: grid; grid-template-columns: 16rem 1fr; min-height: 100vh; }
  nav { border-right: 1px solid #ddd; padding: 1rem; }
  article { padding: 1rem 1.5rem 3rem; max-width: 48rem; }
  button { display: block; width: 100%; text-align: left; margin: 0 0 0.5rem; padding: 0.4rem 0.5rem; background: #fff; }
  .status { color: #555; }
  svg { width: 100%; height: auto; }
  table { border-collapse: collapse; }
  td, th { border: 1px solid #ccc; padding: 0.2rem 0.4rem; }
  @media (max-width: 700px) {
    main { grid-template-columns: 1fr; }
    nav { border-right: 0; border-bottom: 1px solid #ddd; }
  }
</style>
</head>
<body>
<main>
  <nav id="runs"><p class="status">Loading runs.</p></nav>
  <article id="run"></article>
</main>
<script>
const REPO = "kevinkantkode/TradingAgents";
const BRANCH = "main";
const NOTES = [
  "market.md", "fundamentals.md", "news.md", "sentiment.md",
  "bull.md", "bear.md", "omissions.md", "plan.md", "proposal.md",
  "aggressive.md", "conservative.md", "neutral.md", "rating.md"
];
const RUN_RE = /^\.tradingagents\/([^/]+)\/(\d{4}-\d{2}-\d{2})\/(\d{6}(?:-(?:[2-9]|[1-9]\d))?)\/rating\.md$/;
const SVG = "http://www.w3.org/2000/svg";
let view = 0;

function rawUrl(path) {
  return "https://raw.githubusercontent.com/" + REPO + "/" + BRANCH + "/"
    + path.split("/").map(encodeURIComponent).join("/");
}

function parseRun(path) {
  const match = RUN_RE.exec(path);
  if (!match) return null;
  return { path: path, ticker: match[1], date: match[2], time: match[3] };
}

function timeRank(time) {
  const match = /^(\d{6})(?:-(\d+))?$/.exec(time);
  return [Number(match[1]), match[2] ? Number(match[2]) : 0];
}

function compareRuns(a, b) {
  if (a.date !== b.date) return a.date < b.date ? 1 : -1;
  const [aStamp, aSuffix] = timeRank(a.time);
  const [bStamp, bSuffix] = timeRank(b.time);
  if (aStamp !== bStamp) return bStamp - aStamp;
  return bSuffix - aSuffix;
}

function splitRow(line) {
  const trimmed = line.trim();
  if (!trimmed.startsWith("|")) return null;
  const cells = trimmed.split("|").slice(1, -1).map(function (cell) { return cell.trim(); });
  return cells.length >= 2 ? cells : null;
}

function closesFromMarkdown(text) {
  const lines = text.split(/\r?\n/);
  let start = -1;
  for (let i = 0; i < lines.length; i += 1) {
    const cells = splitRow(lines[i]);
    if (cells && cells[0] === "Date" && cells[1] === "Close") {
      start = i + 1;
      break;
    }
  }
  if (start < 0) return [];
  const points = [];
  for (let i = start; i < lines.length; i += 1) {
    if (lines[i].trim() === "") break;
    const cells = splitRow(lines[i]);
    if (!cells) break;
    if (/^:?-+:?$/.test(cells[0])) continue;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(cells[0])) continue;
    const close = Number(cells[1]);
    if (!Number.isFinite(close)) continue;
    points.push({ date: cells[0], close: close });
  }
  return points;
}

function drawChart(host, points) {
  host.replaceChildren();
  if (points.length < 2) return;
  const width = 640;
  const height = 220;
  const padL = 72;
  const padR = 16;
  const padT = 20;
  const padB = 28;
  const closes = points.map(function (point) { return point.close; });
  let min = Math.min.apply(null, closes);
  let max = Math.max.apply(null, closes);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const xOf = function (index) {
    return padL + (index / (points.length - 1)) * (width - padL - padR);
  };
  const yOf = function (close) {
    return padT + (1 - (close - min) / (max - min)) * (height - padT - padB);
  };
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 " + width + " " + height);
  svg.setAttribute("role", "img");
  const line = document.createElementNS(SVG, "polyline");
  line.setAttribute("fill", "none");
  line.setAttribute("stroke", "currentColor");
  line.setAttribute("stroke-width", "2");
  line.setAttribute("points", points.map(function (point, index) {
    return xOf(index).toFixed(1) + "," + yOf(point.close).toFixed(1);
  }).join(" "));
  svg.append(line);
  const low = closes.indexOf(Math.min.apply(null, closes));
  const high = closes.indexOf(Math.max.apply(null, closes));
  const labels = [
    [0, points[0].date + " " + points[0].close],
    [points.length - 1, points[points.length - 1].date + " " + points[points.length - 1].close],
    [low, "low " + points[low].close],
    [high, "high " + points[high].close]
  ];
  const seen = new Set();
  labels.forEach(function (label) {
    if (seen.has(label[0])) return;
    seen.add(label[0]);
    const text = document.createElementNS(SVG, "text");
    text.setAttribute("x", xOf(label[0]).toFixed(1));
    text.setAttribute("y", (yOf(points[label[0]].close) - 6).toFixed(1));
    text.setAttribute("font-size", "11");
    text.textContent = label[1];
    svg.append(text);
  });
  host.append(svg);
}

function renderMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text));
}

async function showRun(run) {
  const token = ++view;
  const article = document.getElementById("run");
  article.replaceChildren();
  const heading = document.createElement("h1");
  heading.textContent = run.ticker + " " + run.date + " " + run.time;
  const chart = document.createElement("div");
  article.append(heading, chart);
  const dir = run.path.slice(0, -"rating.md".length);
  for (const name of NOTES) {
    if (token !== view) return;
    const section = document.createElement("section");
    const label = document.createElement("h2");
    label.textContent = name;
    section.append(label);
    article.append(section);
    let response;
    try {
      response = await fetch(rawUrl(dir + name));
    } catch (error) {
      const failed = document.createElement("p");
      failed.textContent = name + " failed";
      section.append(failed);
      continue;
    }
    if (token !== view) return;
    if (!response.ok) {
      const status = document.createElement("p");
      status.textContent = name + " HTTP " + response.status;
      section.append(status);
      continue;
    }
    const text = await response.text();
    if (name === "market.md") drawChart(chart, closesFromMarkdown(text));
    if (name === "rating.md") {
      const first = text.split(/\r?\n/, 1)[0];
      if (first) heading.textContent = first;
    }
    const body = document.createElement("div");
    try {
      body.innerHTML = renderMarkdown(text);
      section.append(body);
    } catch (error) {
      const failed = document.createElement("p");
      failed.textContent = name + " failed";
      section.append(failed);
    }
  }
}

function showCurrent(runs) {
  const raw = location.hash.replace(/^#/, "");
  const parts = raw ? raw.split("/").map(decodeURIComponent) : [];
  const run = parts.length === 3
    ? runs.find(function (item) {
      return item.ticker === parts[0] && item.date === parts[1] && item.time === parts[2];
    })
    : null;
  if (run) showRun(run);
}

async function loadRuns() {
  const nav = document.getElementById("runs");
  let response;
  try {
    response = await fetch("https://api.github.com/repos/" + REPO + "/git/trees/" + BRANCH + "?recursive=1");
  } catch (error) {
    nav.replaceChildren();
    const failed = document.createElement("p");
    failed.textContent = "The file list failed.";
    nav.append(failed);
    return;
  }
  nav.replaceChildren();
  if (!response.ok) {
    const status = document.createElement("p");
    status.textContent = "The file list failed: HTTP " + response.status;
    nav.append(status);
    return;
  }
  let payload;
  try {
    payload = await response.json();
  } catch (error) {
    nav.replaceChildren();
    const failed = document.createElement("p");
    failed.textContent = "The file list failed.";
    nav.append(failed);
    return;
  }
  if (payload.truncated) {
    const notice = document.createElement("p");
    notice.textContent = "The file list was truncated.";
    nav.append(notice);
  }
  const runs = (payload.tree || []).map(function (entry) {
    return parseRun(entry.path || "");
  }).filter(Boolean).sort(compareRuns);
  if (runs.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = "There are no runs.";
    nav.append(empty);
    return;
  }
  runs.forEach(function (run) {
    const button = document.createElement("button");
    button.type = "button";
    const title = document.createElement("div");
    title.textContent = run.ticker + " " + run.date + " " + run.time;
    const rating = document.createElement("div");
    rating.className = "status";
    button.append(title, rating);
    button.addEventListener("click", function () {
      location.hash = [run.ticker, run.date, run.time].map(encodeURIComponent).join("/");
    });
    nav.append(button);
    fetch(rawUrl(run.path)).then(function (note) {
      if (!note.ok) {
        rating.textContent = "HTTP " + note.status;
        return null;
      }
      return note.text();
    }).then(function (text) {
      if (!text) return;
      const first = text.split(/\r?\n/, 1)[0];
      if (first) rating.textContent = first;
    }).catch(function () {
      rating.textContent = "failed";
    });
  });
  window.addEventListener("hashchange", function () { showCurrent(runs); });
  showCurrent(runs);
}

loadRuns();
</script>
</body>
</html>
```

A flat close series uses a one-unit pad above and below so the line has a vertical range. A point that is both an end and the high or low gets one label.

- [ ] **Step 4: Check the empty page in a browser**

Run: `python -m http.server 8765 --directory docs`

Open `http://127.0.0.1:8765/`. Expected: the nav says `There are no runs.` The article is empty. There is no control that starts a workflow.

Stop the server after that.

The notes, the rating heading, and the chart can be checked when a run is on `main`. Open the row, confirm the thirteen filenames in the order listed in Global Constraints, confirm the heading is the first line of `rating.md`, and confirm the chart is a polyline of the `Date` / `Close` rows. Until a run is on `main`, that check has not happened.

- [ ] **Step 5: Run the suite**

Run: `pytest -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/test_snapshot.py docs/index.html docs/.nojekyll
git commit -m "$(cat <<'EOF'
feat: show merged desk runs on a static page

EOF
)"
```

## One-time settings, after the page is on main

These are not code. Do them once, by hand:

- Pages deploys from the `main` branch, folder `/docs`.
- Actions is allowed to create and approve pull requests. The workflow only creates one.

The address is `https://kevinkantkode.github.io/TradingAgents/`. A merged run appears on refresh. A Pages rebuild is required when `docs/index.html` changes. A merge that only adds a run directory publishes the same shell again.
