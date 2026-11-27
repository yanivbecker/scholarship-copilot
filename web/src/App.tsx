import { HealthStatus } from '@/features/health/HealthStatus'

function App() {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 p-6">
      <h1 className="text-3xl font-semibold tracking-tight">
        Scholarship Copilot
      </h1>
      <HealthStatus />
    </main>
  )
}

export default App
