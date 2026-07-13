import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { TeamProfile } from "./TeamProfile"

it("does not imply a vacancy when no source marker exists",()=>{
  render(<TeamProfile name="AI Centre" roles={["Data Scientist"]} />)
  expect(screen.queryByText(/Recorded as vacant/)).not.toBeInTheDocument()
  expect(screen.queryByRole("link",{name:/apply/i})).not.toBeInTheDocument()
})

it("shows observed evidence without inventing a mandate or job",()=>{
  render(<TeamProfile name="AI Centre" roles={["Data Scientist","Data Scientist",""]} profile={{org_id:"ai",department_name:"Digital Services",canonical_path:["Digital Services","AI Centre"],direct_people_count:4,descendant_people_count:9,child_count:2,snapshot_id:"snapshot"}} />)
  expect(screen.getByText("Observed roles")).toBeVisible()
  expect(screen.getByRole("button",{name:"Filter by Data Scientist"})).toHaveTextContent(/Data Scientist\s*·\s*2/)
  expect(screen.getByText(/No title recorded · 1/i)).toBeVisible()
  expect(screen.getByText("Matched because")).toBeVisible()
  expect(screen.queryByRole("button",{name:/apply/i})).not.toBeInTheDocument()
  expect(screen.queryByText(/This team is responsible for/i)).not.toBeInTheDocument()
})

it("shows freshness, quality, source, related teams, and copies a local-only issue report",async()=>{
  const writeText=vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText}})
  render(<TeamProfile name="AI Centre" roles={["Data Scientist"]} relatedTeams={[{org_id:"child",name:"Platform Team"}]} profile={{org_id:"ai",department_name:"Digital Services",canonical_path:["Digital Services","AI Centre"],direct_people_count:4,descendant_people_count:9,child_count:1,snapshot_id:"snapshot",snapshot_as_of:"2026-07-09T00:00:00Z",quality_status:"partial_overlay",source_url:"https://geds.example/org"}} />)

  expect(screen.getByText(/Snapshot: July 9, 2026/)).toBeVisible()
  expect(screen.getByText(/Partial data warning/)).toBeVisible()
  expect(screen.getByRole("link",{name:"Open official GEDS organization"})).toHaveAttribute("href","https://geds.example/org")
  expect(screen.getByRole("link",{name:"Platform Team"})).toHaveAttribute("href",expect.stringContaining("focus=child"))
  fireEvent.click(screen.getByRole("button",{name:"Copy data issue report"}))
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Organization ID: ai"))
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Snapshot ID: snapshot"))
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Source URL: https://geds.example/org"))
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Correction description:"))
})
