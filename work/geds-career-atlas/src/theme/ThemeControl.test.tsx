import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, expect, it, vi } from "vitest"
import { ThemeControl } from "./ThemeControl"

beforeEach(()=>{
  localStorage.clear()
  delete document.documentElement.dataset.theme
  vi.stubGlobal("matchMedia",vi.fn().mockReturnValue({matches:false,addEventListener:vi.fn(),removeEventListener:vi.fn()}))
})

it("toggles from light to dark with one persistent button",()=>{
  render(<ThemeControl/>)
  expect(document.documentElement.dataset.theme).toBe("light")

  fireEvent.click(screen.getByRole("button",{name:"Theme: Dark"}))

  expect(document.documentElement.dataset.theme).toBe("dark")
  expect(localStorage.getItem("geds-career-theme")).toBe("dark")
})

it("restores a saved dark choice and toggles back to light",()=>{
  localStorage.setItem("geds-career-theme","dark")
  render(<ThemeControl/>)

  expect(document.documentElement.dataset.theme).toBe("dark")
  fireEvent.click(screen.getByRole("button",{name:"Theme: Light"}))

  expect(document.documentElement.dataset.theme).toBe("light")
  expect(localStorage.getItem("geds-career-theme")).toBe("light")
})
