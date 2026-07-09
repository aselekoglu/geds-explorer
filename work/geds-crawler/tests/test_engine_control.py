from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import sqlite3

from geds_crawler.engine import CrawlEngine, CrawlRunConfig, CrawlResult


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def mock_fetcher_with_state():
    with patch("geds_crawler.engine.PoliteFetcher") as mock:
        fetcher_instance = MagicMock()
        fetcher_instance.stats = MagicMock(request_count=0)
        
        # Track URLs requested
        fetcher_instance.requested_urls = []
        
        def fake_fetch_text(url: str) -> str:
            fetcher_instance.stats.request_count += 1
            fetcher_instance.requested_urls.append(url)
            if "pgid=012" in url:
                return load_fixture("department_list.html")
            elif "pgid=014" in url:
                return load_fixture("org_page.html")
            return ""
            
        fetcher_instance.fetch_text.side_effect = fake_fetch_text
        mock.return_value = fetcher_instance
        yield fetcher_instance


def test_cooperative_stop_and_resume(tmp_path, mock_fetcher_with_state):
    db_dir = tmp_path / "stop_resume_test"
    db_path = db_dir / "geds.sqlite"
    stop_file = tmp_path / "stop_now"
    
    # 1. Run engine, request stop after the first fetch
    original_fetch = mock_fetcher_with_state.fetch_text.side_effect
    
    def fetch_with_stop_trigger(url: str) -> str:
        res = original_fetch(url)
        # After we fetch anything (e.g. the department list or the first org page), write the stop file
        if "pgid=014" in url:
            stop_file.write_text("stop")
        return res
        
    mock_fetcher_with_state.fetch_text.side_effect = fetch_with_stop_trigger
    
    config1 = CrawlRunConfig(
        run_id="run-coop-stop",
        output_dir=db_dir,
        department_dns={"OU=ISED-ISDE,O=GC,C=CA"},
        rate_limit_seconds=0.001,
        stop_file=stop_file,
        quiet=True,
        max_depth=2,
    )
    
    engine1 = CrawlEngine(config1)
    result1 = engine1.run()
    
    # Should stop cooperatively
    assert result1.status == "stopped"
    
    # Verify DB state
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    run_row = conn.execute("SELECT * FROM crawl_runs WHERE id=?", ("run-coop-stop",)).fetchone()
    assert run_row is not None
    assert run_row["status"] == "stopped"
    assert run_row["stop_reason"] == "operator_stop"
    assert run_row["heartbeat_at"] is not None
    assert run_row["current_org_dn"] is not None
    
    # Kuyrukta kalan bekleyen (pending) öğeler olmalı
    queue_counts = {
        row["status"]: row["count"]
        for row in conn.execute("SELECT status, COUNT(*) as count FROM crawl_queue GROUP BY status")
    }
    assert queue_counts.get("pending", 0) > 0
    conn.close()
    
    # 2. Resume: stop dosyasını silelim ve aynı DB üzerinde yeniden başlatalım
    if stop_file.exists():
        stop_file.unlink()
        
    # Reset mock call list
    mock_fetcher_with_state.requested_urls.clear()
    mock_fetcher_with_state.fetch_text.side_effect = original_fetch
    
    config2 = CrawlRunConfig(
        run_id="run-resume",
        output_dir=db_dir,
        department_dns={"OU=ISED-ISDE,O=GC,C=CA"},
        rate_limit_seconds=0.001,
        stop_file=stop_file,
        quiet=True,
        max_depth=2,
    )
    
    engine2 = CrawlEngine(config2)
    result2 = engine2.run()
    
    # Should complete successfully
    assert result2.status == "finished"
    
    # Verify no department list URL (pgid=012) was requested on resume
    assert not any("pgid=012" in url for url in mock_fetcher_with_state.requested_urls)
    
    # Verify DB state is finished
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    run_row2 = conn.execute("SELECT * FROM crawl_runs WHERE id=?", ("run-resume",)).fetchone()
    assert run_row2["status"] == "finished"
    
    # All items in queue should be done
    queue_counts2 = {
        row["status"]: row["count"]
        for row in conn.execute("SELECT status, COUNT(*) as count FROM crawl_queue GROUP BY status")
    }
    assert queue_counts2.get("pending", 0) == 0
    conn.close()


