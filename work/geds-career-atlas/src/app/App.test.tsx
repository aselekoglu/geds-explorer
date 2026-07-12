import { render, screen } from "@testing-library/react"
import { vi } from "vitest"
import { App } from "./App"
it("renders public navigation and theme control without private operator actions", () => {
  render(<App />)
  expect(screen.getByRole("link", { name: /discover/i })).toBeVisible()
  expect(screen.getByRole("link", { name: /government explorer/i })).toBeVisible()
  expect(screen.getByRole("link", { name: /constellation/i })).toBeVisible()
  expect(screen.getByLabelText("Theme")).toBeVisible()
  expect(screen.queryByText(/private admin/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/start crawler|run history|schedules|snapshot data/i)).not.toBeInTheDocument()
})

it("marks a selected team profile as an open responsive sheet",()=>{
  history.replaceState(null,"","/?focus=leaf-team")
  vi.stubGlobal("fetch",vi.fn(()=>new Promise(()=>undefined)))
  const {container}=render(<App/>)

  expect(container.querySelector(".detail-panel")).toHaveClass("detail-panel--open")
})
