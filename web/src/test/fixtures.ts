/** Fictional test data (NFR-10). Shaped like real API responses. */
import type { Catalog, Fact, Profile, Story } from '@/api/profile'
import type { Eligibility, Scholarship } from '@/api/scholarships'
import type { Source } from '@/api/sources'

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

// --- Sources and scholarships (fictional) ---

export const source = (overrides: Partial<Source> = {}): Source => ({
  id: 1,
  url: 'https://example.org/awards',
  label: 'Test Foundation',
  status: 'approved',
  created_at: '2026-01-01T00:00:00Z',
  last_checked_at: '2026-01-02T00:00:00Z',
  last_result: 'ok',
  last_message: null,
  last_changed_at: '2026-01-02T00:00:00Z',
  extraction_status: null,
  extraction_message: null,
  ...overrides,
})

export const eligibilityItem = (
  overrides: Partial<Eligibility> = {},
): Eligibility => ({
  scholarship_id: 7,
  name: 'Test Foundation STEM Award',
  sponsor: 'Test Foundation',
  status: 'discovered',
  status_label: 'Discovered',
  amount: 2500,
  amount_text: '$2,500',
  open_questions: 2,
  cycle_id: 70,
  year: 2027,
  deadline: '2027-03-01',
  verdict: 'needs_info',
  summary: '2 questions to answer.',
  as_of: '2027-03-01',
  criteria: [
    {
      criterion_id: 701,
      kind: 'gpa_min',
      quote: 'Applicants must have a cumulative GPA of 3.0 or higher.',
      source_url: 'https://example.org/awards',
      outcome: 'unknown',
      reason: "Your profile doesn't have your gpa yet.",
      question: { text: 'What is your gpa?', fact_key: 'gpa', optional: false },
      confirmable: false,
    },
    {
      criterion_id: 702,
      kind: 'free_text',
      quote: 'Applicants must demonstrate leadership in their community.',
      source_url: 'https://example.org/awards',
      outcome: 'unknown',
      reason: 'This requirement needs your judgment.',
      question: {
        text: 'Do you meet this requirement?',
        fact_key: null,
        optional: false,
      },
      confirmable: true,
    },
  ],
  questions: [
    { text: 'What is your gpa?', fact_key: 'gpa', optional: false },
    { text: 'Do you meet this requirement?', fact_key: null, optional: false },
  ],
  score: {
    total: 62,
    note: 'Our ranking for where to spend effort, not your chances of winning.',
    parts: [
      {
        name: 'amount',
        value: 0.8,
        basis: 'listing',
        detail: '$2,500 published by the sponsor.',
      },
      { name: 'fit', value: 0, basis: 'estimate', detail: '0 of 2 confirmed.' },
    ],
  },
  ...overrides,
})

export const scholarshipRecord = (
  overrides: Partial<Scholarship> = {},
): Scholarship => ({
  id: 7,
  name: 'Test Foundation STEM Award',
  sponsor: 'Test Foundation',
  official_url: null,
  description: null,
  status: 'discovered',
  scam_flags: [],
  needs_review: false,
  review_reason: null,
  cycles: [
    {
      id: 70,
      year: 2027,
      amount_text: '$2,500',
      amount_min: 2500,
      amount_max: 2500,
      deadline: '2027-03-01',
      deadline_quote: 'Applications are due March 1, 2027.',
      source_url: 'https://example.org/awards',
      extracted_by: 'test-model',
      extracted_at: '2026-01-02T00:00:00Z',
      criteria: [],
    },
  ],
  ...overrides,
})
