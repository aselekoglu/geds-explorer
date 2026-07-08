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
