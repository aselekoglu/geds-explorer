# GEDS Career Atlas and Constellation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Do not dispatch subagents unless the user explicitly requests delegation. Steps use checkbox (- [ ]) syntax for durable tracking.

**Goal:** Build a trustworthy, bilingual Career Atlas over the canonical GEDS snapshot, with explainable career matching, top-down Org Walk, evidence-rich Team Profiles, and a required shareable Government Constellation experience.

**Architecture:** Keep crawl and canonical publication inside the existing Python package, but introduce focused hierarchy, projection, taxonomy, index, query, and read-only FastAPI modules. Build a separate React/TypeScript public web application that consumes only the read-only career API; the existing crawler control plane remains a separate operator process.

**Tech Stack:** Python 3.11+, SQLite/FTS5, FastAPI 0.139.x, Uvicorn 0.50.x, pytest/httpx; Node 24, React 19.2.x, TypeScript, Vite 8.1.x, TanStack Router 1.170.x, TanStack Virtual 3.14.x, D3 7.9.x, Vitest 4.1.x, Playwright, axe-core.

## Global Constraints

- The explorer reads exactly one current canonical snapshot and exposes its ID, as-of time, and quality warnings.
- Derive organization parentage and paths from LDAP DN suffixes; never trust stored parent_dn or org_path for public navigation.
- Accept completed and finished as successful historical pagination statuses; write completed for new success rows.
- Failed pagination organizations retain complete base rows, discard partial overlay rows, and emit explicit fallback warnings.
- Reject canonical publication while any pagination organization is pending or running.
- Deduplicate people by source_url until a canonical person DN is available.
- Matching uses versioned bilingual normalization, synonyms, exclusions, weighted evidence, confidence, and visible reasons.
- The first implementation has no embedding service; semantic recall may be designed only after the fixed evaluation set establishes a measurable baseline.
- A GEDS vacancy marker is an unverified directory signal, never a job, application action, or eligibility claim.
- GC Jobs ingestion and a verified Opportunity Engine are excluded.
- Never store phone/email, export contacts, automate outreach, or claim unverified hiring authority.
- Constellation is required and includes semantic zoom, stable URLs, reduced motion, and an accessible synchronized alternative.
- Public routes are read-only and cannot expose crawler/control-plane mutations.
- Do not push, deploy, open a PR, or contact external parties without explicit authorization.
- Preserve unrelated and user-owned working-tree changes.

## Source Documents and Baseline

- Design: docs/superpowers/specs/2026-07-10-geds-career-atlas-constellation-design.md
- Canonical design: docs/superpowers/specs/2026-07-09-canonical-snapshot-data-history-design.md
- Existing package: work/geds-crawler
- Real lineage run: 769b7b73-dc8e-4911-b1d5-80cbe07e34f8
- Control DB: outputs/control/control.sqlite
- Baseline: 98 Python tests passed in 13.02 seconds on 2026-07-10.

## Durable Progress Protocol

After each task, check its boxes here, append exact command/results to docs/superpowers/progress/geds-career-atlas.md, run git diff --check, and commit only task-owned files. Generated SQLite databases, node_modules, dist, coverage, and Playwright artifacts remain out of Git.

---

## Phase 0 — Trustworthy canonical foundation

### Task 1: Terminal overlay resolution and per-organization fallback

**Files:**
- Modify: work/geds-crawler/src/geds_crawler/canonical_resolver.py
- Create: work/geds-crawler/src/geds_crawler/canonical_projection.py
- Modify: work/geds-crawler/tests/test_canonical_resolver.py
- Create: work/geds-crawler/tests/test_canonical_projection.py
- Create: docs/superpowers/progress/geds-career-atlas.md

**Interfaces:**
- OverlayQuality(successful_org_dns, fallback_org_dns, warnings).
- ResolvedSnapshot.quality, iter_people(), iter_orgs(), and iter_departments().

- [x] **Step 1: Write failing resolver tests**

~~~python
def test_resolver_accepts_historical_finished_status(tmp_path):
    control_db, run_id, *_ = _completed_backfill_with_two_bases(tmp_path)
    overlay = tmp_path / "output" / "geds.sqlite"
    with sqlite3.connect(overlay) as con:
        con.execute("UPDATE pagination_orgs SET status='finished'")
    resolved = resolve_completed_run(control_db, run_id)
    assert resolved.quality.successful_org_dns == frozenset(
        {"ou=organization,dc=department"}
    )


def test_failed_org_is_terminal_with_base_fallback(tmp_path):
    control_db, run_id, *_ = _completed_backfill_with_two_bases(tmp_path)
    overlay = tmp_path / "output" / "geds.sqlite"
    with sqlite3.connect(overlay) as con:
        con.execute("UPDATE pagination_orgs SET status='failed'")
    resolved = resolve_completed_run(control_db, run_id)
    assert resolved.quality.fallback_org_dns == frozenset(
        {"ou=organization,dc=department"}
    )
    assert resolved.quality.warnings == (
        "partial_overlay_base_fallback:ou=organization,dc=department",
    )
~~~

- [x] **Step 2: Verify the tests fail under the strict old check**

Run: cd work/geds-crawler; py -m pytest tests/test_canonical_resolver.py -v

Expected: the new tests fail because only completed is accepted and failed is rejected.

- [x] **Step 3: Classify statuses**

~~~python
@dataclass(frozen=True)
class OverlayQuality:
    successful_org_dns: frozenset[str]
    fallback_org_dns: frozenset[str]
    warnings: tuple[str, ...]


SUCCESS_ORG_STATUSES = frozenset({"completed", "finished"})
FALLBACK_ORG_STATUSES = frozenset({"failed"})


def read_overlay_quality(con: sqlite3.Connection) -> OverlayQuality:
    rows = con.execute(
        "SELECT org_dn, status FROM pagination_orgs ORDER BY org_dn"
    ).fetchall()
    if not rows:
        raise CanonicalValidationError("Backfill overlay has no organizations")
    nonterminal = [
        str(row["status"])
        for row in rows
        if row["status"] not in SUCCESS_ORG_STATUSES | FALLBACK_ORG_STATUSES
    ]
    if nonterminal:
        raise CanonicalValidationError(
            "Backfill overlay has non-terminal statuses: "
            + ", ".join(sorted(set(nonterminal)))
        )
    successful = frozenset(
        str(row["org_dn"]) for row in rows
        if row["status"] in SUCCESS_ORG_STATUSES
    )
    fallback = frozenset(
        str(row["org_dn"]) for row in rows
        if row["status"] in FALLBACK_ORG_STATUSES
    )
    return OverlayQuality(
        successful,
        fallback,
        tuple(f"partial_overlay_base_fallback:{dn}" for dn in sorted(fallback)),
    )
~~~

- [x] **Step 4: Write failing projection replacement tests**

~~~python
def test_success_overlay_replaces_base_people_for_target_org(snapshot_set):
    people = {
        row["source_url"]
        for row in snapshot_set.resolved(status="finished").iter_people()
    }
    assert people == {"overlay-person", "untargeted-base-person"}


def test_failed_overlay_discards_partial_rows_and_keeps_base(snapshot_set):
    people = {
        row["source_url"]
        for row in snapshot_set.resolved(status="failed").iter_people()
    }
    assert people == {"base-person", "untargeted-base-person"}
~~~

- [x] **Step 5: Implement deterministic projection**

~~~python
def iter_projected_people(resolved: ResolvedSnapshot) -> Iterator[dict[str, object]]:
    base_rows = dedupe_rows(
        resolved.base_db_paths, table="people_index", key="source_url"
    )
    overlay_rows = dedupe_rows(
        resolved.overlay_db_paths, table="people_index", key="source_url"
    )
    selected: dict[str, dict[str, object]] = {}
    for row in base_rows:
        if str(row["org_dn"]) not in resolved.quality.successful_org_dns:
            selected[str(row["source_url"])] = row
    for row in overlay_rows:
        if str(row["org_dn"]) in resolved.quality.successful_org_dns:
            selected[str(row["source_url"])] = row
    yield from (selected[key] for key in sorted(selected))
~~~

Implement organization and department projections with deterministic source-path ordering and DN deduplication. Failed-org partial overlay people never enter the result.

- [x] **Step 6: Verify and commit**

Run: cd work/geds-crawler; py -m pytest tests/test_canonical_resolver.py tests/test_canonical_projection.py -v

Expected: all focused tests pass.

Run: cd work/geds-crawler; py -m pytest -q

