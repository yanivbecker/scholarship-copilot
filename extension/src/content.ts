/**
 * Injected into the current tab (top frame only) when the student asks.
 * It only makes three functions available to the popup; nothing runs here
 * on its own.
 */
import { clear, fill, preview } from './page'

declare global {
  interface Window {
    __scholarshipCopilot?: {
      preview: typeof preview
      fill: typeof fill
      clear: typeof clear
    }
  }
}

window.__scholarshipCopilot = {
  preview: (entries) => preview(entries),
  fill: (entries, kept) => fill(entries, kept),
  clear: () => clear(),
}
