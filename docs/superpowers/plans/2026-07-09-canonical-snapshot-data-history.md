# Canonical Snapshot Data History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Make Snapshot Data browse one validated canonical dataset and expose person-level change history without retaining full historical snapshots.

**Architecture:** A master SQLite database owns immutable manifests, one current entity state, and append-only change events. A deterministic resolver combines the selected completed pagination-backfill run with every run_pagination_seeds base. A canonicalizer validates and atomically promotes the resolved view; the UI reads master current rows, story aggregates, and timelines.

**Tech Stack:** Python 3 standard library, SQLite/WAL, existing SnapshotReader, standard-library HTTP server, pytest.

## Global Constraints

- Preserve user-owned changes in the master checkout; work only in isolated branch codex/canonical-snapshot-history.
- TDD is mandatory: each production behavior starts with a failing pytest test.
- Do not commit SQLite files, person records, or raw person event exports to Git.
- source_url is the initial strong person key. Never silently merge a new URL into another identity.
- Only complete and validated source graphs promote current state; failed, stopped, partial, or source-incomplete inputs leave master state untouched.
- First eligible absence emits missing_once; second consecutive eligible absence emits departed.
- Snapshot Data has no source picker. Crawler operational screens keep their run controls.

---

## File structure

- Create src/geds_crawler/canonical_models.py: immutable source, manifest, current-person, and event dataclasses.
- Create src/geds_crawler/canonical_store.py: master schema, transaction boundaries, and indexed persistence.
- Create src/geds_crawler/canonical_resolver.py: completed run source graph resolution.
- Create src/geds_crawler/canonicalizer.py: baseline/promotion, validation, and diff events.
- Create src/geds_crawler/canonical_queries.py: story, current browse, and timeline DTOs.
- Modify src/geds_crawler/cli.py: canonicalize command.
- Modify src/geds_crawler/ui_server.py: canonical APIs and story-first Snapshot Data.
- Create tests/test_canonical_store.py, tests/test_canonical_resolver.py, tests/test_canonicalizer.py, tests/test_canonical_queries.py.
- Modify tests/test_ui_server.py and tests/test_ui_cli.py.

### Task 1: Master schema and contracts

**Files:**
- Create: src/geds_crawler/canonical_models.py
- Create: src/geds_crawler/canonical_store.py
- Test: tests/test_canonical_store.py

**Consumes:** SQLite path.
**Produces:** CanonicalStore, CanonicalSnapshot, SnapshotMember, CurrentPerson, PersonChangeEvent.

- [ ] **Step 1: Write failing rollback and index tests**

    def test_failed_transaction_does_not_advance_current_snapshot(tmp_path):
        with CanonicalStore(tmp_path / "master.sqlite") as store:
            store.init_schema()
            with pytest.raises(RuntimeError):
                with store.transaction():
                    store.insert_snapshot(_snapshot("s1", None))
                    store.set_current_snapshot("s1")
                    raise RuntimeError("abort")
            assert store.current_snapshot() is None

    def test_event_indexes_support_person_timeline(tmp_path):
        with CanonicalStore(tmp_path / "master.sqlite") as store:
            store.init_schema()
            assert {"idx_person_change_events_person_time",
                    "idx_person_change_events_snapshot_type"} <= store.index_names()

- [ ] **Step 2: Observe RED**

Run: py -m pytest tests/test_canonical_store.py -q
Expected: FAIL because geds_crawler.canonical_store does not exist.

- [ ] **Step 3: Implement minimal schema and transaction**

    @dataclass(frozen=True)
    class CanonicalSnapshot:
        snapshot_id: str
        parent_snapshot_id: str | None
        as_of_at: str
        source_fingerprint: str
        people_count: int
        org_units_count: int
        departments_count: int
        baseline: bool

    CREATE TABLE canonical_snapshots (...);
    CREATE TABLE canonical_snapshot_members (...);
    CREATE TABLE people_current (person_key TEXT PRIMARY KEY, ...);
    CREATE TABLE person_change_events (...);
    CREATE TABLE canonical_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE INDEX idx_person_change_events_person_time
      ON person_change_events(person_key, occurred_at);
    CREATE INDEX idx_person_change_events_snapshot_type
      ON person_change_events(snapshot_id, event_type);

