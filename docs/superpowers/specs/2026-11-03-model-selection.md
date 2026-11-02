# Model selection

Decided 2026-11-03. Applied in the `model` field of each file under `.cursor/agents/`. The parent does not pass a model on each Task call. Cursor reads the field when that subagent starts.

Two models, in the frontmatter Cursor writes:

```yaml
model: composer-2.5[fast=false]
model: grok-4.7[context=256k,reasoning_effort=low,fast=false]
```

`reasoning_effort` is `low`, `medium`, or `high`. Same weights either way. The field is a thinking budget, not a smarter model.

## Assignment

| Agent | Model | Effort |
|---|---|---|
| `news`, `omissions` | Composer 2.5 | |
| `aggressive`, `conservative`, `neutral` | Composer 2.5 | |
| `market`, `fundamentals`, `sentiment` | Grok 4.7 | low |
| `bull`, `bear`, `trader` | Grok 4.7 | medium |
| `research-manager`, `portfolio-manager` | Grok 4.7 | high |

Per run that is 5 Composer, 3 Grok low, 3 Grok medium, 2 Grok high. The two high calls are serial and single. The parallel waves stay on Composer or Grok low, except bull and bear, which run together at medium.

## Reasoning effort

- **Low** follows the script. Right when the job is "quote this stdout, fill this table, stay in this persona."
- **Low to medium** is the step that changes the answer. Medium re-reads the constraints: do not invent a close, do not blend Yahoo with SEC, show the arithmetic, do not upgrade a missing fact. It is a second pass. It does not go get a new fact.
- **Medium to high** pays for a commitment under contradictory instructions. Which opening won, how decisive the win was, which rating word matches that win. On a quote-the-tool task, high buys latency and longer prose.
- **xhigh** is unused. These agents write to a fixed schema from a fixed set of files. Extra thinking cannot leave those files.

Rule of thumb: low is a clerk, medium checks itself, high decides a conflict. High is reserved for the two judges.

## Grok low versus Composer

They blur on short templated prose. They do not blur on a refusal to fill a hole.

Grok at low effort is still Grok taking a shorter pass. Composer is the fast agent model, tuned to follow a procedure and finish. The price and the speed favor Composer. The prior favors Grok when the failure mode is being helpful.

Keep Grok low where a fabricated figure poisons the rating:

- `market` and `fundamentals` quote a command. The failure is an `N/A` replaced with a remembered close, a percent that got scaled, or a Yahoo line blended with an SEC figure. That restraint is in the weights. A long chain of thought is not what buys it. Downstream, bull and bear are the last agents who see these files, and the trader prices the ticket from `market.md` only. A bad number there becomes the stop.
- `sentiment` is search, but the rubric is negative constraints: silence is not a polite Neutral, one thread is low confidence, a headline is not a post. It rides in the same wave as the other analysts, so the wait is already the Grok-low call.

Composer where the edge is small:

- `news` sorts event from commentary and names sources. The prompt carries the discipline. Search quality matters more than a second thinking pass.
- `omissions` diffs the four reports against the two openings and stops at four lines. The categories and the cap are the discipline. The research manager, not this pass, decides what a dropped fact does.
- The three risk notes are persona prose over `plan.md` and `proposal.md`. No arithmetic, no source table. At low effort Grok is not meaningfully sharper, and three Grok calls would bill a frontier model for a small job. See below for why the job is small.

Rejected cuts: Composer on `market` or `fundamentals`. A bland news note is recoverable. A fabricated price or a blended filing is the rating.

## Matched models

Bull and bear use the same model. If one side is the smarter writer, the research manager inherits that side.

Aggressive, conservative, and neutral use the same model. If neutral is the smarter writer, the portfolio manager rates eloquence. Upgrade the three together, or leave them. Do not upgrade neutral alone.

## Why the risk notes are the cheap tier

Each risk note reads two files and writes short prose. It adds no facts, runs no command, and does not reopen the company. Bull and bear already argued the case. The research manager already picked a side and a rough size.

The notes exist to challenge the ticket, not to rerun the debate. Sizing has two opposite errors, so there are two opposing notes, plus one sizer:

- **Aggressive** argues that the expensive mistake is being too small: a decisive case shrunk, a stand-aside after the plan's own test was met, a stop so tight it is noise.
- **Conservative** argues that the expensive mistake is being too large, or being in the trade: a wide stop on a thin case, a narrow win sized as a decisive one, a thesis standing on a missing filing or a low-confidence read.
- **Neutral** names a size relative to the proposal. The prompt forbids splitting the difference. The agent never sees the other two notes, so it cannot blend them. It reads the same plan and proposal and says where the proposal overreaches and where refusing it would be the mistake.

Bull and bear have no middle writer because that stage is a direction debate, and the research manager is forbidden to average the two openings. Risk has a third writer because the output is a size, not a side. The portfolio manager is the first agent who sees all three notes. When the notes only restate the plan in three moods, they are ceremony, and the rating was already fixed in `plan.md` and `proposal.md`. That is why they sit on Composer.

## Dispatch

Parallel workers set `is_background: true`: the four analysts, bull, bear, and the three risk notes. `omissions`, `research-manager`, `trader`, and `portfolio-manager` stay in the foreground. Each is one step on the critical path, and the next step needs its file.

The procedure for batching Task calls, and the `/multitask` hint, lives in `.cursor/skills/tradingagents/SKILL.md`. The agent cannot switch itself into Multitask mode. The mode switch only accepts `plan` and `agent`. `/multitask` is something the user starts in the Agents window. In ordinary Agent mode, Tasks issued in one turn run together. One Task per turn is a pipeline, whatever the skill says about starting workers "together."
