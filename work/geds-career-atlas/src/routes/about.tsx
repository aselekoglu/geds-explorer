import { useEffect, useState } from "react"
import type { AtlasMeta } from "../features/about/DataMethodology"
import { DataMethodology } from "../features/about/DataMethodology"

type MetaClient = { meta: (signal?: AbortSignal) => Promise<AtlasMeta> }

export function AboutPage({ client }: { client: MetaClient }) {
  const [meta, setMeta] = useState<AtlasMeta | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    client.meta(controller.signal).then(setMeta).catch(() => undefined)
    return () => controller.abort()
  }, [client])
  if (!meta) return null
  return <div id="about"><DataMethodology meta={meta} /></div>
}
