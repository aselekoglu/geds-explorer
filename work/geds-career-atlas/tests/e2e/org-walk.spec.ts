import { expect, test } from "@playwright/test"

test("Organization Walk drills down without opening a profile", async ({ page }) => {
  await page.goto("/#explorer")
  const list = page.getByRole("list", { name: "Top-level government organizations" })
  await expect(list).toBeVisible()
  const firstExpandable = list.locator(".org-card__primary[aria-expanded]").first()
  await firstExpandable.focus()
  await firstExpandable.press("Enter")
  await expect(page.getByLabel("Selected organization path")).toBeVisible()
  await expect(page.getByRole("dialog", { name: "TEAM PROFILE" })).toHaveCount(0)
})
