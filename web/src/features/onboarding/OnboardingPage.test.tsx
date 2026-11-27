import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { Onboarding } from '@/api/onboarding'
import { catalog, profile } from '@/test/fixtures'
import { mockApi, type ApiCall } from '@/test/mockApi'
import { jsonResponse, renderWithQueryClient } from '@/test/render'

import { OnboardingPage } from './OnboardingPage'

// Fictional wizard definition shaped like GET /onboarding (NFR-10).
const steps: Onboarding['steps'] = [
  {
    key: 'basics',
    label: 'Basics and school',
    fact_keys: ['major', 'expected_graduation_year', 'education_level'],
  },
  { key: 'resume', label: 'Resume (optional)', fact_keys: [] },
  {
    key: 'questionnaire',
    label: 'A few more questions',
    fact_keys: ['gpa', 'first_generation'],
  },
  { key: 'preferences', label: 'Mode and notifications', fact_keys: [] },
  { key: 'sources', label: 'First sources', fact_keys: [] },
]
const keys = steps.map((s) => s.key)

function state(doneCount: number): Onboarding {
  return {
    steps,
    completed: keys.slice(0, doneCount),
    next_step: keys[doneCount] ?? null,
    completed_at: doneCount === keys.length ? '2026-01-01T00:00:00Z' : null,
  }
}

/** /facts/missing answers from the given set of keys already on file. */
const missingExcept =
  (onFile: string[]) =>
  ({ search }: ApiCall) => ({
    missing: new URLSearchParams(search)
      .getAll('keys')
      .filter((k) => !onFile.includes(k)),
  })

const base = (doneCount: number, onFile: string[] = []) => ({
  'GET /api/v1/onboarding': state(doneCount),
  'GET /api/v1/profile': profile,
  'GET /api/v1/facts/catalog': catalog,
  'GET /api/v1/facts': [],
  'GET /api/v1/facts/missing': missingExcept(onFile),
  'GET /api/v1/sources': [],
})

const render = (ui: ReactElement) =>
  renderWithQueryClient(<MemoryRouter>{ui}</MemoryRouter>)

describe('OnboardingPage', () => {
  it('resumes at the first unfinished step', async () => {
    mockApi(base(2))
    render(<OnboardingPage />)

    expect(
      await screen.findByRole('heading', {
        name: /Step 3 of 5: A few more questions/,
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /3\. A few more questions/ }),
    ).toHaveAttribute('aria-current', 'step')
    // Later steps can't be jumped to.
    expect(
      screen.getByRole('button', { name: /5\. First sources/ }),
    ).toBeDisabled()
  })

  it('asks only for facts not on file and sends typed answers', async () => {
    const calls = mockApi({
      ...base(0, ['major']),
      'POST /api/v1/onboarding/steps/basics': state(1),
    })
    const user = userEvent.setup()
    render(<OnboardingPage />)

    await screen.findByLabelText('Expected graduation year')
    expect(screen.queryByLabelText('Major')).not.toBeInTheDocument() // on file

    await user.type(screen.getByLabelText('Expected graduation year'), '2029')
    await user.click(screen.getByRole('button', { name: 'Save and continue' }))

    expect(
      await screen.findByRole('heading', { name: /Step 2 of 5: Resume/ }),
    ).toBeInTheDocument()
    const post = calls.find((c) => c.method === 'POST')
    // Unanswered education_level is left out, and 2029 is a number.
    expect(post?.body).toEqual({ facts: { expected_graduation_year: 2029 } })
  })

  it('shows the server field errors and says nothing was saved', async () => {
    mockApi({
      ...base(0),
      'POST /api/v1/onboarding/steps/basics': () =>
        jsonResponse(
          {
            detail: 'Some answers need fixing.',
            field_errors: { major: 'Major must be at most 500 characters.' },
          },
          422,
        ),
    })
    const user = userEvent.setup()
    render(<OnboardingPage />)

    await user.type(await screen.findByLabelText('Major'), 'Biology')
    await user.click(screen.getByRole('button', { name: 'Save and continue' }))

    expect(
      await screen.findByText('Major must be at most 500 characters.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Nothing was saved yet/)).toBeInTheDocument()
    expect(screen.getByLabelText('Major')).toHaveAttribute(
      'aria-invalid',
      'true',
    )
  })

  it('says so when everything for a step is already on file', async () => {
    mockApi(base(0, ['major', 'expected_graduation_year', 'education_level']))
    render(<OnboardingPage />)

    expect(await screen.findByText(/already on file/)).toBeInTheDocument()
  })

  it('marks sensitive questions as optional', async () => {
    mockApi(base(2))
    render(<OnboardingPage />)

    expect(
      await screen.findByLabelText(
        /First-generation college student \(optional, sensitive\)/,
      ),
    ).toBeInTheDocument()
  })

  it('saves preferences before moving on', async () => {
    const calls = mockApi({
      ...base(3),
      'PATCH /api/v1/profile': { ...profile, notifications_enabled: false },
      'POST /api/v1/onboarding/steps/preferences': state(4),
    })
    const user = userEvent.setup()
    render(<OnboardingPage />)

    await user.click(
      await screen.findByRole('checkbox', { name: /in-app notifications/ }),
    )
    await user.click(screen.getByRole('button', { name: 'Save and continue' }))

    await screen.findByRole('heading', { name: /Step 5 of 5/ })
    const writes = calls.filter((c) => c.method !== 'GET').map((c) => c.path)
    expect(writes).toEqual([
      '/api/v1/profile',
      '/api/v1/onboarding/steps/preferences',
    ])
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({
      operating_mode: 'hybrid',
      notifications_enabled: false,
    })
  })

  it('shows why a source was rejected, then finishes', async () => {
    mockApi({
      ...base(4),
      'POST /api/v1/sources': () =>
        jsonResponse(
          { detail: "Aggregator sites aren't used as sources." },
          422,
        ),
      'POST /api/v1/onboarding/steps/sources': state(5),
    })
    const user = userEvent.setup()
    render(<OnboardingPage />)

    await user.type(
      await screen.findByLabelText('Web address'),
      'https://fastweb.com',
    )
    await user.click(screen.getByRole('button', { name: 'Add source' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /Aggregator sites/,
    )

    await user.click(screen.getByRole('button', { name: 'Finish setup' }))
    expect(
      await screen.findByRole('heading', { name: "You're all set" }),
    ).toBeInTheDocument()
  })
})
