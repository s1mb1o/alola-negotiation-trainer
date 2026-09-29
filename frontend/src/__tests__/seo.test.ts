import { describe, expect, it } from 'vitest'
import appHtml from '../../index.html?raw'
import enHtml from '../../en/index.html?raw'
import hackatonHtml from '../../hackaton/index.html?raw'
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
    if (language === 'en' || canonical.endsWith('/ru/')) {
      expect(document.querySelectorAll('link[rel="alternate"][hreflang]')).toHaveLength(3)
    }
    expect(document.querySelector('meta[property="og:image"]')?.getAttribute('content')).toMatch(/^https:\/\//)
    expect(document.querySelector('meta[name="twitter:card"]')?.getAttribute('content')).toBe('summary_large_image')
    expect(document.querySelectorAll('h1')).toHaveLength(1)
    expect(document.querySelector('a[href="/app/training"]')).not.toBeNull()
    expect(structuredData).toBeTruthy()
    expect(JSON.parse(structuredData ?? '{}')['@type']).toBe('WebApplication')
  })

  it('publishes canonical public pages in the sitemap', () => {
    expect(sitemap).toContain('<loc>https://negotiation.alolalab.com/ru/</loc>')
    expect(sitemap).toContain('<loc>https://negotiation.alolalab.com/en/</loc>')
    expect(sitemap).not.toContain('/hackaton')
    expect(sitemap).not.toContain('/presentation')
    expect(sitemap).not.toContain('/app/')
  })

  it('allows marketing pages and blocks application crawling', () => {
    expect(robots).toContain('Allow: /ru/')
    expect(robots).toContain('Allow: /en/')
    expect(robots).toContain('Disallow: /hackaton')
    expect(robots).toContain('Disallow: /presentation')
    expect(robots).not.toMatch(/^Allow: \/hackaton/m)
    expect(robots).toContain('Disallow: /app/')
    expect(robots).toContain('Disallow: /api/')
    expect(robots).toContain('Sitemap: https://negotiation.alolalab.com/sitemap.xml')
  })

  it('marks the trainer HTML as non-indexable', () => {
    const document = parseHtml(appHtml)
    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('noindex, nofollow')
  })

  it('publishes the hackathon pitch and project resources', () => {
    const document = parseHtml(hackatonHtml)

    expect(document.querySelector('#pitch')).not.toBeNull()
    expect(document.querySelector('#demo')).not.toBeNull()
    expect(document.querySelector('#architecture')).not.toBeNull()
    expect(document.querySelector('#resources')).not.toBeNull()
    expect(document.body.textContent).toContain('Nord Systems')
    expect(document.body.textContent).toContain('73,325')
    expect(document.body.textContent).toContain('не независимое измерение навыка')
    expect(document.body.textContent).toContain('Внешний AI-разбор в этом прогоне не запрашивался')
    expect(document.querySelectorAll('img.product-shot')).toHaveLength(2)
    expect(document.querySelector('a[href="https://negotiation.alolalab.com/presentation"]')).not.toBeNull()
    expect(document.querySelector('.access-note')?.textContent).toContain('по доступу жюри')
    expect(document.querySelector('#technical-resources')?.textContent).toContain('Закрытый репозиторий')
    expect(document.querySelector('a[href="https://github.com/s1mb1o/alola-negotiation-trainer"]')).not.toBeNull()
    expect(document.querySelector('a[href="/docs"]')).not.toBeNull()
  })

  it('keeps jury access out of search discovery and public marketing navigation', () => {
    const document = parseHtml(hackatonHtml)
    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('noindex, nofollow, noarchive, nosnippet')
    expect(document.querySelector('meta[name="referrer"]')?.getAttribute('content')).toBe('no-referrer')
    expect(document.querySelector('#resources')?.textContent).toContain('Shrubberies')
    expect(document.querySelector('#jury-username')?.textContent).toBe('jury')
    expect(document.querySelector('#jury-password')?.textContent).toBe('__HACKATON_SITE_PASSWORD__')
    expect(document.querySelector('#jury-inspector-token')?.textContent).toBe('__HACKATON_INSPECTOR_TOKEN__')
    for (const source of [ruHtml, enHtml, appHtml]) {
      expect(parseHtml(source).querySelector('a[href*="/hackaton"]')).toBeNull()
    }
    for (const url of [
      'https://github.com/s1mb1o/alola-negotiation-trainer#readme',
      'https://drive.google.com/drive/folders/1yzsPGGi_2zyS45Ek0EWyomxXNzna-zeW',
      'https://negotiation.alolalab.com/hackaton',
      'https://negotiation.alolalab.com/app/inspector',
    ]) expect(document.querySelector(`a[href="${url}"]`)).not.toBeNull()
  })
})
