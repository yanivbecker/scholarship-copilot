/** Typed functions for scholarships and their eligibility (FR-E1-E6). */
import { apiGet, request, type Schemas } from './client'

export type Eligibility = Schemas['EligibilityOut']
export type CriterionResult = Schemas['CriterionResultOut']
export type Question = Schemas['QuestionOut']
export type Scholarship = Schemas['ScholarshipOut']
export type Duplicate = Schemas['DuplicateOut']

const V1 = '/api/v1'

export const listEligibility = () => apiGet('/api/v1/eligibility')

export const listScholarships = () => apiGet('/api/v1/scholarships')

export const listDuplicates = () => apiGet('/api/v1/scholarships/duplicates')

export const confirmCriterion = (
  scholarshipId: number,
  criterionId: number,
  answer: boolean | null,
) =>
  request<Eligibility>(
    'PUT',
    `${V1}/scholarships/${scholarshipId}/criteria/${criterionId}/confirmation`,
    { body: { answer } },
  )

export const mergeScholarships = (keepId: number, otherId: number) =>
  request<Scholarship>('POST', `${V1}/scholarships/${keepId}/merge`, {
    body: { other_id: otherId },
  })
