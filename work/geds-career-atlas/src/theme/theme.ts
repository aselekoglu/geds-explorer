export type ThemeChoice="light"|"dark"|"system"
export type ResolvedTheme="light"|"dark"
export const CAREER_THEME_KEY="geds-career-theme"
export function resolveTheme(choice:ThemeChoice):ResolvedTheme{return choice==="system"&&globalThis.matchMedia?.("(prefers-color-scheme: dark)").matches?"dark":choice==="dark"?"dark":"light"}
export function readThemeChoice():ThemeChoice{const saved=localStorage.getItem(CAREER_THEME_KEY);return saved==="dark"||saved==="system"||saved==="light"?saved:"light"}
export function applyTheme(choice:ThemeChoice){document.documentElement.dataset.theme=resolveTheme(choice)}
export function initializeTheme(){applyTheme(readThemeChoice())}
