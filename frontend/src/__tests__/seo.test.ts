import { describe, expect, it } from 'vitest'
import appHtml from '../../index.html?raw'
import enHtml from '../../en/index.html?raw'
import robots from '../../public/robots.txt?raw'
import sitemap from '../../public/sitemap.xml?raw'
import ruHtml from '../../ru/index.html?raw'

function parseHtml(source: string): Document {
  return new DOMParser().parseFromString(source, 'text/html')
}

describe('public marketing discovery', () => {
  it.each([
    ['ru/index.html', ruHtml, 'ru', 'https://negotiation.alolalab.com/ru/'],
    ['en/index.html', enHtml, 'en', 'https://negotiation.alolalab.com/en/'],
  ])('publishes complete metadata in %s', (_path, source, language, canonical) => {
    const document = parseHtml(source)
    const structuredData = document.querySelector('script[type="application/ld+json"]')?.textContent

    expect(document.documentElement.lang).toBe(language)
    expect(document.title.length).toBeGreaterThan(30)
    expect(document.querySelector('meta[name="description"]')?.getAttribute('content')?.length).toBeGreaterThan(100)
    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toContain('index')
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe(canonical)
    expect(document.querySelectorAll('link[rel="alternate"][hreflang]')).toHaveLength(3)
    expect(document.querySelector('meta[property="og:image"]')?.getAttribute('content')).toMatch(/^https:\/\//)
    expect(document.querySelector('meta[name="twitter:card"]')?.getAttribute('content')).toBe('summary_large_image')
    expect(document.querySelectorAll('h1')).toHaveLength(1)
    expect(document.querySelector('a[href="/app/training"]')).not.toBeNull()
    expect(structuredData).toBeTruthy()
    expect(JSON.parse(structuredData ?? '{}')['@type']).toBe('WebApplication')
  })

  it('publishes only canonical marketing pages in the sitemap', () => {
    expect(sitemap).toContain('<loc>https://negotiation.alolalab.com/ru/</loc>')
    expect(sitemap).toContain('<loc>https://negotiation.alolalab.com/en/</loc>')
    expect(sitemap).not.toContain('/app/')
  })

  it('allows marketing pages and blocks application crawling', () => {
    expect(robots).toContain('Allow: /ru/')
    expect(robots).toContain('Allow: /en/')
    expect(robots).toContain('Disallow: /app/')
    expect(robots).toContain('Disallow: /api/')
    expect(robots).toContain('Sitemap: https://negotiation.alolalab.com/sitemap.xml')
  })

  it('marks the trainer HTML as non-indexable', () => {
    const document = parseHtml(appHtml)
    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('noindex, nofollow')
  })
})
