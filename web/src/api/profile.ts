/** Typed functions for the profile, facts and story-bank endpoints. */
import { apiGet, request, type Schemas } from './client'

export type Profile = Schemas['ProfileOut']
export type ProfileUpdate = Schemas['ProfileUpdate']
export type OperatingMode = Schemas['OperatingMode']
export type Catalog = Schemas['CatalogOut']
export type CatalogSection = Schemas['SectionOut']
export type FactDefinition = Schemas['FactDefinitionOut']
export type Fact = Schemas['FactOut']
export type FactIn = Schemas['FactIn']
export type FactValue = Fact['value']
export type Story = Schemas['StoryOut']
export type StoryIn = Schemas['StoryIn']

const V1 = '/api/v1'

export const getProfile = () => apiGet('/api/v1/profile')

export const updateProfile = (body: ProfileUpdate) =>
  request<Profile>('PATCH', `${V1}/profile`, { body })

export const getCatalog = () => apiGet('/api/v1/facts/catalog')

export const listFacts = () => apiGet('/api/v1/facts')

export const setFact = (key: string, body: FactIn) =>
  request<Fact>('PUT', `${V1}/facts/${encodeURIComponent(key)}`, { body })

export const deleteFact = (key: string) =>
  request<void>('DELETE', `${V1}/facts/${encodeURIComponent(key)}`)

export const listStories = (theme?: string) =>
  apiGet('/api/v1/stories', { theme })

export const getStoryThemes = () => apiGet('/api/v1/stories/themes')

export const createStory = (body: StoryIn) =>
  request<Story>('POST', `${V1}/stories`, { body })

export const updateStory = (id: number, body: StoryIn) =>
  request<Story>('PUT', `${V1}/stories/${id}`, { body })

export const deleteStory = (id: number) =>
  request<void>('DELETE', `${V1}/stories/${id}`)
