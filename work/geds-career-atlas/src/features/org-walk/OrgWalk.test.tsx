import { render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { OrgWalk } from "./OrgWalk"
it("reveals a shared deep path",()=>{render(<OrgWalk path={["Department","Branch","Directorate","Team"]} />);const breadcrumb=screen.getByRole("navigation",{name:"Organization path"});expect(breadcrumb.querySelector("ol")).toBeInTheDocument();expect(breadcrumb.querySelectorAll("li")).toHaveLength(4);expect(breadcrumb.querySelector('[aria-current="page"]')).toHaveTextContent("Team");expect(screen.getByRole("treeitem",{name:"Team"})).toHaveAttribute("aria-current","true")})

it("keeps a large sibling column bounded",()=>{
  const siblings=Array.from({length:348},(_,index)=>`Organization ${index+1}`)
  render(<OrgWalk path={siblings} />)
  expect(screen.getByText("348 organizations")).toBeInTheDocument()
  expect(screen.getAllByRole("treeitem")).toHaveLength(60)
})
