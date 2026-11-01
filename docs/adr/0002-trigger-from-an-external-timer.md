# Trigger the check from an external timer, keep GitHub's schedule as a backup

GitHub's `schedule` trigger did not fire once in the first two hours after the workflow reached `main` (about eight 15-minute slots, even after a commit that re-registered it), while manual runs worked every time. A free external timer now calls the workflow's manual trigger every 15 minutes through the GitHub API, using a fine-grained token limited to this repository (Actions: read and write). The `schedule` trigger stays in the workflow as a backup: a check is idempotent and runs are serialised by the concurrency group, so a double trigger changes nothing.

## Considered Options

- **Wait for GitHub's schedule**: nothing we can influence, and no sign it would start.
- **A Claude Code scheduled task as the clock and the runner**: a verification run showed it needs the Telegram token in a second place, a routine source with push access that can only be set in the claude.ai UI, and costs Claude usage on every run (about US$0.11 for the verification run).
- **A workflow that sleeps and dispatches itself**: keeps a runner busy all day for no work.

## Consequences

- The token expires (set to 90 days) and must be renewed, otherwise the timer's calls start failing and checks stop. Nothing in the repository notices this.
- A third-party timer service holds a token that can only trigger this repository's workflows.
- Run titles show `workflow_dispatch` instead of `schedule`.
