import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { StatsView } from '../components/StatsView'

describe('StatsView', () => {
  it('uses the backend completed-session agreement rate', () => {
    render(
      <StatsView
        language="en"
        loading={false}
        onStartTraining={vi.fn()}
        localStats={{
          sessions: 0,
          agreements: 0,
          walkaways: 0,
          average_outcome: null,
          average_pareto: null,
          average_skills: {},
          recent: [],
        }}
        remoteStats={{
          totals: {
            total_sessions: 4,
            completed_sessions: 2,
            agreements: 1,
            agreement_rate: 0.5,
            avg_skill_score: 72,
          },
        }}
      />,
    )

    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.queryByText('Average skill')).not.toBeInTheDocument()
    expect(screen.queryByText('Skill profile')).not.toBeInTheDocument()
    expect(screen.queryByText('Average efficiency')).not.toBeInTheDocument()
    expect(screen.queryByText('100%')).not.toBeInTheDocument()
    expect(screen.getByText('Service-wide totals (all sessions)')).toBeInTheDocument()
  })

  it('labels local-history numbers when the service totals are unavailable', () => {
    render(
      <StatsView
        language="ru"
        loading={false}
        error="unavailable"
        onStartTraining={vi.fn()}
        localStats={{
          sessions: 2,
          agreements: 1,
          walkaways: 0,
          average_outcome: 70,
          average_pareto: null,
          average_skills: { probing: 0.5 },
          recent: [],
        }}
      />,
    )

    expect(screen.getAllByText('Только этот браузер').length).toBeGreaterThan(0)
    expect(screen.queryByText('Показатели сервиса (все сессии)')).not.toBeInTheDocument()
    expect(screen.queryByText('100%')).not.toBeInTheDocument()
  })
})
