import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, belongsTo, type Api, type FillSheet } from '../src/api'
import type { PageBridge } from '../src/bridge'
import { clear, fill, preview } from '../src/page'
import { startPopup } from '../src/popup'

const SHEET: FillSheet = {
  packet_id: 11,
  scholarship_name: 'Test Foundation STEM Award',
  official_url: 'https://example.org/awards',
  entries: [
    {
      item_id: 1,
      kind: 'form_field',
      title: 'Email',
      prompt: null,
      text: 'sam@example.org',
    },
    {
      item_id: 2,
      kind: 'form_field',
      title: 'Phone',
      prompt: null,
      text: '555-0100',
    },
  ],
}

function setup(overrides: Partial<Api> = {}) {
  // The "website" lives in this test's document; the popup in its own div.
  document.body.innerHTML = `
    <form id="site"><label>Email <input name="email"></label>
    <label>Hobby <input name="hobby"></label></form>
    <div id="popup"></div>`
  const api: Api = {
    approvedPackets: vi.fn(async () => [
      {
        packet_id: 9,
        scholarship_id: 1,
        name: 'Other Award',
        hosts: ['other.org'],
        approved_at: '2027-01-01T00:00:00Z',
      },
      {
        packet_id: 11,
        scholarship_id: 7,
        name: 'Test Foundation STEM Award',
        hosts: ['example.org'],
        approved_at: '2027-01-02T00:00:00Z',
      },
    ]),
    fillSheet: vi.fn(async () => SHEET),
    reportFill: vi.fn(async () => undefined),
    ...overrides,
  }
  const site = () => document.getElementById('site')!
  const bridge: PageBridge = {
    host: 'apply.example.org',
    // Run the real page code, but only against the "website" part.
    preview: async (e) => preview(e, scoped(site())),
    fill: async (e, k) => fill(e, k, scoped(site())),
    clear: async () => clear(scoped(site())),
  }
  const copy = vi.fn(async () => undefined)
  const root = document.getElementById('popup')!
  return { api, bridge, copy, root, site }
}

/** A Document-like view limited to one element, so the popup's own UI is never "the form". */
function scoped(node: HTMLElement): Document {
  return {
    querySelectorAll: (s: string) => node.querySelectorAll(s),
    getElementById: (id: string) => node.querySelector(`#${id}`),
    querySelector: (s: string) => node.querySelector(s),
    location: { hostname: 'apply.example.org' },
  } as unknown as Document
}

const buttonNamed = (root: HTMLElement, name: string | RegExp) =>
  [...root.querySelectorAll('button')].find((b) =>
    typeof name === 'string'
      ? b.textContent === name
      : name.test(b.textContent ?? ''),
  )!

const flush = () => new Promise((r) => setTimeout(r, 0))

beforeEach(() => vi.restoreAllMocks())

describe('popup', () => {
  it('matches a subdomain to the packet’s site', () => {
    expect(belongsTo('apply.example.org', ['example.org'])).toBe(true)
    expect(belongsTo('www.example.org', ['example.org'])).toBe(true)
    expect(belongsTo('example.org.evil.com', ['example.org'])).toBe(false)
  })

  it('preselects this site’s packet, previews, fills, records, never submits', async () => {
    const { api, bridge, copy, root, site } = setup()
    const submitted = vi.fn((e: Event) => e.preventDefault())
    site().addEventListener('submit', submitted)

    await startPopup({ root, api, bridge: async () => bridge, copy })
    const select = root.querySelector('select')!
    expect(select.value).toBe('11')

    buttonNamed(root, 'Preview').click()
    await flush()
    expect(root.textContent).toContain('Email ← Email')
    expect(root.textContent).toContain('1 left for you')
    expect(root.textContent).toContain('Copy the rest yourself') // Phone found no field

    buttonNamed(root, /^Fill 1 field/).click()
    await flush()

    const email = site().querySelector<HTMLInputElement>('[name=email]')!
    expect(email.value).toBe('sam@example.org')
    expect(root.textContent).toContain('Nothing was submitted.')
    expect(submitted).not.toHaveBeenCalled()
    expect(api.reportFill).toHaveBeenCalledWith(11, {
      host: 'apply.example.org',
      filled: 1,
      unmatched: 1,
    })
  })

  it('fills nothing the student unticked', async () => {
    const { api, bridge, copy, root, site } = setup()
    await startPopup({ root, api, bridge: async () => bridge, copy })
    buttonNamed(root, 'Preview').click()
    await flush()

    root.querySelector<HTMLInputElement>('.plan input')!.click()
    buttonNamed(root, /^Fill 1 field/).click()
    await flush()

    expect(site().querySelector<HTMLInputElement>('[name=email]')!.value).toBe(
      '',
    )
  })

  it('copies an answer that found no field', async () => {
    const { api, bridge, copy, root } = setup()
    await startPopup({ root, api, bridge: async () => bridge, copy })
    buttonNamed(root, 'Preview').click()
    await flush()

    buttonNamed(root, 'Copy').click()
    await flush()

    expect(copy).toHaveBeenCalledWith('555-0100')
  })

  it('treats the page’s labels as text, never as HTML', async () => {
    const { api, bridge, copy, root, site } = setup()
    // A hostile label on a field the popup always lists: passwords are named
    // under "Never filled".
    site().insertAdjacentHTML(
      'beforeend',
      '<input type="password" aria-label="&lt;img src=x onerror=alert(1)&gt;">',
    )
    await startPopup({ root, api, bridge: async () => bridge, copy })
    buttonNamed(root, 'Preview').click()
    await flush()

    expect(root.textContent).toContain(
      '<img src=x onerror=alert(1)> (password field)',
    )
    expect(root.querySelector('img')).toBeNull()
  })

  it('explains when the app isn’t running or nothing is approved', async () => {
    const down = setup({
      approvedPackets: async () => {
        throw new ApiError("Can't reach Scholarship Copilot.")
      },
    })
    await startPopup({ ...down, bridge: async () => down.bridge })
    expect(down.root.querySelector('[role=alert]')!.textContent).toContain(
      "Can't reach",
    )

    const none = setup({ approvedPackets: async () => [] })
    await startPopup({ ...none, bridge: async () => none.bridge })
    expect(none.root.textContent).toContain('No approved packets yet')
  })
})
