'use client'

import CardsBlock from '@/components/chat/CardsBlock'
import { FONTS } from '@/constants/fonts'
import type { ChatMessage, NewsCard, Palette } from '@/types'

interface Props {
  msg: ChatMessage
  palette: Palette
  displayFont: string
  compact: boolean
  onAction: (kind: string, card: NewsCard) => void
}

function renderMd(text: string, color: string): React.ReactNode {
  const lines = text.split('\n')
  const nodes: React.ReactNode[] = []
  const linkRe = /\[([^\]]+)\]\(([^)]+)\)/g

  lines.forEach((line, li) => {
    if (li > 0) nodes.push(<br key={`br-${li}`} />)
    let last = 0
    let m: RegExpExecArray | null
    linkRe.lastIndex = 0
    while ((m = linkRe.exec(line)) !== null) {
      if (m.index > last) nodes.push(line.slice(last, m.index))
      nodes.push(
        <a key={`${li}-${m.index}`} href={m[2]} target="_blank" rel="noreferrer"
          style={{ color, textDecoration: 'underline', textUnderlineOffset: '2px', opacity: 0.8 }}>
          {m[1]}
        </a>
      )
      last = m.index + m[0].length
    }
    if (last < line.length) nodes.push(line.slice(last))
  })
  return <>{nodes}</>
}

export default function Message({ msg, palette, displayFont, compact, onAction }: Props) {
  const isUser = msg.role === 'user'

  if (msg.briefing) {
    return (
      <div className="msg msg-ai">
        <p className="brief-header" style={{ color: palette.muted }}>{msg.briefing.header}</p>
        <p className="brief-greeting" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
          {msg.briefing.greeting}
        </p>
        {msg.cards && <CardsBlock cards={msg.cards} palette={palette} onAction={onAction} />}
      </div>
    )
  }

  return (
    <div className={`msg ${isUser ? 'msg-user' : 'msg-ai'} ${compact ? 'msg-compact' : ''}`}>
      {msg.thinking ? (
        <div className="bubble bubble-ai"
          style={{ background: palette.bubbleAi, color: palette.ink, borderColor: 'rgba(0,0,0,0.06)' }}>
          <span className="thinking">
            <span className="dot" /><span className="dot" /><span className="dot" />
          </span>
        </div>
      ) : (
        <>
          {msg.content && (
            <div
              className={`bubble ${isUser ? 'bubble-user' : 'bubble-ai'}`}
              style={isUser
                ? { background: palette.bubbleUser, color: palette.bubbleUserInk }
                : { background: palette.bubbleAi, color: palette.ink, borderColor: 'rgba(0,0,0,0.06)' }}
            >
              {isUser ? msg.content : renderMd(msg.content, palette.ink)}
            </div>
          )}
          {msg.cards && (
            <CardsBlock cards={msg.cards} palette={palette} onAction={onAction} />
          )}
        </>
      )}
    </div>
  )
}
