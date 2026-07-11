import type { LeadSuggestion, VacancySignal } from "../../api/types"
import { CareerConversationLeads } from "./CareerConversationLeads"
import { useLanguage } from "../../i18n/i18n"

type ProfileFacts = { org_id: string; department_name: string; canonical_path: string[]; direct_people_count: number; descendant_people_count: number; child_count: number; snapshot_id: string; snapshot_as_of?: string; conversation_leads?: LeadSuggestion[]; vacancy_signals?: VacancySignal[] }

export function TeamProfile({ name, roles, profile }: { name: string; roles: string[]; profile?: ProfileFacts }) {
  const { t, formatNumber } = useLanguage()
  return <section aria-label={`${name} team profile`}>
    <p className="eyebrow">{t("profile.eyebrow")}</p><h2>{name}</h2>
    {profile && <><p>{profile.canonical_path.join(" / ")}</p><dl><div><dt>{t("profile.observedPeople")}</dt><dd>{formatNumber(profile.direct_people_count)}</dd></div><div><dt>{t("profile.branchPeople")}</dt><dd>{formatNumber(profile.descendant_people_count)}</dd></div><div><dt>{t("profile.childTeams")}</dt><dd>{formatNumber(profile.child_count)}</dd></div></dl></>}
    <h3>{t("profile.rolesTitle")}</h3><p>{t("profile.rolesIntro")}</p><ul>{roles.map(role => <li key={role}>{role}</li>)}</ul>
    <h3>{t("profile.matchedTitle")}</h3><p>{t("profile.matchedIntro")}</p>
    {profile && <CareerConversationLeads leads={profile.conversation_leads ?? []} vacancies={profile.vacancy_signals ?? []} snapshotAsOf={profile.snapshot_as_of ?? profile.snapshot_id} />}
    <p role="note">{t("profile.vacancyNote")}</p>
  </section>
}
