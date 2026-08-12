import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import type { PeoplePage } from "../../api/types"
import { TeamProfile } from "./TeamProfile"

it("does not imply a vacancy when no source marker exists",()=>{
  render(<TeamProfile name="AI Centre" roles={["Data Scientist"]} />)
  expect(screen.queryByText(/Recorded as vacant/)).not.toBeInTheDocument()
  expect(screen.queryByRole("link",{name:/apply/i})).not.toBeInTheDocument()
})

it("shows observed evidence without inventing a mandate or job",()=>{
  render(<TeamProfile name="AI Centre" roles={["Data Scientist","Data Scientist",""]} profile={{org_id:"ai",department_name:"Digital Services",canonical_path:["Digital Services","AI Centre"],direct_people_count:4,descendant_people_count:9,child_count:2,snapshot_id:"snapshot"}} />)
  const breadcrumb = screen.getByRole("navigation", { name: "Selected organization path" })
  expect(breadcrumb.querySelector("ol")).toBeInTheDocument()
  expect(breadcrumb.querySelectorAll("li")).toHaveLength(2)
  expect(breadcrumb.querySelector('[aria-current="page"]')).toHaveTextContent("AI Centre")
  expect(screen.queryByText("Digital Services / AI Centre")).not.toBeInTheDocument()
  expect(screen.getByText("Observed roles")).toBeVisible()
  expect(screen.getByRole("button",{name:"Filter by Data Scientist"})).toHaveTextContent("Data Scientist")
  expect(screen.getByRole("row",{name:/Data Scientist/})).toHaveTextContent(/Data Scientist\s*2/)
  expect(screen.getByText(/No title recorded/i)).toBeVisible()
  expect(screen.queryByText("Matched because")).not.toBeInTheDocument()
  expect(screen.queryByRole("button",{name:/apply/i})).not.toBeInTheDocument()
  expect(screen.queryByText(/This team is responsible for/i)).not.toBeInTheDocument()
})

it("shows freshness, quality, source, related teams, and copies a local-only issue report",async()=>{
  const writeText=vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText}})
  render(<TeamProfile name="AI Centre" roles={["Data Scientist"]} relatedTeams={[{org_id:"child",name:"Platform Team"}]} profile={{org_id:"ai",department_name:"Digital Services",canonical_path:["Digital Services","AI Centre"],direct_people_count:4,descendant_people_count:9,child_count:1,snapshot_id:"snapshot",snapshot_as_of:"2026-07-09T00:00:00Z",quality_status:"partial_overlay",source_url:"https://geds.example/org"}} />)

  expect(screen.getByText(/Snapshot: July 9, 2026/)).toBeVisible()
  expect(screen.getByRole("note")).toHaveTextContent("Snapshot coverage: partial overlay")
  expect(screen.getByRole("note")).toHaveTextContent("release-level status")
  expect(screen.getByRole("note")).toHaveTextContent("not an assessment of this specific team")
  expect(screen.getByRole("link",{name:"Open official GEDS organization"})).toHaveAttribute("href","https://geds.example/org")
  expect(screen.getByRole("link",{name:"Platform Team"})).toHaveAttribute("href",expect.stringContaining("focus=child"))
  fireEvent.click(screen.getByRole("button",{name:"Copy data issue report"}))
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Organization ID: ai"))
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Snapshot ID: snapshot"))
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Source URL: https://geds.example/org"))
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Correction description:"))
})

it("places the role overview before the long people directory for leaf teams",()=>{
  const client={people:vi.fn(()=>new Promise<PeoplePage>(()=>undefined))}
  const {container}=render(<TeamProfile name="AI Centre" roles={["Data Scientist"]} profile={{org_id:"ai",department_name:"Digital Services",canonical_path:["Digital Services","AI Centre"],direct_people_count:4,descendant_people_count:4,child_count:0,snapshot_id:"snapshot"}} peopleClient={client}/>)
  const rolesHeading=screen.getByRole("heading",{name:"Observed roles"})
  const peopleHeading=screen.getByRole("heading",{name:"People in this team"})
  expect(rolesHeading.compareDocumentPosition(peopleHeading)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(container.querySelector(".title-groups__table")).toBeInTheDocument()
})
