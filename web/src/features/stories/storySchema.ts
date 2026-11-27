/** Story validation, mirroring the backend rules. */
import { z } from 'zod'

// Same limits as the backend (api/app/modules/profile/service.py).
const MAX_TITLE = 200
const MAX_BODY = 20_000
const MAX_THEMES = 10
export const MAX_THEME = 40

export const storySchema = z.object({
  title: z
    .string()
    .trim()
    .min(1, 'Give the story a short title.')
    .max(MAX_TITLE, `Title must be at most ${MAX_TITLE} characters.`),
  // Not trimmed: the body is kept exactly as written (FR-P5).
  body: z
    .string()
    .refine((s) => s.trim().length > 0, "The story can't be empty.")
    .refine((s) => s.length <= MAX_BODY, `At most ${MAX_BODY} characters.`),
  themes: z
    .array(z.string().max(MAX_THEME))
    .max(MAX_THEMES, `Use at most ${MAX_THEMES} themes.`),
})

export type StoryFormValues = z.infer<typeof storySchema>

export const normalizeTheme = (t: string) =>
  t.split(/\s+/).filter(Boolean).join(' ').toLowerCase()
