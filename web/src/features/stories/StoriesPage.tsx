import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  createStory,
  deleteStory,
  updateStory,
  type Story,
  type StoryIn,
} from '@/api/profile'
import { Badge } from '@/components/ui/badge'
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
import {
  queryKeys,
  useStories,
  useStoryThemes,
} from '@/features/profile/queries'

import { StoryForm } from './StoryForm'

/** The story bank: experiences in the student's own words (FR-P5). */
export function StoriesPage() {
  const queryClient = useQueryClient()
  const [theme, setTheme] = useState<string>()
  const stories = useStories(theme)
  const allStories = useStories()
  const themes = useStoryThemes()

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.stories })
  const create = useMutation({ mutationFn: createStory, onSuccess: refresh })

  const suggested = themes.data?.suggested ?? []
  const usedThemes = [
    ...new Set((allStories.data ?? []).flatMap((s) => s.themes)),
  ]
  const filterOptions = [...new Set([...usedThemes, ...suggested])].sort()

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Story bank</h1>
        <p className="text-muted-foreground">
          Experiences in your own words. Writing help draws only on these and
          your profile, never on anything invented.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle role="heading" aria-level={2}>
            Add a story
          </CardTitle>
          <CardDescription>
            A moment, project, challenge, or role. Rough notes are fine.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <StoryForm
            suggestedThemes={suggested}
            submitLabel="Save story"
            onSubmit={(story) => create.mutateAsync(story)}
          />
        </CardContent>
      </Card>

      <section aria-labelledby="your-stories" className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 id="your-stories" className="text-lg font-semibold">
            Your stories
          </h2>
          <div className="space-y-1">
            <Label htmlFor="theme-filter">Filter by theme</Label>
            <NativeSelect
              id="theme-filter"
              value={theme ?? ''}
              onChange={(e) => setTheme(e.target.value || undefined)}
            >
              <NativeSelectOption value="">All themes</NativeSelectOption>
              {filterOptions.map((t) => (
                <NativeSelectOption key={t} value={t}>
                  {t}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
        </div>
        {stories.isPending && <p role="status">Loading stories…</p>}
        {stories.isError && (
          <p role="alert" className="text-destructive">
            Couldn't load stories. Is the API running?
          </p>
        )}
        {stories.isSuccess && stories.data.length === 0 && (
          <p className="text-muted-foreground">
            {theme ? `No stories tagged "${theme}".` : 'No stories yet.'}
          </p>
        )}
        {stories.isSuccess && (
          <ul className="space-y-4">
            {stories.data.map((story) => (
              <li key={story.id}>
                <StoryCard
                  story={story}
                  suggestedThemes={suggested}
                  onChanged={refresh}
                />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

type StoryCardProps = {
  story: Story
  suggestedThemes: string[]
  onChanged: () => Promise<unknown>
}

function StoryCard({ story, suggestedThemes, onChanged }: StoryCardProps) {
  const [editing, setEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const update = useMutation({
    mutationFn: (body: StoryIn) => updateStory(story.id, body),
    onSuccess: async () => {
      await onChanged()
      setEditing(false)
    },
  })
  const remove = useMutation({
    mutationFn: () => deleteStory(story.id),
    onSuccess: onChanged,
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle role="heading" aria-level={3}>
          {story.title}
        </CardTitle>
        {story.themes.length > 0 && (
          <ul aria-label="Themes" className="flex flex-wrap gap-1.5">
            {story.themes.map((t) => (
              <li key={t}>
                <Badge variant="secondary">{t}</Badge>
              </li>
            ))}
          </ul>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {editing ? (
          <StoryForm
            initial={story}
            suggestedThemes={suggestedThemes}
            submitLabel="Save changes"
            onSubmit={(body) => update.mutateAsync(body)}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <>
            {/* pre-wrap shows line breaks exactly as the student typed them */}
            <p className="text-sm whitespace-pre-wrap">{story.body}</p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEditing(true)}
              >
                Edit
              </Button>
              {confirmingDelete ? (
                <>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => remove.mutate()}
                    disabled={remove.isPending}
                  >
                    Yes, delete "{story.title}"
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setConfirmingDelete(false)}
                  >
                    Keep it
                  </Button>
                </>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setConfirmingDelete(true)}
                >
                  Delete
                </Button>
              )}
            </div>
            {remove.isError && (
              <p role="alert" className="text-sm text-destructive">
                {remove.error.message}
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
