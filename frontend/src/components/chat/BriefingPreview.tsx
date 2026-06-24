'use client'

import { useState, useEffect } from 'react'
import { listArticles } from '@/lib/api'
import { FONTS } from '@/constants/fonts'
import { TOPIC_GROUPS } from '@/constants/preferences'
import type { Palette, Prefs, User } from '@/types'

interface ArticlePreview {
  id: string
  source: string
  time: string
  title: string
}

function getTopicLabel(id: string): string {
  for (const g of TOPIC_GROUPS) {
    const item = g.items.find((t) => t.id === id)
    if (item) return item.label
  }
  return id
}

interface Props {
  palette: Palette
  displayFont: string
  prefs: Prefs
  user: User
  onAsk: (q: string) => void
}

export default function BriefingPreview({ palette, displayFont, prefs, user, onAsk }: Props) {
  const [articles, setArticles] = useState<ArticlePreview[]>([])

  const topics = prefs.topics && prefs.topics.length > 0
    ? prefs.topics.slice(0, 4)
    : ['ai_ml', 'bigtech', 'ai_reg', 'hardware']

  const topicKey = topics.join(',')

  useEffect(() => {
    listArticles({ topics, limit: 8 })
      .then((data) =>
        setArticles(
          data.map((a) => ({
            id: a.id,
            source: a.source,
            time: a.published_at
              ? new Date(a.published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
              : '',
            title: a.title,
          }))
        )
      )
      .catch(() => { /* stay empty — show placeholder */ })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicKey])

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  const firstName = user.name?.split(' ')[0] || 'there'
  const dateStr = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })

  return (
    <div className="home-wrap">
      <p className="home-date" style={{ color: palette.muted }}>{dateStr}</p>
      <h1 className="home-greeting" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
        {greeting}, {firstName}.
      </h1>
      <p className="home-sub" style={{ color: palette.muted }}>
        {topics.map(getTopicLabel).join(' · ')}
      </p>

      {articles.length > 0 ? (
        <ul className="home-articles">
          {articles.map((a) => (
            <li key={a.id}>
              <button
                className="home-article"
                onClick={() => onAsk(`Tell me about: ${a.title}`)}
                style={{ color: palette.ink }}
              >
                <span className="home-article-meta" style={{ color: palette.muted }}>
                  {a.source} · {a.time}
                </span>
                <span className="home-article-title">{a.title}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="home-empty" style={{ color: palette.muted }}>
          No briefing yet — ask me anything or wait for articles to be ingested.
        </p>
      )}
    </div>
  )
}
