# Run scheduled checks on GitHub Actions, keep known-product state on a `state` branch

The first version ran as a Claude Code scheduled routine bound to one session; when that session was deleted, the script and its secrets vanished and the routine failed silently every hour. We run the checks on GitHub Actions instead, so the schedule, code and secrets live with the repo and survive any session, and use no Claude usage.

Because a GitHub Actions runner is discarded after each run, the record of known Products is committed to a dedicated `state` branch rather than `main`, which keeps `main` free of automated commits and gives a readable history of changes.

## Considered Options

- **Claude Code scheduled routine**: rejected; tied to a session, easy to delete by accident, consumes Claude usage on every run.
- **GitHub Actions cache for state**: rejected; entries are evicted after about 7 days without use, which would silently reset the Baseline.
- **State committed to `main`**: rejected; floods `main` history with automated commits.

## Consequences

- Scheduled runs can be delayed by a few minutes, which is acceptable for a 15-minute check.
- Public repositories have scheduled workflows disabled after about 60 days without repository activity; whether commits to `state` count is unverified.
