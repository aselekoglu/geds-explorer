import { render, screen } from "@testing-library/react"
import { LanguageProvider } from "../../i18n/i18n"
import { DataMethodology } from "./DataMethodology"

const meta = {
  snapshot_id: "snapshot-123",
  taxonomy_version: "1.0.0",
  quality_status: "partial_overlay",
  as_of_at: "2026-07-09T00:00:00Z",
  people_count: 193163,
  org_units_count: 26421,
  departments_count: 156,
}

it("explains source lineage, deterministic matching, privacy, and limitations", () => {
  history.replaceState(null, "", "/?lang=en")
  render(<LanguageProvider><DataMethodology meta={meta} /></LanguageProvider>)

  expect(screen.getByRole("heading", { name: "About the data" })).toBeVisible()
  expect(screen.getByText(/July 9, 2026/)).toBeVisible()
  expect(screen.getByText(/partial overlay/i)).toBeVisible()
  expect(screen.getByText(/taxonomy version 1.0.0/i)).toBeVisible()
  expect(screen.getByText(/deterministic/i)).toBeVisible()
  expect(screen.getByText(/weights/i)).toBeVisible()
  expect(screen.getByText(/no protected traits are inferred/i)).toBeVisible()
  expect(screen.getByText(/vacancy markers are unverified/i)).toBeVisible()
  expect(screen.getByText(/leadership titles/i)).toBeVisible()
  expect(screen.getByText(/known limitations/i)).toBeVisible()
  expect(screen.getByRole("link", { name: "Open official GEDS" })).toHaveAttribute("href", expect.stringContaining("geds-sage.gc.ca"))
})

it("renders the methodology in French", () => {
  history.replaceState(null, "", "/?lang=fr")
  render(<LanguageProvider><DataMethodology meta={meta} /></LanguageProvider>)

  expect(screen.getByRole("heading", { name: "À propos des données" })).toBeVisible()
  expect(screen.getByText(/9 juillet 2026/i)).toBeVisible()
  expect(screen.getByText(/aucun trait protégé/i)).toBeVisible()
})
