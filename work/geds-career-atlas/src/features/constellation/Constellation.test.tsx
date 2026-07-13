import { render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { Constellation } from "./Constellation"
it("synchronizes selected focus with accessible list",()=>{render(<Constellation nodes={[{id:"a",name:"AI Centre"}]} focus="a"/>);expect(screen.getByRole("option",{name:"AI Centre"})).toHaveAttribute("aria-selected","true")})

it("labels quality and recorded-vacancy semantics without success color claims",()=>{
  render(<Constellation nodes={[{id:"a",name:"AI Centre",quality_status:"partial_overlay",vacancy_count:2,has_more:true}]} focus="a"/>)
  const option=screen.getByRole("option",{name:"AI Centre"})
  expect(option).toHaveAttribute("data-quality","partial_overlay")
  expect(option).toHaveTextContent("Recorded as vacant in GEDS — unverified")
  expect(option).toHaveTextContent("More teams available")
})

it("uses abbreviations at government level and wraps lower-level names without ellipses",()=>{
  const {container,rerender}=render(<Constellation topLevel nodes={[{id:"crtc",name:"Canadian Radio-television and Telecommunications Commission",value:100}]} focus="crtc"/>)
  expect(container.querySelector("svg text")?.textContent).toBe("CRTC")
  rerender(<Constellation nodes={[{id:"team",name:"Dispute Resolution and Regulatory Implementation",value:100}]} focus="team"/>)
  expect(container.querySelector("svg text")?.textContent).not.toContain("...")
  expect(container.querySelectorAll("svg tspan").length).toBeGreaterThan(1)
})
