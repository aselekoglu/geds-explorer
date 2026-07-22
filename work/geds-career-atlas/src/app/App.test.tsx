import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { vi } from "vitest"
import { App } from "./App"
it("renders public navigation and theme control without private operator actions", () => {
  render(<App />)
  expect(screen.getByRole("link", { name: /discover/i })).toBeVisible()
  expect(screen.getByRole("link", { name: /organization walk/i })).toBeVisible()
  expect(screen.queryByRole("link", { name: /constellation/i })).not.toBeInTheDocument()
  expect(screen.queryByRole("link", { name: /tours/i })).not.toBeInTheDocument()
  expect(screen.getByRole("button",{name:/Theme: (Dark|Light)/})).toBeVisible()
  expect(screen.queryByText(/private admin/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/start crawler|run history|schedules|snapshot data/i)).not.toBeInTheDocument()
})

it("does not reserve an empty profile column",()=>{
  history.replaceState(null,"","/#discover")
  const {container}=render(<App/>)
  expect(container.querySelector(".detail-panel")).not.toBeInTheDocument()
})

it("clears a stale team profile when institution changes",async()=>{
  history.replaceState(null,"","/?focus=old-team&department=Department%20A#discover")
  vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>{
    const url=String(input)
    const body=url.includes("/departments")?{items:[{department_id:"a",name:"Department A"},{department_id:"b",name:"Department B"}]}:url.includes("/meta")?{quality_status:"complete"}:url.includes("/constellation/slice")?{nodes:[{org_id:"team",name:"Team",depth:1,child_count:0,direct_people_count:2,descendant_people_count:2}],limit:2000,truncated:false,snapshot_id:"s",etag:"e"}:url.includes("/profile")?{org_id:"old-team",name:"Old Team",department_name:"Department A",canonical_path:["Department A","Old Team"],direct_people_count:1,descendant_people_count:1,child_count:0,snapshot_id:"s"}:url.includes("/roles")?{items:[],snapshot_id:"s",etag:"e"}:url.includes("/people")?{items:[],total:0,limit:50,offset:0,available_classifications:[],snapshot_id:"s",quality_status:"complete",etag:"e"}:{items:[],snapshot_id:"s",etag:"e"}
    return {ok:true,json:async()=>body} as Response
  }))
  render(<App/>)
  fireEvent.change(await screen.findByLabelText("Institution"),{target:{value:"Department B"}})
  await waitFor(()=>expect(new URLSearchParams(location.search).has("focus")).toBe(false))
  expect(screen.queryByLabelText("TEAM PROFILE")).not.toBeInTheDocument()
  vi.unstubAllGlobals()
})

it("marks a selected team profile as an open responsive sheet",()=>{
  history.replaceState(null,"","/?focus=leaf-team")
  vi.stubGlobal("fetch",vi.fn(()=>new Promise(()=>undefined)))
  const {container}=render(<App/>)

  expect(container.querySelector(".detail-panel")).toHaveClass("detail-panel--open")
})

it.each(["discover","explorer"])("applies an observed role query without leaving the %s view",async(view)=>{
  history.replaceState(null,"",`/?focus=team#${view}`)
  vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>{
    const url=String(input)
    const body=url.includes("/departments")?{items:[]}:url.includes("/meta")?{quality_status:"complete"}:url.includes("/constellation/slice")?{nodes:[],limit:2000,truncated:false,snapshot_id:"s",etag:"e"}:url.includes("/profile")?{org_id:"team",name:"Policy Team",department_name:"Department",canonical_path:["Department","Policy Team"],direct_people_count:1,descendant_people_count:1,child_count:0,snapshot_id:"s"}:url.includes("/roles")?{items:[{entity_id:"p",entity_kind:"person",org_id:"team",title:"Senior Advisor",organization_name:"Policy Team",score:1,confidence:"high",evidence:[]}],snapshot_id:"s",etag:"e"}:url.includes("/people")?{items:[],total:0,limit:50,offset:0,available_classifications:[],snapshot_id:"s",quality_status:"complete",etag:"e"}:{items:[],snapshot_id:"s",etag:"e"}
    return {ok:true,json:async()=>body} as Response
  }))
  render(<App/>)
  fireEvent.click(await screen.findByRole("button",{name:/Filter by Senior Advisor/i}))
  await waitFor(()=>expect(location.hash).toBe(`#${view}`))
  expect(new URLSearchParams(location.search).get("q")).toBe("Senior Advisor")
  expect(new URLSearchParams(location.search).has("focus")).toBe(false)
  expect(screen.queryByLabelText("TEAM PROFILE")).not.toBeInTheDocument()
  vi.unstubAllGlobals()
})
