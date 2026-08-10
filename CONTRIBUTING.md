# Contributing to GEDS Explorer

Thank you for helping improve the crawler, data boundaries, analysis, or Career Atlas. Contributions should be small, reviewable, and grounded in the repository's privacy and evidence model.

## Before you start

1. Read the root [`README.md`](README.md), [`SECURITY.md`](SECURITY.md), and the package README relevant to your change.
2. Check existing issues, plans, and specifications under `docs/` before starting new work.
3. Confirm that the change does not expand stored personal data, crawler scope, or public API semantics without an explicit design decision.
4. For a substantial architectural or trust-boundary change, add a short decision record under `docs/decisions/` (use the existing documentation convention and explain alternatives).

## Local setup

Crawler:

```powershell
cd work\geds-crawler
py -m pip install -e ".[dev]"
```

Career Atlas:

```powershell
cd work\geds-career-atlas
npm.cmd install
```

Keep generated snapshots, SQLite files, `node_modules`, build output, traces, and credentials local. Do not commit `.env` files or copied production data.

## Development and tests

Use the narrowest relevant test first, then run the full package checks:

```powershell
cd work\geds-crawler
py -m pytest

cd ..\geds-career-atlas
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test:e2e
```

If a check cannot run because a local database, browser, or service is unavailable, report the exact command and blocker in the pull request rather than claiming it passed.

## Coding and data standards

- Preserve source strings and source URLs; label interpretation, confidence, vacancy markers, and aggregates accurately.
- Never persist phone, email, fax, or address fields in crawler snapshots or public payloads.
- Keep public Career Atlas routes read-only and separate from control-plane operations.
- Prefer deterministic, testable transformations over hidden heuristics. Add or update fixtures when parsing source HTML.
- Keep English/French product copy and accessibility semantics aligned when changing frontend behavior.
- Do not commit generated artifacts, secrets, personal contact data, or unrelated formatting churn.

## Branches, commits, and pull requests

- Create a focused branch from the current default branch, for example `docs/contribution-guide` or `fix/parser-pagination`.
- Use imperative, specific commit subjects (for example, `Document Career Atlas verification flow`). Keep unrelated changes in separate commits/PRs.
- A pull request should explain the problem, scope, data/privacy impact, test commands and results, and any known limitations. Include screenshots or API examples when behavior changes.
- Link the issue or plan when one exists. Keep the PR mergeable and respond to review comments with follow-up commits rather than rewriting history after review unless the maintainer asks.
- A maintainer may request a decision record, fixture, migration note, or rollback plan before approval.

Use [`docs/contribution-checklist.md`](docs/contribution-checklist.md) as the pre-submit gate.

## Bug reports and feature proposals

Open an issue at [aselekoglu/geds-explorer](https://github.com/aselekoglu/geds-explorer). Include:

- package and commit/branch;
- operating system and Python/Node versions;
- minimal reproduction and expected versus actual behavior;
- relevant logs with secrets and personal data removed;
- the exact checks you ran.

Feature proposals should describe the user or operator problem, evidence, data-boundary impact, and a smallest useful increment. Do not attach live snapshots containing personal data.

## Security reports

Do not disclose exploitable details in a public issue. Follow [`SECURITY.md`](SECURITY.md), and review the crawler-specific warning in [`work/geds-crawler/SECURITY.md`](work/geds-crawler/SECURITY.md).

## License and contribution terms

Project code and original assets are licensed under Apache-2.0. Contributions are accepted under the same license unless a separate written agreement says otherwise. This does not license Government of Canada source content or third-party dependencies; see [`docs/LICENSING.md`](docs/LICENSING.md).
