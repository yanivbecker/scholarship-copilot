import { screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { Today } from '@/api/dashboard'
import { mockApi } from '@/test/mockApi'
import { renderWithQueryClient } from '@/test/render'

import { HomePage } from './HomePage'

const today = (overrides: Partial<Today> = {}): Today => ({
  actions: [
    {
      kind: 'add_fact',
      title: 'Add your gpa',
      detail: 'Needed to check 3 scholarships.',
      page: 'profile',
      scholarship_id: null,
      fact_key: 'gpa',
    },
    {
      kind: 'paste_text',
      title: 'Paste a listing that needs a login',
      detail: 'Portal',
      page: 'sources',
      scholarship_id: null,
      fact_key: null,
    },
    {
      kind: 'confirm_eligibility',
      title: 'You meet every requirement: mark eligibility confirmed',
      detail: 'Alpha Award',
      page: 'scholarship',
      scholarship_id: 7,
      fact_key: null,
    },
  ],
  deadlines: [
    {
      scholarship_id: 7,
      name: 'Alpha Award',
      deadline: '2027-02-01',
      days_left: 5,
      verdict: 'eligible',
      status: 'discovered',
    },
  ],
  new_matches: [
    {
      scholarship_id: 8,
      name: 'Beta Award',
      verdict: 'needs_info',
      found_at: '2027-01-20T00:00:00Z',
    },
  ],
  counts: { total: 2, eligible: 1, needs_info: 1 },
  last_run: null,
  ...overrides,
})

const render = () =>
  renderWithQueryClient(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  )

describe('Today screen', () => {
  it('lists actions with links to where they are done', async () => {
    mockApi({ 'GET /api/v1/dashboard/today': today() })
    render()

    expect(
      await screen.findByRole('link', { name: 'Add your gpa' }),
    ).toHaveAttribute('href', '/profile')
    expect(
      screen.getByRole('link', { name: 'Paste a listing that needs a login' }),
    ).toHaveAttribute('href', '/sources')
    expect(
      screen.getByRole('link', { name: /mark eligibility confirmed/ }),
    ).toHaveAttribute('href', '/scholarships/7')
    expect(
      screen.getByText(
        '2 scholarships tracked: 1 eligible, 1 need info, 0 not eligible.',
      ),
    ).toBeInTheDocument()
  })

  it('shows deadlines, new matches and the last run', async () => {
    mockApi({ 'GET /api/v1/dashboard/today': today() })
    render()

    expect(await screen.findByText('in 5 days')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Beta Award' })).toHaveAttribute(
      'href',
      '/scholarships/8',
    )
    expect(
      screen.getByText(/Sources haven't been checked yet/),
    ).toBeInTheDocument()
  })

  it('says when nothing needs doing', async () => {
    mockApi({
      'GET /api/v1/dashboard/today': today({
        actions: [],
        deadlines: [],
        new_matches: [],
      }),
    })
    render()

    expect(
      await screen.findByText('Nothing needs you right now.'),
    ).toBeInTheDocument()
    expect(screen.getByText('None coming up.')).toBeInTheDocument()
  })
})
