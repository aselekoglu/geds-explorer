import AxeBuilder from "@axe-core/playwright"
import { expect, test } from "@playwright/test"

for (const target of ["/?q=AI", "/#explorer", "/#constellation", "/#about"]) {
  test(`has no serious or critical axe violations at ${target}`, async ({ page }) => {
    await page.goto(target)
    await expect(page.locator("main")).toBeVisible()
    const result = await new AxeBuilder({ page }).analyze()
    expect(result.violations.filter(item => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([])
  })
}

test("supports skip link, visible focus, action-list semantics, and reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" })
  await page.goto("/#explorer")
  await page.keyboard.press("Tab")
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused()
  const list = page.getByRole("list", { name: "Top-level government organizations" })
  await expect(list).toBeVisible()
  await page.getByRole("link", { name: "Discover" }).click()
  const duration = await page.locator(".constellation-stage svg circle").first().evaluate(element => getComputedStyle(element).transitionDuration)
  expect(Number.parseFloat(duration)).toBeLessThanOrEqual(0.001)
})
