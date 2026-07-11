import { useLanguage } from "../../i18n/i18n"

const tours = [
  { id: "ai", query: "AI", title: "toursLegacy.aiTitle", description: "toursLegacy.aiDescription" },
  { id: "policy", query: "policy", title: "toursLegacy.policyTitle", description: "toursLegacy.policyDescription" },
  { id: "cyber", query: "cybersecurity", title: "toursLegacy.cyberTitle", description: "toursLegacy.cyberDescription" },
]

export function Tours() {
  const { t } = useLanguage()
  return <section aria-label={t("toursLegacy.label")}><h1>{t("toursLegacy.title")}</h1><ul>{tours.map(tour => <li key={tour.id}><a href={`?q=${encodeURIComponent(tour.query)}&mode=org-walk`}>{t(tour.title)}</a><p>{t(tour.description)}</p></li>)}</ul></section>
}
