import { render, screen } from "@testing-library/react"
import { CareerConversationLeads } from "./CareerConversationLeads"

const leads = [{
  kind: "possible_team_lead" as const,
  confidence: "high",
  title: "Manager, Data Platforms",
  org_id: "team",
  source_url: "https://geds.example/manager",
  reasons: ["Observed leadership title", "Same organization as this team"],
}]

const vacancies = [{
  marker: "VACANT, VACANT",
  title: "Data Scientist",
  org_id: "team",
  observed_at: "2026-07-09",
  source_url: "https://geds.example/vacant",
  confidence: "high",
  reasons: ["placeholder_marker:vacant"],
  live_competition_verified: false as const,
}]

it("presents title-based leads as non-hiring conversation suggestions", () => {
  render(<CareerConversationLeads leads={leads} vacancies={[]} snapshotAsOf="2026-07-09T00:00:00+00:00" />)

  expect(screen.getByRole("heading", { name: "Career conversation leads" })).toBeVisible()
  expect(screen.getByText(/Possible team lead/)).toBeVisible()
  expect(screen.getByText("Manager, Data Platforms")).toBeVisible()
  expect(screen.getByText(/does not verify that they are hiring/i)).toBeVisible()
  expect(screen.getByText(/observed leadership title/i)).toBeVisible()
  expect(screen.getByText(/snapshot: july 9, 2026/i)).toBeVisible()
  expect(screen.getByRole("link", { name: "Open official GEDS record" })).toHaveAttribute("href", "https://geds.example/manager")
  expect(screen.queryByText(/hiring manager/i)).not.toBeInTheDocument()
  expect(screen.queryByRole("button", { name: /apply/i })).not.toBeInTheDocument()
})

it("presents vacancy markers only as unverified signals", () => {
  render(<CareerConversationLeads leads={[]} vacancies={vacancies} snapshotAsOf="2026-07-09T00:00:00+00:00" />)

  expect(screen.getByRole("heading", { name: "Unverified vacancy signals" })).toBeVisible()
  expect(screen.getByText("VACANT, VACANT")).toBeVisible()
  expect(screen.getByText("Data Scientist")).toBeVisible()
  expect(screen.getByText("No live competition verified.")).toBeVisible()
  expect(screen.getByText(/observed july 9, 2026/i)).toBeVisible()
  expect(screen.getByRole("link", { name: "Open vacancy source in GEDS" })).toHaveAttribute("href", "https://geds.example/vacant")
  expect(screen.queryByRole("button", { name: /apply/i })).not.toBeInTheDocument()
})
