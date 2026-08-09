# Turso parallel public-read seam

The current public Vercel entrypoint remains `work/geds-career-atlas/api/index.py`
and continues to use Neon. No production environment or active pointer is
changed by the Turso migration work.

The explicit alternate entrypoint is:

`work/geds-career-atlas/api/turso_index.py`

It reuses the existing route contract and uses the read-only SQL-over-HTTP
adapter in `work/geds-career-atlas/api/turso_backend.py`. The adapter maps the
Postgres-shaped public queries to the SQLite projection (`release_id` to
`snapshot_id`, `%s` to `?`, and `ILIKE` to SQLite `LIKE`).

## Runtime variables for a reviewed cutover

Set these only as a deliberate deployment change:

```text
GEDS_PUBLIC_TURSO_DATABASE_URL=https://geds-explorer-aselekoglu.aws-us-east-1.turso.io
GEDS_PUBLIC_TURSO_AUTH_TOKEN=<Turso database read-only token>
GEDS_PUBLIC_PROJECTION_SCHEMA=main
```

The platform API token is not a runtime credential. The local read-only token
is stored outside the repository in the DPAPI file
`%APPDATA%\GEDS Explorer\turso-db-readonly-token.dpapi`.

## Verified shadow release

- snapshot: `cbcd6b63facc3b6eb7e344a81c899ea22531cfca5417eb52d8eb4bfdf7712d38`
- quality: `partial_overlay`
- departments / organizations / people: `156 / 27,491 / 201,469`
- career entities: `228,960`
- change events / person change events: `36,857 / 20,493`
- people source URL duplicates: `0`
- Neon: untouched

The Turso database was smoke-tested locally through `/api/meta`, department
listing, root organization children, and search. The existing Neon entrypoint
was not switched and no deploy was performed.
