import { fireEvent, render, screen } from "@testing-library/react"
import { vi } from "vitest"
import { FilterRail } from "./FilterRail"

it("keeps institution scope and quality context without low-value filters",()=>{
  const onChange=vi.fn()
  render(<FilterRail departments={[{department_id:"d1",name:"Statistics Canada"}]} value={{department:""}} qualityStatus="partial_overlay" onChange={onChange}/>)
  expect(screen.getByText(/partial overlay/i)).toBeVisible()
  fireEvent.change(screen.getByLabelText("Institution"),{target:{value:"Statistics Canada"}})
  expect(onChange).toHaveBeenCalledWith({department:"Statistics Canada"})
  expect(screen.queryByLabelText("Career domain")).not.toBeInTheDocument()
  expect(screen.queryByLabelText("Minimum confidence")).not.toBeInTheDocument()
  expect(screen.queryByLabelText("Recorded vacancy only")).not.toBeInTheDocument()
})
