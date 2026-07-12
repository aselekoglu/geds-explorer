import { useEffect, useState } from "react"
import type { OrgPage, PeoplePage, PeopleQuery, SearchResult, TeamProfile as TeamProfileData } from "../../api/types"
import { TeamProfile } from "./TeamProfile"
import { useLanguage } from "../../i18n/i18n"

type ProfileClient = { profile: (orgId: string, signal?: AbortSignal) => Promise<TeamProfileData>; roles: (orgId: string, signal?: AbortSignal) => Promise<SearchResult>; children?: (orgId:string,signal?:AbortSignal)=>Promise<OrgPage>; people?: (orgId:string,query?:PeopleQuery,signal?:AbortSignal)=>Promise<PeoplePage> }

export function TeamProfileLoader({ orgId, client }: { orgId: string; client: ProfileClient }) {
  const { t } = useLanguage()
  const [data, setData] = useState<{ profile: TeamProfileData; roles: SearchResult; children: OrgPage["items"] } | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    Promise.all([client.profile(orgId, controller.signal), client.roles(orgId, controller.signal), client.children?.(orgId,controller.signal)??Promise.resolve({items:[],snapshot_id:"",etag:""} as OrgPage)]).then(([profile, roles, children]) => setData({ profile, roles, children:children.items })).catch(value => { if (value.name !== "AbortError") setError(true) })
    return () => controller.abort()
  }, [client, orgId])
  if (error) return <p role="status">{t("profile.unavailable")}</p>
  if (!data) return <p role="status">{t("profile.loading")}</p>
  return <TeamProfile name={data.profile.name} roles={data.roles.items.map(item => item.title)} roleItems={data.roles.items} profile={data.profile} relatedTeams={data.children.map(item=>({org_id:item.org_id,name:item.name}))} peopleClient={client.people?{people:client.people.bind(client)}:undefined} />
}
