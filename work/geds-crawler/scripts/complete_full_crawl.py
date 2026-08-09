"""Finish the versioned full crawl and publish only after strict validation."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CRAWL_DB = ROOT / "outputs" / "geds-snapshot-2026-08-02-full-156" / "geds.sqlite"
MASTER_DB = ROOT / "outputs" / "master" / "geds-master.sqlite"
REPORT = ROOT / "docs" / "reports" / "geds-full-crawl-diff-2026-08-02.md"
TASK_NAME = "GEDS-Full-Crawl-Completion"
TARGETS = {"departments": 156, "organizations": 26421, "people": 193163}


def read_state() -> dict[str, object]:
    con = sqlite3.connect(f"file:{CRAWL_DB.as_posix()}?mode=ro", uri=True, timeout=2)
    try:
        run = con.execute(
            "SELECT status,request_count,started_at,finished_at,heartbeat_at FROM crawl_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        queue = dict(con.execute("SELECT status,COUNT(*) FROM crawl_queue GROUP BY status"))
        counts = {
            "departments": con.execute("SELECT COUNT(*) FROM departments").fetchone()[0],
            "organizations": con.execute("SELECT COUNT(*) FROM org_units").fetchone()[0],
            "people": con.execute("SELECT COUNT(*) FROM people_index").fetchone()[0],
            "errors": con.execute("SELECT COUNT(*) FROM crawl_errors").fetchone()[0],
        }
        return {"run": run, "queue": queue, "counts": counts}
    finally:
        con.close()


def task_action() -> str:
    wrapper = ROOT / "tools" / "run-geds-crawl-completion.ps1"
    return f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{wrapper}"'


def reschedule() -> None:
    when = (datetime.now() + timedelta(hours=1)).strftime("%H:%M")
    date = datetime.now().strftime("%m/%d/%Y")
    subprocess.run(
        ["schtasks", "/Create", "/TN", TASK_NAME, "/TR", task_action(), "/SC", "ONCE", "/SD", date, "/ST", when, "/F"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    print(f"rescheduled for {date} {when}")


def sqlite_rows(path: Path, table: str, key: str, values: tuple[str, ...]) -> dict[str, tuple[object, ...]]:
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=2)
    try:
        cols = ",".join((key, *values))
        return {str(row[0]): tuple(row[1:]) for row in con.execute(f"SELECT {cols} FROM {table}")}
    finally:
        con.close()


def build_diff(state: dict[str, object]) -> str:
    crawl_orgs = sqlite_rows(CRAWL_DB, "org_units", "dn", ("name", "parent_dn", "department_dn"))
    master_orgs = sqlite_rows(MASTER_DB, "organizations_current", "org_dn", ("name", "parent_dn", "department_dn"))
    crawl_people = sqlite_rows(CRAWL_DB, "people_index", "source_url", ("display_name", "title", "org_dn"))
    master_people = sqlite_rows(MASTER_DB, "people_current", "source_url", ("display_name", "title", "org_dn"))
    master_departments = sqlite_rows(MASTER_DB, "departments_current", "department_dn", ("name",))

    def delta(left: dict[str, tuple[object, ...]], right: dict[str, tuple[object, ...]]) -> tuple[int, int, int]:
        added = len(set(left) - set(right))
        removed = len(set(right) - set(left))
        changed = sum(1 for key in set(left) & set(right) if left[key] != right[key])
        return added, removed, changed

    org_added, org_removed, org_changed = delta(crawl_orgs, master_orgs)
    people_added, people_removed, people_changed = delta(crawl_people, master_people)
    counts = state["counts"]
    run = state["run"]
    queue = state["queue"]
    return f"""# GEDS full crawl diff

- Generated: {datetime.now(UTC).isoformat()}
- Crawl database: `{CRAWL_DB}`
- Initial canonical master: `{MASTER_DB}`
- Crawl status: `{run[0]}`
- Queue: `{queue}`
- Crawl errors: `{counts['errors']}`

## Counts

