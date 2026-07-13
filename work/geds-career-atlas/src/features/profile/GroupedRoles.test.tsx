import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { GroupedRoles } from "./GroupedRoles"

it("renders repeated roles once with a count and collapses missing titles",()=>{
  const onRoleQuery=vi.fn()
  render(<GroupedRoles titles={["Analyst"," analyst ",""]} onRoleQuery={onRoleQuery}/>)
  fireEvent.click(screen.getByRole("button",{name:/Filter by Analyst/i}))
  expect(onRoleQuery).toHaveBeenCalledWith("Analyst")
  const empty=screen.getByText(/No title recorded · 1/i)
  expect(empty.closest("details")).not.toHaveAttribute("open")
  expect(screen.getAllByText(/Analyst/)).toHaveLength(1)
})
