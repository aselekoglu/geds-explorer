import { useEffect, useState } from "react"
import { useLanguage } from "../i18n/i18n"
import { applyTheme, CAREER_THEME_KEY, readThemeChoice, resolveTheme, type ResolvedTheme } from "./theme"

export function ThemeControl(){
  const{t}=useLanguage()
  const[theme,setTheme]=useState<ResolvedTheme>(()=>resolveTheme(readThemeChoice()))
  useEffect(()=>{applyTheme(theme)},[theme])
  function toggle(){
    const next=theme==="dark"?"light":"dark"
    localStorage.setItem(CAREER_THEME_KEY,next)
    setTheme(next)
  }
  const targetLabel=theme==="dark"?t("app.themeLight"):t("app.themeDark")
  return <button className="theme-control" type="button" aria-label={`${t("app.theme")}: ${targetLabel}`} aria-pressed={theme==="dark"} onClick={toggle}>
    <span className="theme-control__icon" aria-hidden="true">{theme==="dark"?"◐":"◑"}</span>
    <span>{targetLabel}</span>
  </button>
}
