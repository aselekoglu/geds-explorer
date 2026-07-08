# Handoff Prompt: GEDS Crawl Control Plane

Use the following prompt with the next coding agent.

---

You are continuing the local project at:

`C:\Users\asele\Documents\geds-explorer`

Do not redesign from scratch. Read these files first:

1. `Plan.md`
2. `docs/superpowers/specs/2026-07-08-crawl-control-plane-temporal-history-design.md`
3. `docs/superpowers/plans/2026-07-08-crawl-control-plane-temporal-history.md`
4. `work/geds-crawler/README.md`
5. Existing package and tests under `work/geds-crawler/src/geds_crawler` and `work/geds-crawler/tests`

Objective:

Implement the plan phase by phase using strict test-first development. Use one generic crawler engine with run configurations; do not copy the crawler for ISED/CRTC or all remaining institutions.

Priority order:

1. Generic managed worker with canonical department-DN selection, cooperative stop, resume, heartbeat.
2. Controller database, process manager, traffic policies, and persistent preset/cron scheduler.
3. Management API/UI with crawler, coverage, schedule, rate, ETA, start/stop/resume controls.
4. Temporal master DB storing current state plus deltas, not repeated complete snapshots.
5. Deterministic Git-compatible audit artifacts; do not commit SQLite files.

Decisions already made:

- Initial jobs are `ISED + CRTC` and `all remaining institutions`.
- Department selection is by canonical DN.
- Default polite target is aggregate 1 request/second.
- Operator may choose `queue`, `shared`, or `independent` traffic mode.
- UI shows configured and rolling measured aggregate RPS.
- Exceeding 1 RPS requires explicit warning acknowledgement but is not hard-blocked.
- Schedules support one-time, hourly, daily, weekly, and validated five-field cron.
- Schedule overlap policies are `skip`, `queue`, and `allow`.
- Every run uses an isolated staging SQLite DB.
- Successful staging data merges into a temporal master DB.
- Full staging DB may be deleted after a successful merge; stopped/failed staging remains resumable.
- First complete-crawl absence means `uncertain_missing` with `last_seen`.
- Second consecutive complete-crawl absence means `departed`.
- Partial, stopped, or failed crawls never count as an absence.
- Same canonical person DN gives a certain identity match.
- Changed DN plus same normalized name and department creates an uncertain `possible_move`; never silently merge identities.
- No phone, email, fax, address, or person-detail-page crawling.
- Control UI is temporarily unauthenticated by explicit user choice.
- Add a persistent development-only vulnerability warning in UI, README, and `SECURITY.md`.
- Production requires auth, authorization, CSRF protection, and TLS/reverse proxy.

Important current state:

- An unmanaged crawl is already running against `outputs/geds-snapshot-2026-07-08/geds.sqlite`.
- Do not stop, restart, migrate, or rewrite that live DB during implementation.
- It currently contains nine departments because ISED display-name matching failed.
- Existing monitor reads snapshots read-only and serves on port 8765.
- The workspace is not currently a Git repository. Do not run `git init` without user approval.
- The Windows-to-Mac LAN issue is outside the crawler: both devices are in `192.168.2.0/24`, firewall rule `GEDS-Explorer-UI` allows Private/LocalSubnet/TCP 8765, but Windows cannot ARP the Mac. Suspect AP/client isolation or guest SSID.

Execution rules:

- Inspect current files and process state before editing.
- Preserve user-owned changes.
- Use `apply_patch` for manual edits.
- Write each test first and observe the expected failure.
- Run focused tests after each task and the full suite after each phase.
- Keep the current CLI commands backwards compatible.
- Never start the full all-institution crawl automatically.
- Stop after each phase with a concise verification report and remaining risks.

Begin with Phase 1 only. Do not start implementation until you have checked the live process/output state and confirmed the existing test baseline.

---
