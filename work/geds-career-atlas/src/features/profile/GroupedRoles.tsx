import { useLanguage } from "../../i18n/i18n"
import { groupObservedTitles } from "./titleGroups"

export function GroupedRoles({titles}:{titles:string[]}){
  const {t}=useLanguage()
  return <div className="title-groups">{groupObservedTitles(titles).map(group=>group.empty?<details className="title-group title-group--empty" key={group.key}><summary>{t("profile.noTitle")} · {group.count}</summary><p>{t("profile.noTitleHelp")}</p></details>:<section className="title-group" key={group.key}><h4>{group.label} · {group.count}</h4></section>)}</div>
}
