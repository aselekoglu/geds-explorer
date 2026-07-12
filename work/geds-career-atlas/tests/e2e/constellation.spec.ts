import { expect, test } from "@playwright/test"

test("constellation offers synchronized keyboard-selectable semantic map", async ({ page }) => {
  await page.goto("/#constellation")
  const map = page.getByRole("listbox", { name: "Government map" })
  await expect(map).toBeAttached()
  const option = map.getByRole("option").first()
  await option.focus()
  await option.press("Enter")
  await expect(option).toHaveAttribute("aria-selected", "true")
  await expect(page).toHaveURL(/focus=/)
  await page.goBack()
  await expect(page).not.toHaveURL(/focus=/)
  await expect(page.getByText("Select an organization")).toBeVisible()
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
