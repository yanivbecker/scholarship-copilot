/** Typed functions for the Today screen and status tracking. */
import { apiGet, request, type Schemas } from './client'

export type Today = Schemas['TodayOut']
export type Action = Schemas['ActionOut']
export type StatusView = Schemas['StatusOut']
export type ApplicationStatus = Schemas['ApplicationStatus']

export const getToday = () => apiGet('/api/v1/dashboard/today')

export const getStatus = (scholarshipId: number) =>
  request<StatusView>('GET', `/api/v1/scholarships/${scholarshipId}/status`)

export const changeStatus = (
  scholarshipId: number,
  body: {
    status: ApplicationStatus
    confirmed?: boolean
    note?: string | null
  },
) =>
  request<StatusView>('POST', `/api/v1/scholarships/${scholarshipId}/status`, {
    body,
  })
