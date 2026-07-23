import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { Constellation } from "./Constellation"
it("synchronizes selected focus with accessible list",()=>{render(<Constellation nodes={[{id:"a",name:"AI Centre"}]} focus="a"/>);expect(screen.getByRole("option",{name:"AI Centre"})).toHaveAttribute("aria-selected","true")})

it("labels quality and recorded-vacancy semantics without success color claims",()=>{
  render(<Constellation nodes={[{id:"a",name:"AI Centre",quality_status:"partial_overlay",vacancy_count:2,has_more:true}]} focus="a"/>)
  const option=screen.getByRole("option",{name:"AI Centre"})
  expect(option).toHaveAttribute("data-quality","partial_overlay")
  expect(option).toHaveTextContent("Recorded as vacant in GEDS, unverified")
  expect(option).toHaveTextContent("More teams available")
})

it("uses abbreviations at government level and wraps lower-level names without ellipses",()=>{
  const {container,rerender}=render(<Constellation topLevel nodes={[{id:"crtc",name:"Canadian Radio-television and Telecommunications Commission",value:100}]} focus="crtc"/>)
  expect(container.querySelector("svg text")?.textContent).toBe("CRTC")
  rerender(<Constellation nodes={[{id:"team",name:"Dispute Resolution and Regulatory Implementation",value:100}]} focus="team"/>)
  expect(container.querySelector("svg text")?.textContent).not.toContain("...")
  expect(container.querySelectorAll("svg tspan").length).toBeGreaterThan(1)
})

it("offers accessible pan and zoom controls",()=>{
  render(<Constellation nodes={[{id:"a",name:"AI Centre"}]}/>)
  expect(screen.getByRole("button",{name:"Zoom in"})).toBeInTheDocument()
  expect(screen.getByRole("button",{name:"Zoom out"})).toBeInTheDocument()
  expect(screen.getByRole("button",{name:"Reset view"})).toBeInTheDocument()
})

it("opens details on one click and drills only on double click",()=>{
  const onSelect=vi.fn(),onDrill=vi.fn()
  render(<Constellation nodes={[{id:"a",name:"AI Centre",child_count:1}]} onSelect={onSelect} onDrill={onDrill}/>)
  const option=screen.getByRole("option",{name:"AI Centre"})
  fireEvent.click(option)
  expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({id:"a"}))
  expect(onDrill).not.toHaveBeenCalled()
  fireEvent.doubleClick(option)
  expect(onDrill).toHaveBeenCalledWith(expect.objectContaining({id:"a"}))
})

it("renders a static layered premium bubble surface",()=>{
  const {container}=render(<Constellation nodes={[{id:"a",name:"AI Centre"}]}/>)
  expect(container.querySelector(".constellation-node")).not.toHaveAttribute("style")
  expect(container.querySelector(".constellation-bubble-surface")).toBeInTheDocument()
  expect(container.querySelector(".constellation-bubble-sheen")).toBeInTheDocument()
  expect(container.querySelector(".constellation-bubble-border")).toBeInTheDocument()
})
