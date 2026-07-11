import { expect, test } from "@playwright/test"

test("Organization Walk drills down and preserves selected focus", async ({ page }) => {
  await page.goto("/#explorer")
  const tree = page.getByRole("tree", { name: "Top-level government organizations" })
  await expect(tree).toBeVisible()
  const firstExpandable = tree.getByRole("treeitem").filter({ has: page.locator("small") }).first()
  await firstExpandable.focus()
  await firstExpandable.press("Enter")
  await expect(page).toHaveURL(/focus=/)
  await expect(page.getByLabel("Selected organization path")).toBeVisible()
})
