import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'

import {
  catalog,
  fact,
  packet,
  packetItem,
  scholarshipRecord,
  story,
  version,
} from '@/test/fixtures'
import { mockApi } from '@/test/mockApi'
import { renderWithQueryClient } from '@/test/render'

import { PacketPage } from './PacketPage'

const PACKET = 'GET /api/v1/scholarships/7/packet'
const base = {
  'GET /api/v1/scholarships': [scholarshipRecord()],
  'GET /api/v1/library': [],
  'GET /api/v1/scholarships/7/status': {},
}

const render = () =>
  renderWithQueryClient(
    <MemoryRouter initialEntries={['/scholarships/7/packet']}>
      <Routes>
        <Route path="/scholarships/:id/packet" element={<PacketPage />} />
      </Routes>
    </MemoryRouter>,
  )

describe('PacketPage', () => {
  it('offers coaching before the rules are checked, but not drafting', async () => {
    mockApi({ ...base, [PACKET]: packet({ items: [packetItem()] }) })
    const user = userEvent.setup()
    render()

    await user.click(await screen.findByText('Writing help (AI)'))

    expect(screen.getByText('Not checked')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Ask me questions' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/AI drafting is off/)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Draft a new version' }),
    ).not.toBeInTheDocument()
  })

  it('turns all AI help off when the rules prohibit it', async () => {
    mockApi({
      ...base,
      [PACKET]: packet({
        rules_status: 'prohibited',
        ai_coaching_allowed: false,
        items: [packetItem()],
      }),
    })
    render()

    expect(
      await screen.findByText(/AI help is off: you confirmed/),
    ).toBeInTheDocument()
    expect(screen.queryByText('Writing help (AI)')).not.toBeInTheDocument()
  })

  it('counts length live and flags going over the limit (FR-A6)', async () => {
    const calls = mockApi({
      ...base,
      [PACKET]: packet({ items: [packetItem()] }),
      'POST /api/v1/packet-items/21/versions': packet({
        items: [packetItem()],
      }),
    })
    const user = userEvent.setup()
    render()

    const box = await screen.findByLabelText('Your response')
    await user.type(box, 'one two three')
    expect(screen.getByText('3 / 10 words')).toBeInTheDocument()

    await user.type(box, ' four five six seven eight nine ten eleven')
    expect(screen.getByText(/over the limit/)).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Save as new version' }),
    )
    const saved = calls.find((c) => c.method === 'POST')
    expect(saved?.body).toEqual({
      text: 'one two three four five six seven eight nine ten eleven',
    })
  })

  it('only lets a version within the limit be approved', async () => {
    const calls = mockApi({
      ...base,
      [PACKET]: packet({
        items: [
          packetItem({
            versions: [
              version({
                id: 31,
                number: 1,
                over_limit: true,
                text: 'Too long',
              }),
              version({ id: 32, number: 2, text: 'Just right.' }),
            ],
          }),
        ],
      }),
      'POST /api/v1/packet-items/21/versions/32/approve': packet(),
    })
    const user = userEvent.setup()
    render()

    await user.click(await screen.findByText('Versions (2)'))
    const [second, first] = screen.getAllByRole('listitem', {
      name: (_, el) => el.textContent?.includes('Version') ?? false,
    })
    expect(
      within(first!).getByRole('button', { name: 'Approve this version' }),
    ).toBeDisabled()
    await user.click(
      within(second!).getByRole('button', { name: 'Approve this version' }),
    )
    expect(calls.some((c) => c.path.endsWith('/versions/32/approve'))).toBe(
      true,
    )
  })

  it('confirms "allowed" only with a quote from the listing (FR-A2)', async () => {
    const quote = 'Applicants may use AI writing tools to help edit.'
    const calls = mockApi({
      ...base,
      [PACKET]: packet(),
      'GET /api/v1/packets/11/rules/scan': {
        suggested: 'allowed',
        candidates: [quote],
        source_url: 'https://example.org/awards',
        has_text: true,
      },
      'PUT /api/v1/packets/11/rules': packet({
        rules_status: 'allowed',
        rules_quote: quote,
        ai_writing_allowed: true,
      }),
    })
    const user = userEvent.setup()
    render()

    await user.click(
      await screen.findByRole('button', { name: 'Find what the listing says' }),
    )
    expect(await screen.findByText(/You decide/)).toBeInTheDocument()
    await user.click(screen.getByLabelText('The rules allow AI help'))
    const confirm = screen.getByRole('button', { name: 'Confirm the rules' })
    expect(confirm).toBeDisabled() // no quote yet

    await user.click(screen.getByRole('button', { name: 'Use as quote' }))
    await user.click(confirm)

    const put = calls.find((c) => c.method === 'PUT')
    expect(put?.body).toEqual({ status: 'allowed', quote })
    // The status pill now says so (the suggestion above says it too).
    expect(await screen.findAllByText('AI help allowed')).toHaveLength(2)
  })

  it('says plainly when the listing never mentions AI', async () => {
    mockApi({
      ...base,
      [PACKET]: packet(),
      'GET /api/v1/packets/11/rules/scan': {
        suggested: 'unclear',
        candidates: [],
        source_url: null,
        has_text: true,
      },
    })
    const user = userEvent.setup()
    render()

    await user.click(
      await screen.findByRole('button', { name: 'Find what the listing says' }),
    )

    expect(
      await screen.findByText(
        /doesn't mention AI. That doesn't mean it's allowed/,
      ),
    ).toBeInTheDocument()
  })

  it('drafts only from the stories and facts the student ticks (FR-A4)', async () => {
    const allowed = packet({
      rules_status: 'allowed',
      ai_writing_allowed: true,
      items: [packetItem()],
    })
    const calls = mockApi({
      ...base,
      [PACKET]: allowed,
      'GET /api/v1/stories': [
        story({ id: 1, title: 'Tutoring club' }),
        story({ id: 2, title: 'Baking' }),
      ],
      'GET /api/v1/facts': [fact({ key: 'gpa', value: 3.8 })],
      'GET /api/v1/facts/catalog': catalog,
      'POST /api/v1/packet-items/21/draft': {
        packet: allowed,
        version_id: 40,
        kept: 2,
        removed: [
          {
            text: 'I tutored 40 students.',
            reason: 'Not in what it cites: 40.',
          },
        ],
      },
    })
    const user = userEvent.setup()
    render()

    await user.click(await screen.findByText('Writing help (AI)'))
    const draft = screen.getByRole('button', { name: 'Draft a new version' })
    expect(draft).toBeDisabled() // nothing is pre-selected
    await user.click(await screen.findByLabelText('Story: Tutoring club'))
    await user.click(draft)

    const post = calls.find((c) => c.path.endsWith('/draft'))
    expect(post?.body).toEqual({ story_ids: [1], fact_keys: [] })
    expect(await screen.findByText(/couldn't be traced/)).toBeInTheDocument()
    expect(
      screen.getByText('“I tutored 40 students.”', { exact: false }),
    ).toBeInTheDocument()
  })

  it('ticks off documents and adds items', async () => {
    const doc = packetItem({
      id: 22,
      kind: 'document',
      title: 'Transcript',
      prompt: null,
      limit_value: null,
      limit_unit: null,
    })
    const calls = mockApi({
      ...base,
      [PACKET]: packet({ items: [doc] }),
      'PUT /api/v1/packet-items/22': packet({
        items: [{ ...doc, done: true, finished: true }],
      }),
      'POST /api/v1/packets/11/items': packet({ items: [doc] }),
    })
    const user = userEvent.setup()
    render()

    await user.click(await screen.findByLabelText('I have this ready'))
    expect(calls.find((c) => c.method === 'PUT')?.body).toMatchObject({
      done: true,
    })
    expect(await screen.findByText('Finished')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Type'), 'short_answer')
    await user.type(screen.getByLabelText('Title'), 'Why this award?')
    await user.type(screen.getByLabelText('Length limit (optional)'), '500')
    await user.selectOptions(screen.getByLabelText('Limit counts'), 'chars')
    await user.click(screen.getByRole('button', { name: 'Add to checklist' }))

    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      kind: 'short_answer',
      title: 'Why this award?',
      prompt: null,
      limit_value: 500,
      limit_unit: 'chars',
      required: true,
    })
  })

  it('approves the packet only when every required item is finished', async () => {
    mockApi({
      ...base,
      [PACKET]: packet({
        items: [packetItem()],
        progress: {
          finished: 0,
          required: 1,
          missing: ['Leadership essay'],
          complete: false,
        },
      }),
    })
    render()

    expect(
      await screen.findByText('Still to do: Leadership essay.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Approve the whole packet' }),
    ).toBeDisabled()
  })

  it('gives form fields a value to approve, without AI writing help', async () => {
    const field = packetItem({
      id: 23,
      kind: 'form_field',
      title: 'Email',
      prompt: null,
      limit_value: null,
      limit_unit: null,
      versions: [version({ text: 'sam@example.org', origin: 'profile' })],
    })
    const calls = mockApi({
      ...base,
      [PACKET]: packet({
        rules_status: 'allowed',
        ai_writing_allowed: true,
        items: [field],
      }),
      'POST /api/v1/packets/11/common-fields': packet({ items: [field] }),
    })
    const user = userEvent.setup()
    render()

    expect(await screen.findByLabelText('Value to enter')).toHaveValue(
      'sam@example.org',
    )
    expect(screen.queryByText('Writing help (AI)')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Filled in')).not.toBeInTheDocument()
    await user.click(screen.getByText('Versions (1)'))
    expect(screen.getByText(/From your profile/)).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', {
        name: 'Add common form fields from my profile',
      }),
    )
    expect(calls.some((c) => c.path.endsWith('/common-fields'))).toBe(true)
  })
})
