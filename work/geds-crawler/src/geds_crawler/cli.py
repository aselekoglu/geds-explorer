from __future__ import annotations

import argparse
import socket
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .config import CrawlConfig, DEPARTMENT_LIST_URL, DEFAULT_DEPARTMENTS
from .exporter import export_jsonl, write_report
from .fetcher import PoliteFetcher
from .models import OrgUnit
from .parser import extract_departments, extract_org_children, extract_people
from .progress import format_progress_line, format_status, read_snapshot_status
from .store import SnapshotStore
from .ui_server import create_server
from .urls import geds_url
from .engine import CrawlEngine, CrawlRunConfig



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a privacy-preserving GEDS snapshot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl_parser = subparsers.add_parser("crawl")
    crawl_parser.add_argument("--output-dir", type=Path, default=None)
    crawl_parser.add_argument("--rate-limit", type=float, default=1.0)
    crawl_parser.add_argument("--max-depth", type=int, default=None)
    crawl_parser.add_argument("--departments", nargs="*", default=None)
    crawl_parser.add_argument("--quiet", action="store_true")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--db", type=Path, required=True)

    ui_parser = subparsers.add_parser("ui")
    ui_parser.add_argument("--db", type=Path, required=True)
    ui_parser.add_argument("--host", default="0.0.0.0")
    ui_parser.add_argument("--port", type=int, default=8765)

    args = parser.parse_args(argv)
    if args.command == "crawl":
        output_dir = args.output_dir or Path("outputs") / f"geds-snapshot-{datetime.now(UTC).date().isoformat()}"
        departments = set(args.departments) if args.departments else set(DEFAULT_DEPARTMENTS)
        run_crawl(
            output_dir=output_dir,
            rate_limit=args.rate_limit,
            max_depth=args.max_depth,
            departments=departments,
            quiet=args.quiet,
        )
        return 0
    if args.command == "status":
        try:
            print(format_status(read_snapshot_status(args.db)))
            return 0
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if args.command == "ui":
        try:
            server = create_server(args.db, args.host, args.port)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        actual_port = int(server.server_address[1])
        print("GEDS Snapshot Monitor is available at:", flush=True)
        for url in _server_urls(args.host, actual_port):
            print(f"  {url}", flush=True)
        print("Press Ctrl+C to stop.", flush=True)
        last_interrupt = 0
        while True:
            try:
                server.serve_forever()
                break
            except KeyboardInterrupt:
                now = time.time()
                if now - last_interrupt < 1.5:
                    print("\nStopping UI.", flush=True)
                    break
                else:
                    print("\n[UI Server] Press Ctrl+C again within 1.5 seconds to stop.", flush=True)
                    last_interrupt = now
        server.server_close()
        return 0
    return 1


DEFAULT_DEPARTMENT_DNS = {
    "Shared Services Canada": "OU=SSC-SPC,O=GC,C=CA",
    "Treasury Board of Canada Secretariat": "OU=TBS-SCT,O=GC,C=CA",
    "Innovation Science and Economic Development Canada": "OU=ISED-ISDE,O=GC,C=CA",
    "Employment and Social Development Canada": "OU=ESDC-EDSC,O=GC,C=CA",
    "Canada Revenue Agency": "OU=CRA-ARC,O=GC,C=CA",
    "Public Services and Procurement Canada": "OU=PSPC-SPAC,O=GC,C=CA",
    "Statistics Canada": "OU=STATCAN-STATCAN,O=GC,C=CA",
    "National Research Council Canada": "OU=NRC-CNRC,O=GC,C=CA",
    "Natural Resources Canada": "OU=NRCAN-RNCAN,O=GC,C=CA",
    "National Defence": "OU=DND-MDN,O=GC,C=CA",
}


def run_crawl(output_dir: Path, rate_limit: float, max_depth: int | None, departments: set[str], quiet: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    
    fetcher = PoliteFetcher(rate_limit_seconds=rate_limit)
    html = fetcher.fetch_text(DEPARTMENT_LIST_URL)
    all_depts = extract_departments(html, allowed_names=None)
    
    allowed_dns = set()
    input_normalized = {d.casefold() for d in departments}
    
    for dept_input in departments:
        if dept_input in DEFAULT_DEPARTMENT_DNS:
            allowed_dns.add(DEFAULT_DEPARTMENT_DNS[dept_input])
        else:
            matched = False
            for dept in all_depts:
                if dept.name.casefold() == dept_input.casefold() or dept.dn.casefold() == dept_input.casefold():
                    allowed_dns.add(dept.dn)
                    matched = True
            if not matched and ("=" in dept_input and "," in dept_input):
                allowed_dns.add(dept_input)
                
    run_id = str(uuid.uuid4())
    config = CrawlRunConfig(
        run_id=run_id,
        output_dir=output_dir,
        department_dns=allowed_dns,
        rate_limit_seconds=rate_limit,
        stop_file=None,
        quiet=quiet,
        max_depth=max_depth,
    )
    
    engine = CrawlEngine(config)
    engine.run()



def _log_progress(
    store: SnapshotStore,
    run_id: str,
    request_count: int,
    event: str,
    org_path: str,
    depth: int,
    quiet: bool,
) -> None:
    if quiet:
        return
    queue = store.queue_counts()
    print(
        format_progress_line(
            event=event,
            org_path=org_path,
            depth=depth,
            request_count=request_count,
            org_count=store.count_rows("org_units"),
            people_count=store.count_rows("people_index"),
            queue_done=queue.get("done", 0),
            queue_pending=queue.get("pending", 0),
            error_count=store.count_rows("crawl_errors"),
        ),
        flush=True,
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _server_urls(host: str, port: int) -> list[str]:
    if host not in {"0.0.0.0", "::"}:
        return [f"http://{host}:{port}"]
    addresses = {"127.0.0.1"}
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET):
            address = info[4][0]
            if address and not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass
    return [f"http://{address}:{port}" for address in sorted(addresses)]


if __name__ == "__main__":
    raise SystemExit(main())
