import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { LoaderCircle } from 'lucide-react'
import {
  ApiError,
  apiErrorCode,
  createSession,
  forkSession,
  getComparison,
  requestCoaching,
  requestPlayerAssist,
  getAggregateStats,
  getReview,
  getSession,
  isNpcRenderPending,
  isResumableRequestError,
  listScenarios,
  makeIdempotencyKey,
  requestHint,
  rewindSession,
  sendMessage,
} from './api'
import { AppHeader } from './components/AppHeader'
import { NegotiationWorkspace } from './components/NegotiationWorkspace'
import { SessionInspector } from './components/SessionInspector'
import { SessionSetup, type SessionSetupValue } from './components/SessionSetup'
import { StatsView } from './components/StatsView'
import { apiErrorLabel, translate } from './i18n'
import { applyTheme, applyUiLanguage, initialTheme, initialUiLanguage } from './preferences'
import { appViewFromPathname, appViewPath } from './routing'
import type {
  AggregateStatsResponse,
  ScenarioSummary,
  SessionEnvelope,
  SessionReview,
  ThemePreference,
  TimelineMessage,
  UiLanguage,
  TrainingComparison,
} from './types'
import {
  aggregateReviewHistory,
  clearActiveSession,
  extractParticipantToken,
  extractTimeline,
  isTerminalStatus,
  mergeTimeline,
  readActiveSession,
  storeActiveSession,
  storeReview,
  wait,
} from './utils'

const PARTICIPANT_TOKEN_KEY = 'negotiation.participant-token'
/** Pause before each automatic retry of a message that received `npc_render_pending`. */
const NPC_RENDER_RETRY_DELAYS_MS = [1000, 2000, 4000]

interface PendingCreateAttempt {
  fingerprint: string
  idempotencyKey: string
}

interface PendingMessageAttempt {
  sessionId: string
  sessionGeneration: number
  text: string
  idempotencyKey: string
  expectedRevision: number
  optimisticId: string
}

const fallbackScenario = (language: UiLanguage): ScenarioSummary => ({
  scenario_id: 'supplier_001',
  version: 3,
  title: translate(language, 'scenarioFallback'),
  description: translate(language, 'scenarioFallbackDescription'),
  languages: ['ru', 'en'],
  duration_minutes: 20,
  roles: [
    { role_id: 'buyer', title: translate(language, 'roleBuyer') },
    { role_id: 'seller', title: translate(language, 'roleSeller') },
  ],
})

function errorMessage(error: unknown, language: UiLanguage): string {
  if (error instanceof ApiError) {
    return apiErrorLabel(language, apiErrorCode(error)) ?? translate(language, 'apiError')
  }
  return translate(language, 'backendUnavailable')
}

