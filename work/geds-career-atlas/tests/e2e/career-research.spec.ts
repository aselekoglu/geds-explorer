import { expect, test } from "@playwright/test"
import { findProfileFromInterestResults } from "./helpers"

test("career conversation research remains non-claiming and source-linked", async ({ page, request }) => {
  const profile = await findProfileFromInterestResults(request, value => Array.isArray(value.conversation_leads) && value.conversation_leads.length > 0)
  await page.goto(`/?focus=${encodeURIComponent(profile.org_id)}`)
  await expect(page.getByRole("heading", { name: "Career conversation leads" })).toBeVisible()
  await expect(page.getByText(/does not verify that they are hiring/)).toBeVisible()
  await expect(page.getByRole("link", { name: "Open official GEDS record" }).first()).toHaveAttribute("href", /^https?:/)
  const leadSection = page.locator(".career-leads").filter({ has: page.getByRole("heading", { name: "Career conversation leads" }) })
  await expect(leadSection.getByText(/hiring manager/i)).toHaveCount(0)
  await expect(page.getByRole("button", { name: /apply/i })).toHaveCount(0)
})

test("recorded vacancy is shown only as an unverified signal", async ({ page, request }) => {
  const discovery = await (await request.get("/api/vacancy-signals?limit=1")).json()
  expect(discovery.items).toHaveLength(1)
  expect(discovery.items[0].live_competition_verified).toBe(false)
  await page.goto(`/?focus=${encodeURIComponent(discovery.items[0].org_id)}`)
  await expect(page.getByRole("heading", { name: "Unverified vacancy signals" })).toBeVisible()
  await expect(page.getByText("No live competition verified.").first()).toBeVisible()
  await expect(page.getByRole("link", { name: "Open vacancy source in GEDS" }).first()).toBeVisible()
  await expect(page.getByRole("button", { name: /apply/i })).toHaveCount(0)
})
