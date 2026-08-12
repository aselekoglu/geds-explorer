import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { GroupedRoles } from "./GroupedRoles"

it("presents frequent roles first in a labelled table and separates missing titles",()=>{
  const onRoleQuery=vi.fn()
  render(<GroupedRoles titles={["Analyst","Manager"," manager ","MANAGER",""]} onRoleQuery={onRoleQuery}/>)
  expect(screen.getByText("Records shown: 5 · Distinct titles: 2")).toBeVisible()
  expect(screen.getByRole("columnheader",{name:"Observed title"})).toBeVisible()
  expect(screen.getByRole("columnheader",{name:"Shown"})).toBeVisible()
  const rows=screen.getAllByRole("row").slice(1)
  expect(rows[0]).toHaveTextContent(/Manager\s*3/)
  expect(rows[1]).toHaveTextContent(/Analyst\s*1/)
  fireEvent.click(screen.getByRole("button",{name:/Filter by Analyst/i}))
  expect(onRoleQuery).toHaveBeenCalledWith("Analyst")
  const empty=screen.getByText(/No title recorded/i)
  expect(empty.closest("details")).not.toHaveAttribute("open")
  expect(empty.closest("summary")).toHaveTextContent("1")
})

it("shows a useful empty state when no title records are available",()=>{
  render(<GroupedRoles titles={[]}/>)
  expect(screen.getByText("No observed title records are available for this team.")).toBeVisible()
  expect(screen.queryByRole("table")).not.toBeInTheDocument()
})
