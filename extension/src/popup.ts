/**
 * The popup (FR-X1): pick the approved packet, preview, fill, then the
 * student reviews and submits the form themselves (FR-X2).
 *
 * All text from the page or the app is inserted with textContent, never as
 * HTML: a form's labels are written by strangers.
 */
import { api as realApi, belongsTo, type Api, type FillSheet } from './api'
import { chromeBridge, type PageBridge } from './bridge'
import type { Kept, Preview } from './page'

type Deps = {
  root: HTMLElement
  api: Api
  bridge: () => Promise<PageBridge>
  copy: (text: string) => Promise<void>
}

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  text?: string,
  className?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag)
  if (text !== undefined) node.textContent = text
  if (className) node.className = className
  return node
}

function button(text: string, onClick: () => void, className = '') {
  const b = el('button', text, className)
  b.type = 'button'
  b.addEventListener('click', onClick)
  return b
}

export async function startPopup({ root, api, bridge, copy }: Deps) {
  root.replaceChildren()
  const status = el('p', 'Loading…', 'status')
  status.setAttribute('role', 'status')
  const body = el('div')
  root.append(el('h1', 'Fill from my packet'), status, body)

  const say = (text: string, kind: 'info' | 'error' = 'info') => {
    status.textContent = text
    status.className = kind === 'error' ? 'status error' : 'status'
    status.setAttribute('role', kind === 'error' ? 'alert' : 'status')
  }

  let page: PageBridge
  let packets
  try {
    page = await bridge()
    packets = await api.approvedPackets()
  } catch (e) {
    say(e instanceof Error ? e.message : String(e), 'error')
    return
  }
  if (packets.length === 0) {
    say(
      'No approved packets yet. In the app, finish and approve a packet, then try again.',
    )
    return
  }
  say(`On ${page.host}. Choose the packet for this application.`)

  const choose = el('select')
  choose.setAttribute('aria-label', 'Approved packet')
  for (const p of packets) {
    const option = el('option', p.name)
    option.value = String(p.packet_id)
    option.selected = belongsTo(page.host, p.hosts)
    choose.append(option)
  }
  const results = el('div')
  body.append(
    choose,
    button('Preview', () => void doPreview(), 'primary'),
    results,
  )

  let sheet: FillSheet | null = null

  async function doPreview() {
    results.replaceChildren()
    try {
      sheet = await api.fillSheet(Number(choose.value))
      const plan = await page.preview(sheet.entries)
      showPlan(plan)
    } catch (e) {
      say(e instanceof Error ? e.message : String(e), 'error')
    }
  }

  function showPlan(plan: Preview) {
    const s = sheet!
    say(
      `${plan.planned.length} field(s) can be filled. ${plan.unmatched.length} left for you (outlined in amber on the page).`,
    )
    const list = el('ul', undefined, 'plan')
    const boxes: { box: HTMLInputElement; kept: Kept }[] = []
    for (const p of plan.planned) {
      const item = el('li')
      const label = el('label')
      const box = el('input')
      box.type = 'checkbox'
      box.checked = true
      label.append(box, ` ${p.label} ← ${p.title}`)
      item.append(label)
      list.append(item)
      boxes.push({
        box,
        kept: { fieldId: p.fieldId, label: p.label, itemId: p.itemId },
      })
    }
    results.append(list)
    if (plan.skipped.length) {
      results.append(
        el(
          'p',
          `Never filled: ${plan.skipped.map((x) => `${x.label} (${x.reason})`).join(', ')}.`,
          'muted',
        ),
      )
    }
    const fillButton = button(
      `Fill ${plan.planned.length} field(s)`,
      () => void doFill(boxes.filter((b) => b.box.checked).map((b) => b.kept)),
      'primary',
    )
    fillButton.disabled = plan.planned.length === 0
    results.append(fillButton)

    // Answers that found no field: copy them in by hand.
    const unused = s.entries.filter((e) => plan.unusedTitles.includes(e.title))
    if (unused.length) {
      results.append(el('h2', 'Copy the rest yourself'))
      const copies = el('ul', undefined, 'copies')
      for (const entry of unused) {
        const li = el('li')
        li.append(
          el('span', entry.title),
          button('Copy', () => {
            void copy(entry.text).then(() => say(`Copied “${entry.title}”.`))
          }),
        )
        copies.append(li)
      }
      results.append(copies)
    }
  }

  async function doFill(kept: Kept[]) {
    const s = sheet!
    try {
      const report = await page.fill(s.entries, kept)
      await api
        .reportFill(s.packet_id, {
          host: page.host,
          filled: report.filled,
          unmatched: report.unmatched + report.failed.length,
        })
        .catch(() => undefined) // the record is helpful, not required
      results.replaceChildren(
        el(
          'p',
          `Filled ${report.filled} field(s). Check every answer, fill the amber ones, then submit the form yourself.`,
        ),
      )
      for (const f of report.failed) {
        results.append(el('p', `Not filled: ${f.label}: ${f.reason}.`, 'muted'))
      }
      results.append(button('Remove highlights', () => void page.clear()))
      say('Done. Nothing was submitted.')
    } catch (e) {
      say(e instanceof Error ? e.message : String(e), 'error')
    }
  }
}

// In the real popup (not in tests).
if (typeof chrome !== 'undefined' && chrome.scripting) {
  void startPopup({
    root: document.getElementById('app')!,
    api: realApi,
    bridge: chromeBridge,
    copy: (text) => navigator.clipboard.writeText(text),
  })
}
