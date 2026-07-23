import { expect, test, type Page } from "@playwright/test"

async function waitForPhysicalCard(page: Page) {
  const card = page.getByRole("link", { name: "Visit Ata Selekoglu's website" })
  await expect(card).toBeVisible()
  await expect(card).toHaveAttribute("data-profile-tilt", "disabled")
  await page.waitForTimeout(900)
  return card
}

test("renders the transparent physical Profile Card without replacing About content", async ({ page }) => {
  const pageErrors: string[] = []
  page.on("pageerror", error => pageErrors.push(error.message))
  const response = await page.goto("/#about")

  await expect(page.getByRole("heading", { name: "About", level: 1 })).toBeVisible()
  await expect(page.getByRole("heading", { name: "About the data" })).toBeVisible()
  await expect(page.locator('[data-camera-distance="45"]')).toHaveAttribute("data-render-mode", "physics")
  await expect(page.locator('[data-camera-distance="45"] canvas')).toBeAttached()
  await expect(page.locator(".lanyard-fallback--unavailable")).toHaveCount(0)
  const card = await waitForPhysicalCard(page)
  await expect(card).toContainText("Ata Selekoglu")
  await expect(card).toContainText("Developer")
  await expect(page.locator(".pc-handle, .pc-status, .pc-contact-btn, .pc-mini-avatar, .pc-behind")).toHaveCount(0)

  const layout = await page.locator(".about-page__developer").evaluate(element => {
    const style = getComputedStyle(element)
    const pageStyle = getComputedStyle(element.closest(".about-page")!)
    return {
      background: style.backgroundImage,
      borderTopWidth: style.borderTopWidth,
      boxShadow: style.boxShadow,
      pageDisplay: pageStyle.display,
    }
  })
  expect(layout).toEqual({
    background: "none",
    borderTopWidth: "0px",
    boxShadow: "none",
    pageDisplay: "block",
  })

  const csp = response?.headers()["content-security-policy"] ?? ""
  expect(csp).toContain("script-src 'self' 'wasm-unsafe-eval'")
  expect(csp).not.toContain(" 'unsafe-eval'")
  expect(pageErrors).toEqual([])
})

test("drags the DOM badge without navigating, then keeps click and keyboard activation", async ({ context, page }) => {
  await context.route("https://aselekoglu.github.io/**", route => route.fulfill({
    status: 200,
    contentType: "text/html",
    body: "<title>Ata Selekoglu</title>",
  }))
  const popups: Page[] = []
  page.on("popup", popup => popups.push(popup))
  await page.goto("/#about")
  const card = await waitForPhysicalCard(page)
  const initial = await card.boundingBox()
  expect(initial).not.toBeNull()

  await page.mouse.move(initial!.x + initial!.width / 2, initial!.y + initial!.height / 2)
  await expect(card).toHaveCSS("cursor", "grab")
  await page.mouse.down()
  await page.mouse.move(initial!.x + initial!.width / 2 + 86, initial!.y + initial!.height / 2 + 26, { steps: 8 })
  await expect(card).toHaveAttribute("data-drag-state", "dragging")
  await page.mouse.up()
  await expect(card).toHaveAttribute("data-drag-state", "idle")
  await page.waitForTimeout(350)
  expect(popups).toHaveLength(0)
  await expect(page).toHaveURL(/#about$/)

  const clickPopupPromise = page.waitForEvent("popup")
  await card.click()
  const clickPopup = await clickPopupPromise
  await expect(clickPopup).toHaveURL(/aselekoglu\.github\.io\/.*utm_source=geds-career-atlas/)
  await clickPopup.close()

  await card.focus()
  const keyboardPopupPromise = page.waitForEvent("popup")
  await page.keyboard.press("Enter")
  const keyboardPopup = await keyboardPopupPromise
  await expect(keyboardPopup).toHaveURL(/aselekoglu\.github\.io\/.*utm_source=geds-career-atlas/)
  await keyboardPopup.close()
})

test("keeps the scaled mobile Lanyard clear of the heading and avoids overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/#about")

  await expect(page.locator('meta[name="viewport"]')).toHaveAttribute("content", "width=device-width, initial-scale=1")
  await expect(page.locator('[data-camera-distance="45"] canvas')).toBeAttached()
  const card = await waitForPhysicalCard(page)
  const cardBounds = await card.boundingBox()
  const headingBounds = await page.getByRole("heading", { name: "About", level: 1 }).boundingBox()
  const overlayBounds = await page.locator(".about-page__developer").boundingBox()
  expect(cardBounds).not.toBeNull()
  expect(headingBounds).not.toBeNull()
  expect(overlayBounds).not.toBeNull()
  expect(overlayBounds!.y).toBeLessThan(0)
  expect(cardBounds!.width).toBeGreaterThan(150)
  expect(cardBounds!.width).toBeLessThan(210)

  const overlapsHeading = !(
    cardBounds!.x >= headingBounds!.x + headingBounds!.width ||
    cardBounds!.x + cardBounds!.width <= headingBounds!.x ||
    cardBounds!.y >= headingBounds!.y + headingBounds!.height ||
    cardBounds!.y + cardBounds!.height <= headingBounds!.y
  )
  expect(overlapsHeading).toBe(false)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})

test("uses the same real Profile Card as the reduced-motion fallback", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" })
  await page.goto("/#about")

  await expect(page.locator('[data-camera-distance="45"]')).toHaveAttribute("data-render-mode", "reduced-motion")
  await expect(page.locator('[data-camera-distance="45"] canvas')).toHaveCount(0)
  const card = page.getByRole("link", { name: "Visit Ata Selekoglu's website" })
  await expect(card).toBeVisible()
  await expect(card).toHaveAttribute("data-profile-interactive", "false")
  await expect(card).toHaveCSS("cursor", "pointer")
  await expect(card).toHaveCSS("touch-action", "pan-y")
})
