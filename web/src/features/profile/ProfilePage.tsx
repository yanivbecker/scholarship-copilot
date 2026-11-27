import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  deleteFact,
  updateProfile,
  type Fact,
  type OperatingMode,
} from '@/api/profile'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'

import { MODES } from './modes'
import { ProfileSectionForm } from './ProfileSectionForm'
import { queryKeys, useCatalog, useFacts, useProfile } from './queries'

/** Settings, every catalog section, and custom answers (FR-P3, FR-P6, FR-P7). */
export function ProfilePage() {
  const catalog = useCatalog()
  const facts = useFacts()

  if (catalog.isPending || facts.isPending) {
    return <p role="status">Loading your profile…</p>
  }
  if (catalog.isError || facts.isError) {
    return (
      <p role="alert" className="text-destructive">
        Couldn't load your profile. Is the API running?
      </p>
    )
  }

  const customFacts = facts.data.filter((f) => f.key.startsWith('custom.'))

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Profile</h1>
        <p className="text-muted-foreground">
          Facts used to check eligibility. Every field is optional and can be
          changed any time.
        </p>
      </div>
      <ModeCard />
      {catalog.data.sections.map((section) => (
        <ProfileSectionForm
          key={section.key}
          section={section}
          facts={facts.data}
        />
      ))}
      {customFacts.length > 0 && <CustomFactsCard facts={customFacts} />}
    </div>
  )
}

function ModeCard() {
  const queryClient = useQueryClient()
  const profile = useProfile()
  const mutation = useMutation({
    mutationFn: (mode: OperatingMode) =>
      updateProfile({ operating_mode: mode }),
    onSuccess: (data) => queryClient.setQueryData(queryKeys.profile, data),
  })

  if (!profile.isSuccess) return null
  const current = MODES.find((m) => m.value === profile.data.operating_mode)

  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          Operating mode
        </CardTitle>
        <CardDescription>
          You can change this whenever you like.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <Label htmlFor="operating-mode">Mode</Label>
        <NativeSelect
          id="operating-mode"
          value={profile.data.operating_mode}
          disabled={mutation.isPending}
          onChange={(e) => mutation.mutate(e.target.value as OperatingMode)}
          aria-describedby="operating-mode-help"
        >
          {MODES.map((m) => (
            <NativeSelectOption key={m.value} value={m.value}>
              {m.label}
            </NativeSelectOption>
          ))}
        </NativeSelect>
        <p id="operating-mode-help" className="text-sm text-muted-foreground">
          {current?.description}
        </p>
        {mutation.isError && (
          <p role="alert" className="text-sm text-destructive">
            {mutation.error.message}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function CustomFactsCard({ facts }: { facts: Fact[] }) {
  const queryClient = useQueryClient()
  const remove = useMutation({
    mutationFn: deleteFact,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.facts }),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={2}>
          Answers to scholarship questions
        </CardTitle>
        <CardDescription>
          Saved so you're never asked the same question twice.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y">
          {facts.map((fact) => (
            <li
              key={fact.key}
              className="flex items-start justify-between gap-4 py-3"
            >
              <div>
                <p className="text-sm font-medium">{fact.label}</p>
                <p className="text-sm text-muted-foreground">
                  {String(fact.value)}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => remove.mutate(fact.key)}
                aria-label={`Delete answer: ${fact.label ?? fact.key}`}
              >
                Delete
              </Button>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
