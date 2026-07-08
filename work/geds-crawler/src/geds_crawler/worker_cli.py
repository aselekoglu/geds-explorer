from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import CrawlEngine, CrawlRunConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GEDS Crawler Managed Worker Subprocess")
    parser.add_argument("--run-id", required=True, help="Unique identifier for the crawl run")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory to save run outputs")
    parser.add_argument("--department-dns", nargs="+", required=True, help="Canonical department DNs to crawl")
    parser.add_argument("--rate-limit", type=float, default=1.0, help="Polite rate limit in seconds per request")
    parser.add_argument("--stop-file", type=Path, required=True, help="File to check for cooperative stop signal")
    parser.add_argument("--max-depth", type=int, default=None, help="Maximum search depth for BFS crawl")

    args = parser.parse_args(argv)

    config = CrawlRunConfig(
        run_id=args.run_id,
        output_dir=args.output_dir,
        department_dns=set(args.department_dns),
        rate_limit_seconds=args.rate_limit,
        stop_file=args.stop_file,
        quiet=False,
        max_depth=args.max_depth,
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