| Entity | Crawl | Initial master | Difference |
|---|---:|---:|---:|
| Departments | {counts['departments']} | {len(master_departments)} | {counts['departments'] - len(master_departments):+d} |
| Organizations | {counts['organizations']} | {len(master_orgs)} | {counts['organizations'] - len(master_orgs):+d} |
| People | {counts['people']} | {len(master_people)} | {counts['people'] - len(master_people):+d} |

## Row-level identity diff

- Organizations: {org_added} added, {org_removed} removed, {org_changed} changed
- People: {people_added} added, {people_removed} removed, {people_changed} changed

## Automation gate

The initial canonical master file is never modified by this automation. Neon
activation occurs only when the crawl is finished, the queue has no pending or
error rows, crawl errors are zero, and all three target counts match. A
temporary staging master is used to build and validate the public projection.
"""


def write_report(text: str) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")


def promote_temp_and_neon() -> tuple[str, str]:
    sys.path.insert(0, str(ROOT / "work" / "geds-crawler" / "src"))
    from geds_crawler.canonical_resolver import OverlayQuality, ResolvedSnapshot
    from geds_crawler.canonicalizer import promote_canonical_snapshot
    from geds_crawler.neon_projection_target import NeonProjectionImportTarget
    from geds_crawler.public_projection import export_public_projection, validate_public_projection
    from geds_crawler.public_projection_import import PublicProjectionImportCoordinator

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    staging_dir = ROOT / "outputs" / "automation" / f"geds-crawl-{stamp}"
    staging_dir.mkdir(parents=True, exist_ok=False)
    staging_master = staging_dir / "geds-master.sqlite"
    with sqlite3.connect(f"file:{CRAWL_DB.as_posix()}?mode=ro", uri=True) as con:
        successful = frozenset(
            row[0] for row in con.execute("SELECT org_dn FROM pagination_orgs WHERE status='completed'")
        )
    resolved = ResolvedSnapshot(
        base_db_paths=(CRAWL_DB,),
        overlay_db_paths=(CRAWL_DB,),
        members=(CRAWL_DB,),
        quality=OverlayQuality(successful, frozenset(), ()),
    )
    result = promote_canonical_snapshot(staging_master, resolved, datetime.now(UTC).isoformat())
    projection_dir = staging_dir / "public-projection"
    manifest = export_public_projection(staging_master, projection_dir)
    validate_public_projection(projection_dir)
    url = os.environ.get("GEDS_PUBLIC_DATABASE_URL_UNPOOLED")
    if not url:
        raise RuntimeError("Neon connection is unavailable")
    import psycopg

    with psycopg.connect(url) as connection:
        coordinator = PublicProjectionImportCoordinator(NeonProjectionImportTarget(connection))
        plan = coordinator.stage(projection_dir)
        coordinator.activate(plan)
    return result.snapshot.snapshot_id, manifest.data_sha256


def push_report() -> None:
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    if branch != "master":
        raise RuntimeError(f"refusing to push report from branch {branch!r}; expected 'master'")
    subprocess.run(["git", "add", str(REPORT)], cwd=ROOT, check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
        return
    subprocess.run(["git", "commit", "-m", "docs: record GEDS full crawl diff"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "master"], cwd=ROOT, check=True)


def main() -> int:
    state = read_state()
    run, queue, counts = state["run"], state["queue"], state["counts"]
    if run[0] == "running" or queue.get("pending", 0) or queue.get("error", 0):
        print(f"crawl not ready: status={run[0]} queue={queue} counts={counts}")
        reschedule()
        return 0

    report = build_diff(state)
    ready = run[0] == "finished" and not counts["errors"] and not queue.get("pending", 0) and not queue.get("error", 0) and all(counts[key] == value for key, value in TARGETS.items())
    if ready:
        try:
            snapshot_id, data_sha256 = promote_temp_and_neon()
            report += f"\n## Result\n\n- Neon projection activated: `{snapshot_id}` / `{data_sha256}`\n"
        except Exception as exc:
            report += f"\n## Result\n\n- Neon update blocked after validation: `{exc}`\n"
    else:
        report += "\n## Result\n\n- Neon update blocked because the crawl did not pass the completion gate.\n"
    write_report(report)
    push_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
