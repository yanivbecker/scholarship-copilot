/** Typed functions for the onboarding wizard and sources endpoints. */
import { apiGet, request, type Schemas } from './client'

export type Onboarding = Schemas['OnboardingOut']
export type OnboardingStep = Schemas['OnboardingStepOut']
export type StepFacts = Schemas['OnboardingStepIn']['facts']
export type Source = Schemas['SourceOut']
export type SourceIn = Schemas['SourceIn']

const V1 = '/api/v1'

export const getOnboarding = () => apiGet('/api/v1/onboarding')

export const submitStep = (step: string, facts: StepFacts = {}) =>
  request<Onboarding>('POST', `${V1}/onboarding/steps/${step}`, {
    body: { facts },
  })

export const getMissingFacts = (keys: string[]) =>
  apiGet('/api/v1/facts/missing', { keys })

export const listSources = () => apiGet('/api/v1/sources')

export const addSource = (body: SourceIn) =>
  request<Source>('POST', `${V1}/sources`, { body })

export const deleteSource = (id: number) =>
  request<void>('DELETE', `${V1}/sources/${id}`)
