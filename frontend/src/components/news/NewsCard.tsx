'use client'

import type { NewsCard as NewsCardType, Palette } from '@/types'

interface Props {
  card: NewsCardType
  palette: Palette
  onAction: (kind: string, card: NewsCardType) => void
}

export default function NewsCard({ card, palette, onAction }: Props) {
  return (
    <button className="nitem" onClick={() => onAction('read', card)} style={{ color: palette.ink }}>
      <span className="nitem-meta" style={{ color: palette.muted }}>
        {card.source} · {card.time}
      </span>
      <span className="nitem-title">{card.title}</span>
    </button>
  )
}
