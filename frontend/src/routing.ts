export type AppView = 'training' | 'stats' | 'inspector'

const VIEW_PATHS: Record<AppView, string> = {
  training: '/app/training',
  stats: '/app/progress',
  inspector: '/app/inspector',
}

export function appViewPath(view: AppView): string {
  return VIEW_PATHS[view]
}

export function appViewFromPathname(pathname: string): AppView {
  const normalized = pathname.replace(/\/+$/, '') || '/'
  if (normalized === VIEW_PATHS.stats) return 'stats'
  if (normalized === VIEW_PATHS.inspector) return 'inspector'
  return 'training'
}
