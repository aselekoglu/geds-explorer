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

test("supports skip link, visible focus, tree semantics, and reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" })
  await page.goto("/#explorer")
  await page.keyboard.press("Tab")
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused()
  const tree = page.getByRole("tree", { name: "Top-level government organizations" })
  await expect(tree).toBeVisible()
  const duration = await page.locator(".constellation-stage svg circle").first().evaluate(element => getComputedStyle(element).transitionDuration)
  expect(duration).toBe("0s")
})
