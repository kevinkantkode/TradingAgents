# Run archive

Decided 2026-11-03. A public page reads desk runs from `main`. The notes stay the deliverable. The page is a shell over those files.

This supersedes three sentences in [2026-11-02-cursor-desk-design.md](2026-11-02-cursor-desk-design.md): the run directory is gitignored, a same-day rerun deletes that directory, and an HTML report is out of scope. The desk still does not write an HTML file into the run directory. The ledger path, the rating words, and the rule that a later run does not read the ledger are unchanged.

## What this is for

Someone opens `https://kevinkantkode.github.io/TradingAgents/` and reads one run: the rating, the recent closes, and the thirteen notes in the order the desk wrote them.

A run reaches the page only after it is on `main`. The workflow opens a pull request. A local run is committed by hand. Merging or committing onto `main` is what publishes it.

The shell is what GitHub Pages deploys. Opening the site reads `main` through the GitHub API and then fetches the markdown. A merged run is visible on refresh once that commit is on `main`. A new Pages deploy is required when `docs/index.html` changes. A merge that only adds a run directory leaves the shell the same. GitHub still starts its branch deploy on a push to `main`, and that deploy publishes the same shell again.

## Out of scope

- A button that starts `tradingagents.yml`. The run starts from the Actions tab.
- The score ledger. It stays at `~/.tradingagents/ledger.jsonl`.
- A chart of returns, a chart library, and a generated `index.json`.
- The workflow pushing a commit onto `main`.
- `scripts/fetch-tradingagents.sh` and `.cursor/skills/fetch-tradingagents/`. Both are deleted. A pull is how a local checkout gets a merged run.

## Run directory

A run is one directory:

```text
.tradingagents/<TICKER>/<YYYY-MM-DD>/<time>/
```

`<TICKER>` is the existing `ticker_path_segment`. The date and the time come from one clock: the machine's current local time, or a clock the caller passes in. A provided clock is read as its wall time, with no timezone conversion. The real command passes no clock.

`prepare_run_dir` creates that directory and returns it. It does not delete any directory. Stdout of `tradingagents run-dir` stays one line, the absolute path.

The time name is `HHMMSS`. If that directory exists, the name becomes `HHMMSS-2`, then `HHMMSS-3`, through `HHMMSS-99`. If all of those exist, the command exits 1, prints the reason, and creates nothing. A ticker that fails `safe_ticker_component` still exits 1 before a directory is created.

The desk follows the printed path. The workers write the same filenames.

The ignore rule for `.tradingagents/` is removed, so the directory can be committed.

## Which run the workflow checks

`assert_run_result` still requires exactly one `rating.md` under the directory it is given, and a first line that is one of the five ratings. Once older runs are on `main`, the checkout contains many `rating.md` files. The workflow must not point that check at the whole tree.

Before the agent starts, the job records every `rating.md` path already under `.tradingagents`. After the agent exits, `new_run_directory` in `tradingagents/run_result.py` compares that set with the `rating.md` paths on disk. Exactly one path may be new. It returns that file's parent, the run directory. Zero new files, or more than one, is an error and the job stops. `git add` during the agent run does not hide a new file, because the comparison is against the set recorded before the agent, not against `git ls-files` after it.

The workflow then calls `assert_run_result` on that run directory only. A bad first line stops the job. Nothing is published.

## Pull request

The job checks out the repository's default branch, which is `main`, with `persist-credentials: false`. The agent step still sets `GITHUB_TOKEN` and `GH_TOKEN` to empty. The workflow permissions are `contents: write`, `pull-requests: write`, and `actions: write`. The write token is used only by the publish step and the failure upload.

After the rating check passes, the job copies that run directory to the runner temp area. It fetches `origin/main`, resets the worktree to that commit so agent edits outside the copy are discarded, and creates a branch from it:

```text
tradingagents/<branch_ticker>/<YYYY-MM-DD>-<time>
```

`<branch_ticker>` is `branch_ticker(ticker)` from `tradingagents.run_result`, which returns `ticker.encode("ascii").hex()`. Git ref names cannot contain `^` or `..`, so the run directory may use tickers such as `^GSPC` or `A..B` while the branch uses the hex segment only. The last segment is still the run directory's time name, including a `-2` suffix when the directory has one. The saved copy is placed back at its relative path under `.tradingagents/<TICKER>/…`, and the branch receives one commit of that path only. The commit author on the runner is `github-actions[bot]` (`41898282+github-actions[bot]@users.noreply.github.com`). The commit subject, pull request title, run directory path, and pull request body use the real ticker, not the hex branch segment. The commit subject and the pull request title are the same line:

```text
tradingagents: NVDA 2026-11-03 230155
```

