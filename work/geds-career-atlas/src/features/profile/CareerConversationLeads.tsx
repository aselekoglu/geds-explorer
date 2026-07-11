import type { LeadSuggestion, VacancySignal } from "../../api/types"

type Props = {
  leads: LeadSuggestion[]
  vacancies: VacancySignal[]
  snapshotAsOf: string
}

const dateLabel = (value: string) => {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat("en-CA", { dateStyle: "long", timeZone: "UTC" }).format(parsed)
}

const kindLabel = (kind: LeadSuggestion["kind"]) =>
  kind === "possible_team_lead" ? "Possible team lead" : "Career conversation lead"

export function CareerConversationLeads({ leads, vacancies, snapshotAsOf }: Props) {
  if (!leads.length && !vacancies.length) return null

  return <>
    {leads.length > 0 && <section aria-labelledby="career-conversation-heading" className="career-leads">
      <h3 id="career-conversation-heading">Career conversation leads</h3>
      <p>These records appear relevant from their observed title and organization. This does not verify that they are hiring or connected to a current process.</p>
      <div className="signal-grid">
        {leads.map(lead => <article className="signal-card" key={`${lead.org_id}:${lead.source_url}`}>
          <p className="signal-label">{kindLabel(lead.kind)} · {lead.confidence} confidence</p>
          <h4>{lead.title}</h4>
          <ul>{lead.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
          <p className="signal-date">Snapshot: {dateLabel(snapshotAsOf)}</p>
          <a href={lead.source_url} target="_blank" rel="noreferrer">Open official GEDS record</a>
        </article>)}
      </div>
    </section>}
    {vacancies.length > 0 && <section aria-labelledby="vacancy-signals-heading" className="career-leads">
      <h3 id="vacancy-signals-heading">Unverified vacancy signals</h3>
      <p>A vacancy marker was observed in GEDS. GEDS is not a live jobs board, so verify any opportunity independently.</p>
      <div className="signal-grid">
        {vacancies.map(vacancy => <article className="signal-card vacancy-card" key={`${vacancy.org_id}:${vacancy.source_url}`}>
          <p className="signal-label">{vacancy.marker}</p>
          <h4>{vacancy.title}</h4>
          <strong>No live competition verified.</strong>
          <p className="signal-date">Observed {dateLabel(vacancy.observed_at)}</p>
          <a href={vacancy.source_url} target="_blank" rel="noreferrer">Open vacancy source in GEDS</a>
        </article>)}
      </div>
    </section>}
  </>
}
