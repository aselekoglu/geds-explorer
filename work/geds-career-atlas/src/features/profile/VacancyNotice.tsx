import { en } from "../../i18n/en"
import { fr } from "../../i18n/fr"
import { flatten, useLanguage } from "../../i18n/i18n"
export function VacancyNotice({lang}:{lang?:"en"|"fr"}){const {t}=useLanguage();const copy=lang?flatten(lang==="fr"?fr:en)["profile.vacancyNote"]:t("profile.vacancyNote");return <p role="note">{copy}</p>}
