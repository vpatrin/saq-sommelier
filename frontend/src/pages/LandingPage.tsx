import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { Navigate } from 'react-router'
import { Fragment, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import {
  MagnifyingGlassIcon,
  EyeIcon,
  BookOpenIcon,
  HouseIcon,
  GithubLogoIcon,
} from '@phosphor-icons/react'

const CONTACT_EMAIL = 'victor.patrin@protonmail.com'

const STATS = [
  { value: '14 000+', labelKey: 'landing.stats.wines' },
  { value: '400+', labelKey: 'landing.stats.stores' },
  { value: '~2s', labelKey: 'landing.stats.llm' },
  { value: '24h', labelKey: 'landing.stats.sync' },
] as const

const FEATURES = [
  {
    icon: MagnifyingGlassIcon,
    titleKey: 'landing.features.catalog.title',
    descKey: 'landing.features.catalog.desc',
  },
  {
    icon: EyeIcon,
    titleKey: 'landing.features.watchlist.title',
    descKey: 'landing.features.watchlist.desc',
  },
  {
    icon: BookOpenIcon,
    titleKey: 'landing.features.journal.title',
    descKey: 'landing.features.journal.desc',
  },
  {
    icon: HouseIcon,
    titleKey: 'landing.features.cellar.title',
    descKey: 'landing.features.cellar.desc',
  },
] as const

const RAG_STEPS = [
  {
    num: '01',
    titleKey: 'landing.rag.step1.title',
    detailKey: 'landing.rag.step1.detail',
    codeKey: 'landing.rag.step1.code',
  },
  {
    num: '02',
    titleKey: 'landing.rag.step2.title',
    detailKey: 'landing.rag.step2.detail',
    codeKey: 'landing.rag.step2.code',
  },
  {
    num: '03',
    titleKey: 'landing.rag.step3.title',
    detailKey: 'landing.rag.step3.detail',
    codeKey: 'landing.rag.step3.code',
  },
  {
    num: '04',
    titleKey: 'landing.rag.step4.title',
    detailKey: 'landing.rag.step4.detail',
    codeKey: 'landing.rag.step4.code',
  },
  {
    num: '05',
    titleKey: 'landing.rag.step5.title',
    detailKey: 'landing.rag.step5.detail',
    codeKey: 'landing.rag.step5.code',
    result: '✓ Château Pesquié Terrasses 2022 — 18,95 $ · 1.8s',
  },
  {
    num: '06',
    titleKey: 'landing.rag.step6.title',
    detailKey: 'landing.rag.step6.detail',
    codeKey: 'landing.rag.step6.code',
  },
] as const

interface GitHubCommit {
  sha: string
  commit: { message: string; author: { date: string } }
}

interface RepoData {
  commits: { message: string; timeAgo: string }[]
  loading: boolean
}

interface DeployInfo {
  version: string
  timeAgo: string
}

const GH_API = 'https://api.github.com'
const CHANGELOG = [
  { version: '1.5.2', date: '2026-03-24', titleKey: 'landing.changelog.v152' },
  { version: '1.5.1', date: '2026-03-21', titleKey: 'landing.changelog.v151' },
  { version: '1.5.0', date: '2026-03-19', titleKey: 'landing.changelog.v150' },
  { version: '1.4.0', date: '2026-03-12', titleKey: 'landing.changelog.v140' },
] as const

const REPOS = [
  { owner: 'vpatrin', name: 'coupette', desc: 'FastAPI · React · RAG · Telegram bot' },
  { owner: 'vpatrin', name: 'infra', desc: 'Caddy · Docker · Monitoring · Hardening' },
] as const

function formatTimeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (seconds < 60) return '<1min'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  return `${days}d`
}

const INITIAL_REPOS: Record<string, RepoData> = Object.fromEntries(
  REPOS.map((repo) => [`${repo.owner}/${repo.name}`, { commits: [], loading: true }]),
)

