'use client'

import { useRef, useEffect } from 'react'
import type { Palette } from '@/types'

interface Props {
  value: string
  setValue: (v: string) => void
  onSend: () => void
  palette: Palette
  disabled: boolean
}

export default function Composer({ value, setValue, onSend, palette, disabled }: Props) {
  const taRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = taRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 220) + 'px'
  }, [value])

  return (
    <form className="composer" onSubmit={(e) => { e.preventDefault(); onSend() }}>
      <div className="composer-inner" style={{ background: 'rgba(255,253,247,0.86)' }}>
        <textarea
          ref={taRef}
          className="composer-input"
          placeholder="Ask anything…"
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend() } }}
          style={{ color: palette.ink }}
        />
        <button type="submit" className="send-btn" disabled={disabled || !value.trim()}
          style={{ background: palette.ink, color: palette.bg }} aria-label="Send">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12h14" /><path d="m13 6 6 6-6 6" />
          </svg>
        </button>
      </div>
    </form>
  )
}
