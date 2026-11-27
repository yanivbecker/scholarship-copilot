/**
 * How the popup talks to the current tab. The real bridge injects
 * content.js into the top frame (never into embedded frames) only when the
 * student acts; tests use a bridge that runs page.ts directly.
 */
import type { Entry } from './match'
import type { FillReport, Kept, Preview } from './page'

export type PageBridge = {
  host: string
  preview(entries: Entry[]): Promise<Preview>
  fill(entries: Entry[], kept: Kept[]): Promise<FillReport>
  clear(): Promise<void>
}

export class PageError extends Error {}

export async function chromeBridge(): Promise<PageBridge> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  if (tab?.id === undefined || !tab.url || !/^https?:/.test(tab.url)) {
    throw new PageError(
      'Open the scholarship application form in this tab first.',
    )
  }
  const tabId = tab.id
  const host = new URL(tab.url).hostname
  const ready = chrome.scripting
    .executeScript({ target: { tabId }, files: ['content.js'] })
    .catch(() => {
      throw new PageError("Chrome doesn't allow filling forms on this page.")
    })

  async function run<Args extends unknown[], R>(
    func: (...args: Args) => R,
    args: Args,
  ): Promise<R> {
    await ready
    const [frame] = await chrome.scripting.executeScript({
      target: { tabId },
      func,
      args,
    })
    if (frame?.result === undefined)
      throw new PageError('The page did not answer.')
    return frame.result
  }

  return {
    host,
    preview: (entries) =>
      run((e: Entry[]) => window.__scholarshipCopilot!.preview(e), [entries]),
    fill: (entries, kept) =>
      run(
        (e: Entry[], k: Kept[]) => window.__scholarshipCopilot!.fill(e, k),
        [entries, kept],
      ),
    clear: async () => {
      await run(() => {
        window.__scholarshipCopilot!.clear()
        return true
      }, [])
    },
  }
}
