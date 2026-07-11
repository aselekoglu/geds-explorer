import { fireEvent, render, screen } from "@testing-library/react"
import { en } from "./en"
import { fr } from "./fr"
import { LanguageProvider, flatten, useLanguage } from "./i18n"

function Switcher() {
  const { language, setLanguage, t } = useLanguage()
  return <>
    <span>{t("nav.discover")}</span>
    <button type="button" onClick={() => setLanguage(language === "en" ? "fr" : "en")}>
      {language === "en" ? "Français" : "English"}
    </button>
  </>
}

it("has identical English and French key sets", () => {
  expect(Object.keys(flatten(en)).sort()).toEqual(Object.keys(flatten(fr)).sort())
})

it("preserves explorer state when language changes", async () => {
  history.replaceState(null, "", "/?q=AI&focus=org-id&categories=ai%2Cdata&lang=en")
  render(<LanguageProvider><Switcher /></LanguageProvider>)

  expect(screen.getByText("Discover")).toBeVisible()
  fireEvent.click(screen.getByRole("button", { name: "Français" }))

  expect(screen.getByText("Découvrir")).toBeVisible()
  expect(new URLSearchParams(location.search).get("q")).toBe("AI")
  expect(new URLSearchParams(location.search).get("focus")).toBe("org-id")
  expect(new URLSearchParams(location.search).get("categories")).toBe("ai,data")
  expect(new URLSearchParams(location.search).get("lang")).toBe("fr")
})

it("interpolates named values and formats numbers and dates in the active language", () => {
  history.replaceState(null, "", "/?lang=fr")
  function Sample() {
    const { t, formatNumber, formatDate } = useLanguage()
    return <p>{t("profile.people", { count: formatNumber(1234) })} · {formatDate("2026-07-09T00:00:00Z")}</p>
  }
  render(<LanguageProvider><Sample /></LanguageProvider>)

  expect(screen.getByText(/1[\s  ]234/)).toBeVisible()
  expect(screen.getByText(/9 juillet 2026/i)).toBeVisible()
})
