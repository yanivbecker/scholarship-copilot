# Scholarship Copilot autofill (Chrome extension)

Fills a scholarship application form from your **approved** packet, when you
ask. It never submits, never touches CAPTCHAs, and never reads, fills or
stores passwords (FR-X1, FR-X2).

## Install (once)

```bash
cd extension
npm ci
npm run build          # creates extension/dist/
```

In Chrome: open `chrome://extensions`, switch on **Developer mode**, click
**Load unpacked**, and choose the `extension/dist` folder. Pin it from the
puzzle-piece menu if you like. After pulling new code, run `npm run build`
again and press the reload icon on the extension's card.

The app must be running (`uv run python -m app` in `api/`, port 8000).

## Use

1. In the app, finish the packet: approve every answer (including the form
   fields such as name and email), then approve the packet.
2. Open the scholarship's application form in Chrome and click the
   extension. It picks the packet for that site.
3. **Preview** shows which field gets which answer. Fields it couldn't match
   are outlined in amber on the page. Untick anything you don't want filled.
4. **Fill** types the answers in. Check every field, fill the amber ones,
   then submit the form yourself.

## What it can and can't do

|                |                                                                                                                                                |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Permissions    | `activeTab` and `scripting`: only the tab you click it on, only when you click. `host_permissions` only for the local app at `127.0.0.1:8000`. |
| Never          | submits, clicks, presses keys, enters frames (CAPTCHAs, payment widgets), reads or fills password fields, stores anything from the page.       |
| Leaves for you | fields it can't match confidently, ties (two "Email" boxes), answers longer than a field allows, fields you already typed in.                  |
| Records        | in the app's history: how many fields were filled, on which site (host name only).                                                             |

`tests/never-submits.test.ts` fails the build if the code ever gains a way to
submit, click, type keys, reach into frames or store page data, and CI fails
if the manifest asks for more permissions.
