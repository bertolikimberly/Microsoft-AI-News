'use client'

import NewsCard from '@/components/news/NewsCard'
import type { NewsCard as NewsCardType, Palette } from '@/types'

interface Props {
  cards: NewsCardType[]
  palette: Palette
  onAction: (kind: string, card: NewsCardType) => void
}

export default function CardsBlock({ cards, palette, onAction }: Props) {
  return (
    <div className="cards-list">
      {cards.map((c) => (
        <NewsCard key={c.id} card={c} palette={palette} onAction={onAction} />
      ))}
    </div>
  )
}
