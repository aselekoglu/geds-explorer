import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { ConstellationPage } from "./ConstellationPage"

const rootNode={org_id:"statcan",name:"Statistics Canada",depth:0,child_count:1,direct_people_count:200,descendant_people_count:2400}
const leafNode={org_id:"ai-team",name:"AI Team",parent_id:"statcan",depth:1,child_count:0,direct_people_count:12,descendant_people_count:12}
const page=(nodes:typeof rootNode[])=>({nodes,limit:2000,truncated:false,snapshot_id:"snapshot",etag:"etag"})

it("opens facts on one click and drills into a bubble on double click",async()=>{
  const onProfile=vi.fn()
  const constellationSlice=vi.fn(async(rootId?:string)=>rootId==="statcan"?page([leafNode as typeof rootNode]):page([rootNode]))
  render(<ConstellationPage client={{constellationSlice}} onProfile={onProfile}/>)
  const node=await screen.findByRole("option",{name:/Statistics Canada/i})
  fireEvent.click(node)
  expect(await screen.findByText("People in this team")).toBeVisible()
  expect(constellationSlice).toHaveBeenCalledTimes(1)
  fireEvent.doubleClick(node)
  await waitFor(()=>expect(constellationSlice).toHaveBeenLastCalledWith("statcan",expect.any(AbortSignal)))
  expect(onProfile).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button",{name:"Back"}))
  await waitFor(()=>expect(screen.getByRole("option",{name:/Statistics Canada/i})).toBeVisible())
  expect(screen.queryByRole("button",{name:"Back"})).not.toBeInTheDocument()
})

it("opens a leaf's details without requesting an empty slice",async()=>{
  const constellationSlice=vi.fn(async()=>page([leafNode as typeof rootNode]))
  render(<ConstellationPage client={{constellationSlice}}/>)
  fireEvent.click(await screen.findByRole("option",{name:/AI Team/i}))
  expect(await screen.findByText("People in this team")).toBeVisible()
  expect(constellationSlice).toHaveBeenCalledTimes(1)
})

it("opens fixed facts only after click and opens profile from the explicit action",async()=>{
  const onProfile=vi.fn()
  const client={constellationSlice:async()=>page([rootNode])}
  render(<ConstellationPage client={client} onProfile={onProfile}/>)
  const option=await screen.findByRole("button",{name:"Statistics Canada"})
  fireEvent.mouseEnter(option)
  expect(screen.queryByText("People in this team")).not.toBeInTheDocument()
  fireEvent.click(option)
  expect(await screen.findByText("People in this team")).toBeVisible()
  expect(screen.getByText("200")).toBeVisible()
  expect(screen.getByText("2,400")).toBeVisible()
  fireEvent.click(screen.getByRole("button",{name:"Open Statistics Canada profile"}))
  expect(onProfile).toHaveBeenCalledWith("statcan")
})

it("reloads and resets hierarchy when institution root changes",async()=>{
  const constellationSlice=vi.fn().mockResolvedValue(page([leafNode as typeof rootNode]))
  const {rerender}=render(<ConstellationPage client={{constellationSlice}} rootOrgId="department-a"/>)
  await waitFor(()=>expect(constellationSlice).toHaveBeenLastCalledWith("department-a",expect.any(AbortSignal)))
  rerender(<ConstellationPage client={{constellationSlice}} rootOrgId="department-b"/>)
  await waitFor(()=>expect(constellationSlice).toHaveBeenLastCalledWith("department-b",expect.any(AbortSignal)))
  expect(screen.queryByRole("button",{name:"Back"})).not.toBeInTheDocument()
})

it("dismisses selected facts when the map background is clicked",async()=>{
  render(<ConstellationPage client={{constellationSlice:async()=>page([rootNode])}}/>)
  const option=await screen.findByRole("button",{name:"Statistics Canada"})
  fireEvent.mouseEnter(option)
  expect(screen.queryByText("People in this team")).not.toBeInTheDocument()
  fireEvent.click(option)
  expect(await screen.findByText("People in this team")).toBeVisible()
  fireEvent.click(screen.getByTestId("constellation-stage"))
  expect(screen.queryByText("People in this team")).not.toBeInTheDocument()
})

