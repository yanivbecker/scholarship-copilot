import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { Notification } from '@/api/notifications'
import { mockApi } from '@/test/mockApi'
import { renderWithQueryClient } from '@/test/render'

import { NotificationsCard } from './NotificationsCard'

const note = (overrides: Partial<Notification> = {}): Notification => ({
  id: 1,
  scholarship_id: 7,
  kind: 'deadline',
  title: 'Due in 3 days: Test Foundation STEM Award',
  body: 'Eligible · $2,500 · due 2027-03-01',
  created_at: '2027-02-26T07:00:00Z',
  read_at: null,
  ...overrides,
})

const render = () =>
  renderWithQueryClient(
    <MemoryRouter>
      <NotificationsCard />
    </MemoryRouter>,
  )

describe('NotificationsCard', () => {
  it('shows unread notifications first, linked to the scholarship', async () => {
    mockApi({
      'GET /api/v1/notifications': {
        items: [
          note({ id: 2, title: 'Old news', read_at: '2027-02-01T00:00:00Z' }),
          note(),
        ],
        unread: 1,
      },
    })
    render()

    const links = await screen.findAllByRole('link')
    expect(links[0]).toHaveTextContent('Due in 3 days')
    expect(links[0]).toHaveAttribute('href', '/scholarships/7')
    expect(
      screen.getByRole('heading', { name: 'Notifications (1 new)' }),
    ).toBeInTheDocument()
  })

  it('marks one or all as read', async () => {
    const calls = mockApi({
      'GET /api/v1/notifications': { items: [note()], unread: 1 },
      'POST /api/v1/notifications/read': {
        items: [note({ read_at: '2027-02-26T08:00:00Z' })],
        unread: 0,
      },
    })
    const user = userEvent.setup()
    render()

    await user.click(await screen.findByRole('button', { name: 'Mark read' }))
    expect(calls.at(-1)?.body).toEqual({ ids: [1] })
    expect(
      await screen.findByRole('heading', { name: 'Notifications' }),
    ).toBeInTheDocument()
  })

  it('points to Settings when there is nothing yet', async () => {
    mockApi({ 'GET /api/v1/notifications': { items: [], unread: 0 } })
    render()

    expect(
      await screen.findByRole('link', { name: 'Settings' }),
    ).toHaveAttribute('href', '/settings')
  })
})
