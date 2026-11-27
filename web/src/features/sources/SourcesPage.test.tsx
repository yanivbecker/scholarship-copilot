import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { source } from '@/test/fixtures'
import { mockApi } from '@/test/mockApi'
import { jsonResponse, renderWithQueryClient } from '@/test/render'

import { SourcesPage } from './SourcesPage'
import { timeAgo } from './status'

const base = (sources = [source()]) => ({
  'GET /api/v1/sources': sources,
  'GET /api/v1/discovery/runs/latest': null,
})

describe('SourcesPage', () => {
  it('shows each source with plain-language status', async () => {
    mockApi(
      base([
        source({
          extraction_status: 'needs_ai',
          extraction_message: 'AI is turned off.',
        }),
        source({
          id: 2,
          label: 'Member portal',
          url: 'https://portal.example.org/listing',
          last_result: 'login_required',
          last_message: 'This page needs a login.',
        }),
      ]),
    )
    renderWithQueryClient(<SourcesPage />)

    expect(await screen.findByText('Checked')).toBeInTheDocument()
    expect(
      screen.getByText('Needs a login: paste the text'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('AI is off: add details by hand'),
    ).toBeInTheDocument()
    // A login-walled source opens the paste form straight away (FR-D4),
    // and there's nothing to read yet, so "Find scholarships" is disabled.
    expect(screen.getByLabelText('Listing text')).toBeInTheDocument()
    const buttons = screen.getAllByRole('button', { name: 'Find scholarships' })
    expect(buttons[0]).toBeEnabled()
    expect(buttons[1]).toBeDisabled()
  })

  it('check now reports what happened', async () => {
    const calls = mockApi({
      ...base(),
      'POST /api/v1/sources/1/check': {
        source: source(),
        skipped: false,
        changed: true,
      },
    })
    const user = userEvent.setup()
    renderWithQueryClient(<SourcesPage />)

    await user.click(await screen.findByRole('button', { name: 'Check now' }))

    expect(await screen.findByText(/New text found/)).toBeInTheDocument()
    expect(
      calls.some(
        (c) => c.method === 'POST' && c.path === '/api/v1/sources/1/check',
      ),
    ).toBe(true)
  })

  it('pastes listing text exactly as typed', async () => {
    const calls = mockApi({
      ...base(),
      'POST /api/v1/sources/1/paste': {
        source: source({ last_result: 'pasted' }),
        skipped: false,
        changed: true,
      },
    })
    const user = userEvent.setup()
    renderWithQueryClient(<SourcesPage />)

    await user.click(await screen.findByRole('button', { name: 'Paste text' }))
    await user.type(
      screen.getByLabelText('Listing text'),
      '  Award: $500{Enter}Must live in Ohio. ',
    )
    await user.click(screen.getByRole('button', { name: 'Save text' }))

    expect(await screen.findByText(/Text saved/)).toBeInTheDocument()
    expect(calls.find((c) => c.path.endsWith('/paste'))?.body).toEqual({
      text: '  Award: $500\nMust live in Ohio. ',
    })
  })

  it('shows the extraction result and errors', async () => {
    mockApi({
      ...base(),
      'POST /api/v1/sources/1/extract': () =>
        jsonResponse({ detail: "There's no text for this source yet." }, 422),
    })
    const user = userEvent.setup()
    renderWithQueryClient(<SourcesPage />)

    await user.click(
      await screen.findByRole('button', { name: 'Find scholarships' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "There's no text",
    )
  })

  it('removes a source only after confirmation', async () => {
    const calls = mockApi({ ...base(), 'DELETE /api/v1/sources/1': undefined })
    const user = userEvent.setup()
    renderWithQueryClient(<SourcesPage />)

    await user.click(await screen.findByRole('button', { name: 'Remove' }))
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    await user.click(
      screen.getByRole('button', { name: 'Yes, remove Test Foundation' }),
    )

    expect(
      calls.some(
        (c) => c.method === 'DELETE' && c.path === '/api/v1/sources/1',
      ),
    ).toBe(true)
  })

  it('runs discovery and shows the summary', async () => {
    mockApi({
      ...base(),
      'POST /api/v1/discovery/run': {
        id: 1,
        kind: 'discover',
        trigger: 'api',
        status: 'partial',
        started_at: new Date().toISOString(),
        finished_at: new Date().toISOString(),
        summary: {
          sources: [{}, {}],
          scholarships_created: 1,
          scholarships_updated: 0,
          errors: 1,
        },
        error: null,
      },
    })
    const user = userEvent.setup()
    renderWithQueryClient(<SourcesPage />)

    await user.click(await screen.findByRole('button', { name: 'Run now' }))

    expect(await screen.findByText('Last run: partial')).toBeInTheDocument()
    expect(
      screen.getByText(
        /2 sources checked · 1 new, 0 updated scholarships · 1 errors/,
      ),
    ).toBeInTheDocument()
  })
})

describe('timeAgo', () => {
  const now = Date.parse('2026-01-10T12:00:00Z')

  it.each([
    [null, 'never'],
    ['2026-01-10T11:59:30Z', 'just now'],
    ['2026-01-10T11:00:00Z', '1 hour ago'],
    ['2026-01-08T12:00:00Z', '2 days ago'],
  ])('%s -> %s', (iso, expected) => {
    expect(timeAgo(iso, now)).toBe(expected)
  })
})
