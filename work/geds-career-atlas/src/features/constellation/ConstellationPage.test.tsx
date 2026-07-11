import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { ConstellationPage } from "./ConstellationPage"

it("loads the bounded slice and synchronizes selected focus", async () => {
  const onFocus=vi.fn()
  const client={constellationSlice:async()=>({nodes:[{org_id:"statcan",name:"Statistics Canada",depth:0,child_count:8,descendant_people_count:2400}],limit:2000,truncated:false,snapshot_id:"snapshot",etag:"etag"})}
  render(<ConstellationPage client={client} onFocus={onFocus}/>)
  const item=await screen.findByRole("option",{name:/Statistics Canada/i})
  fireEvent.click(item)
  expect(onFocus).toHaveBeenCalledWith("statcan")
  expect(screen.getByText(/Matched because/i)).toBeVisible()
})

it("keeps the accessible list when the visual layer is unavailable",async()=>{
  const client={constellationSlice:async()=>({nodes:[{org_id:"statcan",name:"Statistics Canada",depth:0,child_count:8,descendant_people_count:2400}],limit:2000,truncated:false,snapshot_id:"snapshot",etag:"etag"})}
  render(<ConstellationPage client={client}/>)
  expect(await screen.findByRole("listbox",{name:/Government map/i})).toBeVisible()
})