Expected: at least 102 tests pass.

~~~powershell
git add work/geds-crawler/src/geds_crawler/canonical_resolver.py work/geds-crawler/src/geds_crawler/canonical_projection.py work/geds-crawler/tests/test_canonical_resolver.py work/geds-crawler/tests/test_canonical_projection.py docs/superpowers/progress/geds-career-atlas.md
git commit -m "fix: build safe canonical overlay projection"
~~~

### Task 2: DN-derived canonical hierarchy

**Files:**
- Create: work/geds-crawler/src/geds_crawler/canonical_hierarchy.py
- Modify: work/geds-crawler/src/geds_crawler/canonical_models.py
- Create: work/geds-crawler/tests/test_canonical_hierarchy.py

**Interfaces:**
- dn_suffixes(dn) and stable_org_id(dn).
- derive_hierarchy(rows) -> tuple[CanonicalOrganization, ...].
- validate_hierarchy(orgs) -> HierarchyQuality.

- [x] **Step 1: Write failing escaped-DN and parent/path tests**

~~~python
def test_dn_suffixes_preserve_escaped_commas():
    assert dn_suffixes(r"OU=Policy\, Planning,OU=Branch,O=GC,C=CA") == (
        r"OU=Branch,O=GC,C=CA",
        r"O=GC,C=CA",
        "C=CA",
    )


def test_parent_and_path_ignore_stored_corruption():
    rows = [
        {"dn": "OU=Dept,O=GC,C=CA", "name": "Dept", "parent_dn": "broken"},
        {
            "dn": "OU=Team,OU=Dept,O=GC,C=CA",
            "name": "Team",
            "parent_dn": "self",
        },
    ]
    orgs = derive_hierarchy(rows)
    assert orgs[1].parent_dn == "OU=Dept,O=GC,C=CA"
    assert orgs[1].canonical_path == ("Dept", "Team")
~~~

- [x] **Step 2: Verify the missing module failure**

Run: cd work/geds-crawler; py -m pytest tests/test_canonical_hierarchy.py -v

Expected: collection fails with ModuleNotFoundError.

- [x] **Step 3: Implement immutable hierarchy types and DN parsing**

~~~python
@dataclass(frozen=True)
class CanonicalOrganization:
    org_id: str
    dn: str
    name: str
    parent_dn: str | None
    department_dn: str
    depth: int
    canonical_path: tuple[str, ...]
    source_url: str


def stable_org_id(dn: str) -> str:
    digest = hashlib.sha256(dn.casefold().encode("utf-8")).digest()[:16]
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
~~~

Parse unescaped commas, choose the nearest suffix present in the known-DN set, calculate paths through memoized parent traversal, and raise CanonicalValidationError on cycles or missing roots.

- [x] **Step 4: Add real-data invariants**

~~~python
def test_current_lineage_has_expected_cycle_free_shape(real_projected_orgs):
    quality = validate_hierarchy(derive_hierarchy(real_projected_orgs))
    assert quality.root_count == 156
    assert quality.missing_parent_count == 0
    assert quality.cycle_count == 0
    assert quality.max_depth == 12
~~~

Skip this integration test only when real output DBs are absent. It must run during final acceptance in this workspace.

- [x] **Step 5: Verify and commit**

Run: cd work/geds-crawler; py -m pytest tests/test_canonical_hierarchy.py -v

Expected: all unit and available real-data tests pass.

~~~powershell
git add work/geds-crawler/src/geds_crawler/canonical_hierarchy.py work/geds-crawler/src/geds_crawler/canonical_models.py work/geds-crawler/tests/test_canonical_hierarchy.py
git commit -m "feat: derive canonical GEDS hierarchy from DNs"
~~~

### Task 3: Canonical current projection and source lineage schema

**Files:**
- Modify: work/geds-crawler/src/geds_crawler/canonical_models.py
- Modify: work/geds-crawler/src/geds_crawler/canonical_store.py
- Modify: work/geds-crawler/tests/test_canonical_store.py

**Interfaces:**
- CanonicalSource, CanonicalDepartment, CanonicalOrganization, CanonicalPerson, CanonicalQuality.
- CanonicalStore.replace_current_projection(departments, organizations, people).
- CanonicalStore.current_manifest() and quality_warnings().

- [x] **Step 1: Add failing schema and rollback tests**

~~~python
def test_store_has_source_and_current_entity_tables(tmp_path):
    with CanonicalStore(tmp_path / "master.sqlite") as store:
        store.init_schema()
        assert {
            "canonical_snapshot_sources",
            "departments_current",
            "organizations_current",
            "people_current",
        } <= store.table_names()


def test_projection_and_pointer_rollback_together(tmp_path, projection):
    with CanonicalStore(tmp_path / "master.sqlite") as store:
        store.init_schema()
        with pytest.raises(RuntimeError):
            with store.transaction():
                store.replace_current_projection(*projection)
                raise RuntimeError("abort")
        assert store.current_snapshot() is None
        count = store.db.execute(
            "SELECT COUNT(*) FROM organizations_current"
        ).fetchone()[0]
        assert count == 0
~~~

- [x] **Step 2: Verify the schema tests fail**

Run: cd work/geds-crawler; py -m pytest tests/test_canonical_store.py -v

Expected: new table and method assertions fail.

- [x] **Step 3: Store true source lineage and current entities**

~~~sql
CREATE TABLE canonical_snapshot_sources (
  snapshot_id TEXT NOT NULL,
  source_path TEXT NOT NULL,
  source_role TEXT NOT NULL CHECK(source_role IN ('base','overlay')),
  precedence INTEGER NOT NULL,
  source_sha256 TEXT NOT NULL,
  PRIMARY KEY(snapshot_id, source_path)
);

CREATE TABLE departments_current (
  department_dn TEXT PRIMARY KEY,
  department_id TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  snapshot_id TEXT NOT NULL
);

CREATE TABLE organizations_current (
  org_dn TEXT PRIMARY KEY,
  org_id TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  parent_dn TEXT,
  department_dn TEXT NOT NULL,
  depth INTEGER NOT NULL,
  canonical_path_json TEXT NOT NULL,
  source_url TEXT NOT NULL,
  direct_people_count INTEGER NOT NULL,
  descendant_people_count INTEGER NOT NULL,
  child_count INTEGER NOT NULL,
  descendant_org_count INTEGER NOT NULL,
  snapshot_id TEXT NOT NULL
);
~~~

Extend people_current with org_dn, department_dn, department_name, org_unit, canonical_path_json, last_seen_at, and source_url. Add indexes on organization parent/name, department/depth, people org/title, and people department. Replace the old person-shaped canonical_snapshot_members behavior with source lineage; current entities provide the projection.

- [x] **Step 4: Verify atomicity and commit**

Run: cd work/geds-crawler; py -m pytest tests/test_canonical_store.py -v

Expected: all canonical-store tests pass.

~~~powershell
git add work/geds-crawler/src/geds_crawler/canonical_models.py work/geds-crawler/src/geds_crawler/canonical_store.py work/geds-crawler/tests/test_canonical_store.py
git commit -m "feat: store canonical organization projection"
~~~

### Task 4: Real canonical publication command and baseline

**Files:**
- Modify: work/geds-crawler/src/geds_crawler/canonicalizer.py
- Create: work/geds-crawler/src/geds_crawler/career_cli.py
- Modify: work/geds-crawler/pyproject.toml
- Modify: root .gitignore
- Modify: work/geds-crawler/tests/test_canonicalizer.py
- Create: work/geds-crawler/tests/test_career_cli.py

**Interfaces:**
- publish_canonical(control_db, run_id, master_db, as_of_at) -> PromotionResult.
- geds-career publish --control-db PATH --run-id ID --master-db PATH --as-of ISO8601.

- [x] **Step 1: Add failing quality and CLI tests**

~~~python
def test_promotion_records_fallback_quality(tmp_path, resolved_with_fallback):
    result = promote_canonical_snapshot(
        tmp_path / "master.sqlite",
        resolved_with_fallback,
        "2026-07-10T00:00:00+00:00",
    )
    assert result.snapshot.quality_status == "partial_overlay"
    assert result.snapshot.fallback_org_count == 1


def test_publish_command_prints_manifest_json(tmp_path, capsys, lineage):
    code = main([
        "publish",
        "--control-db", str(lineage.control_db),
        "--run-id", lineage.run_id,
        "--master-db", str(tmp_path / "master.sqlite"),
        "--as-of", "2026-07-10T00:00:00+00:00",
    ])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["snapshot_id"]