function useGitHubData() {
  const [repos, setRepos] = useState<Record<string, RepoData>>(INITIAL_REPOS)
  const [deploy, setDeploy] = useState<DeployInfo | null>(null)

  useEffect(() => {
    let cancelled = false

    fetch(`${GH_API}/repos/vpatrin/coupette/tags?per_page=1`)
      .then((r) => (r.ok ? r.json() : []))
      .then(async (tags: { name: string; commit: { url: string } }[]) => {
        if (cancelled || !tags.length) return
        const commitRes = await fetch(tags[0].commit.url)
        if (!commitRes.ok) return
        const commitData = await commitRes.json()
        const date = commitData.commit?.author?.date
        if (!cancelled && date) {
          setDeploy({ version: tags[0].name, timeAgo: formatTimeAgo(date) })
        }
      })
      .catch(() => {})

    for (const repo of REPOS) {
      const key = `${repo.owner}/${repo.name}`

      fetch(`${GH_API}/repos/${repo.owner}/${repo.name}/commits?per_page=4`)
        .then((r) => (r.ok ? r.json() : []))
        .then((commits: GitHubCommit[]) => {
          if (cancelled) return
          setRepos((prev) => ({
            ...prev,
            [key]: {
              loading: false,
              commits: commits.map((c) => ({
                message: c.commit.message.split('\n')[0],
                timeAgo: formatTimeAgo(c.commit.author.date),
              })),
            },
          }))
        })
        .catch(() => {
          if (!cancelled) setRepos((prev) => ({ ...prev, [key]: { commits: [], loading: false } }))
        })
    }

    return () => {
      cancelled = true
    }
  }, [])

  return { repos, deploy }
}

/* Content width — matches nav container for alignment */
const SECTION = 'max-w-6xl mx-auto w-full px-8'

// null = form not yet opened; 'idle' | 'loading' | 'success' | 'error' = form visible
type FormState = 'idle' | 'loading' | 'success' | 'error'

