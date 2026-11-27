/** Fictional test data (NFR-10). Shaped like real API responses. */
import type { Catalog, Fact, Profile, Story } from '@/api/profile'

const def = (
  overrides: Partial<Catalog['sections'][number]['facts'][number]>,
) => ({
  label: '',
  help: '',
  choices: [],
  min_value: null,
  max_value: null,
  sensitive: false,
  type: 'text' as const,
  section: 'basics' as const,
  key: '',
  ...overrides,
})

export const catalog: Catalog = {
  sections: [
    {
      key: 'education',
      label: 'Education',
      sensitive: false,
      facts: [
        def({ key: 'major', label: 'Major', section: 'education' }),
        def({
          key: 'gpa',
          label: 'GPA',
          type: 'number',
          section: 'education',
          min_value: 0,
          max_value: 5,
          help: 'As shown on your transcript.',
        }),
        def({
          key: 'expected_graduation_year',
          label: 'Expected graduation year',
          type: 'integer',
          section: 'education',
          min_value: 1950,
          max_value: 2100,
        }),
        def({
          key: 'education_level',
          label: 'Education level',
          type: 'choice',
          section: 'education',
          choices: [
            { value: 'high_school', label: 'High school' },
            { value: 'undergraduate', label: 'Undergraduate' },
          ],
        }),
      ],
    },
    {
      key: 'demographic',
      label: 'Demographic',
      sensitive: true,
      facts: [
        def({
          key: 'first_generation',
          label: 'First-generation college student',
          type: 'boolean',
          section: 'demographic',
          sensitive: true,
        }),
        def({
          key: 'race_ethnicity',
          label: 'Race / ethnicity',
          type: 'multi_choice',
          section: 'demographic',
          sensitive: true,
          choices: [
            { value: 'asian', label: 'Asian' },
            { value: 'white', label: 'White' },
          ],
        }),
      ],
    },
  ],
}

export const fact = (
  overrides: Partial<Fact> & Pick<Fact, 'key' | 'value'>,
): Fact => ({
  label: null,
  origin: 'manual',
  origin_detail: null,
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
})

export const profile: Profile = {
  display_name: 'Test Student',
  operating_mode: 'hybrid',
  notifications_enabled: true,
  onboarding_step: null,
  onboarding_completed_at: null,
}

export const story = (overrides: Partial<Story> = {}): Story => ({
  id: 1,
  title: 'Robotics club',
  body: 'We built a robot.',
  themes: ['teamwork'],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
})
