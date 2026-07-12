import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { ConstellationPage } from "./ConstellationPage"

it("loads the bounded slice and synchronizes selected focus", async () => {
  const onFocus=vi.fn()
  const client={constellationSlice:async()=>({nodes:[{org_id:"statcan",name:"Statistics Canada",depth:0,child_count:8,descendant_people_count:2400}],limit:2000,truncated:false,snapshot_id:"snapshot",etag:"etag"})}
  render(<ConstellationPage client={client} onFocus={onFocus}/>)
  const item=await screen.findByRole("option",{name:/Statistics Canada/i})
  fireEvent.click(item)
  expect(onFocus).toHaveBeenCalledWith("statcan")
  expect(screen.getByText(/Matched because/i)).toBeVisible()
})

it("keeps the accessible list when the visual layer is unavailable",async()=>{
  const client={constellationSlice:async()=>({nodes:[{org_id:"statcan",name:"Statistics Canada",depth:0,child_count:8,descendant_people_count:2400}],limit:2000,truncated:false,snapshot_id:"snapshot",etag:"etag"})}
  render(<ConstellationPage client={client}/>)
  expect(await screen.findByRole("listbox",{name:/Government map/i})).toBeVisible()
})

it("applies shared interest filters to illuminated teams",async()=>{
  const client={
    constellationSlice:async()=>({nodes:[],limit:2000,truncated:false,snapshot_id:"snapshot",etag:"etag"}),
    constellation:async()=>({items:[
      {entity_id:"a",org_id:"statcan",entity_kind:"organization",title:"",organization_name:"Statistics Canada",department_name:"Statistics Canada",score:90,confidence:"medium",vacancy_signal:false,evidence:[{field:"organization",matched_phrase:"AI",source_text:"AI",weight:90,category_id:"data-ai-research"}]},
      {entity_id:"b",org_id:"ssc",entity_kind:"organization",title:"",organization_name:"Shared Services Canada",department_name:"Shared Services Canada",score:120,confidence:"high",vacancy_signal:true,evidence:[{field:"organization",matched_phrase:"AI",source_text:"AI",weight:120,category_id:"data-ai-research"}]},
    ],snapshot_id:"snapshot",etag:"etag"})
  }
  render(<ConstellationPage client={client} query="AI" filters={{domain:"data-ai-research",department:"Shared Services Canada",confidence:"high",vacancy:true}}/>)
  expect(await screen.findByRole("option",{name:/Shared Services Canada/i})).toBeVisible()
  expect(screen.queryByRole("option",{name:/Statistics Canada/i})).not.toBeInTheDocument()
})