export default function App() {
  const [language, setLanguage] = useState<UiLanguage>(initialUiLanguage)
  const [theme, setTheme] = useState<ThemePreference>(initialTheme)
  const [activeView, setActiveView] = useState(() => appViewFromPathname(window.location.pathname))
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([fallbackScenario(language)])
  const [loadingScenarios, setLoadingScenarios] = useState(true)
  const [usingFallback, setUsingFallback] = useState(false)
  const [creating, setCreating] = useState(false)
  const [setupError, setSetupError] = useState<string>()
  const [pendingCreateAttempt, setPendingCreateAttempt] = useState<PendingCreateAttempt>()
  const [session, setSession] = useState<SessionEnvelope>()
  const [sessionConfig, setSessionConfig] = useState<SessionSetupValue>()
  const [token, setToken] = useState(() => sessionStorage.getItem(PARTICIPANT_TOKEN_KEY) ?? '')
  const [restoring, setRestoring] = useState(
    () => Boolean(readActiveSession()) && Boolean(sessionStorage.getItem(PARTICIPANT_TOKEN_KEY)),
  )
  const [ownParticipantId, setOwnParticipantId] = useState('participant_buyer')
  const [messages, setMessages] = useState<TimelineMessage[]>([])
  const [busy, setBusy] = useState(false)
  const [waitingForCounterpart, setWaitingForCounterpart] = useState(false)
  const [messageError, setMessageError] = useState<string>()
  const [pendingMessageAttempt, setPendingMessageAttempt] = useState<PendingMessageAttempt>()
  const [lastFailedMessage, setLastFailedMessage] = useState<string>()
  const [requestingHint, setRequestingHint] = useState(false)
  const [assisting, setAssisting] = useState(false)
  const [rewindingRevision, setRewindingRevision] = useState<number>()
  const [review, setReview] = useState<SessionReview>()
  const [reviewLoading, setReviewLoading] = useState(false)
  const [trainingBusy, setTrainingBusy] = useState(false)
  const [trainingError, setTrainingError] = useState<string>()
  const [comparison, setComparison] = useState<TrainingComparison>()
  const forkAttempt = useRef<{ sessionId: string; revision: number; key: string } | undefined>(undefined)
  const rewindAttempt = useRef<{ sessionId: string; revision: number; key: string } | undefined>(undefined)
  const assistAttempt = useRef<{ sessionId: string; revision: number; key: string } | undefined>(undefined)
  useEffect(() => {
    document.documentElement.scrollTop = 0
    document.body.scrollTop = 0
  }, [session?.session_id, session?.status])
  const [reviewError, setReviewError] = useState<string>()
  const [remoteStats, setRemoteStats] = useState<AggregateStatsResponse>()
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsError, setStatsError] = useState<string>()
  const [statsVersion, setStatsVersion] = useState(0)
  const sessionGeneration = useRef(0)
  // One flag for every mutation that carries `expected_revision` (messages and hints) so they never race.
  const mutationInFlight = useRef(false)

  useEffect(() => {
    applyUiLanguage(language)
  }, [language])

  useEffect(() => {
    applyTheme(theme)
    if (theme !== 'system' || typeof window.matchMedia !== 'function') return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const syncSystemTheme = () => applyTheme('system')
    media.addEventListener?.('change', syncSystemTheme)
    return () => media.removeEventListener?.('change', syncSystemTheme)
  }, [theme])

  useEffect(() => {
    const canonicalPath = appViewPath(appViewFromPathname(window.location.pathname))
    if (window.location.pathname !== canonicalPath) {
      window.history.replaceState({ view: appViewFromPathname(canonicalPath) }, '', canonicalPath)
    }

    const handlePopState = () => setActiveView(appViewFromPathname(window.location.pathname))
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  const navigateToView = useCallback((view: 'training' | 'stats' | 'inspector') => {
    const path = appViewPath(view)
    if (window.location.pathname !== path) window.history.pushState({ view }, '', path)
    setActiveView(view)
  }, [])

  useEffect(() => {
    let active = true
    setLoadingScenarios(true)
    listScenarios(language, token || undefined)
      .then((items) => {
        if (!active) return
        if (items.length > 0) {
          setScenarios(items)
          setUsingFallback(false)
        } else {
          setScenarios([fallbackScenario(language)])
          setUsingFallback(true)
        }
      })
      .catch(() => {
        if (!active) return
        setScenarios([fallbackScenario(language)])
        setUsingFallback(true)
      })
      .finally(() => active && setLoadingScenarios(false))
    return () => { active = false }
  }, [language, token])

  const updateToken = useCallback((nextToken: string) => {
    setToken(nextToken)
    if (nextToken) sessionStorage.setItem(PARTICIPANT_TOKEN_KEY, nextToken)
    else sessionStorage.removeItem(PARTICIPANT_TOKEN_KEY)
  }, [])

  // Restore the session identity stored by this tab once when the page loads.
  useEffect(() => {
    const stored = readActiveSession()
    if (!stored) return
    if (!token) {
      clearActiveSession()
      setRestoring(false)
      return
    }
    const generation = sessionGeneration.current
    let active = true
    setRestoring(true)
    getSession(stored.session_id, token)
      .then((response) => {
        if (!active || sessionGeneration.current !== generation) return
        const normalized: SessionEnvelope = {
          ...response,
          observation: response.observation ?? {},
          language: response.language ?? stored.session_language,
        }
        const roleId = normalized.observation.role ?? stored.role_id
        setOwnParticipantId(normalized.observation.participant_id ?? `participant_${roleId}`)
        setSessionConfig({
          scenario: stored.scenario,
          sessionLanguage: normalized.language ?? stored.session_language,
          difficulty: stored.difficulty,
          // The service is authoritative; the stored value only covers older payloads.
          hintsEnabled: normalized.hints_enabled ?? stored.hints_enabled,
          participantToken: token,
          roleId,
          training: normalized.observation.training?.preparation ? {
            profile: normalized.observation.training.profile,
            relationship: normalized.observation.training.relationship,
            player_name: normalized.observation.training.player_name ?? '',
            shared_background: normalized.observation.training.shared_background,
            personal_detail: normalized.observation.training.personal_detail,
            preparation: normalized.observation.training.preparation,
          } : undefined,
        })
        // `pending_confirmation` and `clarification` travel inside the envelope, so the
        // confirmation card or clarification notice reappears with the restored session.
        setSession(normalized)
        setMessages(extractTimeline(normalized))
        setReview(undefined)
        setReviewError(undefined)
        setMessageError(undefined)
      })
      .catch((error: unknown) => {
        if (!active || sessionGeneration.current !== generation) return
        if (error instanceof ApiError && (error.status === 401 || error.status === 404)) {
          clearActiveSession()
          return
        }
        setSetupError(errorMessage(error, language))
      })
      .finally(() => {
        if (active) setRestoring(false)
      })
    return () => { active = false }
    // The stored identity is read once at mount; later token changes belong to the running session.
  }, [])

  // Keep the stored identity current so a reload lands on the latest revision.
  useEffect(() => {
    if (!session || !sessionConfig) return
    storeActiveSession({
      session_id: session.session_id,
      role_id: sessionConfig.roleId,
      session_language: session.language ?? sessionConfig.sessionLanguage,
      scenario: sessionConfig.scenario,
      difficulty: sessionConfig.difficulty,
      hints_enabled: sessionConfig.hintsEnabled,
      revision: session.revision,
    })
  }, [session, sessionConfig])

  const startSession = async (value: SessionSetupValue) => {
    setCreating(true)
    setSetupError(undefined)
    try {
      const scenarioRoles = value.scenario.roles?.map((role) => role.role_id) ?? ['buyer', 'seller']
      const otherRole = scenarioRoles.find((role) => role !== value.roleId) ?? (value.roleId === 'buyer' ? 'seller' : 'buyer')
      const participants = [value.roleId, otherRole].map((role) => ({
        role,
        controller: role === value.roleId ? 'human' as const : 'built_in_npc' as const,
      }))
      const createRequest = {
        scenario_id: value.scenario.scenario_id,
        scenario_version: value.scenario.version,
        language: value.sessionLanguage,
        participants,
        difficulty: value.difficulty,
        hints_enabled: value.hintsEnabled,
        run_mode: 'training',
        training: value.training,
      } as const
      const fingerprint = JSON.stringify(createRequest)
      const attempt = pendingCreateAttempt?.fingerprint === fingerprint
        ? pendingCreateAttempt
        : { fingerprint, idempotencyKey: makeIdempotencyKey('create') }
      setPendingCreateAttempt(attempt)
      const response = await createSession({
        ...createRequest,
        idempotency_key: attempt.idempotencyKey,
      }, value.participantToken || undefined)

      const deliveredToken = extractParticipantToken(response, value.roleId)
      if (response.credential_delivery === 'initial_response_only' && !deliveredToken) {
        throw new ApiError(409, { error: 'participant_credential_unavailable' })
      }
      const responseToken = deliveredToken || value.participantToken
      setPendingCreateAttempt(undefined)
      updateToken(responseToken)
      sessionGeneration.current += 1
      mutationInFlight.current = false
      const participant = response.participants?.find((item) => item.role === value.roleId)
      setOwnParticipantId(participant?.participant_id ?? `participant_${value.roleId}`)
      setSessionConfig(value)
      setSession({ ...response, observation: response.observation ?? {}, language: response.language ?? value.sessionLanguage })
      setMessages(extractTimeline({ ...response, observation: response.observation ?? {} }))
      setReview(undefined)
      setComparison(undefined)
      setTrainingError(undefined)
      setReviewError(undefined)
      setMessageError(undefined)
      navigateToView('training')
    } catch (error) {
      if (!isResumableRequestError(error)) setPendingCreateAttempt(undefined)
      setSetupError(errorMessage(error, language))
    } finally {
      setCreating(false)
    }
  }

  const performMessageAttempt = useCallback(async (attempt: PendingMessageAttempt) => {
    if (
      !session
      || mutationInFlight.current
      || session.session_id !== attempt.sessionId
      || sessionGeneration.current !== attempt.sessionGeneration
    ) return
    const stale = () => sessionGeneration.current !== attempt.sessionGeneration
    mutationInFlight.current = true
    setMessageError(undefined)
    setBusy(true)
    setMessages((current) => {
      const withoutOtherPending = current.filter(
        (item) => !item.pending || item.id === attempt.optimisticId,
      )
      const optimistic = {
        id: attempt.optimisticId,
        participantId: ownParticipantId,
        role: sessionConfig?.roleId ?? 'buyer',
        text: attempt.text,
        pending: true,
        failed: false,
      }
      return withoutOtherPending.some((item) => item.id === attempt.optimisticId)
        ? withoutOtherPending.map((item) => item.id === attempt.optimisticId ? optimistic : item)
        : [...withoutOtherPending, optimistic]
    })

    try {
      for (let autoRetry = 0; ; autoRetry += 1) {
        try {
          const response = await sendMessage(
            attempt.sessionId,
            attempt.text,
            attempt.expectedRevision,
            attempt.idempotencyKey,
            token,
          )
          if (stale()) return
          const normalized = { ...response, observation: response.observation ?? {}, language: response.language ?? session.language }
          setPendingMessageAttempt(undefined)
          setLastFailedMessage(undefined)
          setSession(normalized)
          setMessages((current) => mergeTimeline(
            current.filter((item) => item.id !== attempt.optimisticId),
            extractTimeline(normalized),
          ))
          if (isTerminalStatus(response.status)) setStatsVersion((value) => value + 1)
          return
        } catch (error) {
          if (stale()) return
          const delay = NPC_RENDER_RETRY_DELAYS_MS[autoRetry]
          if (isNpcRenderPending(error) && delay !== undefined) {
            // The service still renders the previous counterpart reply: retry the same envelope after a pause.
            setWaitingForCounterpart(true)
            await wait(delay)
            if (stale()) return
            continue
          }
          if (error instanceof ApiError) {
            const currentRevision = error.payload.current_revision ?? error.payload.revision
            if (typeof currentRevision === 'number') {
              setSession((current) => current ? {
                ...current,
                revision: currentRevision,
                observation: error.payload.observation ?? current.observation,
              } : current)
            }
          }
          const resumable = isResumableRequestError(error)
          setPendingMessageAttempt(resumable ? attempt : undefined)
          setLastFailedMessage(resumable ? undefined : attempt.text)
          setMessages((current) => resumable
            ? current.map((item) => item.id === attempt.optimisticId
              ? { ...item, pending: false, failed: true }
              : item)
            : current.filter((item) => item.id !== attempt.optimisticId))
          setMessageError(errorMessage(error, language))
          return
        }
      }
    } finally {
      if (!stale()) {
        mutationInFlight.current = false
        setBusy(false)
        setWaitingForCounterpart(false)
      }
    }
  }, [language, ownParticipantId, session, sessionConfig?.roleId, token])

  const submitMessage = useCallback((text: string) => {
    if (!session || mutationInFlight.current || pendingMessageAttempt) return
    const attempt: PendingMessageAttempt = {
      sessionId: session.session_id,
      sessionGeneration: sessionGeneration.current,
      text,
      idempotencyKey: makeIdempotencyKey('message'),
      expectedRevision: session.revision,
      optimisticId: `pending-${Date.now()}`,
    }
    setPendingMessageAttempt(attempt)
    setLastFailedMessage(undefined)
    void performMessageAttempt(attempt)
  }, [pendingMessageAttempt, performMessageAttempt, session])

  const retryMessage = useCallback(() => {
    if (mutationInFlight.current) return
    if (pendingMessageAttempt) {
      void performMessageAttempt(pendingMessageAttempt)
      return
    }
    if (lastFailedMessage) submitMessage(lastFailedMessage)
  }, [lastFailedMessage, pendingMessageAttempt, performMessageAttempt, submitMessage])

  // Drop a failed attempt: the composer unlocks and the text returns to the draft.
  const discardMessageAttempt = useCallback(() => {
    if (mutationInFlight.current) return
    const attempt = pendingMessageAttempt
    setPendingMessageAttempt(undefined)
    setLastFailedMessage(undefined)
    setMessageError(undefined)
    if (attempt) setMessages((current) => current.filter((item) => item.id !== attempt.optimisticId))
  }, [pendingMessageAttempt])

  const failedMessageText = pendingMessageAttempt?.text ?? lastFailedMessage

  const fetchReview = useCallback(async () => {
    if (!session) return
    const generation = sessionGeneration.current
    setReviewLoading(true)
    setReviewError(undefined)
    try {
      const result = await getReview(session.session_id, token)
      if (sessionGeneration.current !== generation) return
      setReview(result)
      storeReview(session.session_id, sessionConfig?.scenario.title ?? session.session_id, result)
      setStatsVersion((value) => value + 1)
      if (result.training?.parent_session_id) {
        try {
          const compared = await getComparison(session.session_id, token)
          if (sessionGeneration.current === generation) setComparison(compared)
        } catch (error) {
          if (sessionGeneration.current === generation) setTrainingError(errorMessage(error, language))
        }
      }
    } catch (error) {
      if (sessionGeneration.current !== generation) return
      setReviewError(errorMessage(error, language))
    } finally {
      if (sessionGeneration.current === generation) setReviewLoading(false)
    }
  }, [language, session, sessionConfig?.scenario.title, token])

  useEffect(() => {
    if (session && isTerminalStatus(session.status) && !review && !reviewLoading && !reviewError) void fetchReview()
  }, [fetchReview, review, reviewError, reviewLoading, session])

  const coachSession = async () => {
    if (!session || trainingBusy) return
    const generation = sessionGeneration.current
    setTrainingBusy(true)
    setTrainingError(undefined)
    try {
      await requestCoaching(session.session_id, token)
      if (generation === sessionGeneration.current) await fetchReview()
    } catch (error) {
      if (generation === sessionGeneration.current) setTrainingError(errorMessage(error, language))
    } finally {
      if (generation === sessionGeneration.current) setTrainingBusy(false)
    }
  }

  const retryDecision = async (revision: number) => {
    if (!session || !sessionConfig || trainingBusy) return
    const generation = sessionGeneration.current
    setTrainingBusy(true)
    setTrainingError(undefined)
    const attempt = forkAttempt.current?.sessionId === session.session_id && forkAttempt.current.revision === revision
      ? forkAttempt.current : { sessionId: session.session_id, revision, key: makeIdempotencyKey('fork') }
    forkAttempt.current = attempt
    try {
      const response = await forkSession(session.session_id, revision, attempt.key, token)
      if (generation !== sessionGeneration.current) return
      const freshToken = extractParticipantToken(response, sessionConfig.roleId)
      if (!freshToken) throw new ApiError(409, { error: 'participant_credential_unavailable' })
      updateToken(freshToken)
      setSessionConfig({ ...sessionConfig, participantToken: freshToken })
      setOwnParticipantId(response.observation.participant_id ?? '')
      setSession(response)
      setMessages(extractTimeline(response))
      setReview(undefined)
      setReviewError(undefined)
      setComparison(undefined)
      setMessageError(undefined)
      setPendingMessageAttempt(undefined)
      setLastFailedMessage(undefined)
      setBusy(false)
      setWaitingForCounterpart(false)
      forkAttempt.current = undefined
      mutationInFlight.current = false
      setTrainingBusy(false)
      sessionGeneration.current += 1
    } catch (error) {
      if (generation === sessionGeneration.current) setTrainingError(errorMessage(error, language))
    } finally {
      if (generation === sessionGeneration.current) setTrainingBusy(false)
    }
  }

  const rewindDialogue = async (revision: number) => {
    if (
      !session
      || !sessionConfig
      || mutationInFlight.current
      || pendingMessageAttempt
      || trainingBusy
    ) return
    const generation = sessionGeneration.current
    const attempt = rewindAttempt.current?.sessionId === session.session_id
      && rewindAttempt.current.revision === revision
      ? rewindAttempt.current
      : { sessionId: session.session_id, revision, key: makeIdempotencyKey('rewind') }
    rewindAttempt.current = attempt
    mutationInFlight.current = true
    setRewindingRevision(revision)
    setMessageError(undefined)
    try {
      const response = await rewindSession(session.session_id, revision, attempt.key, token)
      if (generation !== sessionGeneration.current) return
      const freshToken = extractParticipantToken(response, sessionConfig.roleId)
      if (!freshToken) throw new ApiError(409, { error: 'participant_credential_unavailable' })
      const participant = response.participant_credentials?.find(
        (item) => item.role === sessionConfig.roleId,
      )
      updateToken(freshToken)
      setSessionConfig({ ...sessionConfig, participantToken: freshToken })
      setOwnParticipantId(response.observation.participant_id ?? participant?.participant_id ?? '')
      setSession(response)
      setMessages(extractTimeline(response))
      setReview(undefined)
      setReviewError(undefined)
      setComparison(undefined)
      setTrainingError(undefined)
      setMessageError(undefined)
      setPendingMessageAttempt(undefined)
      setLastFailedMessage(undefined)
      setBusy(false)
      setWaitingForCounterpart(false)
      rewindAttempt.current = undefined
      assistAttempt.current = undefined
      forkAttempt.current = undefined
      mutationInFlight.current = false
      setRewindingRevision(undefined)
      sessionGeneration.current += 1
    } catch (error) {
      if (generation !== sessionGeneration.current) return
      if (error instanceof ApiError) rewindAttempt.current = undefined
      setMessageError(errorMessage(error, language))
    } finally {
      if (generation === sessionGeneration.current) {
        mutationInFlight.current = false
        setRewindingRevision(undefined)
      }
    }
  }

  const answerForMe = async () => {
    if (!session || mutationInFlight.current || pendingMessageAttempt || trainingBusy) return
    const generation = sessionGeneration.current
    const attempt = assistAttempt.current?.sessionId === session.session_id
      && assistAttempt.current.revision === session.revision
      ? assistAttempt.current
      : { sessionId: session.session_id, revision: session.revision, key: makeIdempotencyKey('player-assist') }
    assistAttempt.current = attempt
    let submitted = false
    mutationInFlight.current = true
    setAssisting(true)
    setMessageError(undefined)
    try {
      const reply = await requestPlayerAssist(
        session.session_id,
        session.revision,
        attempt.key,
        token,
      )
      if (generation !== sessionGeneration.current) return
      assistAttempt.current = undefined
      mutationInFlight.current = false
      setAssisting(false)
      submitted = true
      submitMessage(reply.message)
    } catch (error) {
      if (generation !== sessionGeneration.current) return
      if (error instanceof ApiError) assistAttempt.current = undefined
      setMessageError(errorMessage(error, language))
    } finally {
      if (!submitted && generation === sessionGeneration.current) {
        mutationInFlight.current = false
        setAssisting(false)
      }
    }
  }

  const askForHint = async () => {
    if (!session || mutationInFlight.current || pendingMessageAttempt) return
    const generation = sessionGeneration.current
    mutationInFlight.current = true
    setRequestingHint(true)
    setMessageError(undefined)
    try {
      const result = await requestHint(session.session_id, session.revision, makeIdempotencyKey('hint'), token)
      if (sessionGeneration.current !== generation) return
      setSession((current) => {
        if (!current) return current
        const observation = result.observation ?? current.observation
        const currentHints = observation.hints ?? []
        const hasReturnedHint = Boolean(
          result.hint?.id && currentHints.some((hint) => hint.id === result.hint?.id),
        )
        return {
          ...current,
          revision: result.revision ?? current.revision,
          observation: {
            ...observation,
            hints: result.hint && !hasReturnedHint
              ? [...currentHints, result.hint]
              : currentHints,
          },
        }
      })
    } catch (error) {
      if (sessionGeneration.current !== generation) return
      setMessageError(errorMessage(error, language))
    } finally {
      if (sessionGeneration.current === generation) {
        mutationInFlight.current = false
        setRequestingHint(false)
      }
    }
  }

  useEffect(() => {
    if (activeView !== 'stats') return
    let active = true
    setStatsLoading(true)
    setStatsError(undefined)
    getAggregateStats(token || undefined)
      .then((result) => active && setRemoteStats(result))
      .catch((error) => active && setStatsError(errorMessage(error, language)))
      .finally(() => active && setStatsLoading(false))
    return () => { active = false }
  }, [activeView, language, statsVersion, token])

  const localStats = useMemo(() => aggregateReviewHistory(), [statsVersion, activeView])

  const newSession = () => {
    if (
      session
      && !isTerminalStatus(session.status)
      && !window.confirm(translate(language, 'newSessionConfirm'))
    ) return
    sessionGeneration.current += 1
    mutationInFlight.current = false
    clearActiveSession()
    setSession(undefined)
    setSessionConfig(undefined)
    setTrainingBusy(false)
    setTrainingError(undefined)
    setComparison(undefined)
    setMessages([])
    setReview(undefined)
    setReviewError(undefined)
    setMessageError(undefined)
    setPendingMessageAttempt(undefined)
    setLastFailedMessage(undefined)
    setBusy(false)
    setWaitingForCounterpart(false)
    setRequestingHint(false)
    setAssisting(false)
    setRewindingRevision(undefined)
    forkAttempt.current = undefined
    rewindAttempt.current = undefined
    assistAttempt.current = undefined
    setReviewLoading(false)
    setRestoring(false)
    navigateToView('training')
  }

  return (
    <div className="app-shell">
      <AppHeader
        language={language}
        theme={theme}
        activeView={activeView}
        hasSession={Boolean(session)}
        onLanguageChange={setLanguage}
        onThemeChange={setTheme}
        onViewChange={navigateToView}
        onNewSession={newSession}
      />

      {activeView === 'inspector' ? (
        <SessionInspector language={language} />
      ) : activeView === 'stats' ? (
        <StatsView
          language={language}
          localStats={localStats}
          remoteStats={remoteStats}
          loading={statsLoading}
          error={statsError}
          onStartTraining={newSession}
        />
      ) : restoring ? (
        <main className="workspace">
          <section className="review-panel loading-review" role="status">
            <span className="review-loader"><LoaderCircle className="spin" size={28} aria-hidden="true" /></span>
            <h2>{translate(language, 'sessionRestoring')}</h2>
          </section>
        </main>
      ) : session && sessionConfig ? (
        <NegotiationWorkspace
          language={language}
          session={session}
          messages={messages}
          token={token}
          ownParticipantId={ownParticipantId}
          ownRoleId={sessionConfig.roleId}
          scenarioTitle={sessionConfig.scenario.title}
          hintsEnabled={sessionConfig.hintsEnabled}
          busy={busy || Boolean(pendingMessageAttempt)}
          locked={requestingHint || assisting || rewindingRevision !== undefined}
          waitingForCounterpart={waitingForCounterpart}
          requestingHint={requestingHint}
          assisting={assisting}
          rewindingRevision={rewindingRevision}
          error={messageError}
          failedMessageText={failedMessageText}
          review={review}
          reviewLoading={reviewLoading}
          reviewError={reviewError}
          trainingBusy={trainingBusy}
          trainingError={trainingError}
          comparison={comparison}
          onCoaching={() => void coachSession()}
          onFork={(revision) => void retryDecision(revision)}
          onRewind={session.observation.training?.rewind
            ? (revision) => void rewindDialogue(revision)
            : undefined}
          onAnswerForMe={session.observation.training
            ? () => void answerForMe()
            : undefined}
          onSend={submitMessage}
          onRequestHint={askForHint}
          onTokenChange={updateToken}
          onRetryMessage={failedMessageText ? retryMessage : undefined}
          onDiscardMessage={failedMessageText ? discardMessageAttempt : undefined}
          onRetryReview={() => {
            setReviewError(undefined)
            void fetchReview()
          }}
          onNewSession={newSession}
        />
      ) : (
        <SessionSetup
          language={language}
          scenarios={scenarios}
          loadingScenarios={loadingScenarios}
          usingFallback={usingFallback}
          creating={creating}
          error={setupError}
          onStart={startSession}
        />
      )}
    </div>
  )
}
