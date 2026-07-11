import type { LeadSuggestion, VacancySignal } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"

type Props = {
  leads: LeadSuggestion[]
  vacancies: VacancySignal[]
  snapshotAsOf: string
}

export function CareerConversationLeads({ leads, vacancies, snapshotAsOf }: Props) {
  const { t, formatDate } = useLanguage()
  const dateLabel = (value: string) => Number.isNaN(new Date(value).getTime()) ? value : formatDate(value)
  const kindLabel = (kind: LeadSuggestion["kind"]) => kind === "possible_team_lead" ? t("leads.possible") : t("leads.conversation")
  if (!leads.length && !vacancies.length) return null

  return <>
    {leads.length > 0 && <section aria-labelledby="career-conversation-heading" className="career-leads">
      <h3 id="career-conversation-heading">{t("leads.title")}</h3>
      <p>{t("leads.intro")}</p>
      <div className="signal-grid">
        {leads.map(lead => <article className="signal-card" key={`${lead.org_id}:${lead.source_url}`}>
          <p className="signal-label">{kindLabel(lead.kind)} · {t("common.confidence", { level: t(`common.${lead.confidence}`) })}</p>
          <h4>{lead.title}</h4>
          <ul>{lead.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
          <p className="signal-date">{t("leads.snapshot", { date: dateLabel(snapshotAsOf) })}</p>
          <a href={lead.source_url} target="_blank" rel="noreferrer">{t("leads.official")}</a>
        </article>)}
      </div>
    </section>}
    {vacancies.length > 0 && <section aria-labelledby="vacancy-signals-heading" className="career-leads">
      <h3 id="vacancy-signals-heading">{t("leads.vacancies")}</h3>
      <p>{t("leads.vacancyIntro")}</p>
      <div className="signal-grid">
        {vacancies.map(vacancy => <article className="signal-card vacancy-card" key={`${vacancy.org_id}:${vacancy.source_url}`}>
          <p className="signal-label">{vacancy.marker}</p>
          <h4>{vacancy.title}</h4>
          <strong>{t("leads.noCompetition")}</strong>
          <p className="signal-date">{t("leads.observed", { date: dateLabel(vacancy.observed_at) })}</p>
          <a href={vacancy.source_url} target="_blank" rel="noreferrer">{t("leads.vacancySource")}</a>
        </article>)}
      </div>
    </section>}
  </>
}
