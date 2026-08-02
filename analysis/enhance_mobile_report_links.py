#!/usr/bin/env python3
"""Add accessible official-GEDS row navigation to the standalone report output."""

from __future__ import annotations

from pathlib import Path


REPORT_PATH = Path(__file__).resolve().parent / "mobile-report" / "report.html"
MARKER = "<!-- geds-record-row-links -->"

ENHANCEMENT = r'''
<!-- geds-record-row-links -->
<style id="geds-record-row-links-style">
  tr[data-geds-record-url] { cursor: pointer; }
  tr[data-geds-record-url]:focus-visible { outline: 2px solid #0285ff; outline-offset: -2px; }
  .geds-record-link { color: inherit; font-weight: 500; text-decoration: underline; text-underline-offset: 0.18em; }
</style>
<script id="geds-record-row-links-script">
(() => {
  const expectedHeaders = ["Name", "Department", "Title", "GEDS URL"];
  const isOfficialGedsUrl = (value) => {
    try {
      const url = new URL(value);
      return url.protocol === "https:" && url.hostname === "geds-sage.gc.ca";
    } catch {
      return false;
    }
  };
  const findRecordsTable = () => Array.from(document.querySelectorAll("#data-analytics-portable-reader table")).find((table) => {
    const headers = Array.from(table.querySelectorAll("thead th"), (cell) => cell.textContent.trim());
    return headers.length === expectedHeaders.length && headers.every((header, index) => header === expectedHeaders[index]);
  });
  const enhance = () => {
    const table = findRecordsTable();
    if (!table) return false;
    for (const row of table.querySelectorAll("tbody tr")) {
      if (row.dataset.gedsRecordUrl) continue;
      const cells = row.querySelectorAll("td");
      const url = cells[3]?.textContent?.trim();
      const name = cells[0]?.textContent?.trim() || "this GEDS record";
      if (!isOfficialGedsUrl(url)) continue;
      row.dataset.gedsRecordUrl = url;
      row.tabIndex = 0;
      row.setAttribute("role", "link");
      row.setAttribute("aria-label", `Open official GEDS record for ${name}`);
      row.title = `Open official GEDS record for ${name}`;
      const link = document.createElement("a");
      link.className = "geds-record-link";
      link.href = url;
      link.textContent = "Open official record";
      link.setAttribute("aria-label", `Open official GEDS record for ${name}`);
      cells[3].replaceChildren(link);
      row.addEventListener("click", (event) => {
        if (event.target.closest("a, button, input, select, textarea")) return;
        window.location.assign(url);
      });
      row.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        window.location.assign(url);
      });
    }
    return true;
  };
  if (enhance()) return;
  const observer = new MutationObserver(() => {
    if (enhance()) observer.disconnect();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
</script>
'''


def main() -> None:
    content = REPORT_PATH.read_text(encoding="utf-8")
    if MARKER in content:
        start = content.index(MARKER)
        end = content.index("</script>", start) + len("</script>")
        content = content[:start] + content[end:]
    REPORT_PATH.write_text(content.replace("</body>", f"{ENHANCEMENT}</body>"), encoding="utf-8")
    print(f"enhanced={REPORT_PATH}")


if __name__ == "__main__":
    main()
