import { useEffect, useState } from "react"
import type { SearchResult, TeamProfile as TeamProfileData } from "../../api/types"
import { TeamProfile } from "./TeamProfile"
import { useLanguage } from "../../i18n/i18n"

type ProfileClient = { profile: (orgId: string, signal?: AbortSignal) => Promise<TeamProfileData>; roles: (orgId: string, signal?: AbortSignal) => Promise<SearchResult> }

export function TeamProfileLoader({ orgId, client }: { orgId: string; client: ProfileClient }) {
  const { t } = useLanguage()
  const [data, setData] = useState<{ profile: TeamProfileData; roles: SearchResult } | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    Promise.all([client.profile(orgId, controller.signal), client.roles(orgId, controller.signal)]).then(([profile, roles]) => setData({ profile, roles })).catch(value => { if (value.name !== "AbortError") setError(true) })
    return () => controller.abort()
  }, [client, orgId])
  if (error) return <p role="status">{t("profile.unavailable")}</p>
  if (!data) return <p role="status">{t("profile.loading")}</p>
  return <TeamProfile name={data.profile.name} roles={data.roles.items.map(item => item.title)} profile={data.profile} />
}
