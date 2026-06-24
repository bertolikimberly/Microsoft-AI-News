'use client'

import { useState, useEffect } from 'react'
import { listArticles } from '@/lib/api'
import { FONTS } from '@/constants/fonts'
import type { Palette } from '@/types'

interface ArticleRow {
  id: string
  title: string
  source: string
  time: string
  topics: string[]
}

interface Props {
  palette: Palette
  displayFont: string
  userTopics?: string[]
  onAsk: (q: string) => void
}

export default function DashboardView({ palette, displayFont, userTopics, onAsk }: Props) {
  const [articles, setArticles] = useState<ArticleRow[]>([])
  const [loading, setLoading] = useState(true)

  const topicsKey = (userTopics ?? []).join(',')

  useEffect(() => {
    setLoading(true)
    listArticles({ limit: 24, topics: userTopics?.length ? userTopics : undefined })
      .then((data) =>
        setArticles(
          data.map((a) => ({
            id: a.id,
            title: a.title,
            source: a.source,
            time: a.published_at
              ? new Date(a.published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
              : '',
            topics: a.topics ?? [],
          }))
        )
      )
      .catch(() => {})
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicsKey])

  const dateStr = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })

  const [featured, ...rest] = articles

  return (
    <div className="dash-wrap">
      <div className="dash-header">
        <p className="dash-date" style={{ color: palette.muted }}>{dateStr}</p>
        <h1 className="dash-title" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
          Today's Intelligence
        </h1>
        <p className="dash-sub" style={{ color: palette.muted }}>
          Latest stories from across the tech landscape
        </p>
      </div>

      {loading && (
        <p className="dash-empty" style={{ color: palette.muted }}>Loading…</p>
      )}

      {!loading && articles.length === 0 && (
        <p className="dash-empty" style={{ color: palette.muted }}>
          No articles yet — check back once ingestion runs.
        </p>
      )}

      {!loading && featured && (
        <>
          {/* Featured / lead story */}
          <button
            className="dash-featured"
            onClick={() => onAsk(`Tell me more about: ${featured.title}`)}
            style={{ borderColor: 'rgba(0,0,0,0.07)' }}
          >
            <span className="dash-featured-meta" style={{ color: palette.muted }}>
              {featured.source} · {featured.time}
            </span>
            <span className="dash-featured-title" style={{ color: palette.ink, fontFamily: FONTS[displayFont] }}>
              {featured.title}
            </span>
            <span className="dash-cta" style={{ color: palette.accent }}>Ask MAI →</span>
          </button>

          {/* Rest of articles in a list */}
          {rest.length > 0 && (
            <ul className="dash-list">
              {rest.map((a, i) => (
                <li key={a.id} className={`dash-item ${i === 0 ? 'dash-item-first' : ''}`}>
                  <button
                    className="dash-article"
                    onClick={() => onAsk(`Tell me more about: ${a.title}`)}
                    style={{ color: palette.ink }}
                  >
                    <span className="dash-article-meta" style={{ color: palette.muted }}>
                      {a.source} · {a.time}
                    </span>
                    <span className="dash-article-title">{a.title}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
