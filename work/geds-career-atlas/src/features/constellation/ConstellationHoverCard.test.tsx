import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { ConstellationHoverCard } from "./ConstellationHoverCard"

it("shows complete branch facts and a dedicated profile action",()=>{
  const onProfile=vi.fn()
  render(<ConstellationHoverCard node={{id:"team",name:"Policy Team",value:20,child_count:0,direct_people_count:4,descendant_people_count:20}} anchor={{x:590,y:20}} onProfile={onProfile}/>)
  expect(screen.getByRole("heading",{name:"Policy Team"})).toBeVisible()
  expect(screen.getByText("No child teams")).toBeVisible()
  fireEvent.click(screen.getByRole("button",{name:"Open Policy Team profile"}))
  expect(onProfile).toHaveBeenCalledWith("team")
})
