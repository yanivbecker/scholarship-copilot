/** Typed functions for sources, checking them, and discovery runs. */
import { apiGet, request, type Schemas } from './client'

export type Source = Schemas['SourceOut']
export type SourceIn = Schemas['SourceIn']
export type CheckResult = Schemas['CheckOut']
export type Snapshot = Schemas['SnapshotOut']
export type ExtractionReport = Schemas['ExtractionReportOut']
export type JobRun = Schemas['JobRunOut']

const V1 = '/api/v1'

export const listSources = () => apiGet('/api/v1/sources')

export const addSource = (body: SourceIn) =>
  request<Source>('POST', `${V1}/sources`, { body })

export const deleteSource = (id: number) =>
  request<void>('DELETE', `${V1}/sources/${id}`)

export const checkSource = (id: number) =>
  request<CheckResult>('POST', `${V1}/sources/${id}/check`)

export const pasteSourceText = (id: number, text: string) =>
  request<CheckResult>('POST', `${V1}/sources/${id}/paste`, { body: { text } })

export const getLatestSnapshot = (id: number) =>
  request<Snapshot | null>('GET', `${V1}/sources/${id}/snapshot`)

export const extractSource = (id: number) =>
  request<ExtractionReport>('POST', `${V1}/sources/${id}/extract`)

export const runDiscovery = () => request<JobRun>('POST', `${V1}/discovery/run`)

export const getLatestRun = () => apiGet('/api/v1/discovery/runs/latest')
