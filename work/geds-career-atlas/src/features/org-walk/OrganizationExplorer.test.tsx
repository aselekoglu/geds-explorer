import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { OrganizationExplorer } from "./OrganizationExplorer"

it("loads the canonical root organizations from the public API", async () => {
  const client = { rootChildren: async () => ({ items: [{ org_id: "root-1", name: "Digital Services", depth: 0, child_count: 2, direct_people_count: 2, descendant_people_count: 12 }], snapshot_id: "snapshot", etag: "etag" }), children: async () => ({ items: [], snapshot_id: "snapshot", etag: "etag" }) }
  render(<OrganizationExplorer client={client} />)
  expect(await screen.findByRole("button", { name: /^Digital Services\./i })).toBeInTheDocument()
})

it("starts inside the selected institution root",async()=>{
  const rootOrg={org_id:"department-a",name:"Department A",depth:0,child_count:1,direct_people_count:0,descendant_people_count:10}
  const children=vi.fn().mockResolvedValue({items:[{org_id:"team",name:"Team",parent_id:"department-a",depth:1,child_count:0,direct_people_count:2,descendant_people_count:2}],snapshot_id:"snapshot",etag:"etag"})
  render(<OrganizationExplorer client={{rootChildren:vi.fn(),children}} rootOrg={rootOrg}/>)
  expect(await screen.findByRole("button",{name:/^Team\./i})).toBeVisible()
  expect(children).toHaveBeenCalledWith("department-a",expect.any(AbortSignal))
})

it("opens a selected organization in the next hierarchy column", async () => {
  const client = { rootChildren: async () => ({ items: [{ org_id: "root-1", name: "Digital Services", depth: 0, child_count: 1, direct_people_count: 2, descendant_people_count: 12 }], snapshot_id: "snapshot", etag: "etag" }), children: async () => ({ items: [{ org_id: "team-1", name: "AI Centre", parent_id: "root-1", depth: 1, child_count: 0, direct_people_count: 4, descendant_people_count: 4 }], snapshot_id: "snapshot", etag: "etag" }), people: async () => ({items:[{person_id:"p1",display_name:"Maya Chen",observed_title:"Data Scientist",observed_classifications:[],org_id:"team-1",organization_name:"AI Centre",snapshot_id:"snapshot",snapshot_as_of:"2026-07-09",source_url:"https://geds.example/p1"}],total:1,limit:200,offset:0,available_classifications:[],snapshot_id:"snapshot",quality_status:"complete",etag:"etag"}) }
  render(<OrganizationExplorer client={client} />)
  fireEvent.click(await screen.findByRole("button", { name: /^Digital Services\./i }))
  const leaf=await screen.findByRole("button", { name: /^AI Centre\./i })
  fireEvent.click(leaf)
  expect(leaf).toHaveAttribute("aria-current","true")
  expect(await screen.findByText("Digital Services / AI Centre")).toBeInTheDocument()
  expect(await screen.findByText("Maya Chen")).toBeInTheDocument()
  expect(screen.queryByText("No child teams")).not.toBeInTheDocument()
})

it("opens Team Profile only from the compact detail action",async()=>{
  const onProfile=vi.fn()
  const children=vi.fn().mockResolvedValue({items:[],snapshot_id:"snapshot",etag:"etag"})
  const client={rootChildren:async()=>({items:[{org_id:"root-1",name:"Digital Services",depth:0,child_count:1,direct_people_count:2,descendant_people_count:12}],snapshot_id:"snapshot",etag:"etag"}),children}
  render(<OrganizationExplorer client={client} onProfile={onProfile}/>)
  fireEvent.click(await screen.findByRole("button",{name:/^Digital Services\./i}))
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

it("shows institution-scoped deduplicated matching teams and restores a result path",async()=>{
  const root={org_id:"department-a",name:"Department A",depth:0,child_count:1,direct_people_count:0,descendant_people_count:20}
  const branch={org_id:"branch",name:"Digital Branch",parent_id:"department-a",depth:1,child_count:1,direct_people_count:2,descendant_people_count:10}
  const team={org_id:"team",name:"AI Team",parent_id:"branch",depth:2,child_count:0,direct_people_count:4,descendant_people_count:4}
  const onProfile=vi.fn()
  const search=vi.fn().mockResolvedValue({items:[
    {entity_id:"p1",entity_kind:"person",org_id:"team",title:"Data Scientist",organization_name:"AI Team",department_name:"Department A",score:100,confidence:"high",evidence:[]},
    {entity_id:"p2",entity_kind:"person",org_id:"team",title:"Analyst",organization_name:"AI Team",department_name:"Department A",score:90,confidence:"high",evidence:[]},
    {entity_id:"p3",entity_kind:"person",org_id:"other",title:"Data Scientist",organization_name:"Other Team",department_name:"Department B",score:110,confidence:"high",evidence:[]},
  ],snapshot_id:"snapshot",etag:"etag"})
  const client={search,rootChildren:async()=>({items:[root],snapshot_id:"snapshot",etag:"etag"}),ancestors:async()=>({items:[root,branch,team],snapshot_id:"snapshot",etag:"etag"}),children:async(id:string)=>({items:id==="department-a"?[branch]:id==="branch"?[team]:[],snapshot_id:"snapshot",etag:"etag"})}
  render(<OrganizationExplorer client={client} rootOrg={root} query="Data Scientist" institutionName="Department A" onProfile={onProfile}/>)
  const result=await screen.findByRole("button",{name:/Open AI Team in hierarchy/i})
  expect(screen.getByRole("heading",{name:"Teams matching “Data Scientist”"})).toBeVisible()
  expect(screen.getAllByText("AI Team")).toHaveLength(1)
  expect(screen.queryByText("Other Team")).not.toBeInTheDocument()
  const matchCard=result.closest("article")
  fireEvent.click(matchCard!.querySelector<HTMLButtonElement>(".org-match__profile")!)
  expect(onProfile).toHaveBeenCalledWith("team")
  onProfile.mockClear()
  fireEvent.click(result)
  expect(await screen.findByLabelText("Selected organization path")).toHaveTextContent("Department A / Digital Branch / AI Team")
  expect(onProfile).not.toHaveBeenCalled()
})
