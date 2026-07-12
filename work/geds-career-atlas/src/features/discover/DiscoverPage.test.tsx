import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { DiscoverPage } from "./DiscoverPage"
it("explains why an AI team matched", async () => { render(<DiscoverPage search="AI" client={{search:vi.fn().mockResolvedValue({items:[{entity_id:"o1",entity_kind:"organization",title:"",organization_name:"AI Centre",score:85,confidence:"medium",evidence:[{field:"organization",matched_phrase:"artificial intelligence",source_text:"AI Centre",weight:85,category_id:"data-ai-research"}]}]})} as never} />); expect(await screen.findByText("Data, analytics, AI and research")).toBeVisible(); const card=await screen.findByRole("article",{name:/AI Centre/i}); expect(card).toHaveTextContent(/Matched because/i); expect(card).toHaveTextContent(/organization/i) })

it("shows interpretation expansions and removable active constraints", async () => {
  const onFiltersChange=vi.fn()
  render(<DiscoverPage search="AI" filters={{domain:"data-ai-research",department:"Statistics Canada",confidence:"medium",vacancy:true}} onFiltersChange={onFiltersChange} client={{search:vi.fn().mockResolvedValue({items:[],interpretation:{original_query:"AI",normalized_query:"ai",category_ids:["data-ai-research"],expanded_terms:["artificial intelligence","machine learning"],evidence:["data-ai-research: abbreviation AI"],taxonomy_version:"1.0"}})} as never}/>)
  expect(await screen.findByText(/artificial intelligence/i)).toBeVisible()
  fireEvent.click(screen.getByRole("button",{name:/remove institution/i}))
  expect(onFiltersChange).toHaveBeenCalledWith(expect.objectContaining({department:""}))
})

it("expands complete match evidence", async () => {
  render(<DiscoverPage search="AI" client={{search:vi.fn().mockResolvedValue({items:[{entity_id:"o1",entity_kind:"organization",title:"",organization_name:"AI Centre",score:150,confidence:"high",evidence:Array.from({length:4},(_,index)=>({field:"organization",matched_phrase:`phrase ${index+1}`,source_text:"AI Centre",weight:40,category_id:"data-ai-research"}))}],interpretation:{original_query:"AI",normalized_query:"ai",category_ids:["data-ai-research"],expanded_terms:[],evidence:[],taxonomy_version:"1.0"}})} as never}/>)
  expect(await screen.findByText(/phrase 1/i)).toBeVisible()
  expect(screen.queryByText(/phrase 4/i)).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole("button",{name:/show all evidence/i}))
  expect(screen.getByText(/phrase 4/i)).toBeVisible()
})
