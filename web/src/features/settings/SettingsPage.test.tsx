import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { AppSettings, Background } from '@/api/notifications'
import { mockApi } from '@/test/mockApi'
import { jsonResponse, renderWithQueryClient } from '@/test/render'

import { SettingsPage } from './SettingsPage'

const background = (overrides: Partial<Background> = {}): Background => ({
  enabled: true,
  installed: false,
  loaded: false,
  dry_run: false,
  schedule: 'Every day at 07:00, or when your Mac wakes if it was asleep.',
  summary: 'Not installed: run `scholar background on` to start it.',
  last_scheduled_run: null,
  ...overrides,
})

const appSettings = (overrides: Partial<AppSettings> = {}): AppSettings => ({
  background_enabled: true,
  notifications_enabled: true,
  notification_kinds: { new_match: true, changed: true, deadline: true },
  search_queries: [],
  suggested_queries: ['Nursing scholarship OH'],
  search_configured: false,
  last_search_at: null,
  ...overrides,
})

const render = () =>
  renderWithQueryClient(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>,
  )

describe('SettingsPage', () => {
  it('asks before installing the background job (FR-N2)', async () => {
    const calls = mockApi({
      'GET /api/v1/background': background(),
      'GET /api/v1/settings': appSettings(),
      'PUT /api/v1/background': background({
        installed: true,
        loaded: true,
        summary: 'On: Every day at 07:00.',
      }),
    })
    const user = userEvent.setup()
    render()

    await user.click(await screen.findByRole('button', { name: 'Switch on…' }))
    expect(calls.some((c) => c.method === 'PUT')).toBe(false) // not yet
    await user.click(
      screen.getByRole('button', { name: 'Install and switch on' }),
    )

    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({
      enabled: true,
    })
    expect(
      await screen.findByRole('button', { name: 'Switch off' }),
    ).toBeInTheDocument()
  })

  it('runs the daily check on demand and reports notifications', async () => {
    mockApi({
      'GET /api/v1/background': background({ enabled: false }),
      'GET /api/v1/settings': appSettings(),
      'GET /api/v1/notifications': { items: [], unread: 0 },
      'POST /api/v1/discovery/run': {
        id: 1,
        kind: 'discover',
        trigger: 'api',
        status: 'succeeded',
        started_at: '2027-01-01T07:00:00Z',
        finished_at: '2027-01-01T07:01:00Z',
        summary: { notifications_created: 2 },
        error: null,
      },
    })
    const user = userEvent.setup()
    render()

    await user.click(await screen.findByRole('button', { name: 'Run now' }))

    expect(
      await screen.findByText('Run succeeded: 2 new notification(s).'),
    ).toBeInTheDocument()
  })

  it('switches notifications and each kind (FR-N5)', async () => {
    const calls = mockApi({
      'GET /api/v1/background': background(),
      'GET /api/v1/settings': appSettings(),
      'PUT /api/v1/settings/notifications': appSettings({
        notification_kinds: { new_match: true, changed: true, deadline: false },
      }),
      'PATCH /api/v1/profile': {},
    })
    const user = userEvent.setup()
    render()

    await user.click(await screen.findByLabelText(/Deadline reminders/))
    await user.click(screen.getByLabelText('Notify me'))

    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({
      kinds: { deadline: false },
    })
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({
      notifications_enabled: false,
    })
  })

  it('sends nothing to search until the queries are saved (FR-N3)', async () => {
    const calls = mockApi({
      'GET /api/v1/background': background(),
      'GET /api/v1/settings': appSettings(),
      'PUT /api/v1/settings/search-queries': appSettings({
        search_queries: ['Nursing scholarship OH', 'nurse aid Ohio'],
      }),
    })
    const user = userEvent.setup()
    render()

    expect(await screen.findByText(/no search key is set/)).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: 'Add “Nursing scholarship OH”' }),
    )
    await user.type(
      screen.getByLabelText('Queries (one per line)'),
      '\nnurse aid Ohio',
    )
    expect(calls.some((c) => c.method === 'PUT')).toBe(false)

    await user.click(screen.getByRole('button', { name: 'Save queries' }))

    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({
      queries: ['Nursing scholarship OH', 'nurse aid Ohio'],
    })
  })

  it('puts a switch back if saving it fails', async () => {
    mockApi({
      'GET /api/v1/background': background(),
      'GET /api/v1/settings': appSettings(),
      'PUT /api/v1/settings/notifications': () =>
        jsonResponse({ detail: 'Not saved.' }, 500),
    })
    const user = userEvent.setup()
    render()

    const box = await screen.findByLabelText(/Deadline reminders/)
    await user.click(box)

    expect(await screen.findByRole('alert')).toHaveTextContent('Not saved.')
    expect(box).toBeChecked()
  })
})
