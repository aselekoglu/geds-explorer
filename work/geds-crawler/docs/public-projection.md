# Public Career Atlas projection

The public Career Atlas artifact is a versioned, read-only projection. It is
created from a validated canonical master and never exposes the crawler or
control-plane database.

The public person contract permits the observed `display_name` and `title`.
It excludes email, phone, fax, address, last-seen timestamps, crawl lineage,
control-plane fields, and raw SQLite source tables. Official GEDS source URLs
remain available so a visitor can inspect the source record directly.

## Export and validation

Run these commands from `work\\geds-crawler`:

```powershell
py -m geds_crawler.career_cli export `
  --master-db ..\\..\\outputs\\master\\geds-master.sqlite `
  --output-dir ..\\..\\outputs\\public-projection\\<snapshot-id>

py -m geds_crawler.career_cli validate `
  --projection-dir ..\\..\\outputs\\public-projection\\<snapshot-id>
```

The export refuses `partial_overlay` and other non-complete snapshots by
default. A labelled preview requires an explicit flag on both commands:

```powershell
--allow-partial-preview
```

Each projection contains `geds-public.sqlite` and `manifest.json`. The
manifest records the schema/projection versions, snapshot ID, as-of time,
quality/release status, public row counts, taxonomy version, and a
deterministic SHA-256 over the allow-listed data tables. The validator checks
the manifest, exact table/column allow-list, snapshot binding, counts, and
hash before import.

## Manual canary

Use the sequence `export -> validate -> staging import -> GET-only smoke test
-> active snapshot pointer`. Keep the canonical master and all crawler/control
databases private. The FastAPI app accepts a provider-neutral
`CareerReadStore` implementation; the current local implementation is the
SQLite `CareerRepository`. A hosted Postgres adapter can be added behind that
interface after the provider is selected.