The pull request body is the rating line, a blank line, and the run path. The workflow opens the pull request against `main` and stops. It does not approve or merge.

A pull request opened with `GITHUB_TOKEN` does not start `ci.yml`. Merging to `main` does. `main` has no required checks.

If the publish step fails, the job fails and uploads the saved run directory as an artifact. The upload's condition is that failure, and only after the copy of a run that already passed the rating check. A failed rating check uploads nothing. A successful pull request uploads nothing.

## Page

The site is `docs/index.html` and `docs/.nojekyll`. Pages is served from the `docs/` folder of `main`.

The page names `kevinkantkode/TradingAgents` and `main` in one place. It makes anonymous reads.

The list is one git tree call:

```text
GET https://api.github.com/repos/kevinkantkode/TradingAgents/git/trees/main?recursive=1
```

A run is a path with five components:

```text
.tradingagents/<TICKER>/<YYYY-MM-DD>/<time>/rating.md
```

`<time>` is `HHMMSS` or `HHMMSS-N` where `N` is 2 through 99. Any other path is ignored. A truncated tree response is shown as truncated, and the page does not fill in the missing entries. The list is newest date first. Within a date, the later `HHMMSS` is first. The same second orders by the numeric suffix, so `230155-10` is later than `230155-2`, and both are later than `230155`.

Each row shows the ticker, the date, and the time. It then fills in the first line of `rating.md`, fetched from:

```text
https://raw.githubusercontent.com/kevinkantkode/TradingAgents/main/<path>
```

Opening a row sets the URL hash to the ticker, date, and time components as stored in the path. Loading a hash that matches a run opens that run.

The page loads the thirteen notes in this order: `market.md`, `fundamentals.md`, `news.md`, `sentiment.md`, `bull.md`, `bear.md`, `omissions.md`, `plan.md`, `proposal.md`, `aggressive.md`, `conservative.md`, `neutral.md`, `rating.md`. Each note is a section labeled with its filename. The rating line is the heading of the run. The chart sits under that heading and above the notes.

The markdown is rendered with `marked` and sanitized with DOMPurify. Both are loaded from jsDelivr, and each script URL contains its version. Raw HTML in a note is sanitized before it is inserted.

The chart is an inline SVG. It reads the first markdown table in `market.md` whose header cells are `Date` and `Close`, the table `snapshot_text` prints. A body row counts when the first cell is `YYYY-MM-DD` and the second cell is a number. Other rows are skipped. The horizontal position is the row order. The vertical position is the close. The first close, the last close, the minimum, and the maximum are labeled. A point that fills two of those roles gets one label. Fewer than two usable rows leaves the chart slot with nothing drawn. The notes still render.

A note HTTP failure shows `name HTTP <status>` in its section. A note network or render failure shows `name failed`. The other notes still render. A tree with no matching run says there are no runs. An HTTP failure of the tree shows `The file list failed: HTTP <status>`. A tree network error or JSON parse error shows `The file list failed.`

## One-time repository settings

Two settings are not code:

- Pages deploys from the `main` branch, folder `/docs`.
- Actions is allowed to create and approve pull requests. This workflow only creates one. The repository default token is read-only today, and `can_approve_pull_request_reviews` is false. The workflow's own `permissions` block asks for write. The pull request still requires the create-and-approve setting.

## Tests and docs

`tests/test_rundir.py` replaces the wipe test. With a fixed clock, a second call leaves the first directory and its files in place and returns a different path under the same date. An existing `HHMMSS` yields `HHMMSS-2`, then `HHMMSS-3`. The full set through `HHMMSS-99` exits 1 and adds no directory. A bad ticker still exits 1. The command test asserts that stdout is the absolute path and matches `.tradingagents/<TICKER>/<YYYY-MM-DD>/<HHMMSS>/`.

The new helper has tests for one new `rating.md` among older ones, for no new file, and for two new files.

`tests/test_snapshot.py` asserts that `snapshot_text` contains the header `| Date | Close |`, the separator `|---|---:|`, and one dated close row.

`tests/test_tradingagents_workflow.py` keeps the dispatch-only checks. It expects the three write permissions, `persist-credentials: false`, an empty `GITHUB_TOKEN` on the agent step, the branch prefix `tradingagents/`, and `gh pr create`. The artifact upload is present with a failure condition. The workflow file has no push ref of `main`.

`tests/test_tradingagents_contract.py` asserts that the skill describes the time directory and does not tell the parent to wipe a same-day run.

The README, the tradingagents skill, and the `run-dir` help text describe the new path. The fetch script and the fetch skill are deleted.

The page has no JavaScript test runner. It is checked in a browser: the empty state before any run is on `main`, then the list, the notes, and the chart after a merged run.
