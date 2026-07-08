# GEDS Crawler

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
