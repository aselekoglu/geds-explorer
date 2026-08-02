-- GEDS public projection v1 for a hosted read store.
--
-- Importers write one release under geds_public and only change
-- active_projection after staging validation and a GET-only smoke test.
-- The schema intentionally contains no crawler, control-plane, or contact
-- fields. Create the login role in Neon separately; never commit its secret.

CREATE SCHEMA IF NOT EXISTS geds_public;

CREATE TABLE IF NOT EXISTS geds_public.projection_releases (
  release_id TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  projection_version TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  as_of_at TEXT NOT NULL,
  quality_status TEXT NOT NULL,
  release_kind TEXT NOT NULL CHECK (release_kind IN ('public', 'preview')),
  publishable BOOLEAN NOT NULL,
  taxonomy_version TEXT NOT NULL,
  departments_count BIGINT NOT NULL CHECK (departments_count >= 0),
  organizations_count BIGINT NOT NULL CHECK (organizations_count >= 0),
  people_count BIGINT NOT NULL CHECK (people_count >= 0),
  career_entities_count BIGINT NOT NULL CHECK (career_entities_count >= 0),
  data_sha256 CHAR(64) NOT NULL CHECK (data_sha256 ~ '^[0-9a-f]{64}$'),
  status TEXT NOT NULL CHECK (status IN ('staging', 'active', 'retired')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  activated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS geds_public.active_projection (
  singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
  release_id TEXT REFERENCES geds_public.projection_releases(release_id),
  activated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS geds_public.public_meta (
  release_id TEXT PRIMARY KEY REFERENCES geds_public.projection_releases(release_id) ON DELETE CASCADE,
  singleton BOOLEAN NOT NULL DEFAULT TRUE CHECK (singleton),
  snapshot_id TEXT NOT NULL,
  taxonomy_version TEXT NOT NULL,
  quality_status TEXT NOT NULL,
  as_of_at TEXT NOT NULL,
  people_count BIGINT NOT NULL,
  org_units_count BIGINT NOT NULL,
  departments_count BIGINT NOT NULL,
  projection_version TEXT NOT NULL,
  release_kind TEXT NOT NULL CHECK (release_kind IN ('public', 'preview')),
  publishable BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS geds_public.canonical_snapshots (
  release_id TEXT NOT NULL REFERENCES geds_public.projection_releases(release_id) ON DELETE CASCADE,
  snapshot_id TEXT NOT NULL,
  as_of_at TEXT NOT NULL,
  people_count BIGINT NOT NULL,
  org_units_count BIGINT NOT NULL,
  departments_count BIGINT NOT NULL,
  quality_status TEXT NOT NULL,
  PRIMARY KEY (release_id, snapshot_id)
);

CREATE TABLE IF NOT EXISTS geds_public.departments_current (
  release_id TEXT NOT NULL REFERENCES geds_public.projection_releases(release_id) ON DELETE CASCADE,
  department_dn TEXT NOT NULL,
  department_id TEXT NOT NULL,
  name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  PRIMARY KEY (release_id, department_dn),
  UNIQUE (release_id, department_id)
);

CREATE TABLE IF NOT EXISTS geds_public.organizations_current (
  release_id TEXT NOT NULL REFERENCES geds_public.projection_releases(release_id) ON DELETE CASCADE,
  org_dn TEXT NOT NULL,
  org_id TEXT NOT NULL,
  name TEXT NOT NULL,
  parent_dn TEXT,
  department_dn TEXT NOT NULL,
  depth INTEGER NOT NULL,
  canonical_path_json TEXT NOT NULL,
  source_url TEXT NOT NULL,
  direct_people_count BIGINT NOT NULL,
  descendant_people_count BIGINT NOT NULL,
  child_count BIGINT NOT NULL,
  descendant_org_count BIGINT NOT NULL,
  snapshot_id TEXT NOT NULL,
  PRIMARY KEY (release_id, org_dn),
  UNIQUE (release_id, org_id)
);

CREATE TABLE IF NOT EXISTS geds_public.people_current (
  release_id TEXT NOT NULL REFERENCES geds_public.projection_releases(release_id) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  display_name TEXT NOT NULL,
  title TEXT,
  org_path TEXT NOT NULL,
  org_dn TEXT NOT NULL,
  department_dn TEXT NOT NULL,
  department_name TEXT NOT NULL,
  org_unit TEXT NOT NULL,
  canonical_path_json TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  presence_status TEXT NOT NULL,
  PRIMARY KEY (release_id, source_url)
);

CREATE TABLE IF NOT EXISTS geds_public.career_entities (
  release_id TEXT NOT NULL REFERENCES geds_public.projection_releases(release_id) ON DELETE CASCADE,
  entity_id TEXT NOT NULL,
  entity_kind TEXT NOT NULL,
  org_id TEXT,
  title TEXT NOT NULL,
  organization_name TEXT NOT NULL,
  ancestor_text TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  PRIMARY KEY (release_id, entity_id)
);

-- PostgreSQL uses a generated search document instead of SQLite FTS5. The
-- public table remains an allow-listed projection table, with no raw source.
CREATE TABLE IF NOT EXISTS geds_public.career_entities_fts (
  release_id TEXT NOT NULL REFERENCES geds_public.projection_releases(release_id) ON DELETE CASCADE,
  entity_id TEXT NOT NULL,
  title TEXT NOT NULL,
  organization_name TEXT NOT NULL,
  ancestor_text TEXT NOT NULL,
  search_document TSVECTOR GENERATED ALWAYS AS (
    to_tsvector('simple', concat_ws(' ', title, organization_name, ancestor_text))
  ) STORED,
  PRIMARY KEY (release_id, entity_id)
);

CREATE TABLE IF NOT EXISTS geds_public.career_matches (
  release_id TEXT NOT NULL REFERENCES geds_public.projection_releases(release_id) ON DELETE CASCADE,
  entity_id TEXT NOT NULL,
  category_id TEXT NOT NULL,
  score INTEGER NOT NULL,
  confidence TEXT NOT NULL,
  evidence_json JSONB NOT NULL,
  taxonomy_version TEXT NOT NULL,
  PRIMARY KEY (release_id, entity_id, category_id)
);

CREATE TABLE IF NOT EXISTS geds_public.vacancy_signals (
  release_id TEXT NOT NULL REFERENCES geds_public.projection_releases(release_id) ON DELETE CASCADE,
  entity_id TEXT NOT NULL,
  source_text TEXT NOT NULL,
  title TEXT NOT NULL,
  org_id TEXT,
  snapshot_id TEXT NOT NULL,
  confidence TEXT NOT NULL,
  reasons_json JSONB NOT NULL,
  PRIMARY KEY (release_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_geds_public_active_release
  ON geds_public.projection_releases(status, release_id);
CREATE INDEX IF NOT EXISTS idx_geds_public_org_parent_name
  ON geds_public.organizations_current(release_id, parent_dn, name);
CREATE INDEX IF NOT EXISTS idx_geds_public_people_org_title
  ON geds_public.people_current(release_id, org_dn, title);
CREATE INDEX IF NOT EXISTS idx_geds_public_search_document
  ON geds_public.career_entities_fts USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_geds_public_matches_category
  ON geds_public.career_matches(release_id, category_id, score DESC);
CREATE INDEX IF NOT EXISTS idx_geds_public_vacancy_org
  ON geds_public.vacancy_signals(release_id, org_id);

-- Run these grants after creating the Neon login role with the dashboard or
-- an operator secret. The Vercel runtime role must be SELECT-only:
--
-- GRANT USAGE ON SCHEMA geds_public TO geds_public_reader;
-- GRANT SELECT ON ALL TABLES IN SCHEMA geds_public TO geds_public_reader;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA geds_public
--   GRANT SELECT ON TABLES TO geds_public_reader;
