export type AppView = 'training' | 'stats' | 'inspector' | 'admin'

const VIEW_PATHS: Record<AppView, string> = {
  training: '/app/training',
  stats: '/app/progress',
  inspector: '/app/inspector',
  admin: '/app/admin',
}

export function appViewPath(view: AppView): string {
  return VIEW_PATHS[view]
}

export function appViewFromPathname(pathname: string): AppView {
  const normalized = pathname.replace(/\/+$/, '') || '/'
  if (normalized === VIEW_PATHS.stats) return 'stats'
  if (normalized === VIEW_PATHS.inspector) return 'inspector'
  if (normalized === VIEW_PATHS.admin) return 'admin'
  return 'training'
}
