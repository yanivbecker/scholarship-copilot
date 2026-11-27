import { screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import { mockApi } from '@/test/mockApi'
import { renderWithQueryClient } from '@/test/render'

import { SetupBanner } from './SetupBanner'

const steps = ['a', 'b', 'c'].map((key) => ({ key, label: key, fact_keys: [] }))

describe('SetupBanner', () => {
  it('invites the student to continue where they left off', async () => {
    mockApi({
      'GET /api/v1/onboarding': {
        steps,
        completed: ['a'],
        next_step: 'b',
        completed_at: null,
      },
    })
    renderWithQueryClient(
      <MemoryRouter>
        <SetupBanner />
      </MemoryRouter>,
    )

    expect(
      await screen.findByText("You've finished 1 of 3 steps."),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Continue setup' }),
    ).toHaveAttribute('href', '/onboarding')
  })

  it('is hidden once setup is finished', async () => {
    mockApi({
      'GET /api/v1/onboarding': {
        steps,
        completed: ['a', 'b', 'c'],
        next_step: null,
        completed_at: '2026-01-01T00:00:00Z',
      },
    })
    const { container } = renderWithQueryClient(
      <MemoryRouter>
        <SetupBanner />
      </MemoryRouter>,
    )

    await new Promise((r) => setTimeout(r, 50))
    expect(container).toBeEmptyDOMElement()
  })
})