def test_engine_pagination_full_crawl(tmp_path):
    db_dir = tmp_path / "paginated_crawl"
    db_path = db_dir / "geds.sqlite"

    with patch("geds_crawler.engine.PoliteFetcher") as mock_fetcher_cls:
        fetcher_inst = MagicMock()
        fetcher_inst.stats = MagicMock(request_count=0)
        requested_urls = []

        def fake_fetch_text(url: str) -> str:
            fetcher_inst.stats.request_count += 1
            requested_urls.append(url)
            if "pgid=012" in url:
                return load_fixture("department_list.html")
            elif "page=2" in url:
                return load_fixture("org_people_page_2.html")
            elif "pgid=014" in url:
                # Page 1
                return load_fixture("org_people_page_1.html")
            return ""

        fetcher_inst.fetch_text.side_effect = fake_fetch_text
        mock_fetcher_cls.return_value = fetcher_inst

        config = CrawlRunConfig(
            run_id="run-paginated",
            output_dir=db_dir,
            department_dns={"OU=ISED-ISDE,O=GC,C=CA"},
            rate_limit_seconds=0.001,
            stop_file=None,
            quiet=True,
            max_depth=1,
        )
        engine = CrawlEngine(config)
        result = engine.run()

        assert result.status == "finished"
        assert any("page=2" in url for url in requested_urls)

        # Verify 30 people exist in the db
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM people_index").fetchone()[0]
        assert count == 30
        conn.close()


def test_engine_pagination_stop_and_resume(tmp_path):
    db_dir = tmp_path / "stop_resume_paginated"
    db_path = db_dir / "geds.sqlite"
    stop_file = tmp_path / "stop_now_pag"

    with patch("geds_crawler.engine.PoliteFetcher") as mock_fetcher_cls:
        fetcher_inst = MagicMock()
        fetcher_inst.stats = MagicMock(request_count=0)
        requested_urls = []

        def fake_fetch_text(url: str) -> str:
            fetcher_inst.stats.request_count += 1
            requested_urls.append(url)
            if "pgid=012" in url:
                return load_fixture("department_list.html")
            elif "pgid=014" in url:
                if "page=2" not in url:
                    stop_file.write_text("stop")
                    return load_fixture("org_people_page_1.html")
                else:
                    return load_fixture("org_people_page_2.html")
            return ""

        fetcher_inst.fetch_text.side_effect = fake_fetch_text
        mock_fetcher_cls.return_value = fetcher_inst

        config1 = CrawlRunConfig(
            run_id="run-stop-pag",
            output_dir=db_dir,
            department_dns={"OU=ISED-ISDE,O=GC,C=CA"},
            rate_limit_seconds=0.001,
            stop_file=stop_file,
            quiet=True,
            max_depth=1,
        )
        engine1 = CrawlEngine(config1)
        res1 = engine1.run()
        assert res1.status == "stopped"

        # Verify page 1 is done, page 2 is pending
        conn = sqlite3.connect(db_path)
        p1_status = conn.execute("SELECT status FROM people_page_queue WHERE page_index=1").fetchone()[0]
        p2_status = conn.execute("SELECT status FROM people_page_queue WHERE page_index=2").fetchone()[0]
        assert p1_status == "done"
        assert p2_status == "pending"
        conn.close()

        # Resume
        if stop_file.exists():
            stop_file.unlink()

        requested_urls.clear()
        config2 = CrawlRunConfig(
            run_id="run-resume-pag",
            output_dir=db_dir,
            department_dns={"OU=ISED-ISDE,O=GC,C=CA"},
            rate_limit_seconds=0.001,
            stop_file=stop_file,
            quiet=True,
            max_depth=1,
        )
        engine2 = CrawlEngine(config2)
        res2 = engine2.run()
        assert res2.status == "finished"
        assert any("page=2" in url for url in requested_urls)
        assert not any("page=1" in url or "pgid=012" in url for url in requested_urls)

        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM people_index").fetchone()[0]
        assert count == 30
        conn.close()


def test_engine_pagination_cycle(tmp_path):
    db_dir = tmp_path / "cycle_paginated"
    db_path = db_dir / "geds.sqlite"

    with patch("geds_crawler.engine.PoliteFetcher") as mock_fetcher_cls:
        fetcher_inst = MagicMock()
        fetcher_inst.stats = MagicMock(request_count=0)

        def fake_fetch_text(url: str) -> str:
            fetcher_inst.stats.request_count += 1
            if "pgid=012" in url:
                return load_fixture("department_list.html")
            elif "pgid=014" in url:
                # Keep returning next links that point back to page 1/2 to create a cycle
                # Let's say page 1 points to page 2, page 2 points to page 1
                if "page=2" in url:
                    # Page 2 points to Page 1
                    return """
                    <html><body>
                    <a href="/en/GEDS?pgid=015&dn=CN=Person 2,O=GC,C=CA">Person 2</a>
                    <a href="/en/GEDS?pgid=014&amp;dn=OU=ISED-ISDE,O=GC,C=CA&amp;page=1" rel="next">Next</a>
                    </body></html>
                    """
                else:
                    # Page 1 points to Page 2
                    return """
                    <html><body>
                    <a href="/en/GEDS?pgid=015&dn=CN=Person 1,O=GC,C=CA">Person 1</a>
                    <a href="/en/GEDS?pgid=014&amp;dn=OU=ISED-ISDE,O=GC,C=CA&amp;page=2" rel="next">Next</a>
                    </body></html>
                    """
            return ""

        fetcher_inst.fetch_text.side_effect = fake_fetch_text
        mock_fetcher_cls.return_value = fetcher_inst

        config = CrawlRunConfig(
            run_id="run-cycle",
            output_dir=db_dir,
            department_dns={"OU=ISED-ISDE,O=GC,C=CA"},
            rate_limit_seconds=0.001,
            stop_file=None,
            quiet=True,
            max_depth=1,
        )
        engine = CrawlEngine(config)
        result = engine.run()

        # The organization crawl failed due to cycle
        conn = sqlite3.connect(db_path)
        org_status = conn.execute("SELECT status, last_error FROM crawl_queue WHERE dn='OU=ISED-ISDE,O=GC,C=CA'").fetchone()
        assert org_status[0] == "error"
        assert "Cycle detected" in org_status[1]
        
        pag_org_status = conn.execute("SELECT status, last_error FROM pagination_orgs WHERE org_dn='OU=ISED-ISDE,O=GC,C=CA'").fetchone()
        assert pag_org_status[0] == "failed"
        assert "Cycle detected" in pag_org_status[1]
        conn.close()


