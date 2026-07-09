from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import CrawlEngine, CrawlRunConfig


from .pagination import MAX_PAGES_PER_ORG


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="GEDS Crawler Managed Worker Subprocess")
    parser.add_argument("--run-id", required=True, help="Unique identifier for the crawl run")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory to save run outputs")
    parser.add_argument("--department-dns", nargs="+", required=False, help="Canonical department DNs to crawl")
    parser.add_argument("--rate-limit", type=float, default=1.0, help="Polite rate limit in seconds per request")
    parser.add_argument("--stop-file", type=Path, required=True, help="File to check for cooperative stop signal")
    parser.add_argument("--max-depth", type=int, default=None, help="Maximum search depth for BFS crawl")
    parser.add_argument("--crawl-kind", default="full", choices=["full", "pagination_backfill"], help="Kind of crawl")
    parser.add_argument("--control-db", type=Path, default=None, help="Control database path")
    parser.add_argument("--max-pages-per-org", type=int, default=MAX_PAGES_PER_ORG, help="Maximum pages to crawl per org")

    args = parser.parse_args(argv)

    if args.crawl_kind == "full" and not args.department_dns:
        parser.error("--department-dns is required when --crawl-kind is 'full'")

    config = CrawlRunConfig(
        run_id=args.run_id,
        output_dir=args.output_dir,
        department_dns=set(args.department_dns) if args.department_dns else set(),
        rate_limit_seconds=args.rate_limit,
        stop_file=args.stop_file,
        quiet=False,
        max_depth=args.max_depth,
        crawl_kind=args.crawl_kind,
        control_db_path=args.control_db,
        max_pages_per_org=args.max_pages_per_org,
    )

    engine = CrawlEngine(config)
    result = engine.run()
    
    if result.status == "finished":
        return 0
    elif result.status == "stopped":
        return 3
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
