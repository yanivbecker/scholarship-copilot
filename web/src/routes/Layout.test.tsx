import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { mockApi } from '@/test/mockApi'
import { catalog, profile, story } from '@/test/fixtures'

import { routes } from './router'

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('navigation', () => {
  it('marks the current page and moves between pages', async () => {
    mockApi({
      'GET /api/v1/health': { status: 'ok', version: '0.1.0' },
      'GET /api/v1/facts/catalog': catalog,
      'GET /api/v1/facts': [],
      'GET /api/v1/profile': profile,
      'GET /api/v1/stories': [story()],
      'GET /api/v1/stories/themes': { suggested: [] },
    })
    const user = userEvent.setup()
    renderAt('/')

    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(screen.getByRole('link', { name: 'Today' })).toHaveAttribute(
      'aria-current',
      'page',
    )

    await user.click(screen.getByRole('link', { name: 'Story bank' }))
    expect(
      await screen.findByRole('heading', { name: 'Story bank', level: 1 }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Story bank' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(nav).toBeInTheDocument()
  })

  it('has a skip link to the main content', () => {
    mockApi({ 'GET /api/v1/health': { status: 'ok', version: '0.1.0' } })
    renderAt('/')

    expect(
      screen.getByRole('link', { name: 'Skip to content' }),
    ).toHaveAttribute('href', '#main')
  })
})
