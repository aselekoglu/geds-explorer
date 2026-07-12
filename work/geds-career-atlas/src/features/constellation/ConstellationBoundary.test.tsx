import { render, screen } from "@testing-library/react"
import { ConstellationBoundary } from "./ConstellationBoundary"
import type { ReactNode } from "react"

function BrokenVisual():ReactNode{throw new Error("visual unavailable")}

it("keeps the synchronized list when the visual layer throws",()=>{
  render(<ConstellationBoundary nodes={[{id:"statcan",name:"Statistics Canada"}]} label="Government map"><BrokenVisual/></ConstellationBoundary>)
  expect(screen.getByRole("listbox",{name:"Government map"})).toBeVisible()
  expect(screen.getByRole("option",{name:"Statistics Canada"})).toBeVisible()
})
