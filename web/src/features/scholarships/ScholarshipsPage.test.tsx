import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import { eligibilityItem, scholarshipRecord } from '@/test/fixtures'
import { mockApi } from '@/test/mockApi'
import { renderWithQueryClient } from '@/test/render'

import { ScholarshipsPage } from './ScholarshipsPage'

const render = () =>
  renderWithQueryClient(
    <MemoryRouter>
      <ScholarshipsPage />
    </MemoryRouter>,
  )

const base = {
  'GET /api/v1/eligibility': [eligibilityItem()],
  'GET /api/v1/scholarships': [scholarshipRecord()],
  'GET /api/v1/scholarships/duplicates': [],
}

describe('ScholarshipsPage', () => {
  it('shows the verdict, priority, amount and deadline', async () => {
    mockApi(base)
    render()

    expect(
      await screen.findByRole('heading', {
        name: 'Test Foundation STEM Award',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('Needs info')).toBeInTheDocument()
    expect(screen.getByText('Priority 62/100')).toBeInTheDocument()
    expect(
      screen.getByText('Test Foundation · $2,500 · Due 2027-03-01'),
    ).toBeInTheDocument()
  })

  it('shows the evidence quote for every requirement', async () => {
    mockApi(base)
    const user = userEvent.setup()
    render()

    await user.click(await screen.findByText('Requirements and evidence (2)'))

    expect(
      screen.getByText(
        'Applicants must have a cumulative GPA of 3.0 or higher.',
      ),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Source' })[0]).toHaveAttribute(
      'href',
      'https://example.org/awards',
    )
  })

  it('points profile questions to the profile page', async () => {
    mockApi(base)
    render()

    expect(await screen.findByText('What is your gpa?')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Go to your profile' }),
    ).toHaveAttribute('href', '/profile')
  })

  it('says which requirements need a yes or no', async () => {
    mockApi(base)
    render()

    expect(
      await screen.findByText(/1 requirement needs your yes or no/),
    ).toBeInTheDocument()
  })

  it('lets the student confirm a free-text requirement (FR-E3)', async () => {
    const calls = mockApi({
      ...base,
      'PUT /api/v1/scholarships/7/criteria/702/confirmation': eligibilityItem({
        verdict: 'eligible',
      }),
    })
    const user = userEvent.setup()
    render()

    await user.click(await screen.findByText('Requirements and evidence (2)'))
    await user.click(screen.getByRole('button', { name: 'Yes' }))

    const put = calls.find((c) => c.method === 'PUT')
    expect(put?.body).toEqual({ answer: true })
  })

  it('warns about scam signals with their evidence (FR-D9)', async () => {
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

    const warning = await screen.findByRole('alert')
    expect(warning).toHaveTextContent('Warning signs on this listing')
    expect(warning).toHaveTextContent('A $30 processing fee is required.')
  })

  it('labels the priority as a ranking, not odds (FR-E6)', async () => {
    mockApi(base)
    const user = userEvent.setup()
    render()

    await user.click(await screen.findByText('How the priority is worked out'))

    expect(screen.getByText(/not your chances of winning/)).toBeInTheDocument()
    expect(screen.getByText('(our estimate)')).toBeInTheDocument()
    expect(screen.getByText('(from the listing)')).toBeInTheDocument()
  })

  it('offers to merge possible duplicates (FR-D6)', async () => {
    const calls = mockApi({
      ...base,
      'GET /api/v1/scholarships/duplicates': [
        {
          first_id: 7,
          first_name: 'Test Award',
          second_id: 8,
          second_name: 'Test Memorial Award',
          score: 80,
        },
      ],
      'POST /api/v1/scholarships/7/merge': scholarshipRecord(),
    })
    const user = userEvent.setup()
    render()

    await user.click(
      await screen.findByRole('button', { name: 'Merge into “Test Award”' }),
    )

    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      other_id: 8,
    })
  })

  it('explains what to do when there are no scholarships yet', async () => {
    mockApi({
      ...base,
      'GET /api/v1/eligibility': [],
      'GET /api/v1/scholarships': [],
    })
    render()

    expect(
      await screen.findByRole('link', { name: 'Sources' }),
    ).toHaveAttribute('href', '/sources')
  })
})
