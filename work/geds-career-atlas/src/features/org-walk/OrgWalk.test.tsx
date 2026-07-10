import { render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { OrgWalk } from "./OrgWalk"
it("reveals a shared deep path",()=>{render(<OrgWalk path={["Department","Branch","Directorate","Team"]} />);expect(screen.getByLabelText("Organization path")).toHaveTextContent("Department / Branch / Directorate / Team");expect(screen.getByRole("treeitem",{name:"Team"})).toHaveAttribute("aria-current","true")})

it("keeps a large sibling column bounded",()=>{
  const siblings=Array.from({length:348},(_,index)=>`Organization ${index+1}`)
  render(<OrgWalk path={siblings} />)
  expect(screen.getByText("348 organizations")).toBeInTheDocument()
  expect(screen.getAllByRole("treeitem")).toHaveLength(60)
})
