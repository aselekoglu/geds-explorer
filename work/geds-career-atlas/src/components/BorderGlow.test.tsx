import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { BorderGlow } from "./BorderGlow"

it("keeps the reusable surface API without decorative glow layers", () => {
  const { container } = render(<BorderGlow backgroundColor="var(--canvas)" borderRadius={2}>Content</BorderGlow>)
  const surface = container.querySelector<HTMLElement>(".border-glow-card")!

  expect(surface.style.getPropertyValue("--card-bg")).toBe("var(--canvas)")
  expect(surface.style.getPropertyValue("--border-radius")).toBe("2px")
  expect(surface.querySelector(".border-glow-inner")).toHaveTextContent("Content")
  expect(surface.querySelector(".edge-light")).not.toBeInTheDocument()
})

it("renders the requested semantic element and accessible attributes", () => {
  render(<BorderGlow as="section" aria-label="Organization results">Content</BorderGlow>)
  expect(screen.getByRole("region", { name: "Organization results" })).toBeVisible()
})

it("passes ordinary interaction handlers to the surface", () => {
  const onClick = vi.fn()
  render(<BorderGlow as="article" aria-label="Result" onClick={onClick}>Content</BorderGlow>)
  fireEvent.click(screen.getByRole("article", { name: "Result" }))
  expect(onClick).toHaveBeenCalledOnce()
})
