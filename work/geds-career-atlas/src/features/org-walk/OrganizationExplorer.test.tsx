import { render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { OrganizationExplorer } from "./OrganizationExplorer"

it("loads the canonical root organizations from the public API", async () => {
  const client = { rootChildren: async () => ({ items: [{ org_id: "root-1", name: "Digital Services", depth: 0, child_count: 2, descendant_people_count: 12 }], snapshot_id: "snapshot", etag: "etag" }) }
  render(<OrganizationExplorer client={client} />)
  expect(await screen.findByRole("treeitem", { name: /Digital Services/i })).toBeInTheDocument()
})
