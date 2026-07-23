import { expect, test } from "@playwright/test"

test("Organization Walk drills down without opening a profile", async ({ page }) => {
  await page.goto("/#explorer")
  const list = page.getByRole("list", { name: "Top-level government organizations" })
  await expect(list).toBeVisible()
  const firstExpandable = list.locator(".org-card__primary[aria-expanded]").first()
  await firstExpandable.focus()
  await firstExpandable.press("Enter")
  const breadcrumb = page.getByRole("navigation", { name: "Selected organization path" })
  await expect(breadcrumb).toBeVisible()
  await expect(breadcrumb.locator("ol > li")).toHaveCount(1)
  await expect(breadcrumb.locator('[aria-current="page"]')).toBeVisible()
  await expect(page.getByRole("dialog", { name: "TEAM PROFILE" })).toHaveCount(0)
})

test("Organization Walk breadcrumb remains usable on a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 })
  await page.goto("/#explorer")
  const list = page.getByRole("list", { name: "Top-level government organizations" })
  const firstExpandable = list.locator(".org-card__primary[aria-expanded]").first()
  await firstExpandable.press("Enter")

  await expect(page.getByRole("navigation", { name: "Selected organization path" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Back one organization level" })).toBeVisible()

  const hasHorizontalPageOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(hasHorizontalPageOverflow).toBe(false)
})

test("Team profile exposes its canonical path as a breadcrumb", async ({ page, request }) => {
  const roots = (await (await request.get("/api/orgs/root/children?limit=200")).json()).items as Array<{ org_id: string; child_count: number }>
  const root = roots.find(item => item.child_count > 0)
  expect(root).toBeDefined()
  const children = (await (await request.get(`/api/orgs/${encodeURIComponent(root!.org_id)}/children?limit=1`)).json()).items as Array<{ org_id: string }>
  expect(children.length).toBeGreaterThan(0)
  const profile = await (await request.get(`/api/orgs/${encodeURIComponent(children[0].org_id)}/profile`)).json() as { org_id: string; canonical_path: string[] }
  const canonicalPath = profile.canonical_path
  await page.goto(`/?focus=${encodeURIComponent(profile.org_id)}`)

  const dialog = page.getByRole("dialog", { name: "TEAM PROFILE" })
  const breadcrumb = dialog.getByRole("navigation", { name: "Selected organization path" })
  await expect(breadcrumb.locator("ol > li")).toHaveCount(canonicalPath.length)
  await expect(breadcrumb.locator('[aria-current="page"]')).toHaveText(canonicalPath.at(-1)!)
  await expect(breadcrumb.getByRole("button")).toHaveCount(0)
})
