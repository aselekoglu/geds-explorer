import { Component, lazy, Suspense, useEffect, useState, type ErrorInfo, type ReactNode } from "react"
import type { AtlasMeta } from "../features/about/DataMethodology"
import { DataMethodology } from "../features/about/DataMethodology"
import { useLanguage } from "../i18n/i18n"

type MetaClient = { meta: (signal?: AbortSignal) => Promise<AtlasMeta> }
const Lanyard = lazy(() => import("../features/about/lanyard/Lanyard"))
const StaticProfileCard = lazy(() =>
  import("../features/about/profile-card/ProfileCard").then(module => ({ default: module.ProfileCard }))
)

function LanyardFallback() {
  return <div className="lanyard-fallback" role="status" aria-label="Loading interactive lanyard">
    <span className="lanyard-fallback__band" aria-hidden="true" />
    <span className="lanyard-fallback__card" aria-hidden="true" />
  </div>
}

class LanyardErrorBoundary extends Component<{ children: ReactNode, fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(_error: Error, _info: ErrorInfo) { /* Keep the About content mounted if WebGL/WASM is unavailable. */ }
  render() {
    return this.state.failed
      ? this.props.fallback
      : this.props.children
  }
}

export function AboutPage({ client }: { client: MetaClient }) {
  const [meta, setMeta] = useState<AtlasMeta | null>(null)
  const { t } = useLanguage()
  useEffect(() => {
    const controller = new AbortController()
    client.meta(controller.signal).then(setMeta).catch(() => undefined)
    return () => controller.abort()
  }, [client])
  return <section id="about" className="about-page">
    <div className="about-page__hero">
      <header className="about-page__intro"><p className="eyebrow">{t("about.eyebrow")}</p><h1>{t("about.pageTitle")}</h1><p>{t("about.generalIntro")}</p></header>
      <aside className="about-page__developer" aria-label="Interactive developer lanyard">
        <LanyardErrorBoundary fallback={
          <Suspense fallback={<LanyardFallback />}>
            <div className="lanyard-wrapper lanyard-wrapper--static lanyard-fallback--unavailable" data-render-mode="error-fallback">
              <StaticProfileCard interactive={false} />
            </div>
          </Suspense>
        }>
          <Suspense fallback={<LanyardFallback />}><Lanyard position={[0, 0, 45]} gravity={[0, -40, 0]} /></Suspense>
        </LanyardErrorBoundary>
      </aside>
    </div>
    <div className="about-page__content">
      {meta ? <DataMethodology meta={meta} /> : <p className="about-page__loading" role="status">{t("about.loading")}</p>}
    </div>
  </section>
}
