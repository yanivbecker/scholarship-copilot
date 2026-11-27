import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { story } from '@/test/fixtures'
import { mockApi } from '@/test/mockApi'
import { renderWithQueryClient } from '@/test/render'

import { StoriesPage } from './StoriesPage'

const themes = { suggested: ['leadership', 'teamwork'] }

describe('StoriesPage', () => {
  it('sends the story body exactly as typed', async () => {
    const calls = mockApi({
      'GET /api/v1/stories': [],
      'GET /api/v1/stories/themes': themes,
      'POST /api/v1/stories': story(),
    })
    const user = userEvent.setup()
    renderWithQueryClient(<StoriesPage />)

    await user.type(screen.getByLabelText('Title'), '  Tutoring club ')
    await user.type(
      screen.getByLabelText('Your story, in your own words'),
      '  I started a club.{Enter}{Enter}It grew.  ',
    )
    await user.click(await screen.findByRole('button', { name: 'leadership' }))
    await user.type(
      screen.getByLabelText('Add your own theme'),
      '  Peer  Mentoring{Enter}',
    )
    await user.click(screen.getByRole('button', { name: 'Save story' }))

    await screen.findByText('No stories yet.')
    const post = calls.find((c) => c.method === 'POST')
    expect(post?.body).toEqual({
      title: 'Tutoring club',
      body: '  I started a club.\n\nIt grew.  ', // untouched
      themes: ['leadership', 'peer mentoring'],
    })
  })

  it('requires a title and a non-empty story', async () => {
    const calls = mockApi({
      'GET /api/v1/stories': [],
      'GET /api/v1/stories/themes': themes,
    })
    const user = userEvent.setup()
    renderWithQueryClient(<StoriesPage />)

    await user.type(
      screen.getByLabelText('Your story, in your own words'),
      '   ',
    )
    await user.click(screen.getByRole('button', { name: 'Save story' }))

    expect(
      await screen.findByText('Give the story a short title.'),
    ).toBeInTheDocument()
    expect(screen.getByText("The story can't be empty.")).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('lists stories with line breaks kept, and deletes after confirmation', async () => {
    const calls = mockApi({
      'GET /api/v1/stories': [story({ body: 'Line one\nLine two' })],
      'GET /api/v1/stories/themes': themes,
      'DELETE /api/v1/stories/1': undefined,
    })
    const user = userEvent.setup()
    renderWithQueryClient(<StoriesPage />)

    const body = await screen.findByText(/Line one/)
    expect(body.textContent).toBe('Line one\nLine two')
    expect(body).toHaveClass('whitespace-pre-wrap')

    await user.click(screen.getByRole('button', { name: 'Delete' }))
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false) // not yet
    await user.click(
      screen.getByRole('button', { name: 'Yes, delete "Robotics club"' }),
    )

    expect(
      calls.some(
        (c) => c.method === 'DELETE' && c.path === '/api/v1/stories/1',
      ),
    ).toBe(true)
  })

  it('filters by theme', async () => {
    const calls = mockApi({
      'GET /api/v1/stories': [story()],
      'GET /api/v1/stories/themes': themes,
    })
    const user = userEvent.setup()
    renderWithQueryClient(<StoriesPage />)
    await screen.findByText('We built a robot.')

    await user.selectOptions(
      screen.getByLabelText('Filter by theme'),
      'leadership',
    )

    expect(calls.some((c) => c.search === '?theme=leadership')).toBe(true)
  })
})