CanonicalStore.transaction() executes BEGIN IMMEDIATE and rolls back on every exception. current_snapshot_id is stored only in canonical_state.

- [ ] **Step 4: Verify GREEN**

Run: py -m pytest tests/test_canonical_store.py tests/test_store.py -q
Expected: PASS.

- [ ] **Step 5: Commit**

    git add src/geds_crawler/canonical_models.py src/geds_crawler/canonical_store.py tests/test_canonical_store.py
    git commit -m "feat: add canonical snapshot master store"

### Task 2: Resolve complete multi-base source lineage

**Files:**
- Create: src/geds_crawler/canonical_resolver.py
- Create: tests/test_canonical_resolver.py
- Modify: src/geds_crawler/ui_server.py lines 459-536 after the resolver exists.

**Consumes:** control SQLite crawl_runs and run_pagination_seeds, SnapshotReader.
**Produces:** resolve_completed_run(control_db: Path, run_id: str) -> ResolvedSnapshot.

- [ ] **Step 1: Write failing source-graph tests**

    def test_resolve_completed_backfill_uses_every_distinct_seed_base(tmp_path):
        control_db, run_id, base_one, base_two, overlay = _completed_backfill_with_two_bases(tmp_path)
        resolved = resolve_completed_run(control_db, run_id)
        assert resolved.base_db_paths == (base_one.resolve(), base_two.resolve())
        assert resolved.overlay_db_paths == (overlay.resolve(),)
        assert resolved.reader().people(limit=10)["total"] == 3

    def test_resolver_rejects_incomplete_backfill(tmp_path):
        control_db, run_id = _backfill_with_pending_page(tmp_path)
        with pytest.raises(CanonicalValidationError, match="not complete"):
            resolve_completed_run(control_db, run_id)

- [ ] **Step 2: Observe RED**

Run: py -m pytest tests/test_canonical_resolver.py -q
Expected: FAIL because the resolver does not exist.

- [ ] **Step 3: Implement deterministic resolution**

    def resolve_completed_run(control_db: Path, run_id: str) -> ResolvedSnapshot:
        run = _load_finished_run(control_db, run_id)
        if run["crawl_kind"] != "pagination_backfill":
            raise CanonicalValidationError("canonical promotion requires pagination_backfill")
        bases = _distinct_existing_seed_bases(control_db, run_id)
        overlay = _existing_output_db(run["output_dir"])
        _assert_pagination_terminal(overlay)
        return ResolvedSnapshot(tuple(bases), (overlay,), _members(...))

Require every source path. Do not use the unmanaged-snapshot fallback. The returned reader uses existing SnapshotReader deduplication.

- [ ] **Step 4: Verify GREEN**

Run: py -m pytest tests/test_canonical_resolver.py tests/test_ui_server.py -q
Expected: PASS.

- [ ] **Step 5: Commit**

    git add src/geds_crawler/canonical_resolver.py src/geds_crawler/ui_server.py tests/test_canonical_resolver.py
    git commit -m "feat: resolve complete canonical source lineage"

### Task 3: Transactional baseline, promotion, and person deltas

**Files:**
- Create: src/geds_crawler/canonicalizer.py
- Create: tests/test_canonicalizer.py
- Modify: src/geds_crawler/canonical_store.py

**Consumes:** ResolvedSnapshot and CanonicalStore.
**Produces:** promote_canonical_snapshot(master_db, resolved, as_of_at) -> PromotionResult.

- [ ] **Step 1: Write failing lifecycle tests**

    def test_first_promotion_is_baseline_without_person_events(tmp_path):
        result = promote_canonical_snapshot(master, _resolved(ada_title="Engineer"), T1)
        assert result.snapshot.baseline is True
        assert result.event_counts == {}

    def test_second_promotion_records_title_change_and_join(tmp_path):
        promote_canonical_snapshot(master, _resolved(ada_title="Engineer"), T1)
        result = promote_canonical_snapshot(master, _resolved(ada_title="Principal", include_grace=True), T2)
        assert result.event_counts == {"title_changed": 1, "joined": 1}
        assert _events(master, "ada")[-1].before["title"] == "Engineer"
        assert _events(master, "ada")[-1].after["title"] == "Principal"

    def test_absence_is_missing_once_then_departed_after_two_eligible_promotions(tmp_path):
        promote_canonical_snapshot(master, _resolved(include_ada=True), T1)
        promote_canonical_snapshot(master, _resolved(include_ada=False), T2)
        assert _events(master, "ada")[-1].event_type == "missing_once"
        promote_canonical_snapshot(master, _resolved(include_ada=False), T3)
        assert _events(master, "ada")[-1].event_type == "departed"

