import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { ConstellationPage } from "./ConstellationPage"

const rootNode={org_id:"statcan",name:"Statistics Canada",depth:0,child_count:1,direct_people_count:200,descendant_people_count:2400}
const leafNode={org_id:"ai-team",name:"AI Team",parent_id:"statcan",depth:1,child_count:0,direct_people_count:12,descendant_people_count:12}
const page=(nodes:typeof rootNode[])=>({nodes,limit:2000,truncated:false,snapshot_id:"snapshot",etag:"etag"})

it("drills bubbles, returns one level with Back, and never opens profile from the bubble",async()=>{
  const onProfile=vi.fn()
  const constellationSlice=vi.fn(async(rootId?:string)=>rootId==="statcan"?page([leafNode as typeof rootNode]):page([rootNode]))
  render(<ConstellationPage client={{constellationSlice}} onProfile={onProfile}/>)
  fireEvent.click(await screen.findByRole("option",{name:/Statistics Canada/i}))
  await waitFor(()=>expect(constellationSlice).toHaveBeenLastCalledWith("statcan",expect.any(AbortSignal)))
  expect(onProfile).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button",{name:"Back"}))
  await waitFor(()=>expect(constellationSlice).toHaveBeenLastCalledWith(undefined,expect.any(AbortSignal)))
  expect(screen.queryByRole("button",{name:"Back"})).not.toBeInTheDocument()
})

it("selects a leaf without requesting an empty slice",async()=>{
  const constellationSlice=vi.fn(async()=>page([leafNode as typeof rootNode]))
  render(<ConstellationPage client={{constellationSlice}}/>)
  fireEvent.click(await screen.findByRole("option",{name:/AI Team/i}))
  expect(await screen.findByRole("status",{name:""})).toHaveTextContent("No child teams")
  expect(constellationSlice).toHaveBeenCalledTimes(1)
})

it("shows hover facts and opens profile only from the explicit action",async()=>{
  const onProfile=vi.fn()
  const client={constellationSlice:async()=>page([rootNode])}
  render(<ConstellationPage client={client} onProfile={onProfile}/>)
  fireEvent.mouseEnter(await screen.findByRole("button",{name:"Statistics Canada"}))
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

it("applies shared interest filters to illuminated teams",async()=>{
  const client={constellationSlice:async()=>page([]),constellation:async()=>({items:[
    {entity_id:"a",org_id:"statcan",entity_kind:"organization",title:"",organization_name:"Statistics Canada",department_name:"Statistics Canada",score:90,confidence:"medium",vacancy_signal:false,evidence:[{field:"organization",matched_phrase:"AI",source_text:"AI",weight:90,category_id:"data-ai-research"}]},
    {entity_id:"b",org_id:"ssc",entity_kind:"organization",title:"",organization_name:"Shared Services Canada",department_name:"Shared Services Canada",score:120,confidence:"high",vacancy_signal:true,evidence:[{field:"organization",matched_phrase:"AI",source_text:"AI",weight:120,category_id:"data-ai-research"}]},
  ],snapshot_id:"snapshot",etag:"etag"})}
  render(<ConstellationPage client={client} query="AI" scope={{department:"Shared Services Canada"}}/>)
  expect(await screen.findByRole("option",{name:/Shared Services Canada/i})).toBeVisible()
  expect(screen.queryByRole("option",{name:/Statistics Canada/i})).not.toBeInTheDocument()
})
