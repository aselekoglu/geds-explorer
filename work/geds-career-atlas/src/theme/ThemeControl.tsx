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
    <svg className="theme-control__icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">{theme==="dark"?<><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" strokeWidth="1.8"/><path d="M12 2v2.2M12 19.8V22M4.9 4.9l1.6 1.6M17.5 17.5l1.6 1.6M2 12h2.2M19.8 12H22M4.9 19.1l1.6-1.6M17.5 6.5l1.6-1.6" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8"/></>:<path d="M20.2 14.7A8.3 8.3 0 0 1 9.3 3.8 8.5 8.5 0 1 0 20.2 14.7Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.8"/>}</svg>
    <span>{targetLabel}</span>
  </button>
}
