const REVIEWED_ABBREVIATIONS: Record<string, string> = {
  "canadian radio-television and telecommunications commission": "CRTC",
  "canada revenue agency": "CRA",
  "employment and social development canada": "ESDC",
  "shared services canada": "SSC",
  "innovation, science and economic development canada - innovation, sciences et développement économique canada": "ISED",
  "innovation, science and economic development canada": "ISED",
  "public services and procurement canada": "PSPC",
  "fisheries and oceans canada": "DFO",
  "treasury board of canada secretariat": "TBS",
}

const CONNECTORS = new Set(["and", "of", "the", "for", "et", "de", "du", "des", "la", "le", "les", "pour"])

export function institutionAbbreviation(name: string): string {
  const normalized = name.trim().toLocaleLowerCase("en-CA")
  const reviewed = REVIEWED_ABBREVIATIONS[normalized]
  if (reviewed) return reviewed
  const words = name.match(/[\p{L}\p{N}]+/gu) ?? []
  const initials = words.filter(word => !CONNECTORS.has(word.toLocaleLowerCase("en-CA"))).map(word => word[0]?.toLocaleUpperCase("en-CA") ?? "").join("")
  if (initials) return initials.slice(0, 6)
  return words[0]?.slice(0, 6).toLocaleUpperCase("en-CA") ?? "ORG"
}

export function wrapBubbleLabel(name: string, maxCharacters: number, maxLines = 4): string[] {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (!words.length) return []
  const lines: string[] = []
  for (const word of words) {
    const last = lines.at(-1)
    if (!last) lines.push(word)
    else if (last.length + 1 + word.length <= maxCharacters && lines.length <= maxLines) lines[lines.length - 1] = `${last} ${word}`
    else if (lines.length < maxLines) lines.push(word)
    else lines[lines.length - 1] = `${last} ${word}`
  }
  return lines
}
