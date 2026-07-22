import { expect, test } from "@playwright/test"
import { buildPackLayout } from "../../src/features/constellation/layout"

const median = (values: number[]) => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)]

test("layout medians stay inside real interaction budgets", () => {
  const samples = (count: number) => Array.from({ length: 5 }, () => {
    const nodes = Array.from({ length: count }, (_, index) => ({ id: `org-${index}`, name: `Organization ${index}`, value: (index % 300) + 1 }))
    const start = performance.now(); buildPackLayout(nodes, 620, 620); return performance.now() - start
  })
  const roots = samples(156)
  const maximum = samples(2000)
  console.info(`PERF root-layout-ms=${roots.join(",")}`)
  console.info(`PERF 2000-layout-ms=${maximum.join(",")}`)
  expect(median(roots), `root samples: ${roots.join(", ")}`).toBeLessThan(50)
  expect(median(maximum), `2000-node samples: ${maximum.join(", ")}`).toBeLessThan(150)
})

test("cached initial Discover is useful under 2.5 seconds and feedback appears under 150ms", async ({ page }) => {
  const useful: number[] = []
  for (let run = 0; run < 5; run += 1) {
    const started = performance.now()
    await page.goto("/?q=AI")
    const discover = page.getByRole("region", { name: "Government constellation" })
    await expect(discover.getByRole("option").first()).toBeVisible()
    useful.push(performance.now() - started)
  }
  console.info(`PERF discover-useful-ms=${useful.join(",")}`)
  expect(median(useful), `Discover samples: ${useful.join(", ")}`).toBeLessThan(2500)

  const feedback: number[] = []
  for (let run = 0; run < 5; run += 1) {
    await page.goto("/")
    await page.evaluate(() => {
      const state = window as Window & { __feedbackMs?: number }
      document.querySelector("input")!.addEventListener("input", () => {
        const started = performance.now()
        const check = () => {
          if (!document.body.textContent?.includes("Finding matching teams")) return
          state.__feedbackMs = performance.now() - started
          observer.disconnect()
        }
        const observer = new MutationObserver(check)
        observer.observe(document.body, { childList: true, characterData: true, subtree: true })
        check()
      }, { once: true })
    })
    await page.getByRole("textbox", { name: "Career interest" }).fill("AI")
    await expect(page.getByText(/Finding matching teams/)).toBeVisible()
    feedback.push(await page.evaluate(() => (window as Window & { __feedbackMs: number }).__feedbackMs))
  }
  console.info(`PERF filter-feedback-ms=${feedback.join(",")}`)
  expect(median(feedback), `feedback samples: ${feedback.join(", ")}`).toBeLessThan(150)
})

test("public API stays bounded and exposes no complete person dataset", async ({ request }) => {
  const constellation = await request.get("/api/constellation?q=AI&limit=10000")
  expect((await constellation.json()).limit).toBe(2000)
  expect((await request.get("/api/people")).status()).toBe(404)
})
