import { render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { TeamProfile } from "./TeamProfile"

it("uses non-claiming vacancy language",()=>{
  render(<TeamProfile name="AI Centre" roles={["Data Scientist"]} />)
  expect(screen.getByRole("note")).toBeVisible()
  expect(screen.queryByRole("link",{name:/apply/i})).not.toBeInTheDocument()
})

it("shows observed evidence without inventing a mandate or job",()=>{
  render(<TeamProfile name="AI Centre" roles={["Data Scientist"]} profile={{org_id:"ai",department_name:"Digital Services",canonical_path:["Digital Services","AI Centre"],direct_people_count:4,descendant_people_count:9,child_count:2,snapshot_id:"snapshot"}} />)
  expect(screen.getByText("Observed roles")).toBeVisible()
  expect(screen.getByText("Matched because")).toBeVisible()
  expect(screen.queryByRole("button",{name:/apply/i})).not.toBeInTheDocument()
  expect(screen.queryByText(/This team is responsible for/i)).not.toBeInTheDocument()
})
