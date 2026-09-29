/** Optional enhancements. Every resource remains a normal link without JavaScript. */
export function enhanceLanding(page: Document): void {
  const clipboard = page.defaultView?.navigator.clipboard
  if (clipboard?.writeText) {
    page.querySelectorAll<HTMLButtonElement>('[data-copy-target]').forEach((button) => {
      button.hidden = false
      button.addEventListener('click', async () => {
        const value = page.getElementById(button.dataset.copyTarget ?? '')?.textContent
        const status = page.querySelector<HTMLElement>('[data-copy-status]')
        if (!value || !status) return
        try {
          await clipboard.writeText(value)
          status.textContent = 'Скопировано.'
        } catch {
          status.textContent = 'Не удалось скопировать. Выделите значение и скопируйте вручную.'
        }
      })
    })
  }

  const themeButton = page.querySelector<HTMLButtonElement>('[data-theme-toggle]')
  const themes = ['system', 'light', 'dark'] as const
  const labels = ['авто', 'светлая', 'тёмная']
  const descriptions = [
    'Тема: системная. Включить светлую тему.',
    'Тема: светлая. Включить тёмную тему.',
    'Тема: тёмная. Использовать системную тему.',
  ]
  let themeIndex = 0

  if (themeButton) {
    themeButton.hidden = false
    themeButton.addEventListener('click', () => {
      themeIndex = (themeIndex + 1) % themes.length
      if (themeIndex === 0) delete page.documentElement.dataset.theme
      else page.documentElement.dataset.theme = themes[themeIndex]
      themeButton.textContent = `Тема: ${labels[themeIndex]}`
      themeButton.setAttribute('aria-label', descriptions[themeIndex])
    })
  }

  const dialog = page.querySelector<HTMLDialogElement>('[data-image-dialog]')
  const image = page.querySelector<HTMLImageElement>('[data-preview-image]')
  const caption = page.querySelector<HTMLElement>('#preview-caption')
  const original = page.querySelector<HTMLAnchorElement>('[data-preview-original]')
  if (!dialog || typeof dialog.showModal !== 'function' || !image || !caption || !original) return

  page.querySelectorAll<HTMLAnchorElement>('a[data-preview]').forEach((link) => {
    link.addEventListener('click', (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return
      event.preventDefault()
      image.src = link.href
      image.alt = link.querySelector('img')?.alt ?? link.dataset.caption ?? ''
      caption.textContent = link.dataset.caption ?? ''
      original.href = link.href
      dialog.showModal()
    })
  })
  page.querySelector('[data-close-preview]')?.addEventListener('click', () => dialog.close())
  dialog.addEventListener('click', (event) => {
    if (event.target !== dialog) return
    const bounds = dialog.getBoundingClientRect()
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close()
  })
}
