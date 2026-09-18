import { describe, expect, it } from 'vitest'
import styles from '../styles.css?raw'

const expectedScale = {
  'font-size-caption': 12,
  'font-size-meta': 13,
  'font-size-small': 14,
  'font-size-body': 16,
  'font-size-subtitle': 18,
}

function ruleBody(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = styles.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`, 's'))
  expect(match, `Missing CSS rule for ${selector}`).not.toBeNull()
  return match?.[1] ?? ''
}

describe('Web UI typography', () => {
  it('uses sentence-case body styling for long explanations', () => {
    const copy = ruleBody('.explanatory-copy')
    expect(copy).toContain('text-transform: none')
    expect(copy).toContain('letter-spacing: normal')
    expect(copy).toContain('font-weight: 500')
    expect(copy).toContain('line-height: 1.6')
  })

  it('defines a readable shared type scale for 100% browser zoom', () => {
    const tokens = Object.fromEntries(
      [...styles.matchAll(/--(font-size-[a-z-]+):\s*(\d+)px/g)]
        .map((match) => [match[1], Number(match[2])]),
    )

    expect(tokens).toMatchObject(expectedScale)
    expect(Math.min(...Object.values(expectedScale))).toBeGreaterThanOrEqual(12)
  })

  it('does not reintroduce tiny direct pixel sizes', () => {
    const violations = [...styles.matchAll(/font-size:\s*(\d+(?:\.\d+)?)px/g)]
      .map((match) => Number(match[1]))
      .filter((size) => size < 12)

    expect(violations).toEqual([])
  })

  it('uses readable tokens in the main training surfaces', () => {
    expect(ruleBody('.message-bubble p')).toContain('font-size: var(--font-size-body)')
    expect(ruleBody('.composer textarea')).toContain('font-size: var(--font-size-body)')
    expect(ruleBody('.brief-section-content p')).toContain('font-size: var(--font-size-small)')
    expect(ruleBody('.term-row dt')).toContain('font-size: var(--font-size-caption)')
    expect(ruleBody('.term-row dd')).toContain('font-size: var(--font-size-small)')
    expect(ruleBody('.protocol-notice p:not(.notice-kicker)'))
      .toContain('font-size: var(--font-size-meta)')
    expect(ruleBody('.inspector-timeline p')).toContain('font-size: var(--font-size-small)')
  })

  it('stacks setup story cards before larger text can clip them', () => {
    expect(styles).toMatch(
      /@media \(max-width: 700px\)\s*\{\s*\.story-points\s*\{\s*grid-template-columns: 1fr;/,
    )
  })
})
