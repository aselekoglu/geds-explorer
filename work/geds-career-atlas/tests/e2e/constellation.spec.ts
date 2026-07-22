import { expect, test } from "@playwright/test"

test("constellation separates keyboard details from keyboard drill", async ({ page }) => {
  await page.goto("/#constellation")
  const map = page.getByRole("listbox", { name: "Government map" })
  await expect(map).toBeAttached()
  const option = map.getByRole("option").filter({ hasText: "More teams available" }).first()
  await option.focus()
  await option.press("Enter")
  await expect(page.locator(".constellation-info-panel")).toBeVisible()
  await option.press("ArrowRight")
  await expect(page.getByRole("button", { name: "Back" })).toBeVisible()
  await page.getByRole("button", { name: "Back" }).click()
  await expect(page.getByRole("button", { name: "Back" })).toHaveCount(0)
})

test("mobile constellation is list-first without page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  await page.goto("/?lang=fr#constellation")
  await expect(page.getByRole("listbox", { name: "Carte gouvernementale" })).toBeAttached()
  const result = await page.evaluate(() => {
    const root = document.documentElement
    const list = document.querySelector(".constellation-stage [role=listbox]")!.getBoundingClientRect()
    const svg = document.querySelector(".constellation-stage svg")!.getBoundingClientRect()
    return { overflow: root.scrollWidth > root.clientWidth + 1, listFirst: list.top < svg.top }
  })
  expect(result).toEqual({ overflow: false, listFirst: true })
})

test("constellation opens details on click and drills only on double click", async ({ page }) => {
  await page.goto("/#constellation")
  const stage=page.getByTestId("constellation-stage")
  const bubble=stage.locator('g.constellation-node[aria-label="Shared Services Canada"]')
  await expect(bubble).toHaveCount(1)
  await bubble.click()
  await expect(stage.locator(".constellation-info-panel")).toBeVisible()
  await expect(page.getByRole("button", { name: "Back" })).toHaveCount(0)
  await bubble.dblclick()
  await expect(page.getByRole("button", { name: "Back" })).toBeVisible()
})

test("dot field renders and empty map space dismisses selected facts", async ({ page }) => {
  await page.goto("/#constellation")
  const stage = page.getByTestId("constellation-stage")
  const canvas = stage.locator(".dot-field canvas")
  await expect(canvas).toBeVisible()
  const field = stage.locator(".dot-field")
  await expect(field).toHaveAttribute("data-bulge-strength", "58")
  await expect(field).toHaveAttribute("data-dot-spacing", "18")

  const option=stage.getByRole("option").first()
  await option.focus()
  await option.press("Enter")
  await expect(stage.locator(".constellation-info-panel")).toBeVisible()
  await stage.click({ position: { x: 18, y: 18 } })
  await expect(stage.locator(".constellation-info-panel")).toHaveCount(0)
})