function LandingPage() {
  const { t, i18n } = useTranslation()
  const { token } = useAuth()
  const { repos, deploy } = useGitHubData()
  const [formState, setFormState] = useState<FormState | null>(null)
  const [email, setEmail] = useState('')
  const heroRef = useRef<HTMLElement>(null)

  const toggleLang = () => {
    i18n.changeLanguage(i18n.resolvedLanguage === 'fr' ? 'en' : 'fr')
  }

  const openForm = () => {
    setFormState('idle')
    heroRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (formState === 'loading') return
    setFormState('loading')
    try {
      await api('/waitlist', { method: 'POST', body: JSON.stringify({ email }) })
      setEmail('')
      setFormState('success')
    } catch {
      setFormState('error')
    }
  }

  if (token) return <Navigate to="/chat" replace />

  const mailtoHref = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(t('landing.mailto.subject'))}&body=${encodeURIComponent(t('landing.mailto.body'))}`

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Nav */}
      <nav className="fixed top-0 inset-x-0 z-50 bg-background/60 backdrop-blur-xl border-b border-border">
        <div className="max-w-6xl mx-auto w-full px-8 flex items-center justify-between py-3.5">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-7.5 h-7.5 rounded-lg bg-gradient-to-br from-primary/35 to-primary/15 flex items-center justify-center text-sm font-semibold text-primary">
              C
            </div>
            <span className="text-base font-medium">{t('brand')}</span>
          </Link>
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={toggleLang}
              className="w-8 text-center text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {i18n.resolvedLanguage === 'fr' ? 'EN' : 'FR'}
            </button>
            <Link
              to="/login"
              className="min-w-24 text-center text-[length:var(--text-sidebar)] text-muted-foreground hover:text-foreground transition-colors"
            >
              {t('landing.nav.login')}
            </Link>
            <button
              type="button"
              onClick={openForm}
              className="min-w-44 text-center px-4 py-2 rounded-xl bg-primary/15 border border-primary/20 text-primary text-sm font-medium hover:bg-primary/25 transition-colors"
            >
              {t('landing.nav.requestAccess')}
            </button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section ref={heroRef} className="pt-44 pb-28">
        <div className={`${SECTION}`}>
          <h1 className="text-5xl md:text-7xl font-extralight leading-[1.08] tracking-tight mb-6 max-w-3xl">
            {t('landing.hero.title.before')}{' '}
            <span className="text-primary font-light">{t('landing.hero.title.accent')}</span>
            <br />
            {t('landing.hero.title.afterBefore')}{' '}
            <strong className="font-semibold">{t('landing.hero.title.afterBold')}</strong>
            {t('landing.hero.title.afterEnd')}
          </h1>

          <p className="text-base font-light text-foreground/80 max-w-lg leading-relaxed mb-10">
            {t('landing.hero.subtitle')}
          </p>

          {/* CTA */}
          {formState === null && (
            <div className="flex items-center gap-6 mb-3">
              <button
                type="button"
                onClick={openForm}
                className="px-6 py-3 rounded-xl bg-primary/15 border border-primary/20 text-primary text-sm font-medium hover:bg-primary/25 transition-colors"
              >
                {t('landing.hero.cta')}
              </button>
              <Link
                to="/login"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                {t('landing.hero.signin')}
              </Link>
            </div>
          )}
          {formState !== null && formState !== 'success' && (
            <form onSubmit={handleSubmit} className="flex items-center gap-3 mb-3">
              <input
                type="email"
                required
                autoFocus
                aria-label={t('landing.hero.formPlaceholder')}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t('landing.hero.formPlaceholder')}
                disabled={formState === 'loading'}
                className="px-4 py-3 rounded-xl bg-card border border-border text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50 disabled:opacity-50 w-72"
              />
              <button
                type="submit"
                disabled={formState === 'loading'}
                className="px-5 py-3 rounded-xl bg-primary/15 border border-primary/20 text-primary text-sm font-medium hover:bg-primary/25 transition-colors disabled:opacity-50"
              >
                {formState === 'loading'
                  ? t('landing.hero.formSubmitting')
                  : t('landing.hero.formSubmit')}
              </button>
              {formState === 'error' && (
                <span className="text-xs text-destructive">{t('landing.hero.formError')}</span>
              )}
            </form>
          )}
          {formState === 'success' && (
            <p className="text-sm text-primary mb-3">{t('landing.hero.formSuccess')}</p>
          )}
          <p className="text-xs text-muted-foreground mb-12">
            {formState !== 'success' && t('landing.hero.betaNote')}
          </p>
        </div>

        {/* Chat preview — flush with content, bottom fade */}
        <div className={`${SECTION} relative`}>
          <div className="rounded-2xl border border-border/50 bg-card/30 overflow-hidden">
            {/* Browser chrome */}
            <div className="h-9 flex items-center px-3.5 gap-1.5 bg-surface-hover border-b border-border/50">
              <span className="w-2.5 h-2.5 rounded-full bg-[rgba(255,255,255,0.08)]" />
              <span className="w-2.5 h-2.5 rounded-full bg-[rgba(255,255,255,0.08)]" />
              <span className="w-2.5 h-2.5 rounded-full bg-[rgba(255,255,255,0.08)]" />
              <span className="flex-1 text-center font-mono text-[length:var(--text-sidebar-xs)] text-muted-foreground">
                coupette.club
              </span>
            </div>

            <div className="p-5 md:p-6 flex flex-col gap-3.5">
              {/* User message */}
              <div className="flex flex-col items-end">
                <div className="max-w-[75%] px-4 py-2.5 rounded-2xl rounded-br-sm bg-primary/10 border border-primary/12 text-[length:var(--text-sidebar)] leading-relaxed">
                  {t('landing.preview.userMsg')}
                </div>
              </div>

              {/* Bot response */}
              <div className="flex flex-col items-start">
                <div className="max-w-[88%] px-4 py-3.5 rounded-2xl rounded-tl-sm bg-card/50 border border-border/50 text-[length:var(--text-sidebar)] font-light leading-relaxed text-muted-foreground">
                  {/* SSE pipeline trace */}
                  <div className="font-mono text-[length:var(--text-sidebar-xs)] leading-relaxed mb-3 px-3 py-2.5 rounded-lg bg-[rgba(0,0,0,0.3)] border border-[rgba(255,255,255,0.03)]">
                    <div>
                      <span className="text-primary">›</span> query: rouge, ≤25$, pâtes, épicé
                    </div>
                    <div> intent_route: pairing → sql_filter</div>
                    <div> pgvector: cosine_sim top_k=8 → mmr_rerank</div>
                    <div>
                      <span className="text-green-500">✓</span> 3 candidates · 1.8s
                    </div>
                  </div>

                  <p className="mb-3">{t('landing.preview.botIntro')}</p>

                  {/* Wine card */}
                  <div className="p-3.5 rounded-xl bg-[rgba(255,255,255,0.025)] border border-border/50 relative overflow-hidden">
                    <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-primary/4 to-transparent pointer-events-none" />
                    <div className="flex justify-between gap-3 relative">
                      <div>
                        <div className="text-sm font-medium text-foreground mb-1.5">
                          Château Pesquié Terrasses 2022
                        </div>
                        <div className="flex gap-1 flex-wrap mb-1">
                          <span className="text-[9px] px-2 py-0.5 rounded bg-primary/10 text-primary">
                            Rouge
                          </span>
                          <span className="text-[9px] px-2 py-0.5 rounded bg-[rgba(255,255,255,0.04)] text-muted-foreground">
                            Ventoux
                          </span>
                          <span className="text-[9px] px-2 py-0.5 rounded bg-[rgba(255,255,255,0.04)] text-muted-foreground">
                            Grenache · Syrah
                          </span>
                        </div>
                        <span className="font-mono text-[9px] text-muted-foreground">
                          SAQ 10264381
                        </span>
                      </div>
                      <span className="text-lg font-light text-primary whitespace-nowrap">
                        18,95 $
                      </span>
                    </div>
                    <p className="text-xs font-light text-muted-foreground mt-2.5 pt-2.5 border-t border-border/50 leading-relaxed">
                      {t('landing.preview.tastingNote')}
                    </p>
                  </div>
                </div>
              </div>

              {/* Fake input */}
              <div className="flex items-center gap-3 px-4 py-2.5 rounded-2xl border border-border/50 bg-[rgba(255,255,255,0.02)]">
                <span className="flex-1 text-[length:var(--text-sidebar)] font-light text-muted-foreground">
                  {t('landing.preview.placeholder')}
                </span>
                <div className="w-7 h-7 rounded-lg bg-primary/20 flex items-center justify-center text-primary text-xs">
                  ↑
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Stats banner */}
      <div className="w-full border-y border-border bg-[rgba(255,255,255,0.012)]">
        <div className="flex items-center justify-center gap-16 py-8">
          {STATS.map(({ value, labelKey }) => (
            <div key={labelKey} className="text-center">
              <div className="text-2xl font-semibold tabular-nums">{value}</div>
              <div className="text-sm text-muted-foreground mt-0.5">{t(labelKey)}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Features */}
      <section className="pt-28 pb-28">
        <div className={`${SECTION}`}>
          <div className="grid grid-cols-2 gap-16 mb-16">
            <h2 className="text-4xl font-medium text-foreground leading-tight">
              {t('landing.features.title')
                .split(' ')
                .map((word, i) => (
                  <Fragment key={i}>
                    {word}
                    <br />
                  </Fragment>
                ))}
            </h2>
            <p className="text-lg font-light text-foreground leading-relaxed pt-2 whitespace-pre-line">
              {t('landing.features.subtitle')}
            </p>
          </div>
          <div className="grid grid-cols-4 w-full">
            {FEATURES.map(({ icon: Icon, titleKey, descKey }, i) => (
              <div
                key={titleKey}
                className={`py-2 ${i === 0 ? 'pr-8' : i === 3 ? 'pl-8 border-l border-border/50' : 'px-8 border-l border-border/50'}`}
              >
                <div className="font-mono text-xs text-muted-foreground tracking-widest mb-10">
                  FIG 0.{i + 1}
                </div>
                <div className="flex items-center gap-3 mb-3">
                  <Icon size={22} weight="light" className="text-primary" />
                  <span className="text-base font-semibold">{t(titleKey)}</span>
                </div>
                <div className="text-sm font-light text-muted-foreground leading-relaxed">
                  {t(descKey)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* RAG Pipeline */}
      <section className="pt-20 pb-28">
        <div className={`${SECTION}`}>
          {/* Split header: title left, subtitle right */}
          <div className="grid grid-cols-2 gap-16 mb-16">
            <h2 className="text-4xl font-light text-foreground">
              {t('landing.rag.title.before')}{' '}
              <strong className="font-semibold">{t('landing.rag.title.bold')}</strong>
            </h2>
            <p className="text-lg font-light text-foreground leading-relaxed pt-2">
              {t('landing.rag.subtitle')}
            </p>
          </div>

          {/* Row 1: 01 → 02 → 03 */}
          <div className="grid grid-cols-[1fr_auto_1fr_auto_1fr] items-stretch">
            {RAG_STEPS.slice(0, 3).map((step, i) => (
              <Fragment key={step.num}>
                <div className="rag-card p-6 min-h-[168px]">
                  <span className="font-mono text-xs font-semibold text-primary drop-shadow-[0_0_8px_oklch(0.7_0.13_65_/_40%)]">
                    {step.num}
                  </span>
                  <div className="text-[15px] font-semibold mt-4 mb-2">{t(step.titleKey)}</div>
                  <div className="font-mono text-xs text-muted-foreground leading-relaxed">
                    {t(step.detailKey)}
                  </div>
                  {t(step.codeKey) && (
                    <div className="font-mono text-xs text-primary/80 mt-2">{t(step.codeKey)}</div>
                  )}
                </div>
                {i < 2 && (
                  <div className="flex items-center justify-center w-10">
                    <svg width="32" height="16" viewBox="0 0 32 16" className="rag-arrow">
                      <line x1="0" y1="8" x2="24" y2="8" stroke="currentColor" strokeWidth="1" />
                      <polyline
                        points="20,4 26,8 20,12"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1"
                      />
                    </svg>
                  </div>
                )}
              </Fragment>
            ))}
          </div>

          {/* ↓ connector under col 3 */}
          <div className="grid grid-cols-[1fr_auto_1fr_auto_1fr]">
            <div className="col-start-5 flex justify-center py-2">
              <svg width="16" height="24" viewBox="0 0 16 24" className="rag-arrow">
                <line x1="8" y1="0" x2="8" y2="18" stroke="currentColor" strokeWidth="1" />
                <polyline
                  points="4,14 8,20 12,14"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1"
                />
              </svg>
            </div>
          </div>

          {/* Row 2: 06 ← 05 ← 04 (reversed so 06 is under 01) */}
          <div className="grid grid-cols-[1fr_auto_1fr_auto_1fr] items-stretch">
            {[RAG_STEPS[5], RAG_STEPS[4], RAG_STEPS[3]].map((step, i) => (
              <Fragment key={step.num}>
                <div className="rag-card p-6 min-h-[168px]">
                  <span className="font-mono text-xs font-semibold text-primary drop-shadow-[0_0_8px_oklch(0.7_0.13_65_/_40%)]">
                    {step.num}
                  </span>
                  <div className="text-[15px] font-semibold mt-4 mb-2">{t(step.titleKey)}</div>
                  <div className="font-mono text-xs text-muted-foreground leading-relaxed">
                    {t(step.detailKey)}
                  </div>
                  {t(step.codeKey) && (
                    <div className="font-mono text-xs text-primary/80 mt-2">{t(step.codeKey)}</div>
                  )}
                  {'result' in step && step.result && (
                    <div className="font-mono text-xs text-green-500 mt-2">{step.result}</div>
                  )}
                </div>
                {i < 2 && (
                  <div className="flex items-center justify-center w-10">
                    <svg width="32" height="16" viewBox="0 0 32 16" className="rag-arrow">
                      <line x1="8" y1="8" x2="32" y2="8" stroke="currentColor" strokeWidth="1" />
                      <polyline
                        points="12,4 6,8 12,12"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1"
                      />
                    </svg>
                  </div>
                )}
              </Fragment>
            ))}
          </div>
        </div>
      </section>

      {/* Changelog */}
      <section className="py-28 border-t border-border">
        <div className={`${SECTION}`}>
          {/* Split header */}
          <div className="grid grid-cols-2 gap-16 mb-16">
            <h2 className="text-4xl font-light text-foreground">
              {t('landing.changelog.title.before')}{' '}
              <strong className="font-semibold">{t('landing.changelog.title.bold')}</strong>
            </h2>
            <p className="text-lg font-light text-foreground leading-relaxed pt-2">
              {t('landing.changelog.subtitle')}
            </p>
          </div>

          {/* Timeline */}
          <div className="relative">
            {/* Horizontal line */}
            <div className="absolute top-3 left-0 right-0 h-px bg-border/50" />

            <div className="grid grid-cols-4 gap-6">
              {CHANGELOG.map(({ version, date, titleKey }, i) => (
                <div key={version} className="relative pt-8">
                  {/* Dot on timeline */}
                  <div
                    className={`absolute top-1.5 left-0 w-3 h-3 rounded-full border-2 ${i === 0 ? 'bg-primary border-primary shadow-[0_0_8px_oklch(0.7_0.13_65_/_40%)]' : 'bg-background border-border'}`}
                  />
                  <div className="text-base font-semibold mb-1">{version}</div>
                  <p className="text-sm font-light text-muted-foreground leading-relaxed mb-3">
                    {t(titleKey)}
                  </p>
                  <span className="font-mono text-xs text-muted-foreground">{date}</span>
                </div>
              ))}
            </div>
          </div>

          <a
            href="https://github.com/vpatrin/coupette/blob/main/CHANGELOG.md"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 mt-8 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            {t('landing.changelog.seeAll')} <span>→</span>
          </a>
        </div>
      </section>

      {/* Open Source */}
      <section className="pt-20 pb-28">
        <div className={`${SECTION}`}>
          {/* Split header: title left, subtitle right */}
          <div className="grid grid-cols-2 gap-16 mb-16">
            <h2 className="text-4xl font-light text-foreground">
              {t('landing.dev.title.before')}{' '}
              <strong className="font-semibold">{t('landing.dev.title.bold')}</strong>
            </h2>
            <p className="text-lg font-light text-foreground leading-relaxed pt-2">
              {t('landing.dev.subtitle')}
            </p>
          </div>

          {/* Deploy banner */}
          {deploy && (
            <div className="flex items-center justify-center gap-3 mb-5 px-5 py-2.5 rounded-lg bg-card border border-border w-full">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(80,200,120,0.4)]" />
              <span className="font-mono text-xs text-muted-foreground">
                {t('landing.dev.deployed')} ·{' '}
                <span className="text-primary font-medium">{deploy.version}</span> ·{' '}
                {deploy.timeAgo}
              </span>
            </div>
          )}

          {/* Repo cards */}
          <div className="grid grid-cols-2 gap-3.5 w-full">
            {REPOS.map((repo) => {
              const key = `${repo.owner}/${repo.name}`
              const data = repos[key]
              return (
                <div
                  key={key}
                  className="p-5 bg-card border border-border rounded-xl text-left hover:border-border-warm transition-colors"
                >
                  <a
                    href={`https://github.com/${repo.owner}/${repo.name}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 mb-3 hover:text-primary transition-colors"
                  >
                    <GithubLogoIcon size={18} className="text-muted-foreground" />
                    <div>
                      <div className="text-sm font-medium">
                        {repo.owner}/{repo.name}
                      </div>
                      <div className="font-mono text-[length:var(--text-sidebar-xs)] text-muted-foreground">
                        {repo.desc}
                      </div>
                    </div>
                  </a>

                  <div className="flex flex-col gap-1.5">
                    {data?.loading && (
                      <>
                        {[1, 2, 3].map((n) => (
                          <div
                            key={n}
                            className="h-7 rounded-md bg-[rgba(255,255,255,0.015)] animate-pulse"
                          />
                        ))}
                      </>
                    )}
                    {!data?.loading && data?.commits.length === 0 && (
                      <a
                        href={`https://github.com/${repo.owner}/${repo.name}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-muted-foreground hover:text-primary transition-colors"
                      >
                        {t('landing.dev.viewRepo')} →
                      </a>
                    )}
                    {data?.commits.map((commit, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-[rgba(255,255,255,0.015)] border border-[rgba(255,255,255,0.03)]"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                        <span className="text-xs text-muted-foreground flex-1 truncate">
                          {commit.message}
                        </span>
                        <span className="font-mono text-[9px] text-muted-foreground shrink-0">
                          {commit.timeAgo}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-14 border-t border-border">
        <div className={`${SECTION} flex flex-col items-center gap-1.5`}>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span>© 2026 Coupette</span>
            <span className="w-px h-3 bg-border" />
            <span>Montréal, QC</span>
            <span className="w-px h-3 bg-border" />
            <a href={mailtoHref} className="hover:text-foreground transition-colors">
              Contact
            </a>
            <span className="w-px h-3 bg-border" />
            <a
              href="https://www.educalcool.qc.ca/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground transition-colors"
            >
              Éduc'alcool
            </a>
          </div>
          <p className="text-[length:var(--text-sidebar-xs)] text-muted-foreground text-center">
            {t('landing.footer.legal')}
          </p>
        </div>
      </footer>
    </div>
  )
}

export default LandingPage
