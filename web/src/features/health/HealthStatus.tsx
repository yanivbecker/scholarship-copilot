import { useQuery } from '@tanstack/react-query'

import { apiGet } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

/** Shows whether the backend API is reachable (GET /api/v1/health). */
export function HealthStatus() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet('/api/v1/health'),
    retry: false,
  })

  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle>Backend status</CardTitle>
        <CardDescription>Checks the local API on 127.0.0.1.</CardDescription>
      </CardHeader>
      <CardContent role="status" aria-live="polite">
        {health.isPending && <Badge variant="secondary">Checking…</Badge>}
        {health.isError && (
          <div className="space-y-2">
            <Badge variant="destructive">Unreachable</Badge>
            <p className="text-sm text-muted-foreground">
              Start it with <code>uv run python -m app</code> in the{' '}
              <code>api/</code> folder.
            </p>
          </div>
        )}
        {health.isSuccess && (
          <Badge>
            {health.data.status === 'ok' ? 'Online' : health.data.status} · v
            {health.data.version}
          </Badge>
        )}
      </CardContent>
    </Card>
  )
}
