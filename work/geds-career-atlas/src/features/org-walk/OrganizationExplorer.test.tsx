import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { OrganizationExplorer } from "./OrganizationExplorer"

it("loads the canonical root organizations from the public API", async () => {
  const client = { rootChildren: async () => ({ items: [{ org_id: "root-1", name: "Digital Services", depth: 0, child_count: 2, descendant_people_count: 12 }], snapshot_id: "snapshot", etag: "etag" }), children: async () => ({ items: [], snapshot_id: "snapshot", etag: "etag" }) }
  render(<OrganizationExplorer client={client} />)
  expect(await screen.findByRole("treeitem", { name: /Digital Services/i })).toBeInTheDocument()
})

it("opens a selected organization in the next hierarchy column", async () => {
  const client = { rootChildren: async () => ({ items: [{ org_id: "root-1", name: "Digital Services", depth: 0, child_count: 1, descendant_people_count: 12 }], snapshot_id: "snapshot", etag: "etag" }), children: async () => ({ items: [{ org_id: "team-1", name: "AI Centre", parent_id: "root-1", depth: 1, child_count: 0, descendant_people_count: 4 }], snapshot_id: "snapshot", etag: "etag" }) }
  render(<OrganizationExplorer client={client} />)
  fireEvent.click(await screen.findByRole("treeitem", { name: /Digital Services/i }))
  fireEvent.click(await screen.findByRole("treeitem", { name: /AI Centre/i }))
  expect(await screen.findByText("Digital Services / AI Centre")).toBeInTheDocument()
})
