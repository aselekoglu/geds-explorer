import { useLanguage } from "../../i18n/i18n"

export type AtlasMeta = {
  snapshot_id: string
  taxonomy_version: string
  quality_status: string
  as_of_at: string
  people_count: number
  org_units_count: number
  departments_count: number
}

export function DataMethodology({ meta }: { meta: AtlasMeta }) {
  const { t, formatDate, formatNumber } = useLanguage()
  const quality = meta.quality_status.replaceAll("_", " ")
  return <section className="methodology" aria-labelledby="about-data-heading">
    <p className="eyebrow">{t("about.eyebrow")}</p>
    <h2 id="about-data-heading">{t("about.title")}</h2>
    <p className="methodology-intro">{t("about.intro")}</p>
    <dl className="methodology-facts">
      <div><dt>{t("about.snapshot")}</dt><dd>{t("about.asOf", { date: formatDate(meta.as_of_at) })}</dd></div>
      <div><dt>ID</dt><dd><code>{meta.snapshot_id.slice(0, 16)}</code></dd></div>
    </dl>
    <p>{t("about.scale", { people: formatNumber(meta.people_count), orgs: formatNumber(meta.org_units_count), departments: formatNumber(meta.departments_count) })}</p>
    <article><h3>{t("about.lineageTitle")}</h3><p>{t("about.lineage", { quality })}</p><p role="note">{t("about.fallback")}</p></article>
    <article><h3>{t("about.matchingTitle")}</h3><p>{t("about.matching", { version: meta.taxonomy_version })}</p></article>
    <article><h3>{t("about.privacyTitle")}</h3><p>{t("about.privacy")}</p></article>
    <article><h3>{t("about.vacancyTitle")}</h3><p>{t("about.vacancy")}</p></article>
    <article><h3>{t("about.limitsTitle")}</h3><p>{t("about.limits")}</p></article>
    <a href="https://geds-sage.gc.ca/en/GEDS" target="_blank" rel="noreferrer">{t("about.official")}</a>
  </section>
}
