import { render, screen } from "@testing-library/react"
import { vi } from "vitest"
import { App } from "./App"
it("renders public navigation and theme control without private operator actions", () => {
  render(<App />)
  expect(screen.getByRole("link", { name: /discover/i })).toBeVisible()
  expect(screen.getByRole("link", { name: /organization walk/i })).toBeVisible()
  expect(screen.queryByRole("link", { name: /constellation/i })).not.toBeInTheDocument()
  expect(screen.queryByRole("link", { name: /tours/i })).not.toBeInTheDocument()
  expect(screen.getByLabelText("Theme")).toBeVisible()
  expect(screen.queryByText(/private admin/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/start crawler|run history|schedules|snapshot data/i)).not.toBeInTheDocument()
})

it("does not reserve an empty profile column",()=>{
  history.replaceState(null,"","/#discover")
  const {container}=render(<App/>)
  expect(container.querySelector(".detail-panel")).not.toBeInTheDocument()
})

it("marks a selected team profile as an open responsive sheet",()=>{
  history.replaceState(null,"","/?focus=leaf-team")
  vi.stubGlobal("fetch",vi.fn(()=>new Promise(()=>undefined)))
  const {container}=render(<App/>)

  expect(container.querySelector(".detail-panel")).toHaveClass("detail-panel--open")
})
