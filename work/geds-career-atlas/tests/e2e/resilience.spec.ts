import { expect, test } from "@playwright/test"

test("constellation failure points people to Organization Walk", async ({ page }) => {
  await page.route("**/api/constellation/slice**", route => route.abort())
  await page.goto("/")
  const failure = page.getByRole("status").filter({ hasText: "visual map is unavailable" })
  await expect(failure).toBeVisible()
  await expect(failure).toContainText("Organization Walk")
})

test("profile source failure has a useful status", async ({ page }) => {
  await page.route("**/api/orgs/*/profile", route => route.abort())
  await page.goto("/?focus=unavailable-source")
  await expect(page.getByRole("status").filter({ hasText: "team profile is unavailable" })).toBeVisible()
})

test("partial canonical quality and known limitations are visible", async ({ page }) => {
  await page.goto("/#about")
  await expect(page.getByText(/Quality status: partial overlay/i)).toBeVisible()
  await expect(page.getByRole("heading", { name: "Known limitations" })).toBeVisible()
})
