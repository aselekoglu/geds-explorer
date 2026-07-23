import { fireEvent, render, screen, within } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { OrgBreadcrumb } from "./OrgBreadcrumb"

it("keeps the mobile back action and exposes ancestor selection",()=>{
  const onBack=vi.fn()
  const onSelect=vi.fn()
  render(<OrgBreadcrumb path={["Department","Branch","Team"]} label="Selected organization path" onBack={onBack} onSelect={onSelect}/>)

  fireEvent.click(screen.getByRole("button",{name:"Back one organization level"}))
  expect(onBack).toHaveBeenCalledOnce()

  const path=screen.getByRole("navigation",{name:"Selected organization path"})
  fireEvent.click(within(path).getByRole("button",{name:"Branch"}))
  expect(onSelect).toHaveBeenCalledWith(1)
  expect(within(path).getByText("Team")).toHaveAttribute("aria-current","page")
})