- [ ] **Step 2: Observe RED**

Run: py -m pytest tests/test_canonicalizer.py -q
Expected: FAIL because promote_canonical_snapshot does not exist.

- [ ] **Step 3: Implement comparison and atomic promotion**

    def _event_for_change(previous: CurrentPerson, incoming: CurrentPerson) -> PersonChangeEvent | None:
        if previous.title != incoming.title:
            return event("title_changed", before={"title": previous.title},
                         after={"title": incoming.title}, certainty="certain")
        if previous.org_dn != incoming.org_dn:
            return event("org_changed", before=_position(previous),
                         after=_position(incoming), certainty="certain")
        if previous.department_dn != incoming.department_dn:
            return event("department_changed", before=_position(previous),
                         after=_position(incoming), certainty="certain")
        return None

Use one CanonicalStore.transaction for current rows, event inserts, manifest/members, count validation, then current_snapshot_id. Implement joined, missing_once, departed, reappeared, and uncertain possible_move.

- [ ] **Step 4: Verify GREEN**

Run: py -m pytest tests/test_canonicalizer.py tests/test_canonical_resolver.py tests/test_canonical_store.py -q
Expected: PASS.

- [ ] **Step 5: Commit**

    git add src/geds_crawler/canonicalizer.py src/geds_crawler/canonical_store.py tests/test_canonicalizer.py
    git commit -m "feat: promote canonical snapshots with person deltas"

### Task 4: Read queries and promotion command

**Files:**
- Create: src/geds_crawler/canonical_queries.py
- Modify: src/geds_crawler/cli.py
- Create: tests/test_canonical_queries.py
- Modify: tests/test_ui_cli.py

**Consumes:** master DB from Task 3.
**Produces:** CanonicalQueries.story(), people(), orgs(), person_timeline() and canonicalize CLI command.

- [ ] **Step 1: Write failing query and CLI tests**

    def test_story_reports_current_and_parent_change_counts(master_with_two_snapshots):
        story = CanonicalQueries(master_with_two_snapshots).story()
        assert story["current"]["people"] == 2
        assert story["changes"] == {"joined": 1, "title_changed": 1}

    def test_cli_canonicalize_promotes_requested_completed_run(tmp_path, capsys):
        assert main(["canonicalize", "--control-db", str(control),
                     "--master-db", str(master), "--run-id", run_id]) == 0
        assert json.loads(capsys.readouterr().out)["people_count"] == 3

- [ ] **Step 2: Observe RED**

Run: py -m pytest tests/test_canonical_queries.py tests/test_ui_cli.py -q
Expected: FAIL because query module and command are absent.

- [ ] **Step 3: Implement command and DTOs**

    elif args.command == "canonicalize":
        resolved = resolve_completed_run(Path(args.control_db), args.run_id)
        result = promote_canonical_snapshot(Path(args.master_db), resolved,
                                            datetime.now(UTC).isoformat())
        print(json.dumps(result.to_dict(), sort_keys=True))
        return 0

story() returns current, parent, changes, coverage, and read-only lineage. Timeline rows return event date, type, certainty, before, after, and source snapshot ID.

- [ ] **Step 4: Verify GREEN**

Run: py -m pytest tests/test_canonical_queries.py tests/test_ui_cli.py -q
Expected: PASS.

- [ ] **Step 5: Commit**

    git add src/geds_crawler/canonical_queries.py src/geds_crawler/cli.py tests/test_canonical_queries.py tests/test_ui_cli.py
    git commit -m "feat: expose canonical history queries and command"

### Task 5: Story-first Snapshot Data HTTP and UI

**Files:**
- Modify: src/geds_crawler/ui_server.py
- Modify: tests/test_ui_server.py

**Consumes:** CanonicalQueries.
**Produces:** GET /api/canonical/story, /api/canonical/people, /api/canonical/orgs, and /api/canonical/people?person_key=... .

