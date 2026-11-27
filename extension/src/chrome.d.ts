/**
 * The few Chrome extension APIs the popup uses, typed by hand so the
 * extension needs no extra type package. See developer.chrome.com/docs/extensions/reference.
 */
declare namespace chrome {
  namespace tabs {
    type Tab = { id?: number; url?: string }
    function query(info: {
      active: boolean
      currentWindow: boolean
    }): Promise<Tab[]>
  }
  namespace scripting {
    type Target = { tabId: number }
    function executeScript(details: {
      target: Target
      files: string[]
    }): Promise<unknown[]>
    function executeScript<Args extends unknown[], Result>(details: {
      target: Target
      func: (...args: Args) => Result
      args: Args
    }): Promise<{ result?: Result }[]>
  }
}
