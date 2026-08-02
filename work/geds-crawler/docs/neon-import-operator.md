# Neon import operator seam

`neon_projection_target.NeonProjectionImportTarget` is the DB-API adapter for
the checked-in public projection schema. It receives an operator-owned
read/write connection for staging and activation; it is never used by the
Vercel request path.

The runtime uses `GEDS_PUBLIC_DATABASE_URL` with a separate SELECT-only Neon
role. The operator connection is not stored in the repository and its value
must not be printed. The coordinator sequence remains:

```text
complete canonical snapshot -> export -> validate -> stage -> smoke -> activate
```

Preview projections cannot be activated. Existing active releases are not
deleted during staging; activation changes only the singleton pointer after
staging validation.
