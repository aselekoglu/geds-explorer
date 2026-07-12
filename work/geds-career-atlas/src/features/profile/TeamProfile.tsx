import { useState } from "react"
import type { LeadSuggestion, SearchResult, VacancySignal } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"
import { CareerConversationLeads } from "./CareerConversationLeads"
import { RoleExplorer } from "../roles/RoleExplorer"

type ProfileFacts = { org_id: string; department_name: string; canonical_path: string[]; direct_people_count: number; descendant_people_count: number; child_count: number; snapshot_id: string; snapshot_as_of?: string; quality_status?: string; source_url?: string; conversation_leads?: LeadSuggestion[]; vacancy_signals?: VacancySignal[] }
type RelatedTeam = { org_id: string; name: string }

export function TeamProfile({ name, roles, roleItems = [], profile, relatedTeams = [] }: { name: string; roles: string[]; roleItems?: SearchResult["items"]; profile?: ProfileFacts; relatedTeams?: RelatedTeam[] }) {
  const { t, formatDate, formatNumber } = useLanguage()
  const [copied, setCopied] = useState(false)
  async function copyIssueReport() {
    if (!profile) return
    const report = [`Organization ID: ${profile.org_id}`, `Snapshot ID: ${profile.snapshot_id}`, `Observed organization: ${name}`, `Observed titles: ${roles.join(" | ")}`, `Source URL: ${profile.source_url ?? "unavailable"}`, "Correction description:", ""].join("\n")
    await navigator.clipboard.writeText(report)
    setCopied(true)
  }
  return <section aria-label={`${name} team profile`}>
    <p className="eyebrow">{t("profile.eyebrow")}</p><h2>{name}</h2>
    {profile && <><p>{profile.canonical_path.join(" / ")}</p><dl><div><dt>{t("profile.observedPeople")}</dt><dd>{formatNumber(profile.direct_people_count)}</dd></div><div><dt>{t("profile.branchPeople")}</dt><dd>{formatNumber(profile.descendant_people_count)}</dd></div><div><dt>{t("profile.childTeams")}</dt><dd>{formatNumber(profile.child_count)}</dd></div></dl>{profile.snapshot_as_of && <p>{t("profile.snapshot", { date: formatDate(profile.snapshot_as_of) })}</p>}{profile.quality_status && profile.quality_status !== "complete" && <p role="note">{t("profile.qualityWarning")}</p>}{profile.source_url && <p><a href={profile.source_url} target="_blank" rel="noreferrer">{t("profile.officialOrg")}</a></p>}</>}
    <h3>{t("profile.rolesTitle")}</h3><p>{t("profile.rolesIntro")}</p><ul>{roles.map(role => <li key={role}>{role}</li>)}</ul>
    {roleItems.length > 0 && <RoleExplorer items={roleItems} />}
    <h3>{t("profile.matchedTitle")}</h3><p>{t("profile.matchedIntro")}</p>
    {relatedTeams.length > 0 && <section><h3>{t("profile.relatedTitle")}</h3><ul>{relatedTeams.map(team => <li key={team.org_id}><a href={`?focus=${encodeURIComponent(team.org_id)}`}>{team.name}</a></li>)}</ul></section>}
    {profile && <><button type="button" onClick={() => void copyIssueReport()}>{t("profile.issueCopy")}</button>{copied && <p role="status">{t("profile.issueCopied")}</p>}<CareerConversationLeads leads={profile.conversation_leads ?? []} vacancies={profile.vacancy_signals ?? []} snapshotAsOf={profile.snapshot_as_of ?? profile.snapshot_id} /></>}
  </section>
}
