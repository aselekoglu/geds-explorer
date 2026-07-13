import { render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { GroupedRoles } from "./GroupedRoles"

it("renders repeated roles once with a count and collapses missing titles",()=>{
  render(<GroupedRoles titles={["Analyst"," analyst ",""]}/>)
  expect(screen.getByRole("heading",{name:/Analyst · 2/i})).toBeVisible()
  const empty=screen.getByText(/No title recorded · 1/i)
  expect(empty.closest("details")).not.toHaveAttribute("open")
  expect(screen.getAllByText(/Analyst/)).toHaveLength(1)
})
