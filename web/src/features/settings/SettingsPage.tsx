import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId, useState } from 'react'

import {
  getAppSettings,
  getBackground,
  setBackground,
  setNotificationKinds,
  setSearchQueries,
  type AppSettings,
  type NotificationKind,
} from '@/api/notifications'
import { updateProfile } from '@/api/profile'
import { runDiscovery } from '@/api/sources'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { notificationKeys } from '@/features/notifications/keys'
import { queryKeys } from '@/features/profile/queries'
import { Pill } from '@/features/scholarships/components'
import { timeAgo } from '@/features/sources/status'

const settingsKeys = {
  settings: ['settings'] as const,
  background: ['background'] as const,
}

const KIND_LABELS: Record<NotificationKind, string> = {
  new_match: 'New scholarships I may be eligible for',
  changed: 'Changes to a deadline, amount, eligibility or requirements',
  deadline: 'Deadline reminders (14 and 3 days before)',
}

/** FR-N2, FR-N3, FR-N5: background running, notifications, weekly search. */
export function SettingsPage() {
  const settings = useQuery({
    queryKey: settingsKeys.settings,
    queryFn: getAppSettings,
  })

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          The daily check, what you're notified about, and the weekly search for
          new scholarship pages.
        </p>
      </div>
      <BackgroundCard />
      {settings.isPending && <p role="status">Loading settings…</p>}
      {settings.isError && (
        <p role="alert" className="text-destructive">
          Couldn't load settings. Is the API running?
        </p>
      )}
      {settings.isSuccess && (
        <>
          <NotificationsSettings settings={settings.data} />
          <SearchSettings settings={settings.data} />
        </>
      )}
    </div>
  )
}

