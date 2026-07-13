import { expect, test } from "@playwright/test"
import { waitForAtlas } from "./helpers"

test("broad interest illuminates explainable government teams", async ({ page }) => {
  await page.goto("/?q=AI&lang=en")
  await waitForAtlas(page)
  const discover = page.getByRole("region", { name: "Government constellation" })
  await expect(discover.getByRole("option").first()).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await expect(page.getByRole("button", { name: /apply/i })).toHaveCount(0)

  await page.getByRole("button", { name: "Français" }).click()
  await expect(page.getByRole("link", { name: "Découvrir" })).toBeVisible()
  await expect(page).toHaveURL(/q=AI/)
  await expect(page).toHaveURL(/lang=fr/)
})

test("unknown interest produces a useful no-match state", async ({ page }) => {
  await page.goto("/?q=zzzz-no-category")
  await expect(page.getByText(/No strong match yet/)).toBeVisible()
})
