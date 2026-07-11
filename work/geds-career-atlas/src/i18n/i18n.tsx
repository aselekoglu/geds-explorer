import { createContext, useContext, useMemo, useState, type ReactNode } from "react"
import { en } from "./en"
import { fr } from "./fr"

export type Language = "en" | "fr"
interface Dictionary { [key: string]: string | Dictionary }
type Values = Record<string, string | number>

type LanguageContextValue = {
  language: Language
  setLanguage: (language: Language) => void
  t: (key: string, values?: Values) => string
  formatNumber: (value: number) => string
  formatDate: (value: string | Date) => string
}

const dictionaries: Record<Language, Dictionary> = { en, fr }
const LanguageContext = createContext<LanguageContextValue | null>(null)

export function flatten(dictionary: Dictionary, prefix = ""): Record<string, string> {
  return Object.entries(dictionary).reduce<Record<string, string>>((result, [key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (typeof value === "string") result[path] = value
    else Object.assign(result, flatten(value, path))
    return result
  }, {})
}

const getInitialLanguage = (): Language => new URLSearchParams(location.search).get("lang") === "fr" ? "fr" : "en"

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, updateLanguage] = useState<Language>(getInitialLanguage)
  const value = useMemo<LanguageContextValue>(() => {
    const messages = flatten(dictionaries[language])
    return {
      language,
      setLanguage(next) {
        const params = new URLSearchParams(location.search)
        params.set("lang", next)
        history.replaceState(null, "", `${location.pathname}?${params}${location.hash}`)
        updateLanguage(next)
      },
      t(key, values = {}) {
        const template = messages[key]
        if (!template) return key
        return Object.entries(values).reduce((copy, [name, replacement]) => copy.replaceAll(`{${name}}`, String(replacement)), template)
      },
      formatNumber: value => new Intl.NumberFormat(language === "fr" ? "fr-CA" : "en-CA").format(value),
      formatDate: value => new Intl.DateTimeFormat(language === "fr" ? "fr-CA" : "en-CA", { dateStyle: "long", timeZone: "UTC" }).format(new Date(value)),
    }
  }, [language])
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  const value = useContext(LanguageContext)
  if (value) return value
  const messages = flatten(en)
  return {
    language: "en" as const,
    setLanguage: () => undefined,
    t: (key: string, values: Values = {}) => Object.entries(values).reduce((copy, [name, replacement]) => copy.replaceAll(`{${name}}`, String(replacement)), messages[key] ?? key),
    formatNumber: (number: number) => new Intl.NumberFormat("en-CA").format(number),
    formatDate: (date: string | Date) => new Intl.DateTimeFormat("en-CA", { dateStyle: "long", timeZone: "UTC" }).format(new Date(date)),
  }
}
