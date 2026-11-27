import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { StatusView } from '@/api/dashboard'
import {
  catalog,
  eligibilityItem,
  fact,
  scholarshipRecord,
} from '@/test/fixtures'
import { mockApi } from '@/test/mockApi'
import { jsonResponse, renderWithQueryClient } from '@/test/render'

import { ScholarshipDetailPage } from './ScholarshipDetailPage'

const status = (overrides: Partial<StatusView> = {}): StatusView => ({
  status: 'discovered',
  label: 'Discovered',
  next_steps: [
    {
      status: 'eligibility_confirmed',
      label: 'Eligibility confirmed',
      blocked_reason: 'Answer the open questions first.',
      needs_confirmation: false,
    },
  ],
  history: [],
  ...overrides,
})

const base = {
  'GET /api/v1/eligibility': [eligibilityItem()],
  'GET /api/v1/scholarships': [scholarshipRecord()],
  'GET /api/v1/scholarships/7/status': status(),
  'GET /api/v1/facts/catalog': catalog,
}

const render = (path = '/scholarships/7') =>
  renderWithQueryClient(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/scholarships/:id" element={<ScholarshipDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )

describe('ScholarshipDetailPage', () => {
  it('shows the listing fields, the deadline wording and the official link', async () => {
    mockApi(base)
    render()

    expect(
      await screen.findByRole('heading', {
        name: 'Test Foundation STEM Award',
        level: 1,
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('$2,500')).toBeInTheDocument()
    expect(
      screen.getByText('Applications are due March 1, 2027.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'https://example.org/awards' }),
    ).toHaveAttribute('target', '_blank')
    // No official page is known, so it's labeled as where it was listed.
    expect(screen.getByText('Listed on')).toBeInTheDocument()
    expect(screen.queryByText('Official page')).not.toBeInTheDocument()
    expect(
      screen.getByText(/Details last read from the source/),
    ).toBeInTheDocument()
  })

  it('shows every requirement with its exact quote', async () => {
    mockApi(base)
    render()

    expect(
      await screen.findByText(
        'Applicants must have a cumulative GPA of 3.0 or higher.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'Applicants must demonstrate leadership in their community.',
      ),
    ).toBeInTheDocument()
  })

  it('lets missing facts be answered right here, saved to the profile', async () => {
    const calls = mockApi({
      ...base,
      'PUT /api/v1/facts/gpa': fact({ key: 'gpa', value: 3.6 }),
    })
    const user = userEvent.setup()
    render()

    await user.type(await screen.findByLabelText('GPA'), '3.6')
    await user.click(screen.getByRole('button', { name: 'Save gpa' }))

    expect(await screen.findByText('Saved.')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({
      value: 3.6,
      origin: 'manual',
    })
  })

  it('rejects an invalid quick answer before sending', async () => {
    const calls = mockApi(base)
    const user = userEvent.setup()
    render()

    await user.type(await screen.findByLabelText('GPA'), '9')
    await user.click(screen.getByRole('button', { name: 'Save gpa' }))

    expect(
      await screen.findByText('GPA must be between 0 and 5.'),
    ).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'PUT')).toBe(false)
  })

  it('shows why a status step is blocked', async () => {
    mockApi(base)
    render()

    expect(
      await screen.findByRole('heading', { name: 'Status: Discovered' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Move to “Eligibility confirmed”' }),
    ).toBeDisabled()
    expect(
      screen.getByText('Answer the open questions first.'),
    ).toBeInTheDocument()
  })

  it('only marks submitted after the student confirms they did it (FR-A7)', async () => {
    const calls = mockApi({
      ...base,
      'GET /api/v1/scholarships/7/status': status({
        status: 'awaiting_approval',
        label: 'Awaiting approval',
        next_steps: [
          {
            status: 'submitted',
            label: 'Submitted',
            blocked_reason: null,
            needs_confirmation: true,
          },
          {
            status: 'in_progress',
            label: 'In progress',
            blocked_reason: null,
            needs_confirmation: false,
          },
        ],
      }),
      'POST /api/v1/scholarships/7/status': status({
        status: 'submitted',
        label: 'Submitted',
        next_steps: [],
      }),
    })
    const user = userEvent.setup()
    render()

    const submit = await screen.findByRole('button', {
      name: 'Move to “Submitted”',
    })
    expect(submit).toBeDisabled()
    await user.click(
      screen.getByRole('checkbox', {
        name: 'I submitted this application myself',
      }),
    )
    await user.click(submit)

    expect(
      await screen.findByRole('heading', { name: 'Status: Submitted' }),
    ).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      status: 'submitted',
      confirmed: true,
    })
  })

  it('shows a server refusal', async () => {
    mockApi({
      ...base,
      'GET /api/v1/scholarships/7/status': status({
        next_steps: [
          {
            status: 'eligibility_confirmed',
            label: 'Eligibility confirmed',
            blocked_reason: null,
            needs_confirmation: false,
          },
        ],
      }),
      'POST /api/v1/scholarships/7/status': () =>
        jsonResponse({ detail: 'Not eligible yet.' }, 422),
    })
    const user = userEvent.setup()
    render()

    await user.click(
      await screen.findByRole('button', {
        name: 'Move to “Eligibility confirmed”',
      }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Not eligible yet.',
    )
  })

  it('warns about scam signs', async () => {
    mockApi({
      ...base,
      'GET /api/v1/scholarships': [
        scholarshipRecord({
          scam_flags: [
            { signal: 'fee', evidence: 'A $30 processing fee is required.' },
          ],
        }),
      ],
    })
    render()

    const alerts = await screen.findAllByRole('alert')
    expect(
      alerts.some((a) =>
        a.textContent?.includes('A $30 processing fee is required.'),
      ),
    ).toBe(true)
  })

  it('handles an unknown scholarship', async () => {
    mockApi(base)
    render('/scholarships/999')

    expect(
      await screen.findByRole('heading', { name: 'Scholarship not found' }),
    ).toBeInTheDocument()
  })
})
