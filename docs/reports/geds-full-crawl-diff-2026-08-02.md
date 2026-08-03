# GEDS full crawl diff

- Generated: 2026-08-03T13:56:34.110859+00:00
- Crawl database: `C:\Users\asele\Documents\geds-explorer\outputs\geds-snapshot-2026-08-02-full-156\geds.sqlite`
- Initial canonical master: `C:\Users\asele\Documents\geds-explorer\outputs\master\geds-master.sqlite`
- Crawl status: `finished`
- Queue: `{'done': 25958}`
- Crawl errors: `3`

## Counts

| Entity | Crawl | Initial master | Difference |
|---|---:|---:|---:|
| Departments | 156 | 156 | +0 |
| Organizations | 25960 | 27491 | -1531 |
| People | 194044 | 206942 | -12898 |

## Row-level identity diff

- Organizations: 0 added, 1531 removed, 6505 changed
- People: 0 added, 12898 removed, 0 changed

## Automation gate

The initial canonical master file is never modified by this automation. Neon
activation occurs only when the crawl is finished, the queue has no pending or
error rows, crawl errors are zero, and all three target counts match. A
temporary staging master is used to build and validate the public projection.

## Result

- Neon update blocked because the crawl did not pass the completion gate.