function BackgroundCard() {
  const queryClient = useQueryClient()
  const [confirmOn, setConfirmOn] = useState(false)
  const background = useQuery({
    queryKey: settingsKeys.background,
    queryFn: getBackground,
  })
  const toggle = useMutation({
    mutationFn: (enabled: boolean) => setBackground(enabled),
    onSuccess: (data) => {
      queryClient.setQueryData(settingsKeys.background, data)
      setConfirmOn(false)
    },
  })
  const run = useMutation({
    mutationFn: runDiscovery,
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: notificationKeys.all }),
        queryClient.invalidateQueries({ queryKey: settingsKeys.background }),
        queryClient.invalidateQueries({ queryKey: settingsKeys.settings }),
      ]),
  })

  if (!background.isSuccess) return null
  const b = background.data
  const on = b.enabled && b.loaded

  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          Daily check
        </CardTitle>
        <CardDescription>{b.schedule}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <Pill
            text={on ? 'On' : b.enabled ? 'Not installed' : 'Off'}
            tone={on ? 'good' : 'neutral'}
          />
          <span>{b.summary}</span>
        </div>
        {b.dry_run && (
          <p className="text-muted-foreground">
            Dry run: switching only writes a file in the data folder; launchd
            isn't touched.
          </p>
        )}
        <p className="text-muted-foreground">
          Last scheduled run:{' '}
          {b.last_scheduled_run
            ? `${timeAgo(b.last_scheduled_run.started_at)} (${b.last_scheduled_run.status})`
            : 'never'}
        </p>

        {on ? (
          <Button
            size="sm"
            variant="outline"
            disabled={toggle.isPending}
            onClick={() => toggle.mutate(false)}
          >
            Switch off
          </Button>
        ) : confirmOn ? (
          <div className="space-y-2 rounded-md border p-3">
            <p>
              This installs a background job for your Mac user that runs the
              daily check. You can switch it off here or with{' '}
              <code>scholar background off</code>.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={toggle.isPending}
                onClick={() => toggle.mutate(true)}
              >
                Install and switch on
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setConfirmOn(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button
            size="sm"
            variant="outline"
            onClick={() => setConfirmOn(true)}
          >
            Switch on…
          </Button>
        )}
        {toggle.isError && (
          <p role="alert" className="text-destructive">
            {toggle.error.message}
          </p>
        )}

        <div className="space-y-1 border-t pt-3">
          <Button
            size="sm"
            variant="outline"
            disabled={run.isPending}
            onClick={() => run.mutate()}
          >
            {run.isPending ? 'Checking… (this can take a minute)' : 'Run now'}
          </Button>
          <p className="text-xs text-muted-foreground">
            Works even when the daily check is off.
          </p>
          {run.isSuccess && (
            <p role="status">
              Run {run.data.status}:{' '}
              {Number(run.data.summary.notifications_created ?? 0)} new
              notification(s).
            </p>
          )}
          {run.isError && (
            <p role="alert" className="text-destructive">
              {run.error.message}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function NotificationsSettings({ settings }: { settings: AppSettings }) {
  const queryClient = useQueryClient()
  // Optimistic: the checkbox changes at once; a failed save puts it back.
  const patch = (change: Partial<AppSettings>) => {
    const before = queryClient.getQueryData<AppSettings>(settingsKeys.settings)
    if (before) {
      queryClient.setQueryData(settingsKeys.settings, { ...before, ...change })
    }
    return { before }
  }
  const restore = (before?: AppSettings) => {
    if (before) queryClient.setQueryData(settingsKeys.settings, before)
  }
  const master = useMutation({
    mutationFn: (enabled: boolean) =>
      updateProfile({ notifications_enabled: enabled }),
    onMutate: (enabled) => patch({ notifications_enabled: enabled }),
    onError: (_error, _vars, context) => restore(context?.before),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: settingsKeys.settings }),
        queryClient.invalidateQueries({ queryKey: queryKeys.profile }),
      ]),
  })
  const kinds = useMutation({
    mutationFn: setNotificationKinds,
    onMutate: (change) =>
      patch({
        notification_kinds: { ...settings.notification_kinds, ...change },
      }),
    onError: (_error, _vars, context) => restore(context?.before),
    onSuccess: (data) => queryClient.setQueryData(settingsKeys.settings, data),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          Notifications
        </CardTitle>
        <CardDescription>
          Shown on the Today screen (in the app only). Nothing is repeated
          unless something important changes.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <label className="flex items-center gap-2 font-medium">
          <input
            type="checkbox"
            className="size-4 accent-primary"
            checked={settings.notifications_enabled}
            disabled={master.isPending}
            onChange={(e) => master.mutate(e.target.checked)}
          />
          Notify me
        </label>
        <fieldset
          className="space-y-1.5 pl-6"
          disabled={!settings.notifications_enabled}
        >
          <legend className="sr-only">Kinds of notification</legend>
          {(Object.keys(KIND_LABELS) as NotificationKind[]).map((kind) => (
            <label key={kind} className="flex items-center gap-2">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={settings.notification_kinds[kind] ?? true}
                onChange={(e) => kinds.mutate({ [kind]: e.target.checked })}
              />
              {KIND_LABELS[kind]}
            </label>
          ))}
        </fieldset>
        {(master.isError || kinds.isError) && (
          <p role="alert" className="text-destructive">
            {(master.error ?? kinds.error)?.message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function SearchSettings({ settings }: { settings: AppSettings }) {
  const queryClient = useQueryClient()
  const id = useId()
  const [text, setText] = useState(settings.search_queries.join('\n'))
  const save = useMutation({
    mutationFn: () => setSearchQueries(text.split('\n')),
    onSuccess: (data) => {
      queryClient.setQueryData(settingsKeys.settings, data)
      setText(data.search_queries.join('\n'))
    },
  })
  const current = text
    .split('\n')
    .map((q) => q.trim())
    .filter(Boolean)
  const unsaved = current.join('\n') !== settings.search_queries.join('\n')
  const suggestions = settings.suggested_queries.filter(
    (q) => !current.includes(q),
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          Weekly search for new pages
        </CardTitle>
        <CardDescription>
          Once a week, these exact words are sent to Tavily, an outside search
          service. Nothing else from your profile is sent. Pages it finds wait
          on the Sources page for you to approve.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {!settings.search_configured && (
          <p className="rounded-md border border-dashed p-3 text-muted-foreground">
            Search is off: no search key is set. To use it, add{' '}
            <code>TAVILY_API_KEY</code> to <code>api/.env</code>. You can still
            prepare your queries now.
          </p>
        )}
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-queries`}>Queries (one per line)</Label>
          <Textarea
            id={`${id}-queries`}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. nursing scholarship Ohio"
          />
        </div>
        {suggestions.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-muted-foreground">
              Suggestions from your studies and state (not added until you
              save):
            </p>
            <ul className="flex flex-wrap gap-2">
              {suggestions.map((q) => (
                <li key={q}>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      setText((t) => (t.trim() ? `${t.trim()}\n${q}` : q))
                    }
                  >
                    Add “{q}”
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="sm"
            disabled={!unsaved || save.isPending}
            onClick={() => save.mutate()}
          >
            Save queries
          </Button>
          <span className="text-xs text-muted-foreground">
            Last search:{' '}
            {settings.last_search_at
              ? timeAgo(settings.last_search_at)
              : 'never'}
          </span>
        </div>
        {save.isError && (
          <p role="alert" className="text-destructive">
            {save.error.message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
