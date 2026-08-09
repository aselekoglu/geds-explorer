type Translate = (key: string) => string

const qualityKeys: Record<string, string> = {
  complete: "qualityStatus.complete",
  partial_overlay: "qualityStatus.partialOverlay",
  loading: "qualityStatus.loading",
  unknown: "qualityStatus.unknown",
}

const evidenceKeys: Record<string, string> = {
  ancestor: "evidenceField.ancestor",
  display_name: "evidenceField.displayName",
  organization: "evidenceField.organization",
  title: "evidenceField.title",
}

function translatedOrFallback(key: string | undefined, fallback: string, t: Translate) {
  if (!key) return fallback
  const translated = t(key)
  return translated === key ? fallback : translated
}

export function localizeQualityStatus(status: string, t: Translate) {
  return translatedOrFallback(qualityKeys[status], status.replaceAll("_", " "), t)
}

export function localizeEvidenceField(field: string, t: Translate) {
  return translatedOrFallback(evidenceKeys[field], field.replaceAll("_", " "), t)
}
