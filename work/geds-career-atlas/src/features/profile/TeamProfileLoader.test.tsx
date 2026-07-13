import { render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { TeamProfileLoader } from "./TeamProfileLoader"

it("loads a profile and observed titles from the public API", async () => {
  const client = { profile: async () => ({ org_id:"ai",name:"AI Centre",department_name:"Digital Services",canonical_path:["Digital Services","AI Centre"],direct_people_count:4,descendant_people_count:9,child_count:2,snapshot_id:"snapshot" }), roles: async () => ({ items:[{entity_id:"person",entity_kind:"person",title:"Data Scientist",organization_name:"AI Centre",score:0,confidence:"none",evidence:[]}],snapshot_id:"snapshot",etag:"etag" }) }
  render(<TeamProfileLoader orgId="ai" client={client} />)
  expect(await screen.findByRole("heading", { name: "AI Centre" })).toBeVisible()
  expect(screen.getByRole("button",{name:/Filter by Data Scientist/i})).toBeVisible()
})
