import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, expect, it, vi } from "vitest"
import { ThemeControl } from "./ThemeControl"

beforeEach(()=>{
  localStorage.clear()
  delete document.documentElement.dataset.theme
  vi.stubGlobal("matchMedia",vi.fn().mockReturnValue({matches:false,addEventListener:vi.fn(),removeEventListener:vi.fn()}))
})

it("defaults Career Atlas to light and persists an explicit dark choice",()=>{
  render(<ThemeControl/>)
  expect(document.documentElement.dataset.theme).toBe("light")

  fireEvent.change(screen.getByLabelText("Theme"),{target:{value:"dark"}})

  expect(document.documentElement.dataset.theme).toBe("dark")
  expect(localStorage.getItem("geds-career-theme")).toBe("dark")
})

it("resolves the system choice and stores it independently",()=>{
  vi.stubGlobal("matchMedia",vi.fn().mockReturnValue({matches:true,addEventListener:vi.fn(),removeEventListener:vi.fn()}))
  render(<ThemeControl/>)

  fireEvent.change(screen.getByLabelText("Theme"),{target:{value:"system"}})

  expect(document.documentElement.dataset.theme).toBe("dark")
  expect(localStorage.getItem("geds-career-theme")).toBe("system")
})
