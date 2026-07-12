import { fireEvent, render, screen } from "@testing-library/react"
import { vi } from "vitest"
import { FilterRail } from "./FilterRail"

it("emits institution, confidence, and vacancy filters without losing quality context",()=>{
  const onChange=vi.fn()
  render(<FilterRail departments={[{department_id:"d1",name:"Statistics Canada"}]} value={{domain:"",department:"",confidence:"exploratory",vacancy:false}} qualityStatus="partial_overlay" onChange={onChange}/>)
  expect(screen.getByText(/partial overlay/i)).toBeVisible()
  fireEvent.change(screen.getByLabelText("Institution"),{target:{value:"Statistics Canada"}})
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({department:"Statistics Canada"}))
  fireEvent.change(screen.getByLabelText("Career domain"),{target:{value:"cybersecurity"}})
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({domain:"cybersecurity"}))
  fireEvent.change(screen.getByLabelText("Minimum confidence"),{target:{value:"high"}})
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({confidence:"high"}))
  fireEvent.click(screen.getByLabelText("Recorded vacancy only"))
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({vacancy:true}))
})
