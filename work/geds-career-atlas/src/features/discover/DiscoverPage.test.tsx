import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { DiscoverPage } from "./DiscoverPage"

const evidence={field:"organization",matched_phrase:"policy",source_text:"Policy Team",weight:85,category_id:"policy-programs"}
const interpretation={original_query:"policy",normalized_query:"policy",category_ids:["policy-programs"],expanded_terms:["public policy"],evidence:["policy-programs: policy"],taxonomy_version:"1.0"}

it("switches one deterministic query between topics, teams, and people",async()=>{
  const client={search:vi.fn().mockResolvedValue({items:[
    {entity_id:"org:1",entity_kind:"organization",org_id:"1",title:"",organization_name:"Policy Team",department_name:"Department A",score:85,confidence:"high",evidence:[evidence]},
    {entity_id:"person:ada",entity_kind:"person",org_id:"1",display_name:"Ada Smith",source_url:"https://geds-sage.gc.ca/ada",title:"Policy Analyst",organization_name:"Policy Team",department_name:"Department A",score:75,confidence:"high",evidence:[evidence]},
  ],interpretation})}
  render(<DiscoverPage search="policy" client={client}/>)
  expect(await screen.findByText("Policy and programs")).toBeVisible()
  expect(screen.getByRole("article",{name:"Policy Team"})).toBeVisible()
  expect(screen.getByRole("article",{name:"Ada Smith"})).toBeVisible()
  fireEvent.click(screen.getByRole("radio",{name:"People"}))
  expect(screen.queryByRole("article",{name:"Policy Team"})).not.toBeInTheDocument()
  expect(screen.getByRole("article",{name:"Ada Smith"})).toBeVisible()
})

it("applies institution scope without confidence or vacancy filtering",async()=>{
  const client={search:vi.fn().mockResolvedValue({items:[
    {entity_id:"a",entity_kind:"organization",title:"",organization_name:"Department A Team",department_name:"Department A",score:10,confidence:"none",vacancy_signal:false,evidence:[evidence]},
    {entity_id:"b",entity_kind:"organization",title:"",organization_name:"Department B Team",department_name:"Department B",score:10,confidence:"none",vacancy_signal:false,evidence:[evidence]},
  ],interpretation})}
  render(<DiscoverPage search="policy" scope={{department:"Department B"}} client={client}/>)
  expect(await screen.findByText("Department B Team")).toBeVisible()
  expect(screen.queryByText("Department A Team")).not.toBeInTheDocument()
})

it("expands complete match evidence",async()=>{
  render(<DiscoverPage search="AI" client={{search:vi.fn().mockResolvedValue({items:[{entity_id:"o1",entity_kind:"organization",title:"",organization_name:"AI Centre",score:150,confidence:"high",evidence:Array.from({length:4},(_,index)=>({...evidence,matched_phrase:`phrase ${index+1}`}))}],interpretation})} as never}/>)
  expect(await screen.findByText(/phrase 1/i)).toBeVisible()
  expect(screen.queryByText(/phrase 4/i)).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole("button",{name:/show all evidence/i}))
  expect(screen.getByText(/phrase 4/i)).toBeVisible()
})
