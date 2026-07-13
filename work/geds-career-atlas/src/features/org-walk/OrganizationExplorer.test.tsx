import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { OrganizationExplorer } from "./OrganizationExplorer"

it("loads the canonical root organizations from the public API", async () => {
  const client = { rootChildren: async () => ({ items: [{ org_id: "root-1", name: "Digital Services", depth: 0, child_count: 2, direct_people_count: 2, descendant_people_count: 12 }], snapshot_id: "snapshot", etag: "etag" }), children: async () => ({ items: [], snapshot_id: "snapshot", etag: "etag" }) }
  render(<OrganizationExplorer client={client} />)
  expect(await screen.findByRole("treeitem", { name: /Digital Services/i })).toBeInTheDocument()
})

it("starts inside the selected institution root",async()=>{
  const rootOrg={org_id:"department-a",name:"Department A",depth:0,child_count:1,direct_people_count:0,descendant_people_count:10}
  const children=vi.fn().mockResolvedValue({items:[{org_id:"team",name:"Team",parent_id:"department-a",depth:1,child_count:0,direct_people_count:2,descendant_people_count:2}],snapshot_id:"snapshot",etag:"etag"})
  render(<OrganizationExplorer client={{rootChildren:vi.fn(),children}} rootOrg={rootOrg}/>)
  expect(await screen.findByRole("treeitem",{name:/Team/i})).toBeVisible()
  expect(children).toHaveBeenCalledWith("department-a",expect.any(AbortSignal))
})

it("opens a selected organization in the next hierarchy column", async () => {
  const client = { rootChildren: async () => ({ items: [{ org_id: "root-1", name: "Digital Services", depth: 0, child_count: 1, direct_people_count: 2, descendant_people_count: 12 }], snapshot_id: "snapshot", etag: "etag" }), children: async () => ({ items: [{ org_id: "team-1", name: "AI Centre", parent_id: "root-1", depth: 1, child_count: 0, direct_people_count: 4, descendant_people_count: 4 }], snapshot_id: "snapshot", etag: "etag" }) }
  render(<OrganizationExplorer client={client} />)
  fireEvent.click(await screen.findByRole("treeitem", { name: /Digital Services/i }))
  fireEvent.click(await screen.findByRole("treeitem", { name: /AI Centre/i }))
  expect(await screen.findByText("Digital Services / AI Centre")).toBeInTheDocument()
  expect(screen.getByText("No child teams")).toBeInTheDocument()
})

it("opens Team Profile only from the compact detail action",async()=>{
  const onProfile=vi.fn()
  const children=vi.fn().mockResolvedValue({items:[],snapshot_id:"snapshot",etag:"etag"})
  const client={rootChildren:async()=>({items:[{org_id:"root-1",name:"Digital Services",depth:0,child_count:1,direct_people_count:2,descendant_people_count:12}],snapshot_id:"snapshot",etag:"etag"}),children}
  render(<OrganizationExplorer client={client} onProfile={onProfile}/>)
  fireEvent.click(await screen.findByRole("treeitem",{name:/Digital Services/i}))
  expect(onProfile).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button",{name:"Open Digital Services profile"}))
  expect(onProfile).toHaveBeenCalledWith("root-1")
  expect(children).toHaveBeenCalledTimes(1)
})

it("restores a deep shared path from selected URL state",async()=>{
  const root={org_id:"root-1",name:"Department",depth:0,child_count:1,direct_people_count:2,descendant_people_count:20}
  const branch={org_id:"branch-1",name:"Branch",parent_id:"root-1",depth:1,child_count:1,direct_people_count:3,descendant_people_count:10}
  const team={org_id:"team-1",name:"Team",parent_id:"branch-1",depth:2,child_count:0,direct_people_count:4,descendant_people_count:4}
  const client={
    rootChildren:async()=>({items:[root],snapshot_id:"snapshot",etag:"etag"}),
    ancestors:async()=>({items:[root,branch,team],snapshot_id:"snapshot",etag:"etag"}),
    children:async(id:string)=>({items:id==="root-1"?[branch]:id==="branch-1"?[team]:[],snapshot_id:"snapshot",etag:"etag"}),
  }
  render(<OrganizationExplorer client={client} selectedOrgId="team-1"/>)
  expect(await screen.findByLabelText("Selected organization path")).toHaveTextContent("Department / Branch / Team")
})
