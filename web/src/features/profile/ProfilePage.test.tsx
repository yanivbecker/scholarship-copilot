import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { catalog, fact, profile } from '@/test/fixtures'
import { mockApi } from '@/test/mockApi'
import { jsonResponse, renderWithQueryClient } from '@/test/render'

import { ProfilePage } from './ProfilePage'

const baseRoutes = {
  'GET /api/v1/facts/catalog': catalog,
  'GET /api/v1/profile': profile,
}

/** Render the page and wait until the catalog has loaded. */
async function renderPage() {
  renderWithQueryClient(<ProfilePage />)
  return screen.findByRole('heading', { name: 'Education' })
}

const educationForm = () => screen.getByRole('form', { name: 'Education' })

describe('ProfilePage', () => {
  it('shows each section, stored values, and where they came from', async () => {
    mockApi({
      ...baseRoutes,
      'GET /api/v1/facts': [
        fact({
          key: 'gpa',
          value: 3.5,
          origin: 'resume',
          origin_detail: 'cv.pdf',
        }),
      ],
    })
    await renderPage()

    expect(screen.getByLabelText('GPA')).toHaveValue('3.5')
    expect(screen.getByText('From your resume (cv.pdf)')).toBeInTheDocument()
    expect(screen.getByText('Optional · sensitive')).toBeInTheDocument()
  })

  it('saves only changed fields, as typed values', async () => {
    const calls = mockApi({
      ...baseRoutes,
      'GET /api/v1/facts': [fact({ key: 'gpa', value: 3.5 })],
      'PUT /api/v1/facts/gpa': ({ body }) =>
        fact({ key: 'gpa', value: (body as { value: number }).value }),
    })
    const user = userEvent.setup()
    await renderPage()

    await user.clear(screen.getByLabelText('GPA'))
    await user.type(screen.getByLabelText('GPA'), '3.9')
    await user.click(
      within(educationForm()).getByRole('button', { name: /save/i }),
    )

    expect(
      await within(educationForm()).findByText('Saved.'),
    ).toBeInTheDocument()
    const writes = calls.filter((c) => c.method !== 'GET')
    expect(writes).toEqual([
      expect.objectContaining({
        method: 'PUT',
        path: '/api/v1/facts/gpa',
        body: { value: 3.9, origin: 'manual' }, // a number, not "3.9"
      }),
    ])
  })

  it('blocks invalid input before sending anything', async () => {
    const calls = mockApi({ ...baseRoutes, 'GET /api/v1/facts': [] })
    const user = userEvent.setup()
    await renderPage()

    await user.type(screen.getByLabelText('GPA'), 'abc')
    await user.click(
      within(educationForm()).getByRole('button', { name: /save/i }),
    )

    expect(await screen.findByText('GPA must be a number.')).toBeInTheDocument()
    expect(screen.getByLabelText('GPA')).toHaveAttribute('aria-invalid', 'true')
    expect(calls.filter((c) => c.method !== 'GET')).toEqual([])
  })

  it('clears an old "Saved." when the next attempt is invalid', async () => {
    mockApi({
      ...baseRoutes,
      'GET /api/v1/facts': [],
      'PUT /api/v1/facts/major': fact({ key: 'major', value: 'Art' }),
    })
    const user = userEvent.setup()
    await renderPage()
    const save = () =>
      user.click(within(educationForm()).getByRole('button', { name: /save/i }))

    await user.type(screen.getByLabelText('Major'), 'Art')
    await save()
    await within(educationForm()).findByText('Saved.')

    await user.type(screen.getByLabelText('GPA'), '9')
    await save()

    await screen.findByText('GPA must be between 0 and 5.')
    expect(
      within(educationForm()).queryByText('Saved.'),
    ).not.toBeInTheDocument()
  })

  it('shows the backend message next to the field it rejected', async () => {
    mockApi({
      ...baseRoutes,
      'GET /api/v1/facts': [],
      'PUT /api/v1/facts/major': () =>
        jsonResponse({ detail: 'Major must be at most 500 characters.' }, 422),
    })
    const user = userEvent.setup()
    await renderPage()

    await user.type(screen.getByLabelText('Major'), 'Biology')
    await user.click(
      within(educationForm()).getByRole('button', { name: /save/i }),
    )

    expect(
      await screen.findByText('Major must be at most 500 characters.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/1 field\(s\) could not be saved/),
    ).toBeInTheDocument()
  })

  it('clearing a field deletes the fact', async () => {
    const calls = mockApi({
      ...baseRoutes,
      'GET /api/v1/facts': [fact({ key: 'major', value: 'History' })],
      'DELETE /api/v1/facts/major': undefined,
    })
    const user = userEvent.setup()
    await renderPage()

    await user.clear(screen.getByLabelText('Major'))
    await user.click(
      within(educationForm()).getByRole('button', { name: /save/i }),
    )

    await within(educationForm()).findByText('Saved.')
    expect(
      calls.some(
        (c) => c.method === 'DELETE' && c.path === '/api/v1/facts/major',
      ),
    ).toBe(true)
  })

  it('changes the operating mode', async () => {
    const calls = mockApi({
      ...baseRoutes,
      'GET /api/v1/facts': [],
      'PATCH /api/v1/profile': { ...profile, operating_mode: 'discovery' },
    })
    const user = userEvent.setup()
    await renderPage()

    await user.selectOptions(await screen.findByLabelText('Mode'), 'discovery')

    expect(
      await screen.findByText(/Find, evaluate, and track/),
    ).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({
      operating_mode: 'discovery',
    })
  })
})
