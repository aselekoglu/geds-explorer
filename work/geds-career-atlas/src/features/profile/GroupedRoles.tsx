import { useLanguage } from "../../i18n/i18n"
import { groupObservedTitles } from "./titleGroups"

export function GroupedRoles({titles,onRoleQuery}:{titles:string[];onRoleQuery?:(title:string)=>void}){
  const {t}=useLanguage()
  return <div className="title-groups">{groupObservedTitles(titles).map(group=>group.empty?<details className="title-group title-group--empty" key={group.key}><summary>{t("profile.noTitle")} · {group.count}</summary><p>{t("profile.noTitleHelp")}</p></details>:<section className="title-group" key={group.key}><button type="button" aria-label={t("profile.filterByRole",{title:group.label})} onClick={()=>onRoleQuery?.(group.label)}><span>{group.label}</span><small>· {group.count}</small></button></section>)}</div>
}
