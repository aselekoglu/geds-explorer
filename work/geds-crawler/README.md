# GEDS Crawler

> [!WARNING]
> **Development only**: This repository contains an unauthenticated crawl control plane interface. Do not expose this service to an untrusted local area network (LAN) or the public internet.

Privacy-preserving snapshot crawler for Government of Canada Electronic Directory Services.

## Setup

```powershell
py -m pip install -e .[dev]
```

## Tests

```powershell
py -m pytest
```

## SSC Depth-1 Dry Run

```powershell
py -m geds_crawler.cli crawl `
  --output-dir outputs\geds-snapshot-2026-07-08-ssc-depth1 `
  --max-depth 1 `
  --departments "Shared Services Canada"
```

By default, `crawl` prints one progress line per processed org page:

```text
[2026-07-08T16:10:00+00:00] done depth=1 requests=15 orgs=94 people=222 done=14 pending=80 errors=0 org="Shared Services Canada / Cloud Services"
```

Use `--quiet` to suppress progress logs.

## Live Status For A Running Snapshot

From the repository root:

```powershell
py -m geds_crawler.cli status --db outputs\geds-snapshot-2026-07-08\geds.sqlite
```

From `work\geds-crawler`:

```powershell
py -m geds_crawler.cli status --db ..\..\outputs\geds-snapshot-2026-07-08\geds.sqlite
```

For a simple PowerShell watch loop from the repository root:

```powershell
while ($true) {
  py -m geds_crawler.cli status --db outputs\geds-snapshot-2026-07-08\geds.sqlite
  Start-Sleep -Seconds 15
}
```

## Live Snapshot UI

The UI opens the running SQLite snapshot in read-only mode and refreshes every three seconds. It binds to `0.0.0.0` so another device on the same local network can browse it.

From the repository root:

```powershell
py -m geds_crawler.cli ui --db outputs\geds-snapshot-2026-07-08\geds.sqlite
```

From `work\geds-crawler`:

```powershell
py -m geds_crawler.cli ui --db ..\..\outputs\geds-snapshot-2026-07-08\geds.sqlite
```

The command prints both `127.0.0.1` and detected LAN URLs. The default port is `8765`; override it with `--port`. Because the server is visible on the local network and has no authentication, use it only on a trusted network.

## 10-Institution Crawl

This uses the default 1 request/sec polite rate limit.

```powershell
py -m geds_crawler.cli crawl `
  --output-dir ..\..\outputs\geds-snapshot-2026-07-08
```

## Outputs

- `geds.sqlite`
- `org_units.jsonl`
- `people_index.jsonl`
- `crawl_report.md`

The crawler does not store phone, email, fax, or address fields. Person rows keep only display name, title when visible, department, org context, official GEDS source URL, and crawl metadata.

## Pagination Backfill Operator Workflow

Follow this workflow to perform a pagination backfill for capped organizations (those showing exactly 25 people in the base snapshot):

1. **Initialize/Upgrade Control Schema**: Ensure the control plane database has all migrations applied.
2. **Create Backfill Job**: Set up a `pagination_backfill` job targeting the finished base snapshot database (e.g. `outputs/geds-snapshot-2026-07-08/geds.sqlite`) through the UI or API.
3. **Run Bounded Live Verification**: Before launching the production run, verify the setup with a 2-organization test:
   - Start the run in the UI.
   - Wait until at least one continuation page has been crawled, then click **Stop** in the UI to pause.
   - Click **Resume** to ensure continuation works and the crawl completes.
   - Run the verifier script to validate integrity:
     ```powershell
     py scripts/verify_pagination_backfill.py `
       --base-db outputs/geds-snapshot-2026-07-08/geds.sqlite `
       --overlay-db outputs/runs/2026-07-09/two-org-backfill/geds.sqlite `
       --expected-org-dn "OU=FIRST-CAPPED-ORG,O=GC,C=CA" `
       --expected-org-dn "OU=SECOND-CAPPED-ORG,O=GC,C=CA"
     ```
   - Review that `base_unchanged` is `true`, no contact columns exist, and the UI progress bar and ETA calculations behave stably.
4. **Create Production Job**: Once verified, create the full 1,418 capped organization production backfill.

> [!NOTE]
> GEDS and TBS employee totals represent different populations and are not expected to be identical. Do not attempt to force them to match.

## Career Atlas publication and serving

Career Atlas is a separate public, read-only application. It never mounts the crawler control-plane routes and cannot start, stop, schedule, or configure crawler work.

From `work\geds-crawler`, install the backend and test dependencies:

```powershell
py -m pip install -e ".[dev]"
```

Publish a canonical snapshot from a completed control-plane run, then rebuild the deterministic career index:

```powershell
py -m geds_crawler.career_cli publish `
  --control-db ..\..\outputs\control.sqlite `
  --run-id <completed-run-id> `
  --master-db ..\..\outputs\master\geds-master.sqlite `
  --as-of <ISO-8601-timestamp>

py -m geds_crawler.career_cli index `
  --master-db ..\..\outputs\master\geds-master.sqlite `
  --taxonomy src\geds_crawler\data\career_taxonomy.v1.json
```

Build the frontend first, then serve both the public API and static application:

```powershell
cd ..\geds-career-atlas
npm.cmd install
npm.cmd run build

cd ..\geds-crawler
py -m geds_crawler.career_cli serve `
  --master-db ..\..\outputs\master\geds-master.sqlite `
  --frontend-dir ..\geds-career-atlas\dist `
  --host 127.0.0.1 `
  --port 8780
```

Use `--host 0.0.0.0` only for trusted-LAN review. The public app is read-only but local HTTP still has no transport encryption or authentication.

Trust boundaries:

- The canonical SQLite database and generated `dist\` assets are build/runtime artifacts and must not be committed.
- Public payloads contain organization IDs, observed titles, aggregate counts, evidence, and official GEDS source URLs. They contain no email, phone, fax, address, or personal display-name fields.
- Matching is deterministic and versioned. Confidence and evidence describe relevance, not eligibility, responsibility, hiring intent, or a job opening.
- A GEDS `vacant` marker is always labelled as an unverified directory signal. It is not a verified GC Jobs competition and never creates an Apply action.
- GC Jobs ingestion and a verified Opportunity Engine are intentionally deferred to a later, separately approved design.
