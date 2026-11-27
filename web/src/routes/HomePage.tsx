import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'

import { getToday, type Action } from '@/api/dashboard'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { HealthStatus } from '@/features/health/HealthStatus'
import { NotificationsCard } from '@/features/notifications/NotificationsCard'
import { SetupBanner } from '@/features/onboarding/SetupBanner'
import { VerdictPill } from '@/features/scholarships/components'
import { timeAgo } from '@/features/sources/status'

const todayKey = ['dashboard', 'today'] as const

function actionLink(action: Action): string {
  if (action.page === 'scholarship' && action.scholarship_id !== null) {
    return `/scholarships/${action.scholarship_id}`
  }
  return action.page === 'sources' ? '/sources' : '/profile'
}

/** The Today screen (FR-UI1): actions, deadlines, new matches, last run. */
export function HomePage() {
  const today = useQuery({ queryKey: todayKey, queryFn: getToday })

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Today</h1>
        {today.isSuccess && (
          <p className="text-muted-foreground">
            {today.data.counts.total ?? 0} scholarships tracked:{' '}
            {today.data.counts.eligible ?? 0} eligible,{' '}
            {today.data.counts.needs_info ?? 0} need info,{' '}
            {today.data.counts.ineligible ?? 0} not eligible.
          </p>
        )}
      </div>
      <SetupBanner />
      {today.isPending && <p role="status">Loading…</p>}
      {today.isError && (
        <p role="alert" className="text-destructive">
          Couldn't load today's overview. Is the API running?
        </p>
      )}
      {today.isSuccess && (
        <div className="grid gap-6 lg:grid-cols-2">
          <NotificationsCard />
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle role="heading" aria-level={2}>
                Things to do
              </CardTitle>
              <CardDescription>
                The most useful first: one answer can settle several
                scholarships.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {today.data.actions.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nothing needs you right now.
                </p>
              ) : (
                <ul className="divide-y">
                  {today.data.actions.slice(0, 12).map((action, i) => (
                    <li key={i} className="py-2">
                      <Link
                        to={actionLink(action)}
                        className="font-medium underline-offset-4 hover:underline"
                      >
                        {action.title}
                      </Link>
                      <p className="text-sm text-muted-foreground">
                        {action.detail}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle role="heading" aria-level={2}>
                Upcoming deadlines
              </CardTitle>
              <CardDescription>Open ones in the next 60 days.</CardDescription>
            </CardHeader>
            <CardContent>
              {today.data.deadlines.length === 0 ? (
                <p className="text-sm text-muted-foreground">None coming up.</p>
              ) : (
                <ul className="space-y-2">
                  {today.data.deadlines.map((d) => (
                    <li
                      key={d.scholarship_id}
                      className="flex flex-wrap items-center justify-between gap-2"
                    >
                      <Link
                        to={`/scholarships/${d.scholarship_id}`}
                        className="underline-offset-4 hover:underline"
                      >
                        {d.name}
                      </Link>
                      <span className="flex items-center gap-2 text-sm">
                        <VerdictPill verdict={d.verdict} />
                        <span
                          className={
                            d.days_left <= 7 ? 'font-semibold' : undefined
                          }
                        >
                          {d.days_left === 0
                            ? 'today'
                            : `in ${d.days_left} days`}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle role="heading" aria-level={2}>
                New matches
              </CardTitle>
              <CardDescription>Found in the last 7 days.</CardDescription>
            </CardHeader>
            <CardContent>
              {today.data.new_matches.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nothing new this week.
                </p>
              ) : (
                <ul className="space-y-2">
                  {today.data.new_matches.map((m) => (
                    <li
                      key={m.scholarship_id}
                      className="flex flex-wrap items-center justify-between gap-2"
                    >
                      <Link
                        to={`/scholarships/${m.scholarship_id}`}
                        className="underline-offset-4 hover:underline"
                      >
                        {m.name}
                      </Link>
                      <VerdictPill verdict={m.verdict} />
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle role="heading" aria-level={2}>
                Last check of your sources
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm">
              {today.data.last_run ? (
                <p>
                  {today.data.last_run.status === 'succeeded'
                    ? 'Completed'
                    : today.data.last_run.status === 'partial'
                      ? 'Completed with some errors'
                      : today.data.last_run.status}{' '}
                  {timeAgo(
                    today.data.last_run.finished_at ??
                      today.data.last_run.started_at,
                  )}
                  .{' '}
                  <Link to="/sources" className="underline underline-offset-4">
                    See sources
                  </Link>
                </p>
              ) : (
                <p>
                  Sources haven't been checked yet.{' '}
                  <Link to="/sources" className="underline underline-offset-4">
                    Run a check
                  </Link>
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
      <HealthStatus />
    </div>
  )
}
