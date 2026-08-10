# Contribution checklist

Use this checklist before requesting review. Delete or explain any item that does not apply.

## Scope and design

- [ ] The change has one clear purpose and does not include unrelated cleanup.
- [ ] Existing plans/specifications/issues were checked; links are included in the PR when relevant.
- [ ] A decision record was added for a durable architecture, API, privacy, or trust-boundary decision.

## Data, privacy, and security

- [ ] No phone, email, fax, address, credentials, or unapproved personal data was added to fixtures, snapshots, logs, or API responses.
- [ ] Crawler and public Career Atlas boundaries remain explicit and unchanged unless reviewed.
- [ ] Control-plane bind/authentication behavior was reviewed against `work/geds-crawler/SECURITY.md`.
- [ ] Generated databases, build output, traces, and local environment files remain untracked.

## Implementation quality

- [ ] Source URLs, source strings, confidence, vacancy markers, and aggregation semantics remain truthful.
- [ ] Parser or API changes include focused fixtures/tests.
- [ ] Frontend changes preserve keyboard access, accessible names, and English/French parity where applicable.
- [ ] Public API changes document compatibility or migration impact.

## Verification

- [ ] `py -m pytest` (from `work/geds-crawler`) passes, or the blocker is recorded.
- [ ] `npm.cmd test`, `npm.cmd run typecheck`, and `npm.cmd run build` (from `work/geds-career-atlas`) pass, or blockers are recorded.
- [ ] `npm.cmd run test:e2e` was run when frontend behavior or serving changed, or the reason is recorded.
- [ ] `git diff --check` passes.
- [ ] The PR description includes commands, results, screenshots/API evidence, and known limitations.

## Review hand-off

- [ ] Commit and branch names describe the change.
- [ ] The working tree contains no unrelated user changes.
- [ ] Reviewer questions and requested follow-ups are addressed.

## Government of Canada readiness

- [ ] Review [government-of-canada-open-source-readiness.md](government-of-canada-open-source-readiness.md); incomplete or institution/contract-dependent items are marked for verification.
- [ ] Do not describe the project as Government of Canada compliant, certified, or endorsed.
