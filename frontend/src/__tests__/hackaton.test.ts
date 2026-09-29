/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enhanceLanding } from '../../hackaton/interactions'
import html from '../../hackaton/index.html?raw'

describe('hackathon landing enhancements', () => {
  beforeEach(() => {
    document.body.innerHTML = new DOMParser().parseFromString(html, 'text/html').body.innerHTML
    delete document.documentElement.dataset.theme
  })
  afterEach(() => {
    document.body.innerHTML = ''
    delete document.documentElement.dataset.theme
    Reflect.deleteProperty(navigator, 'clipboard')
    vi.restoreAllMocks()
  })

  it('defaults to system preference and cycles light, dark, and system', () => {
    enhanceLanding(document)
    const button = document.querySelector<HTMLButtonElement>('[data-theme-toggle]')!
    expect(button.hidden).toBe(false)
    expect(document.documentElement.dataset.theme).toBeUndefined()
    button.click()
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(button.getAttribute('aria-label')).toContain('Включить тёмную')
    button.click()
    expect(document.documentElement.dataset.theme).toBe('dark')
    button.click()
    expect(document.documentElement.dataset.theme).toBeUndefined()
    expect(button.textContent).toBe('Тема: авто')
  })

  it('opens the original screenshot with its caption and closes the dialog', () => {
    const dialog = document.querySelector<HTMLDialogElement>('dialog')!
    const show = vi.fn(() => dialog.setAttribute('open', ''))
    const close = vi.fn(() => dialog.removeAttribute('open'))
    dialog.showModal = show
    dialog.close = close
    enhanceLanding(document)
    const link = document.querySelector<HTMLAnchorElement>('a[data-preview]')!
    const event = new MouseEvent('click', { bubbles: true, cancelable: true })
    link.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
    expect(show).toHaveBeenCalledOnce()
    expect(document.querySelector<HTMLImageElement>('[data-preview-image]')?.src).toBe(link.href)
    expect(document.querySelector('#preview-caption')?.textContent).toBe(link.dataset.caption)
    expect(document.querySelector<HTMLAnchorElement>('[data-preview-original]')?.href).toBe(link.href)
    document.querySelector<HTMLButtonElement>('[data-close-preview]')!.click()
    expect(close).toHaveBeenCalledOnce()
    expect(dialog.open).toBe(false)
  })

  it('preserves modified clicks and falls back to links without dialog support', () => {
    const dialog = document.querySelector<HTMLDialogElement>('dialog')!
    dialog.showModal = vi.fn()
    enhanceLanding(document)
    const link = document.querySelector<HTMLAnchorElement>('a[data-preview]')!
    // Prevent jsdom navigation after observing the enhancement's decision.
    let prevented = true
    link.addEventListener('click', (event) => {
      prevented = event.defaultPrevented
      event.preventDefault()
    })
    link.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, metaKey: true }))
    expect(prevented).toBe(false)
    expect(dialog.showModal).not.toHaveBeenCalled()

    document.body.innerHTML = new DOMParser().parseFromString(html, 'text/html').body.innerHTML
    Object.defineProperty(document.querySelector('dialog'), 'showModal', { value: undefined })
    enhanceLanding(document)
    const fallback = document.querySelector<HTMLAnchorElement>('a[data-preview]')!
    fallback.addEventListener('click', (event) => {
      prevented = event.defaultPrevented
      event.preventDefault()
    })
    fallback.click()
    expect(prevented).toBe(false)
    expect(fallback.getAttribute('href')).toBe('/hackaton/nord-dialogue.png')
  })

  it('ships PNG screenshots, a PDF, and valid in-page destinations', () => {
    for (const image of document.querySelectorAll<HTMLImageElement>('img.product-shot')) {
      expect(image.alt.length).toBeGreaterThan(40)
      expect(image.getAttribute('width')).toBe('1600')
      expect(image.getAttribute('height')).toBe('1200')
      const bytes = readFileSync(resolve(process.cwd(), 'public', image.getAttribute('src')!.slice(1)))
      expect(bytes.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a')
    }
    expect(document.querySelector('a[href="https://negotiation.alolalab.com/presentation"]')).not.toBeNull()
    const bytes = readFileSync(resolve(process.cwd(), 'public/hackaton/alola-presentation-v6.pdf'))
    expect(bytes.subarray(0, 5).toString()).toBe('%PDF-')
    for (const link of document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]')) {
      expect(document.querySelector(link.getAttribute('href')!)).not.toBeNull()
    }
  })

  it('keeps supporting details collapsed and the score caveat visible', () => {
    const recording = document.querySelector<HTMLDetailsElement>('#recording-details')!
    const technical = document.querySelector<HTMLDetailsElement>('#technical-resources')!
    expect(recording.open).toBe(false)
    expect(technical.open).toBe(false)
    expect(recording.textContent).toContain('73,325 / 100')
    expect(recording.textContent).toContain('€112 785')
    const caveat = document.querySelector('.evidence-note')!
    expect(caveat.closest('details')).toBeNull()
    expect(caveat.textContent).toContain('не измерение навыка')
    expect(document.querySelector('.hero-bottom')).toBeNull()
    expect(document.querySelector('.engine-flow')).toBeNull()
  })

  it('copies access values and gives a manual fallback when clipboard access fails', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    enhanceLanding(document)
    const button = document.querySelector<HTMLButtonElement>('[data-copy-target="jury-username"]')!
    expect(button.hidden).toBe(false)
    button.click()
    await vi.waitFor(() => expect(document.querySelector('[data-copy-status]')?.textContent).toBe('Скопировано.'))
    expect(writeText).toHaveBeenCalledWith('jury')
    writeText.mockRejectedValueOnce(new Error('Permission denied'))
    button.click()
    await vi.waitFor(() => expect(document.querySelector('[data-copy-status]')?.textContent).toContain('скопируйте вручную'))
  })
})
