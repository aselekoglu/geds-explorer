from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import sqlite3

from geds_crawler.engine import CrawlEngine, CrawlRunConfig, CrawlResult


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def mock_fetcher():
    with patch("geds_crawler.engine.PoliteFetcher") as mock:
        fetcher_instance = MagicMock()
        fetcher_instance.stats = MagicMock(request_count=0)
        
        def fake_fetch_text(url: str) -> str:
            fetcher_instance.stats.request_count += 1
            if "pgid=012" in url:
                return load_fixture("department_list.html")
            elif "pgid=014" in url:
                return load_fixture("org_page.html")
            return ""
            
        fetcher_instance.fetch_text.side_map = {}
        fetcher_instance.fetch_text.side_effect = fake_fetch_text
        mock.return_value = fetcher_instance
        yield fetcher_instance


def test_engine_basic_crawl(tmp_path, mock_fetcher):
    db_dir = tmp_path / "run_test"
    db_path = db_dir / "geds.sqlite"
    
    # We want to crawl only ISED, which is in the department list
    config = CrawlRunConfig(
        run_id="test-run-123",
        output_dir=db_dir,
        department_dns={"OU=ISED-ISDE,O=GC,C=CA"},
        rate_limit_seconds=0.01,
        stop_file=None,
        quiet=True,
        max_depth=1,
    )
    
    engine = CrawlEngine(config)
    result = engine.run()
    
    assert isinstance(result, CrawlResult)
    assert result.run_id == "test-run-123"
    assert result.status == "finished"
    assert result.request_count > 0
    
    # Connect and verify database contents
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Assert ISED was inserted into departments
    dept = conn.execute("SELECT * FROM departments").fetchone()
    assert dept is not None
    assert dept["dn"] == "OU=ISED-ISDE,O=GC,C=CA"
    assert dept["name"] == "Innovation Science and Economic Development Canada"
    
    # Assert org units and people were parsed and saved
    orgs = conn.execute("SELECT * FROM org_units ORDER BY depth").fetchall()
    assert len(orgs) > 0
    
    people = conn.execute("SELECT * FROM people_index").fetchall()
    assert len(people) > 0
    
    # Assert privacy: no contact fields
    columns = [r[1] for r in conn.execute("PRAGMA table_info(people_index)")]
    assert "phone" not in columns
    assert "email" not in columns
    
    conn.close()
