from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from .canonical_resolver import CanonicalValidationError
from .canonicalizer import publish_canonical
from .career_index import build_career_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish and serve GEDS Career Atlas data")
    subparsers = parser.add_subparsers(dest="command", required=True)
    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("--control-db", type=Path, required=True)
    publish_parser.add_argument("--run-id", required=True)
    publish_parser.add_argument("--master-db", type=Path, required=True)
    publish_parser.add_argument("--as-of", required=True)
    index_parser = subparsers.add_parser("index")
    index_parser.add_argument("--master-db", type=Path, required=True)
    index_parser.add_argument("--taxonomy", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "publish":
        try:
            result = publish_canonical(
                args.control_db,
                args.run_id,
                args.master_db,
                args.as_of,
            )
        except (CanonicalValidationError, FileNotFoundError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(
            json.dumps(
                {
                    "snapshot_id": result.snapshot.snapshot_id,
                    "as_of_at": result.snapshot.as_of_at,
                    "people_count": result.snapshot.people_count,
                    "org_units_count": result.snapshot.org_units_count,
                    "departments_count": result.snapshot.departments_count,
                    "quality_status": result.snapshot.quality_status,
                    "fallback_org_count": result.snapshot.fallback_org_count,
                    "root_count": result.snapshot.root_count,
                    "missing_parent_count": result.snapshot.missing_parent_count,
                    "cycle_count": result.snapshot.cycle_count,
                    "max_depth": result.snapshot.max_depth,
                    "warnings": result.snapshot.quality_warnings,
                    "event_counts": result.event_counts,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "index":
        try:
            report = build_career_index(args.master_db, args.taxonomy)
        except (FileNotFoundError, ValueError, sqlite3.Error) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(report.__dict__, ensure_ascii=False, sort_keys=True))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