- [ ] **Step 1: Write failing public contracts**

    def test_snapshot_data_serves_current_canonical_story_without_source_picker(canonical_server):
        code, story = _get_json(f"{canonical_server}/api/canonical/story")
        _, html = _get_text(canonical_server)
        assert code == 200
        assert story["current"]["people"] == 2
        assert "overview-job-select" not in html
        assert "What changed" in html

    def test_person_timeline_returns_before_after_and_certainty(canonical_server):
        _, timeline = _get_json(f"{canonical_server}/api/canonical/people?person_key=ada")
        assert timeline["events"][0]["event_type"] == "title_changed"
        assert timeline["events"][0]["certainty"] == "certain"

- [ ] **Step 2: Observe RED**

Run: py -m pytest tests/test_ui_server.py -q
Expected: FAIL because canonical routes and story content are absent.

- [ ] **Step 3: Implement endpoint routing and UI**

    async function refreshSnapshotStory() {
      const story = await getJson("/api/canonical/story");
      el("snapshot-as-of").textContent = formatAsOf(story.current.as_of_at);
      el("snapshot-people").textContent = formatNumber(story.current.people);
      renderChangeSummary(story.changes);
      renderChangeDepartments(story.departments);
    }

Render as-of context, current totals, joins, title/org/department changes, possible moves, missing/departed counts, changing departments, current people/org browse, and a person timeline drawer. Escape server text with escapeHtml. Remove source picker and run_id construction only from Snapshot Data.

- [ ] **Step 4: Verify GREEN**

Run: py -m pytest tests/test_ui_server.py tests/test_ui_queries.py -q
Expected: PASS.

- [ ] **Step 5: Commit**

    git add src/geds_crawler/ui_server.py tests/test_ui_server.py
    git commit -m "feat: make snapshot data canonical and story-first"

### Task 6: End-to-end verification and operator docs

**Files:**
- Modify: work/geds-crawler/README.md
- Modify: docs/HANDOFF-CRAWL-CONTROL-PLANE.md
- Modify: work/geds-crawler/tests/test_ui_server.py

**Consumes:** Tasks 1 through 5.
**Produces:** verified promotion workflow and retention documentation.

- [ ] **Step 1: Write end-to-end test**

    def test_promoted_multi_base_snapshot_is_default_http_dataset(tmp_path):
        control_db, run_id, expected_people = _completed_multi_base_backfill(tmp_path)
        main(["canonicalize", "--control-db", str(control_db),
              "--master-db", str(master_db), "--run-id", run_id])
        with _running_server(control_db, master_db) as root:
            _, story = _get_json(f"{root}/api/canonical/story")
            _, people = _get_json(f"{root}/api/canonical/people?limit=1")
        assert story["current"]["people"] == expected_people
        assert people["total"] == expected_people

- [ ] **Step 2: Verify integration behavior**

Run: py -m pytest tests/test_ui_server.py::test_promoted_multi_base_snapshot_is_default_http_dataset -q
Expected: PASS after Tasks 1 through 5.

- [ ] **Step 3: Document operation and retention**

Document:

    py -m geds_crawler.cli canonicalize --control-db outputs/control/control.sqlite --master-db outputs/master/geds-master.sqlite --run-id <completed-pagination-run-id>

State that reruns are safe, validation failure preserves master state, and configured staging cleanup is permitted only after successful promotion.

- [ ] **Step 4: Run full verification**

Run: py -m pytest -q
Expected: PASS.

Run: git diff --check
Expected: no output.

- [ ] **Step 5: Commit**

    git add README.md ../../docs/HANDOFF-CRAWL-CONTROL-PLANE.md tests/test_ui_server.py
    git commit -m "docs: explain canonical snapshot operations"

## Plan self-review

- **Spec coverage:** Tasks 1–3 implement manifests/current/events, multi-base resolution, atomic diff semantics, and absence safety. Task 4 exposes promotion and timeline data. Task 5 makes Snapshot Data canonical and story-first. Task 6 proves the promoted default and documents retention.
- **Placeholder scan:** Each task names files, interfaces, tests, commands, expected outcomes, and commit scope.
- **Type consistency:** ResolvedSnapshot feeds promote_canonical_snapshot; CanonicalStore persists it; CanonicalQueries reads it; HTTP/UI consume those DTOs.