~~~

- [x] **Step 2: Verify tests fail**

Run: cd work/geds-crawler; py -m pytest tests/test_canonicalizer.py tests/test_career_cli.py -v

Expected: quality fields and career CLI are absent.

- [x] **Step 3: Publish one atomic projection**

~~~python
def publish_canonical(
    control_db: Path,
    run_id: str,
    master_db: Path,
    as_of_at: str,
) -> PromotionResult:
    resolved = resolve_completed_run(control_db, run_id)
    people = tuple(resolved.iter_people())
    organizations = derive_hierarchy(tuple(resolved.iter_orgs()))
    quality = validate_hierarchy(organizations).merge(resolved.quality)
    if quality.has_blocking_errors:
        raise CanonicalValidationError(quality.describe())
    return promote_canonical_snapshot(
        master_db,
        resolved,
        as_of_at,
        projected_people=people,
        projected_orgs=organizations,
        quality=quality,
    )
~~~

Fingerprint normalized current entities and source checksums. Write manifest, true sources, current projection, history events, and pointer inside one transaction.

- [x] **Step 4: Add CLI entry point and ignores**

~~~toml
[project.scripts]
geds-crawl = "geds_crawler.cli:main"
geds-career = "geds_crawler.career_cli:main"
~~~

Ignore outputs/master/*.sqlite plus WAL/SHM, work/geds-career-atlas/node_modules, dist, coverage, and Playwright artifacts.

- [x] **Step 5: Run all Python tests**

Run: cd work/geds-crawler; py -m pytest -q

Expected: all tests pass.

- [x] **Step 6: Publish the real baseline**

Run in this isolated worktree: cd work/geds-crawler; py -m geds_crawler.career_cli publish --control-db C:/Users/asele/Documents/geds-explorer/outputs/control/control.sqlite --run-id 769b7b73-dc8e-4911-b1d5-80cbe07e34f8 --master-db C:/Users/asele/Documents/geds-explorer/outputs/master/geds-master.sqlite --as-of 2026-07-09T07:05:04.674049+00:00

Expected: departments 156, organizations 26421, people 193163, roots 156, cycles 0, missing parents 0, max depth 12, fallback organizations 4, quality partial_overlay. If a count differs, reconcile source lineage rather than editing expected values to pass.

- [x] **Step 7: Commit**

~~~powershell
git add .gitignore work/geds-crawler/pyproject.toml work/geds-crawler/src/geds_crawler/canonicalizer.py work/geds-crawler/src/geds_crawler/career_cli.py work/geds-crawler/tests/test_canonicalizer.py work/geds-crawler/tests/test_career_cli.py docs/superpowers/progress/geds-career-atlas.md
git commit -m "feat: publish canonical GEDS baseline"
~~~

## Phase 1 — Career Atlas data and API spine

### Task 5: Versioned bilingual taxonomy and normalization

**Files:**
- Create: work/geds-crawler/src/geds_crawler/data/career_taxonomy.v1.json
- Create: work/geds-crawler/src/geds_crawler/career_taxonomy.py
- Create: work/geds-crawler/tests/test_career_taxonomy.py

**Interfaces:**
- load_taxonomy(path) -> CareerTaxonomy.
- normalize_text(value) and tokenize(value).
- CareerTaxonomy.interpret(query) -> QueryInterpretation.

- [x] **Step 1: Write failing bilingual interpretation tests**

~~~python
@pytest.mark.parametrize(
    ("query", "category"),
    [
        ("AI", "data-ai-research"),
        ("intelligence artificielle", "data-ai-research"),
        ("cybersécurité", "cyber-it-infrastructure"),
        ("approvisionnement", "finance-audit-procurement"),
        ("relations publiques", "communications-public-affairs"),
    ],
)
def test_interpret_maps_bilingual_terms(query, category, taxonomy):
    result = taxonomy.interpret(query)
    assert category in result.category_ids
    assert result.evidence


def test_normalization_is_diacritic_aware():
    assert normalize_text("Cybersécurité") == "cybersecurite"
~~~

- [x] **Step 2: Verify missing-module failure**

Run: cd work/geds-crawler; py -m pytest tests/test_career_taxonomy.py -v

Expected: collection fails with ModuleNotFoundError.

- [x] **Step 3: Create all ten initial categories**

The JSON schema requires version, unique id, bilingual labels, bilingual phrases, abbreviations, bilingual synonyms, exclusions, positive_examples, and negative_examples. Required IDs:

~~~json
[
  "software-digital-delivery",
  "data-ai-research",
  "cyber-it-infrastructure",
  "policy-programs-regulation",
  "communications-public-affairs",
  "finance-audit-procurement",
  "legal-enforcement-investigations",
  "science-engineering-environment-health",
  "hr-organizational-services",
  "executive-management-coordination"
]
~~~

Validate bilingual labels, normalized phrase collisions, duplicate IDs, empty phrase sets, and exclusion collisions during load.

- [x] **Step 4: Implement deterministic query interpretation**

~~~python
@dataclass(frozen=True)
class QueryInterpretation:
    original_query: str
    normalized_query: str
    category_ids: tuple[str, ...]
    expanded_terms: tuple[str, ...]
    evidence: tuple[str, ...]
    taxonomy_version: str


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(TOKEN_RE.findall(plain))
~~~

Original source strings are never overwritten. Interpretation sorts category IDs and expanded terms for reproducibility.

- [x] **Step 5: Verify and commit**

Run: cd work/geds-crawler; py -m pytest tests/test_career_taxonomy.py -v

Expected: all tests pass.

~~~powershell
git add work/geds-crawler/src/geds_crawler/data/career_taxonomy.v1.json work/geds-crawler/src/geds_crawler/career_taxonomy.py work/geds-crawler/tests/test_career_taxonomy.py
git commit -m "feat: add bilingual government career taxonomy"
~~~

### Task 6: Explainable deterministic matcher and fixed evaluation set

**Files:**
- Create: work/geds-crawler/src/geds_crawler/career_matcher.py
- Create: work/geds-crawler/tests/fixtures/career_match_evaluation.v1.json
- Create: work/geds-crawler/tests/test_career_matcher.py

**Interfaces:**
- match_entity(entity, interpretation) -> CareerMatch.
- evaluate_matcher(cases, taxonomy) -> EvaluationReport.

- [x] **Step 1: Write failing weight and exclusion tests**

~~~python
def test_direct_title_outranks_ancestor_only(matcher, ai_query):
    title = matcher.match_entity(
        MatchEntity("p1", "person", "Machine Learning Engineer", "Platform", ()),
        ai_query,
    )
    ancestor = matcher.match_entity(
        MatchEntity("o1", "organization", "", "Administration", ("AI Centre",)),
        ai_query,
    )
    assert title.score > ancestor.score
    assert title.confidence == "high"
    assert title.evidence[0].field == "title"


def test_exclusion_suppresses_ambiguous_policy_term(matcher, policy_query):
    result = matcher.match_entity(
        MatchEntity("o1", "organization", "", "Insurance Policy Processing", ()),
        policy_query,
    )
    assert result.score == 0
    assert result.exclusions
~~~

- [x] **Step 2: Verify missing-module failure**

Run: cd work/geds-crawler; py -m pytest tests/test_career_matcher.py -v

Expected: collection fails with ModuleNotFoundError.

- [x] **Step 3: Implement explicit scores and evidence**

~~~python
WEIGHTS = {
    "title_phrase": 100,
    "organization_phrase": 85,
    "title_synonym": 70,
    "organization_synonym": 55,
    "ancestor_phrase": 25,
}


def confidence_for(score: int) -> str:
    if score >= 100:
        return "high"
    if score >= 60:
        return "medium"
    if score >= 25:
        return "exploratory"
    return "none"
~~~

CareerMatch contains entity_id, category_ids, score, confidence, evidence, exclusions, and taxonomy_version. MatchEvidence contains field, matched_phrase, source_text, weight, and category_id. Deduplicate identical evidence before summing. Ancestor-only evidence can never exceed medium confidence.

- [x] **Step 4: Add a stratified evaluation fixture**

Create at least 40 reviewed cases: four per category, with English, French, abbreviation, ambiguous-negative, title, organization, and deep-ancestor coverage distributed across the set.

~~~json
{
  "query": "cybersecurity",
  "entity": {
    "id": "case-cyber-1",
    "kind": "organization",
    "title": "",
    "organization": "Security Operations Centre",
    "ancestors": ["Digital Services"]
  },
  "expected_categories": ["cyber-it-infrastructure"],
  "minimum_confidence": "medium",
  "forbidden_categories": []
}
~~~

- [x] **Step 5: Verify quality gates and commit**

Run: cd work/geds-crawler; py -m pytest tests/test_career_matcher.py -v

Expected: all cases pass; precision_at_10 is at least 0.80 for each category with ten or more positives; no forbidden category appears.

~~~powershell
git add work/geds-crawler/src/geds_crawler/career_matcher.py work/geds-crawler/tests/fixtures/career_match_evaluation.v1.json work/geds-crawler/tests/test_career_matcher.py
git commit -m "feat: rank career matches with explainable evidence"
~~~

### Task 7: Snapshot-versioned FTS index and recorded vacancy signals

**Files:**
- Create: work/geds-crawler/src/geds_crawler/career_index.py
- Modify: work/geds-crawler/src/geds_crawler/canonical_store.py
- Modify: work/geds-crawler/src/geds_crawler/career_cli.py
- Create: work/geds-crawler/tests/test_career_index.py

**Interfaces:**
- build_career_index(master_db, taxonomy_path) -> IndexBuildReport.
- geds-career index --master-db PATH --taxonomy PATH.
- career_entities, career_entities_fts, career_matches, vacancy_signals, career_index_state.

- [x] **Step 1: Write failing rebuild and vacancy tests**

~~~python
def test_index_is_bound_to_current_snapshot(canonical_master, taxonomy_path):
    report = build_career_index(canonical_master, taxonomy_path)
    assert report.snapshot_id == current_snapshot_id(canonical_master)
    assert report.entity_count > 0
    assert report.taxonomy_version == "1"


@pytest.mark.parametrize(
    ("name", "confidence"),
    [
        ("VACANT, VACANT", "high"),
        ("Vacant, Inocuppé", "high"),
        ("Position, Vacant", "high"),
        ("Vacancy Planning Officer", "none"),
    ],
)
def test_vacancy_requires_placeholder_shaped_name(name, confidence):
    assert parse_vacancy_signal(name, "Analyst").confidence == confidence
~~~

- [x] **Step 2: Verify missing-module failure**

Run: cd work/geds-crawler; py -m pytest tests/test_career_index.py -v

Expected: collection fails with ModuleNotFoundError.

- [x] **Step 3: Build transactional FTS and match tables**

~~~sql
CREATE TABLE career_entities (
  entity_id TEXT PRIMARY KEY,
  entity_kind TEXT NOT NULL,
  org_id TEXT,
  title TEXT NOT NULL,
  organization_name TEXT NOT NULL,
  ancestor_text TEXT NOT NULL,
  normalized_title TEXT NOT NULL,
  normalized_organization TEXT NOT NULL,
  normalized_ancestors TEXT NOT NULL,
  snapshot_id TEXT NOT NULL
);

CREATE VIRTUAL TABLE career_entities_fts USING fts5(
  entity_id UNINDEXED,
  title,
  organization_name,
  ancestor_text,
  tokenize='unicode61 remove_diacritics 2'
);

CREATE TABLE career_matches (
  entity_id TEXT NOT NULL,
  category_id TEXT NOT NULL,
  score INTEGER NOT NULL,
  confidence TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  taxonomy_version TEXT NOT NULL,
  PRIMARY KEY(entity_id, category_id)
);
~~~

Build temporary tables, validate row counts and foreign keys, then swap in one transaction. A failed rebuild leaves the previous career_index_state usable.

- [x] **Step 4: Parse vacancy markers conservatively**

Recognize placeholder-shaped names using normalized vacant, vacancy, inoccupe, inoccupee, inoccupé, and known misspelling inocuppé only when remaining tokens are numeric, position, poste, or repeated markers. Store exact source text, title, org_id, snapshot_id, confidence, and reasons. Store no application status or URL.

- [x] **Step 5: Run the real index build**

Run: cd work/geds-crawler; py -m geds_crawler.career_cli index --master-db ../../outputs/master/geds-master.sqlite --taxonomy src/geds_crawler/data/career_taxonomy.v1.json

Observed baseline: 26421 organizations, 193163 people, and 18 recorded vacancy signals; snapshot_id equals the current manifest; career tables have no contact columns. The original 17-signal estimate was reconciled against source lineage: all 18 rows have distinct GEDS source URLs/DNs, including separately recorded Vacancy/Vacant records with similar role titles.

- [x] **Step 6: Verify and commit**

Run: cd work/geds-crawler; py -m pytest tests/test_career_index.py -v

Expected: all tests pass.

~~~powershell
git add work/geds-crawler/src/geds_crawler/career_index.py work/geds-crawler/src/geds_crawler/canonical_store.py work/geds-crawler/src/geds_crawler/career_cli.py work/geds-crawler/tests/test_career_index.py
git commit -m "feat: build snapshot career index and vacancy signals"
~~~

### Task 8: Bounded read-only repository queries

**Files:**
- Create: work/geds-crawler/src/geds_crawler/career_repository.py
- Create: work/geds-crawler/tests/test_career_repository.py

**Interfaces:**
- CareerRepository.meta(), search(), departments(), children(), ancestors(), team_profile(), roles(), constellation(), tours().
- SQLite connections use mode=ro and query_only=ON.

- [x] **Step 1: Write failing ranking, bounds, and privacy tests**

~~~python
def test_search_returns_explainable_ranked_results(repository):
    result = repository.search(query="AI", limit=20)
    assert result.items
    assert result.items[0].evidence
    assert result.items[0].confidence in {"high", "medium", "exploratory"}
    assert result.limit == 20


def test_children_caps_unbounded_limit(repository):
    assert repository.children(parent_id=None, limit=10000).limit == 200


def test_team_profile_has_no_contact_fields(repository):
    payload = dataclasses.asdict(repository.team_profile("team-id"))
    assert not {"email", "phone", "fax", "address"} & set(payload)
~~~

- [x] **Step 2: Verify missing-module failure**

Run: cd work/geds-crawler; py -m pytest tests/test_career_repository.py -v

Expected: collection fails with ModuleNotFoundError.

- [x] **Step 3: Implement read-only boundaries**

~~~python
class CareerRepository:
    def __init__(self, master_db: Path | str):
        self.master_db = Path(master_db).resolve()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(
            f"file:{self.master_db.as_posix()}?mode=ro",
            uri=True,
            timeout=2,
        )
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        con.execute("PRAGMA busy_timeout=2000")
        return con
~~~

Rank stored category evidence first, FTS phrase score second, stable entity_id last. Include snapshot_id and quality status in every response. Cap ordinary pages at 200 and constellation slices at 2000; aggregate deeper children instead of returning the complete graph. Generate deterministic ETags from snapshot_id plus normalized query arguments so immutable snapshot-versioned reads can be cached without hiding a snapshot change.

- [x] **Step 4: Verify and commit**

Run: cd work/geds-crawler; py -m pytest tests/test_career_repository.py -v

Expected: ranking, bounds, stable-order, profile, and privacy tests pass.

~~~powershell
git add work/geds-crawler/src/geds_crawler/career_repository.py work/geds-crawler/tests/test_career_repository.py
git commit -m "feat: query the canonical career atlas"
~~~

### Task 9: Separate read-only FastAPI application

**Files:**
- Modify: work/geds-crawler/pyproject.toml
- Create: work/geds-crawler/src/geds_crawler/career_api_models.py
- Create: work/geds-crawler/src/geds_crawler/career_api.py
- Modify: work/geds-crawler/src/geds_crawler/career_cli.py
- Create: work/geds-crawler/tests/test_career_api.py

**Interfaces:**
- create_career_app(master_db, frontend_dir=None) -> FastAPI.
- geds-career serve --master-db PATH --frontend-dir PATH --host HOST --port PORT.

- [x] **Step 1: Write failing API isolation tests**

~~~python
def test_meta_and_search_contract(career_client):
    meta = career_client.get("/api/meta")
    assert meta.status_code == 200
    assert meta.json()["snapshot_id"]
    search = career_client.get("/api/search", params={"q": "AI", "limit": 20})
    assert search.status_code == 200
    assert search.json()["items"][0]["evidence"]


@pytest.mark.parametrize("path", ["/api/crawlers", "/api/jobs", "/api/schedules"])
def test_public_app_has_no_control_routes(career_client, path):
    assert career_client.get(path).status_code == 404
    assert career_client.post(path).status_code in {404, 405}
~~~

- [x] **Step 2: Add pinned API dependencies**

~~~toml
dependencies = [
  "beautifulsoup4>=4.12",
  "croniter>=2.0.0",
  "fastapi>=0.139,<0.140",
  "uvicorn>=0.50,<0.51",
  "tzdata; sys_platform == 'win32'",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.28"]
~~~

- [x] **Step 3: Implement app factory and response security**

~~~python
def create_career_app(master_db: Path, frontend_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="GEDS Career Atlas API", docs_url="/api/docs")
    app.state.repository = CareerRepository(master_db)
    app.include_router(api_router, prefix="/api")
    if frontend_dir is not None:
        app.frontend("/", directory=str(frontend_dir))
    return app
~~~

Add middleware headers: Content-Security-Policy with same-origin scripts/styles/connect, X-Content-Type-Options nosniff, and Referrer-Policy strict-origin-when-cross-origin. Do not enable wildcard CORS.

Routes: GET /api/meta, /api/search, /api/departments, /api/orgs/{org_id}/children, /ancestors, /profile, /api/roles, /api/constellation, and /api/tours. Validate and bound every query.

- [x] **Step 4: Add safe server defaults**

Default host 127.0.0.1, port 8780. Refuse a missing master DB, absent current snapshot, or stale career index with stderr explanation and exit code 2.

- [x] **Step 5: Verify and commit**

Run: cd work/geds-crawler; py -m pytest tests/test_career_api.py -v

Run: cd work/geds-crawler; py -m pytest -q

Expected: API tests and full Python suite pass.

~~~powershell
git add work/geds-crawler/pyproject.toml work/geds-crawler/src/geds_crawler/career_api_models.py work/geds-crawler/src/geds_crawler/career_api.py work/geds-crawler/src/geds_crawler/career_cli.py work/geds-crawler/tests/test_career_api.py
git commit -m "feat: expose read-only Career Atlas API"
~~~

## Phase 1 UI — Discover, Org Walk, Team Profile, and Roles

### Task 10: Separate React application and visual system

**Files:**
- Create: work/geds-career-atlas/package.json and package-lock.json
- Create: work/geds-career-atlas/index.html, tsconfig.json, vite.config.ts
- Create: work/geds-career-atlas/src/main.tsx
- Create: work/geds-career-atlas/src/app/App.tsx and router.tsx
- Create: work/geds-career-atlas/src/styles/tokens.css and global.css
- Create: work/geds-career-atlas/src/test/setup.ts
- Create: work/geds-career-atlas/src/app/App.test.tsx

**Interfaces:**
- Routed public application shell with stable tokens and no control actions.

- [ ] **Step 1: Create exact package metadata**

~~~json
{
  "name": "geds-career-atlas",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "typecheck": "tsc -b --pretty false",
    "test": "vitest run",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "@tanstack/react-router": "1.170.17",
    "@tanstack/react-virtual": "3.14.4",
    "d3": "7.9.0",
    "react": "19.2.7",
    "react-dom": "19.2.7",
    "zod": "4.4.3"
  },
  "devDependencies": {
    "@playwright/test": "1.61.1",
    "@types/d3": "7.4.3",
    "@vitejs/plugin-react": "6.0.3",
    "typescript": "6.0.3",
    "vite": "8.1.3",
    "vitest": "4.1.9"
  }
}
~~~

Add compatible current patches of Testing Library, jest-dom, jsdom, and axe-core, then commit the generated lockfile. The lockfile is the transitive dependency authority.

- [x] **Step 2: Write a failing public-shell test**

~~~tsx
it("renders public navigation without crawler actions", () => {
  render(<App />)
  expect(screen.getByRole("link", { name: /discover/i })).toBeVisible()
  expect(screen.getByRole("link", { name: /constellation/i })).toBeVisible()
  expect(screen.queryByText(/start crawler/i)).not.toBeInTheDocument()
})
~~~

- [x] **Step 3: Install, observe failure, and implement shell**

Run: cd work/geds-career-atlas; npm.cmd install; npm.cmd test

Expected before implementation: App/navigation test fails.

Implement a skip link, landmark navigation, snapshot/quality status slot, responsive outlet, and error boundary. Tokens cover surfaces, stable institution palette, career overlays, focus ring, typography, spacing, status, motion, and prefers-reduced-motion.

- [x] **Step 4: Verify and commit**

Run: cd work/geds-career-atlas; npm.cmd test; npm.cmd run typecheck; npm.cmd run build

Expected: all commands exit 0 and dist contains index.html plus hashed assets.

~~~powershell
git add work/geds-career-atlas
git commit -m "feat: scaffold Career Atlas web application"
~~~

### Task 11: Typed API client and shareable URL state

**Files:**
- Create: work/geds-career-atlas/src/api/types.ts
- Create: work/geds-career-atlas/src/api/client.ts and client.test.ts
- Create: work/geds-career-atlas/src/state/explorerSearch.ts and explorerSearch.test.ts
- Modify: work/geds-career-atlas/src/app/router.tsx

**Interfaces:**
- CareerApiClient.
- ExplorerSearch and explorerSearchSchema.

- [x] **Step 1: Write failing round-trip and error tests**

~~~typescript
it("round-trips shareable explorer state", () => {
  const state = explorerSearchSchema.parse({
    q: "AI",
    categories: ["data-ai-research"],
    department: "dept-id",
    org: "org-id",
    confidence: "medium",
    vacancy: true,
    lang: "en",
    mode: "constellation",
    focus: "org-id",
  })
  expect(explorerSearchSchema.parse(state)).toEqual(state)
})

it("raises typed API errors", async () => {
  fetchMock.mockResolvedValue(new Response(
    JSON.stringify({ detail: "index stale" }),
    { status: 409 },
  ))
  await expect(client.meta()).rejects.toMatchObject({ status: 409 })
})
~~~

- [x] **Step 2: Implement strict state and API types**

~~~typescript
export const explorerSearchSchema = z.object({
  q: z.string().catch(""),
  categories: z.array(z.string()).catch([]),
  department: z.string().optional(),
  org: z.string().optional(),
  confidence: z.enum(["high", "medium", "exploratory"]).catch("exploratory"),
  vacancy: z.boolean().catch(false),
  lang: z.enum(["en", "fr"]).catch("en"),
  mode: z.enum(["list", "org-walk", "constellation"]).catch("list"),
  focus: z.string().optional(),
})
~~~

The client accepts AbortSignal, encodes every query parameter, rejects non-2xx responses, and validates snapshot_id/evidence fields before returning data. TanStack Router validates and serializes search state.

- [x] **Step 3: Verify and commit**

Run: cd work/geds-career-atlas; npm.cmd test -- src/api/client.test.ts src/state/explorerSearch.test.ts

Expected: all tests pass.

~~~powershell
git add work/geds-career-atlas/src/api work/geds-career-atlas/src/state work/geds-career-atlas/src/app/router.tsx
git commit -m "feat: synchronize Career Atlas state with URLs"
~~~

### Task 12: Discover and explainable ranked results

**Files:**
- Create: work/geds-career-atlas/src/routes/index.tsx
- Create: work/geds-career-atlas/src/features/discover/InterestSearch.tsx
- Create: work/geds-career-atlas/src/features/discover/InterpretationChips.tsx
- Create: work/geds-career-atlas/src/features/discover/FilterRail.tsx
- Create: work/geds-career-atlas/src/features/discover/MatchCard.tsx
- Create: work/geds-career-atlas/src/features/discover/DiscoverPage.tsx and DiscoverPage.test.tsx
- Create: work/geds-career-atlas/src/styles/discover.css

**Interfaces:**
- Consumes CareerApiClient.search and ExplorerSearch.
- Produces query interpretation, facets, and accessible ranked results.

- [x] **Step 1: Write a failing broad-interest journey**

~~~tsx
it("explains why an AI team matched", async () => {
  renderDiscover({ q: "AI" })
  expect(await screen.findByText("Data, analytics, AI and research")).toBeVisible()
  const card = await screen.findByRole("article", { name: /AI Centre/i })
  expect(within(card).getByText(/Matched because/i)).toBeVisible()
  expect(within(card).getByText(/organization phrase/i)).toBeVisible()
})
~~~

- [x] **Step 2: Implement progressive disclosure**

InterestSearch updates URL state after 250 ms. InterpretationChips make expansions removable. FilterRail exposes domain, institution, confidence, vacancy, and quality. MatchCard shows confidence text and the first three evidence records with an expandable complete list.

- [x] **Step 3: Implement trust states**

No-match displays interpreted concepts, related terms, and removable constraints. Partial data names fallback organizations. Stale state shows canonical as-of time. Loading reserves card space and preserves prior interpretation. Vacancy copy is exactly “Recorded as vacant in GEDS”; no apply action exists.

- [x] **Step 4: Verify and commit**

Run: cd work/geds-career-atlas; npm.cmd test -- src/features/discover/DiscoverPage.test.tsx

Expected: journey, no-match, partial, stale, and loading tests pass.

~~~powershell
git add work/geds-career-atlas/src/routes/index.tsx work/geds-career-atlas/src/features/discover work/geds-career-atlas/src/styles/discover.css
git commit -m "feat: discover government teams by career interest"
~~~

### Task 13: Virtualized top-down Org Walk

**Files:**
- Create: work/geds-career-atlas/src/routes/organizations.tsx
- Create: work/geds-career-atlas/src/features/org-walk/OrgColumn.tsx
- Create: work/geds-career-atlas/src/features/org-walk/OrgBreadcrumb.tsx
- Create: work/geds-career-atlas/src/features/org-walk/OrgWalk.tsx and OrgWalk.test.tsx
- Create: work/geds-career-atlas/src/styles/org-walk.css

**Interfaces:**
- Consumes departments(), children(), ancestors(), and selected org URL state.
- Produces desktop multi-column hierarchy and mobile drill-in.

- [ ] **Step 1: Write failing path and fanout tests**

~~~tsx
it("reveals a shared deep path", async () => {
  renderOrgWalk({ org: "deep-org-id" })
  expect(await screen.findByLabelText("Organization path")).toHaveTextContent(
    "Department / Branch / Directorate / Team",
  )
  expect(screen.getByRole("treeitem", { name: /Team/i })).toHaveAttribute(
    "aria-current",
    "true",
  )
})

it("virtualizes 348 siblings", async () => {
  renderOrgWalkWithChildren(348)
  await screen.findByText("348 organizations")
  expect(screen.getAllByRole("treeitem").length).toBeLessThan(80)
})
~~~

- [ ] **Step 2: Implement accessible virtual columns**

Use useVirtualizer with useFlushSync false for React 19. Columns use role tree and rows role treeitem plus aria-level. Arrow keys move, Right/Enter opens, Left returns, and typeahead filters. Counts distinguish direct people, descendant people, children, and descendants.

- [ ] **Step 3: Implement one-state responsive drill-in**

Below 760 px render one active column and persistent breadcrumb/back action. Reuse the same selected-org URL state; do not create a separate mobile navigation model.

- [ ] **Step 4: Verify and commit**

Run: cd work/geds-career-atlas; npm.cmd test -- src/features/org-walk/OrgWalk.test.tsx

Expected: path, virtualization, keyboard, and mobile tests pass.

~~~powershell
git add work/geds-career-atlas/src/routes/organizations.tsx work/geds-career-atlas/src/features/org-walk work/geds-career-atlas/src/styles/org-walk.css
git commit -m "feat: browse government through virtualized Org Walk"
~~~

### Task 14: Team Profile and Roles

**Files:**
- Create: work/geds-career-atlas/src/routes/team.$orgId.tsx
- Create: work/geds-career-atlas/src/routes/roles.tsx
- Create: work/geds-career-atlas/src/features/team-profile/TeamProfile.tsx
- Create: work/geds-career-atlas/src/features/team-profile/MatchEvidence.tsx
- Create: work/geds-career-atlas/src/features/team-profile/ObservedRoles.tsx
- Create: work/geds-career-atlas/src/features/roles/RoleExplorer.tsx
- Create: work/geds-career-atlas/src/features/team-profile/TeamProfile.test.tsx
- Create: work/geds-career-atlas/src/styles/team-profile.css

**Interfaces:**
- Consumes team_profile(), roles(), and active interpretation.
- Produces evidence-rich team details and role-family/title exploration.

- [ ] **Step 1: Write failing trust-language tests**

~~~tsx
it("shows observed evidence without inventing a mandate or job", async () => {
  renderTeamProfile(profileFixture)
  expect(await screen.findByText("Observed roles")).toBeVisible()
  expect(screen.getByText("Matched because")).toBeVisible()
  expect(screen.getByRole("link", { name: /Open official GEDS/i })).toBeVisible()
  expect(screen.queryByRole("button", { name: /Apply/i })).not.toBeInTheDocument()
  expect(screen.queryByText(/This team is responsible for/i)).not.toBeInTheDocument()
})
~~~

- [ ] **Step 2: Implement profile evidence**

Render canonical chain, direct/descendant counts, role families, representative titles, match evidence, related teams, freshness, fallback warnings, and official GEDS links. Computed prose begins “Inferred from observed organization and role names” and immediately lists evidence. A “Copy data issue report” action copies organization ID, snapshot ID, observed source values, source URL, and a blank correction description; it does not transmit anything.

- [ ] **Step 3: Implement role exploration**

Group normalized titles under taxonomy categories while preserving originals. Support institution, subtree, and confidence filters; each group links back to matching teams.

- [ ] **Step 4: Verify and commit**

Run: cd work/geds-career-atlas; npm.cmd test -- src/features/team-profile/TeamProfile.test.tsx

Expected: evidence, source-link, related-team, role, and no-apply tests pass.

~~~powershell
git add work/geds-career-atlas/src/routes work/geds-career-atlas/src/features/team-profile work/geds-career-atlas/src/features/roles work/geds-career-atlas/src/styles/team-profile.css
git commit -m "feat: explain teams and observed government roles"
~~~

## Phase 2 — Required Government Constellation showcase

### Task 15: Bounded constellation slices and deterministic layout evaluation

**Files:**
- Modify: work/geds-crawler/src/geds_crawler/career_repository.py
- Modify: work/geds-crawler/tests/test_career_repository.py
- Create: work/geds-career-atlas/src/features/constellation/layout.ts and layout.test.ts
- Create: docs/superpowers/evidence/constellation-layout-evaluation.md

**Interfaces:**
- GET /api/constellation?root_id&max_depth&limit&category.
- buildPackLayout(slice, width, height) -> PackedNode[].

- [ ] **Step 1: Write failing bounds and stability tests**

~~~python
def test_root_constellation_returns_departments_not_every_org(repository):
    result = repository.constellation(root_id=None, max_depth=1, limit=2000)
    assert len(result.nodes) == 156
    assert result.truncated is False
~~~

~~~typescript
it("returns identical positions for identical input", () => {
  expect(buildPackLayout(sliceFixture, 1200, 800)).toEqual(
    buildPackLayout(sliceFixture, 1200, 800),
  )
})
~~~

- [ ] **Step 2: Implement aggregate slices**

Root returns 156 institutions. Focused requests return descendants to max_depth with a 2000-node cap. Over-bound branches become aggregate nodes carrying child_count, descendant_org_count, descendant_people_count, match_count, quality_status, and has_more true.

- [ ] **Step 3: Implement stable circle packing**

Use d3.hierarchy, sum by selected metric, sort by descending value then stable org_id, pack.size, and fixed padding. Use no random or force simulation.

- [ ] **Step 4: Evaluate three hierarchical layouts on real data**

Record circle pack, partition, and treemap results for hierarchy readability, label density, hit targets, and focus-transition continuity. Record root and largest 2000-node layout timings. Targets: root under 50 ms and focused layout under 150 ms. Circle pack remains primary unless measured evidence requires a committed plan amendment.

- [ ] **Step 5: Verify and commit**

Run: cd work/geds-crawler; py -m pytest tests/test_career_repository.py -v

Run: cd work/geds-career-atlas; npm.cmd test -- src/features/constellation/layout.test.ts

Expected: bounds and stable-layout tests pass.

~~~powershell
git add work/geds-crawler/src/geds_crawler/career_repository.py work/geds-crawler/tests/test_career_repository.py work/geds-career-atlas/src/features/constellation docs/superpowers/evidence/constellation-layout-evaluation.md
git commit -m "feat: lay out bounded government constellations"
~~~

### Task 16: Interactive canvas Constellation and accessible synchronization

**Files:**
- Create: work/geds-career-atlas/src/routes/constellation.tsx
- Create: work/geds-career-atlas/src/features/constellation/ConstellationCanvas.tsx
- Create: work/geds-career-atlas/src/features/constellation/ConstellationLegend.tsx
- Create: work/geds-career-atlas/src/features/constellation/ConstellationList.tsx
- Create: work/geds-career-atlas/src/features/constellation/useConstellationCamera.ts
- Create: work/geds-career-atlas/src/features/constellation/ConstellationPage.tsx and ConstellationPage.test.tsx
- Create: work/geds-career-atlas/src/styles/constellation.css

**Interfaces:**
- Consumes constellation API, URL category/focus, and packed layout.
- Produces spatial focus, semantic zoom, synchronized list, and shareable state.

- [ ] **Step 1: Write failing focus, reduced-motion, and fallback tests**

~~~tsx
it("lights systems and synchronizes focus", async () => {
  renderConstellation({ q: "AI", category: "data-ai-research" })
  const item = await screen.findByRole("option", { name: /Statistics Canada/i })
  await user.click(item)
  expect(mockNavigate).toHaveBeenCalledWith(
    expect.objectContaining({
      search: expect.objectContaining({ focus: "statcan" }),
    }),
  )
  expect(screen.getByText(/Matched because/i)).toBeVisible()
})

it("disables flight animation for reduced motion", () => {
  mockReducedMotion(true)
  renderConstellation({})
  expect(camera.transitionDuration).toBe(0)
})

it("keeps the synchronized list when canvas fails", async () => {
  mockCanvasFailure()
  renderConstellation({})
  expect(await screen.findByRole("listbox", { name: /Government map/i })).toBeVisible()
})
~~~

- [ ] **Step 2: Implement canvas semantic zoom**

Render visible nodes only. Wide zoom shows institutions and aggregate match intensity; focused zoom reveals branches; close zoom adds names, counts, role families, quality halo, and vacancy badge. Use a spatial lookup for hit testing. Hover never becomes the only detail path.

- [ ] **Step 3: Synchronize accessible list and URL**

ConstellationList exposes the same sorted nodes, selected state, evidence, and focus actions in semantic HTML. Focus updates mode, focus, and breadcrumb URL state. Browser Back restores state. Recompute layout from stable IDs instead of serializing coordinates.

- [ ] **Step 4: Apply visual semantics**

Institution colors stay stable. Domain relevance uses intensity plus outline. Quality uses labelled halo/badge. Vacancy uses a dotted marker and “Recorded as vacant in GEDS”, never the healthy-success green.

- [ ] **Step 5: Verify and commit**

Run: cd work/geds-career-atlas; npm.cmd test -- src/features/constellation/ConstellationPage.test.tsx; npm.cmd run typecheck; npm.cmd run build

Expected: interaction, accessible synchronization, reduced-motion, fallback, typecheck, and build all pass.

~~~powershell
git add work/geds-career-atlas/src/routes/constellation.tsx work/geds-career-atlas/src/features/constellation work/geds-career-atlas/src/styles/constellation.css
git commit -m "feat: explore government as a constellation"
~~~

### Task 17: Curated tours and saved local maps

**Files:**
- Create: work/geds-crawler/src/geds_crawler/data/career_tours.v1.json
- Modify: work/geds-crawler/src/geds_crawler/career_repository.py
- Create: work/geds-career-atlas/src/routes/saved-map.tsx
- Create: work/geds-career-atlas/src/features/saved-map/tours.ts
- Create: work/geds-career-atlas/src/features/saved-map/SavedMap.tsx and SavedMap.test.tsx

**Interfaces:**
- Curated AI, software, cybersecurity, policy, and data tours.
- Local-only SavedView with no person/contact fields.

- [ ] **Step 1: Write failing tour and privacy tests**

~~~tsx
it("opens an AI tour as shareable state", async () => {
  renderSavedMap()
  await user.click(screen.getByRole("button", { name: /Explore AI in government/i }))
  expect(mockNavigate).toHaveBeenCalledWith(
    expect.objectContaining({
      search: expect.objectContaining({
        categories: ["data-ai-research"],
        mode: "constellation",
      }),
    }),
  )
})

it("does not persist people or contacts", () => {
  saveView(savedViewFixture)
  const raw = localStorage.getItem("geds-career-atlas:saved-views:v1") ?? ""
  expect(raw).not.toMatch(/email|phone|person_name|source_url/)
})
~~~

- [ ] **Step 2: Implement editorial tours**

Each tour has id, bilingual title/description, categories, initial focus, ordered stops, and evidence notes. Validate stop IDs against current snapshot and mark missing stops rather than retargeting.

- [ ] **Step 3: Implement local SavedView**

Persist query, categories, department, org/focus IDs, confidence, vacancy, mode, language, user label, an optional local note capped at 2000 characters, and created_at. Compare at most four teams and store only aggregate/profile references. Notes never enter URLs or API requests.

- [ ] **Step 4: Verify and commit**

Run: cd work/geds-career-atlas; npm.cmd test -- src/features/saved-map/SavedMap.test.tsx

Expected: tours, snapshot mismatch, persistence, comparison bound, and privacy tests pass.

~~~powershell
git add work/geds-crawler/src/geds_crawler/data/career_tours.v1.json work/geds-crawler/src/geds_crawler/career_repository.py work/geds-career-atlas/src/routes/saved-map.tsx work/geds-career-atlas/src/features/saved-map
git commit -m "feat: add shareable career tours and saved maps"
~~~

## Phase 3 — Career guidance and vacancy evidence

### Task 18: Conservative lead inference and vacancy presentation

**Files:**
- Create: work/geds-crawler/src/geds_crawler/data/lead_titles.v1.json
- Create: work/geds-crawler/src/geds_crawler/career_leads.py
- Modify: work/geds-crawler/src/geds_crawler/career_repository.py
- Create: work/geds-crawler/tests/test_career_leads.py
- Modify: work/geds-career-atlas/src/features/team-profile/TeamProfile.tsx
- Create: work/geds-career-atlas/src/features/team-profile/CareerConversationLeads.tsx and CareerConversationLeads.test.tsx

**Interfaces:**
- infer_leads(org_id, people, rules) -> tuple[LeadSuggestion, ...].
- LeadSuggestion(kind, confidence, title, org_id, source_url, reasons).

- [ ] **Step 1: Write failing inference-boundary tests**

~~~python
def test_manager_can_be_possible_team_lead(rules):
    lead = infer_lead(
        title="Manager, Data Platforms",
        person_org_id="team",
        target_org_id="team",
        rules=rules,
    )
    assert lead.kind == "possible_team_lead"
    assert lead.confidence == "high"


@pytest.mark.parametrize(
    "title",
    ["Executive Assistant", "Advisor to the Director", "Acting Assistant"],
)
def test_assistants_and_advisors_are_excluded(title, rules):
    assert infer_lead(title, "team", "team", rules) is None
~~~

- [ ] **Step 2: Implement bilingual rules**

Include manager/gestionnaire, director/directeur/directrice, chief/chef, head/responsable, commissioner/commissaire, and executive variants. Exclude assistant, advisor to, conseiller auprès, support, office, and administrative roles. Direct-org leads outrank parent-org leads. Return at most three.

- [ ] **Step 3: Implement non-claiming UI**

~~~tsx
<section aria-labelledby="career-conversation-heading">
  <h2 id="career-conversation-heading">Career conversation leads</h2>
  <p>
    These people appear relevant from their observed title and organization.
    This does not verify that they are hiring or connected to a current process.
  </p>
</section>
~~~

Cards say “Possible team lead” or “Career conversation lead”, show reasons, confidence, snapshot date, and official GEDS. Vacancy cards show the exact marker, observed title, org, date, and “No live competition verified.” No application action exists.

- [ ] **Step 4: Verify and commit**

Run: cd work/geds-crawler; py -m pytest tests/test_career_leads.py -v

Run: cd work/geds-career-atlas; npm.cmd test -- src/features/team-profile/CareerConversationLeads.test.tsx

Expected: exclusions, confidence, wording, no-apply, and no-hiring-manager tests pass.

~~~powershell
git add work/geds-crawler/src/geds_crawler/data/lead_titles.v1.json work/geds-crawler/src/geds_crawler/career_leads.py work/geds-crawler/src/geds_crawler/career_repository.py work/geds-crawler/tests/test_career_leads.py work/geds-career-atlas/src/features/team-profile
git commit -m "feat: suggest evidence-based career conversation leads"
~~~

## Phase 4 — Bilingual UX, resilience, accessibility, and hardening

### Task 19: Complete bilingual and responsive experience

**Files:**
- Create: work/geds-career-atlas/src/i18n/en.ts and fr.ts
- Create: work/geds-career-atlas/src/i18n/i18n.tsx and i18n.test.tsx
- Create: work/geds-career-atlas/src/routes/about.tsx
- Create: work/geds-career-atlas/src/features/about/DataMethodology.tsx and DataMethodology.test.tsx
- Modify: every route/feature component containing product-owned copy
- Modify: work/geds-career-atlas/src/styles/global.css

**Interfaces:**
- t(key, params), LanguageProvider, language-preserving navigation.

- [ ] **Step 1: Write failing copy-completeness and state tests**

~~~tsx
it("has identical English and French key sets", () => {
  expect(Object.keys(flatten(en)).sort()).toEqual(Object.keys(flatten(fr)).sort())
})

it("preserves filters when language changes", async () => {
  renderApp({ q: "AI", org: "org-id", lang: "en" })
  await user.click(screen.getByRole("button", { name: "Français" }))
  expect(mockNavigate).toHaveBeenCalledWith(
    expect.objectContaining({
      search: expect.objectContaining({ q: "AI", org: "org-id", lang: "fr" }),
    }),
  )
})
~~~

- [ ] **Step 2: Centralize product copy**

Source names/titles remain unchanged. Navigation, states, filters, methodology, inference disclaimers, vacancy warnings, dates, and number formats use the language provider. The task fails if either language lacks a key.

About the Data shows canonical snapshot/as-of, source lineage summary, taxonomy version and weights, quality/fallback warnings, privacy limits, vacancy semantics, contact-inference rules, known limitations, and a link back to official GEDS. It describes deterministic matching in plain language and states that no protected traits are inferred.

- [ ] **Step 3: Verify responsive journeys**

At 360, 768, 1280, and 1600 CSS pixels: no clipped navigation or page-level horizontal scroll; Org Walk drills in below 760; Constellation is list-first on small screens; evidence/warnings precede long lists; touch targets are at least 44 by 44.

- [ ] **Step 4: Verify and commit**

Run: cd work/geds-career-atlas; npm.cmd test -- src/i18n/i18n.test.tsx; npm.cmd run typecheck; npm.cmd run build

Expected: all commands pass.

~~~powershell
git add work/geds-career-atlas/src
git commit -m "feat: complete bilingual responsive Career Atlas UX"
~~~

### Task 20: End-to-end accessibility, performance, resilience, and security gates

**Files:**
- Create: work/geds-career-atlas/playwright.config.ts
- Create: work/geds-career-atlas/tests/e2e/discover.spec.ts
- Create: work/geds-career-atlas/tests/e2e/org-walk.spec.ts
- Create: work/geds-career-atlas/tests/e2e/constellation.spec.ts
- Create: work/geds-career-atlas/tests/e2e/accessibility.spec.ts
- Create: work/geds-career-atlas/tests/e2e/resilience.spec.ts
- Create: work/geds-career-atlas/tests/e2e/performance.spec.ts
- Modify: work/geds-crawler/tests/test_career_api.py

**Interfaces:**
- Repeatable browser/API release gate against real canonical data.

- [ ] **Step 1: Write four core browser journeys**

~~~typescript
test("broad interest to government map", async ({ page }) => {
  await page.goto("/?q=AI")
  await expect(page.getByText("Matched because")).toBeVisible()
  await page.getByRole("link", { name: "Constellation" }).click()
  await page.getByRole("option", { name: /Statistics Canada/i }).click()
  await expect(page).toHaveURL(/focus=/)
})
~~~

Add precise Org Walk, career-conversation research, and recorded-vacancy discovery journeys with assertions from the design.

- [ ] **Step 2: Add automated and keyboard accessibility gates**

Run axe on Discover, Organizations, Constellation, Roles, and Team routes and reject critical/serious violations. Assert skip link, visible focus, semantic canvas alternative, tree state, reduced-motion duration zero, and keyboard-only completion. Record manual screen-reader checks separately because automation is incomplete by nature.

- [ ] **Step 3: Add performance budgets**

Against real data and cached assets: initial useful Discover under 2.5 seconds; filter feedback or pending state under 150 ms; root layout under 50 ms; 2000-node layout under 150 ms; bounded API responses; no complete-person-dataset request. Run five times and assert median, while recording all samples.

- [ ] **Step 4: Add public security and resilience tests**

Verify CSP, nosniff, referrer policy, no wildcard CORS, GET-only surface, path traversal rejection, bounded parameters, escaped FTS input, no contacts, no control routes, and useful no-match, partial, stale, source-unavailable, and canvas-failure states.

- [ ] **Step 5: Verify and commit**

Run: cd work/geds-career-atlas; npm.cmd run build; npm.cmd run test:e2e

Expected: all journeys, accessibility, resilience, security, and performance tests pass.

~~~powershell
git add work/geds-career-atlas/playwright.config.ts work/geds-career-atlas/tests/e2e work/geds-crawler/tests/test_career_api.py docs/superpowers/progress/geds-career-atlas.md
git commit -m "test: gate Career Atlas accessibility and performance"
~~~

### Task 21: Final acceptance audit and operator handoff

**Files:**
- Modify: work/geds-crawler/README.md
- Create: work/geds-career-atlas/README.md
- Create: docs/superpowers/evidence/geds-career-atlas-acceptance.md
- Modify: docs/superpowers/progress/geds-career-atlas.md

**Interfaces:**
- Exact build/run workflow and requirement-by-requirement completion evidence.

- [ ] **Step 1: Document local workflows**

Backend run:

~~~powershell
cd work/geds-crawler
py -m pip install -e .[dev]
py -m geds_crawler.career_cli serve --master-db ../../outputs/master/geds-master.sqlite --frontend-dir ../geds-career-atlas/dist --host 127.0.0.1 --port 8780
~~~

Frontend dev:

~~~powershell
cd work/geds-career-atlas
npm.cmd install
npm.cmd run dev
~~~

Document publication/index rebuild, trust indicators, no-contact policy, vacancy semantics, public/control separation, and generated artifacts.

- [ ] **Step 2: Run complete verification**

Run: cd work/geds-crawler; py -m pytest -q

Run: cd work/geds-career-atlas; npm.cmd test; npm.cmd run typecheck; npm.cmd run build; npm.cmd run test:e2e

Run: cd ../..; git diff --check; git status --short

Expected: all tests/builds pass, diff check is silent, and only intended handoff docs remain before final commit.

- [ ] **Step 3: Audit every design criterion**

The acceptance file has one row per criterion with requirement text, implementing task/files, exact automated test, real-data/browser evidence, and status proven or not proven. Intent, a narrower unit test, or absence of observed failure is not proof.

- [ ] **Step 4: Inspect rendered screens**

Review desktop Discover, Org Walk, Team Profile, Constellation, Roles, Saved Map, About, French Discover; mobile Discover/Org Walk; reduced-motion Constellation; and no-match, partial, stale, source-unavailable, and canvas-failure states. Record findings/fixes and rerun affected gates.

- [ ] **Step 5: Commit handoff**

~~~powershell
git add work/geds-crawler/README.md work/geds-career-atlas/README.md docs/superpowers/evidence/geds-career-atlas-acceptance.md docs/superpowers/progress/geds-career-atlas.md
git commit -m "docs: verify and hand off GEDS Career Atlas"
~~~

- [ ] **Step 6: Completion gate**

Re-run status, full tests, acceptance audit, and the durable goal objective. Mark the goal complete only when all 21 tasks are checked, every acceptance row is proven, no required work remains, and current evidence passes. Do not push or deploy.

## Plan Self-Review Record

- Spec coverage: canonical truth, DN hierarchy, bilingual noisy matching, explainable confidence, vacancy distinction, Discover, Org Walk, Team Profile, Roles, required Constellation, career leads, saved/shareable state, privacy, public/control separation, bilingual UX, accessibility, resilience, performance, and final audit each map to a task.
- Type consistency: org_id is the stable public identifier; org_dn remains the canonical relationship key; snapshot_id versions public responses/index rows; QueryInterpretation, CareerMatch, OverlayQuality, and LeadSuggestion each have one producer and named consumers.
- Scope: all phases depend on one canonical projection and one synchronized public state model, so one ordered plan is appropriate. GC Jobs remains a separate excluded subsystem.
- Baseline: 98 Python tests passed before implementation.