it("uses the requested Dot Field interaction tuning",async()=>{
  render(<ConstellationPage client={{constellationSlice:async()=>page([rootNode])}}/>)
  const stage=await screen.findByTestId("constellation-stage")
  const field=stage.querySelector(".dot-field")
  expect(field).toHaveAttribute("data-bulge-strength","58")
  expect(field).toHaveAttribute("data-dot-spacing","18")
  expect(field).toHaveAttribute("data-cursor-radius","600")
  expect(field).toHaveAttribute("data-wave-amplitude","1")
  expect(field).toHaveAttribute("data-glow-radius","110")
  expect(field).not.toHaveAttribute("data-active-frame-rate")
})

it("does not repeat the selected root organization inside its child bubble map",async()=>{
  const constellationSlice=vi.fn(async(rootId?:string)=>rootId==="statcan"?page([rootNode,leafNode as typeof rootNode]):page([rootNode]))
  render(<ConstellationPage client={{constellationSlice}}/>)
  const node=await screen.findByRole("option",{name:/Statistics Canada/i})
  fireEvent.click(node)
  expect(await screen.findByText("People in this team")).toBeVisible()
  expect(constellationSlice).toHaveBeenCalledTimes(1)
  fireEvent.doubleClick(node)
  expect(await screen.findByRole("option",{name:/AI Team/i})).toBeVisible()
  expect(screen.queryByRole("option",{name:/Statistics Canada/i})).not.toBeInTheDocument()
})

it("ignores an out-of-order drill response and commits only the newest level",async()=>{
  let resolveA:(value:ReturnType<typeof page>)=>void=()=>{}
  let resolveB:(value:ReturnType<typeof page>)=>void=()=>{}
  const a={...rootNode,org_id:"a",name:"A Team"}
  const b={...rootNode,org_id:"b",name:"B Team"}
  const client={constellationSlice:vi.fn((rootId?:string)=>{
    if(rootId==="a")return new Promise<ReturnType<typeof page>>(resolve=>{resolveA=resolve})
    if(rootId==="b")return new Promise<ReturnType<typeof page>>(resolve=>{resolveB=resolve})
    return Promise.resolve(page([a,b]))
  })}
  render(<ConstellationPage client={client}/>)
  fireEvent.doubleClick(await screen.findByRole("option",{name:"A Team"}))
  fireEvent.doubleClick(screen.getByRole("option",{name:"B Team"}))
  resolveB(page([{...leafNode,org_id:"b-child",name:"B child"} as typeof rootNode]))
  await screen.findByRole("option",{name:"B child"})
  resolveA(page([{...leafNode,org_id:"a-child",name:"A child"} as typeof rootNode]))
  await waitFor(()=>expect(screen.queryByRole("option",{name:"A child"})).not.toBeInTheDocument())
})

it("applies shared interest filters to illuminated teams",async()=>{
  const client={constellationSlice:async()=>page([]),constellation:async()=>({items:[
    {entity_id:"a",org_id:"statcan",entity_kind:"organization",title:"",organization_name:"Statistics Canada",department_name:"Statistics Canada",score:90,confidence:"medium",vacancy_signal:false,evidence:[{field:"organization",matched_phrase:"AI",source_text:"AI",weight:90,category_id:"data-ai-research"}]},
    {entity_id:"b",org_id:"ssc",entity_kind:"organization",title:"",organization_name:"Shared Services Canada",department_name:"Shared Services Canada",score:120,confidence:"high",vacancy_signal:true,evidence:[{field:"organization",matched_phrase:"AI",source_text:"AI",weight:120,category_id:"data-ai-research"}]},
  ],snapshot_id:"snapshot",etag:"etag"})}
  render(<ConstellationPage client={client} query="AI" scope={{department:"Shared Services Canada"}}/>)
  expect(await screen.findByRole("option",{name:/Shared Services Canada/i})).toBeVisible()
  expect(screen.queryByRole("option",{name:/Statistics Canada/i})).not.toBeInTheDocument()
})

it("shows a useful empty state instead of unrelated organizations for an unknown query",async()=>{
  const client={constellationSlice:async()=>page([rootNode]),constellation:async()=>({items:[],snapshot_id:"snapshot",etag:"etag"})}
  render(<ConstellationPage client={client} query="zzzz-no-category"/>)
  expect(await screen.findByText(/No strong match yet/)).toBeVisible()
  expect(screen.queryByRole("option",{name:/Statistics Canada/i})).not.toBeInTheDocument()
})
