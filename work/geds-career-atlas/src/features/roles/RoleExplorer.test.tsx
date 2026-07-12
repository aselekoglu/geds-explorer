import { fireEvent, render, screen } from "@testing-library/react"
import { RoleExplorer } from "./RoleExplorer"

const items = [
  { entity_id:"p1",entity_kind:"person",org_id:"ai",title:"Data Scientist",organization_name:"AI Centre",department_name:"Statistics Canada",score:100,confidence:"high",vacancy_signal:true,evidence:[{field:"title",matched_phrase:"data science",source_text:"Data Scientist",weight:100,category_id:"data-ai-research"}] },
  { entity_id:"p2",entity_kind:"person",org_id:"security",title:"Security Analyst",organization_name:"Cyber Centre",department_name:"Shared Services Canada",score:70,confidence:"medium",vacancy_signal:false,evidence:[{field:"title",matched_phrase:"security",source_text:"Security Analyst",weight:70,category_id:"cybersecurity"}] },
]

it("groups original titles by taxonomy category and links back to teams",()=>{
  render(<RoleExplorer items={items}/>)
  expect(screen.getByRole("heading",{name:"Data AI Research"})).toBeVisible()
  expect(screen.getByText("Data Scientist")).toBeVisible()
  expect(screen.getByRole("link",{name:"AI Centre"})).toHaveAttribute("href",expect.stringContaining("focus=ai"))
})

it("filters role groups by confidence, institution, and recorded vacancy",()=>{
  render(<RoleExplorer items={items}/>)
  fireEvent.change(screen.getByLabelText("Minimum confidence"),{target:{value:"high"}})
  expect(screen.queryByText("Security Analyst")).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText("Institution"),{target:{value:"Statistics Canada"}})
  fireEvent.change(screen.getByLabelText("Team or subtree"),{target:{value:"AI Centre"}})
  fireEvent.click(screen.getByLabelText("Recorded vacancy only"))
  expect(screen.getByText("Data Scientist")).toBeVisible()
})