def test_engine_pagination_max_pages_limit(tmp_path):
    db_dir = tmp_path / "max_pages_paginated"
    db_path = db_dir / "geds.sqlite"

    with patch("geds_crawler.engine.PoliteFetcher") as mock_fetcher_cls:
        fetcher_inst = MagicMock()
        fetcher_inst.stats = MagicMock(request_count=0)

        def fake_fetch_text(url: str) -> str:
            fetcher_inst.stats.request_count += 1
            if "pgid=012" in url:
                return load_fixture("department_list.html")
            elif "pgid=014" in url:
                # Return page index + 1 next link
                import urllib.parse
                qs = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
                page_idx = int(qs.get("page", 1))
                return f"""
                <html><body>
                <a href="/en/GEDS?pgid=015&dn=CN=Person {page_idx},O=GC,C=CA">Person {page_idx}</a>
                <a href="/en/GEDS?pgid=014&amp;dn=OU=ISED-ISDE,O=GC,C=CA&amp;page={page_idx + 1}" rel="next">Next</a>
                </body></html>
                """
            return ""

        fetcher_inst.fetch_text.side_effect = fake_fetch_text
        mock_fetcher_cls.return_value = fetcher_inst

        config = CrawlRunConfig(
            run_id="run-max-pages",
            output_dir=db_dir,
            department_dns={"OU=ISED-ISDE,O=GC,C=CA"},
            rate_limit_seconds=0.001,
            stop_file=None,
            quiet=True,
            max_depth=1,
            max_pages_per_org=2,
        )
        engine = CrawlEngine(config)
        result = engine.run()

        conn = sqlite3.connect(db_path)
        org_status = conn.execute("SELECT status, last_error FROM crawl_queue WHERE dn='OU=ISED-ISDE,O=GC,C=CA'").fetchone()
        assert org_status[0] == "error"
        assert "Max pages limit exceeded" in org_status[1]
        conn.close()


def test_engine_logging_exception_does_not_fail_crawl(tmp_path):
    db_dir = tmp_path / "logging_fail"
    db_path = db_dir / "geds.sqlite"

    with patch("geds_crawler.engine.PoliteFetcher") as mock_fetcher_cls:
        fetcher_inst = MagicMock()
        fetcher_inst.stats = MagicMock(request_count=0)

        def fake_fetch_text(url: str) -> str:
            fetcher_inst.stats.request_count += 1
            if "pgid=012" in url:
                return load_fixture("department_list.html")
            elif "pgid=014" in url:
                return load_fixture("org_people_page_2.html") # Terminal page, 5 people
            return ""

        fetcher_inst.fetch_text.side_effect = fake_fetch_text
        mock_fetcher_cls.return_value = fetcher_inst

        config = CrawlRunConfig(
            run_id="run-logging-fail",
            output_dir=db_dir,
            department_dns={"OU=ISED-ISDE,O=GC,C=CA"},
            rate_limit_seconds=0.001,
            stop_file=None,
            quiet=True,
            max_depth=1,
        )
        engine = CrawlEngine(config)
        
        # Patch _log_progress to raise an exception ONLY when event == "done" (main loop)
        original_log = engine._log_progress
        def fake_log(store, request_count, event, org_path, depth):
            if event == "done":
                raise Exception("UI logger broke")
            return original_log(store, request_count, event, org_path, depth)
            
        with patch.object(engine, "_log_progress", side_effect=fake_log):
            result = engine.run()

        assert result.status == "finished"
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM people_index").fetchone()[0]
        assert count == 5
        conn.close()
