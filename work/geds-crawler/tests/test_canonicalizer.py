import sqlite3

from geds_crawler.canonical_resolver import OverlayQuality, ResolvedSnapshot
from geds_crawler.canonicalizer import promote_canonical_snapshot


def _db(path, *, ada_title="Engineer", include_ada=True, include_grace=False):
    department_dn = "OU=Dept,O=GC,C=CA"
    org_dn = f"OU=Team,{department_dn}"
    con = sqlite3.connect(path)
    con.executescript("""
      CREATE TABLE crawl_runs(request_count INTEGER,status TEXT,crawl_kind TEXT,started_at TEXT);
      CREATE TABLE departments(dn TEXT,name TEXT);
      CREATE TABLE org_units(dn TEXT,name TEXT,department_dn TEXT,depth INTEGER,org_path TEXT,source_url TEXT);
      CREATE TABLE people_index(display_name TEXT,title TEXT,department_name TEXT,org_unit TEXT,org_path TEXT,source_url TEXT,last_seen TEXT,org_dn TEXT,department_dn TEXT);
      CREATE TABLE crawl_queue(status TEXT); CREATE TABLE crawl_errors(id INTEGER);
    """)
    con.execute("INSERT INTO crawl_runs VALUES (0,'finished','full','2026-07-09')")
    con.execute("INSERT INTO departments VALUES (?,?)", (department_dn, "Dept"))
    con.execute(
        "INSERT INTO org_units VALUES (?,?,?,?,?,?)",
        (org_dn, "Team", department_dn, 1, "Dept / Team", "org"),
    )
    if include_ada:
        con.execute(
            "INSERT INTO people_index VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "Ada Lovelace",
                ada_title,
                "Dept",
                "Team",
                "Dept / Team",
                "ada",
                "",
                org_dn,
                department_dn,
            ),
        )
    if include_grace:
        con.execute(
            "INSERT INTO people_index VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "Grace Hopper",
                "Chief",
                "Dept",
                "Team",
                "Dept / Team",
                "grace",
                "",
                org_dn,
                department_dn,
            ),
        )
    con.commit(); con.close()


def _resolved(path):
    return ResolvedSnapshot((path,), (), (path,))


def _events(master, person):
    with sqlite3.connect(master) as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute("SELECT * FROM person_change_events WHERE person_key=? ORDER BY id", (person,))]


def test_first_promotion_is_baseline_without_person_events(tmp_path):
    source = tmp_path / "source.sqlite"; _db(source)
    result = promote_canonical_snapshot(tmp_path / "master.sqlite", _resolved(source), "2026-07-09T00:00:00+00:00")
    assert result.snapshot.baseline is True
    assert result.event_counts == {}


def test_promotion_materializes_sources_and_current_projection(tmp_path):
    source = tmp_path / "source.sqlite"; _db(source)
    master = tmp_path / "master.sqlite"

    result = promote_canonical_snapshot(
        master,
        _resolved(source),
        "2026-07-09T00:00:00+00:00",
    )

    with sqlite3.connect(master) as con:
        con.row_factory = sqlite3.Row
        assert con.execute(
            "SELECT COUNT(*) FROM canonical_snapshot_sources"
        ).fetchone()[0] == 1
        assert con.execute(
            "SELECT COUNT(*) FROM departments_current"
        ).fetchone()[0] == 1
        assert con.execute(
            "SELECT COUNT(*) FROM organizations_current"
        ).fetchone()[0] == 1
        assert con.execute(
            "SELECT COUNT(*) FROM people_current WHERE presence_status='present'"
        ).fetchone()[0] == 1
        assert con.execute(
            "SELECT source_role FROM canonical_snapshot_sources"
        ).fetchone()[0] == "base"
    assert result.snapshot.root_count == 1
    assert result.snapshot.cycle_count == 0


def test_promotion_records_partial_overlay_quality(tmp_path):
    base = tmp_path / "base.sqlite"; _db(base)
    overlay = tmp_path / "overlay.sqlite"; _db(overlay, include_ada=False)
    org_dn = "OU=Team,OU=Dept,O=GC,C=CA"
    resolved = ResolvedSnapshot(
        (base,),
        (overlay,),
        (base, overlay),
        OverlayQuality(
            frozenset(),
            frozenset({org_dn}),
            (f"partial_overlay_base_fallback:{org_dn}",),
        ),
    )

    result = promote_canonical_snapshot(
        tmp_path / "master.sqlite",
        resolved,
        "2026-07-09T00:00:00+00:00",
    )

    assert result.snapshot.quality_status == "partial_overlay"
    assert result.snapshot.fallback_org_count == 1
    assert result.snapshot.quality_warnings == (
        f"partial_overlay_base_fallback:{org_dn}",
    )


def test_second_promotion_records_title_change_and_join(tmp_path):
    source = tmp_path / "source.sqlite"; _db(source)
    master = tmp_path / "master.sqlite"
    promote_canonical_snapshot(master, _resolved(source), "2026-07-09T00:00:00+00:00")
    source2 = tmp_path / "source2.sqlite"; _db(source2, ada_title="Principal", include_grace=True)
    result = promote_canonical_snapshot(master, _resolved(source2), "2026-07-10T00:00:00+00:00")
    assert result.event_counts["title_changed"] == 1
    assert result.event_counts["joined"] == 1
    assert _events(master, "ada")[-1]["event_type"] == "title_changed"


def test_absence_is_missing_once_then_departed_after_two_eligible_promotions(tmp_path):
    source = tmp_path / "source.sqlite"; _db(source)
    master = tmp_path / "master.sqlite"
    promote_canonical_snapshot(master, _resolved(source), "2026-07-09T00:00:00+00:00")
    absent = tmp_path / "absent.sqlite"; _db(absent, include_ada=False)
    promote_canonical_snapshot(master, _resolved(absent), "2026-07-10T00:00:00+00:00")
    assert _events(master, "ada")[-1]["event_type"] == "missing_once"
    promote_canonical_snapshot(master, _resolved(absent), "2026-07-11T00:00:00+00:00")
    assert _events(master, "ada")[-1]["event_type"] == "departed"


def test_missing_person_reappears_with_same_stable_identity(tmp_path):
    source = tmp_path / "source.sqlite"; _db(source)
    absent = tmp_path / "absent.sqlite"; _db(absent, include_ada=False)
    master = tmp_path / "master.sqlite"
    promote_canonical_snapshot(
        master,
        _resolved(source),
        "2026-07-09T00:00:00+00:00",
    )
    promote_canonical_snapshot(
        master,
        _resolved(absent),
        "2026-07-10T00:00:00+00:00",
    )

    result = promote_canonical_snapshot(
        master,
        _resolved(source),
        "2026-07-11T00:00:00+00:00",
    )

    assert result.event_counts["reappeared"] == 1
    assert _events(master, "ada")[-1]["event_type"] == "reappeared"
