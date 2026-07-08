# GEDS Live Snapshot UI Design

## Purpose

Provide a small local web UI for observing and browsing a GEDS SQLite snapshot while the crawler is still writing to it.

## Architecture

The UI runs from the existing Python package and uses only the standard library. A local `ThreadingHTTPServer` serves one static HTML page and read-only JSON endpoints. Every request opens a short-lived SQLite connection using URI `mode=ro`, so the UI cannot mutate crawler state.

The command is:

```powershell
py -m geds_crawler.cli ui --db <snapshot-path> --port 8765
```

It binds to `0.0.0.0` by default and prints both the loopback URL and detected LAN URLs. The crawler and UI remain independent processes. Binding to all interfaces makes the read-only snapshot visible to other devices on the local network.

## User Interface

The first screen is an operational dashboard, not a landing page. It contains:

- Crawl status, request count, departments, org units, people, errors, completed queue items, pending queue items, and calculated completion percentage.
- Tabs for `Org Units`, `People`, `Queue`, and `Errors`.
- Text search, department filter, status filter where relevant, page size, previous/next pagination, and a manual refresh command.
- Automatic refresh every three seconds without changing the active tab or filters.
- Official GEDS source links for org and person rows.

The people view exposes only `display_name`, `title`, `department_name`, `org_unit`, `org_path`, and `source_url`. Phone numbers, email addresses, and arbitrary database columns are never returned.

## Data API

- `GET /api/status` returns aggregate crawl and queue counts.
- `GET /api/departments` returns department names for filters.
- `GET /api/orgs?q=&department=&limit=&offset=` returns allowlisted org fields and total count.
- `GET /api/people?q=&department=&limit=&offset=` returns allowlisted person fields and total count.
- `GET /api/queue?q=&department=&status=&limit=&offset=` returns queue progress fields and total count.
- `GET /api/errors?q=&limit=&offset=` returns crawl errors and total count.

Inputs are parsed and bounded. SQL values use parameters; sort order and selected columns are fixed in code.

## Runtime Behavior

SQLite connections use read-only mode, a short busy timeout, and `query_only`. A transient locked/busy database response becomes a JSON `503` error, and the page retains the previous successful data until the next refresh. A missing database fails before the server starts with a concise CLI error.

## Testing

Tests create a temporary real SQLite snapshot using the existing schema. They verify aggregate status, filtering and pagination, endpoint JSON behavior, missing database handling, and the absence of phone/email/contact fields from people responses.
