import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import { eligibilityItem as row, scholarshipRecord } from '@/test/fixtures'
import { mockApi } from '@/test/mockApi'
import { renderWithQueryClient } from '@/test/render'

import { ScholarshipsPage } from './ScholarshipsPage'

const score = (total: number) => ({ ...row().score, total })
const rows = [
  row({
    scholarship_id: 7,
    name: 'Alpha Award',
    score: score(40),
    deadline: '2099-04-01',
    amount: 1000,
    amount_text: '$1,000',
  }),
  row({
    scholarship_id: 8,
    name: 'Beta Award',
    score: score(80),
    deadline: '2099-02-01',
    amount: 5000,
    amount_text: '$5,000',
    verdict: 'eligible',
  }),
]

const render = () =>
  renderWithQueryClient(
    <MemoryRouter>
      <ScholarshipsPage />
    </MemoryRouter>,
  )

const base = {
  'GET /api/v1/eligibility': rows,
  'GET /api/v1/scholarships/duplicates': [],
}

const bodyNames = () =>
  within(screen.getAllByRole('rowgroup')[1])
    .getAllByRole('rowheader')
    .map((cell) => within(cell).getByRole('link').textContent)

describe('ScholarshipsPage (table)', () => {
  it('lists scholarships by priority, linking to details', async () => {
    mockApi(base)
    render()

    await screen.findByRole('table')
    expect(bodyNames()).toEqual(['Beta Award', 'Alpha Award'])
    expect(screen.getByRole('link', { name: 'Beta Award' })).toHaveAttribute(
      'href',
      '/scholarships/8',
    )
    expect(
      screen.getByRole('columnheader', { name: /Priority/ }),
    ).toHaveAttribute('aria-sort', 'descending')
  })

  it('sorts by a column when its header is clicked, and reverses on a second click', async () => {
    mockApi(base)
    const user = userEvent.setup()
    render()
    await screen.findByRole('table')

    await user.click(screen.getByRole('button', { name: /Deadline/ }))
    expect(bodyNames()).toEqual(['Beta Award', 'Alpha Award']) // Feb before Apr
    expect(
      screen.getByRole('columnheader', { name: /Deadline/ }),
    ).toHaveAttribute('aria-sort', 'ascending')

    await user.click(screen.getByRole('button', { name: /Deadline/ }))
    expect(bodyNames()).toEqual(['Alpha Award', 'Beta Award'])
  })

  it('filters by eligibility and search', async () => {
    mockApi(base)
    const user = userEvent.setup()
    render()
    await screen.findByRole('table')

    await user.selectOptions(screen.getByLabelText('Eligibility'), 'eligible')
    expect(bodyNames()).toEqual(['Beta Award'])
    expect(screen.getByText('Showing 1 of 2')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Eligibility'), '')
    await user.type(screen.getByLabelText('Search'), 'alpha')
    expect(bodyNames()).toEqual(['Alpha Award'])
  })

  it('offers to merge possible duplicates (FR-D6)', async () => {
    const calls = mockApi({
      ...base,
      'GET /api/v1/scholarships/duplicates': [
        {
          first_id: 7,
          first_name: 'Alpha Award',
          second_id: 8,
          second_name: 'Beta Award',
          score: 80,
        },
      ],
      'POST /api/v1/scholarships/7/merge': scholarshipRecord(),
    })
    const user = userEvent.setup()
    render()

    await user.click(
      await screen.findByRole('button', { name: 'Merge into “Alpha Award”' }),
    )

    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      other_id: 8,
    })
  })

  it('explains what to do when there are no scholarships yet', async () => {
    mockApi({ ...base, 'GET /api/v1/eligibility': [] })
    render()

    expect(
      await screen.findByRole('link', { name: 'Sources' }),
    ).toHaveAttribute('href', '/sources')
  })
})
