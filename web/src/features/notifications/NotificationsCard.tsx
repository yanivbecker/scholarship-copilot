import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'

import {
  listNotifications,
  markNotificationsRead,
  type Notification,
} from '@/api/notifications'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Pill } from '@/features/scholarships/components'
import { timeAgo, type Tone } from '@/features/sources/status'
import { cn } from '@/lib/utils'

import { notificationKeys } from './keys'

const KINDS: Record<string, { text: string; tone: Tone }> = {
  new_match: { text: 'New match', tone: 'good' },
  changed: { text: 'Changed', tone: 'warning' },
  deadline: { text: 'Deadline', tone: 'bad' },
}

/** FR-N5: in-app notifications, newest first; each said only once (FR-N4). */
export function NotificationsCard() {
  const queryClient = useQueryClient()
  const notes = useQuery({
    queryKey: notificationKeys.all,
    queryFn: listNotifications,
  })
  const read = useMutation({
    mutationFn: (ids?: number[]) => markNotificationsRead(ids),
    onSuccess: (data) => queryClient.setQueryData(notificationKeys.all, data),
  })

  if (!notes.isSuccess) return null
  const { items, unread } = notes.data
  const visible = [...items]
    .sort((a, b) => Number(a.read_at !== null) - Number(b.read_at !== null))
    .slice(0, 10)

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle role="heading" aria-level={2}>
            Notifications{unread > 0 && ` (${unread} new)`}
          </CardTitle>
          {unread > 0 && (
            <Button
              size="sm"
              variant="ghost"
              disabled={read.isPending}
              onClick={() => read.mutate(undefined)}
            >
              Mark all read
            </Button>
          )}
        </div>
        <CardDescription>
          From the daily check: new matches, changes to deadlines, amounts,
          eligibility or requirements, and reminders. Each is said once.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {visible.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing yet. The daily check runs in the background when it's
            switched on (see{' '}
            <Link to="/settings" className="underline underline-offset-4">
              Settings
            </Link>
            ).
          </p>
        ) : (
          <ul className="space-y-3">
            {visible.map((n) => (
              <NotificationRow
                key={n.id}
                note={n}
                onRead={() => read.mutate([n.id])}
                busy={read.isPending}
              />
            ))}
          </ul>
        )}
        {read.isError && (
          <p role="alert" className="text-sm text-destructive">
            {read.error.message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function NotificationRow({
  note: n,
  onRead,
  busy,
}: {
  note: Notification
  onRead: () => void
  busy: boolean
}) {
  const kind = KINDS[n.kind] ?? { text: n.kind, tone: 'neutral' as Tone }
  const unread = n.read_at === null
  return (
    <li
      className={cn(
        'flex flex-wrap items-start justify-between gap-2 rounded-md border p-3 text-sm',
        !unread && 'opacity-70',
      )}
    >
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <Pill {...kind} />
          {n.scholarship_id ? (
            <Link
              to={`/scholarships/${n.scholarship_id}`}
              className="font-medium underline-offset-4 hover:underline"
            >
              {n.title}
            </Link>
          ) : (
            <span className="font-medium">{n.title}</span>
          )}
          {unread && <span className="sr-only">(new)</span>}
        </div>
        {n.body && <p className="text-muted-foreground">{n.body}</p>}
        <p className="text-xs text-muted-foreground">{timeAgo(n.created_at)}</p>
      </div>
      {unread && (
        <Button size="sm" variant="outline" disabled={busy} onClick={onRead}>
          Mark read
        </Button>
      )}
    </li>
  )
}
