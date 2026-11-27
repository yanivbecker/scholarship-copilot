/** Typed functions for notifications, settings and background (Phase 8). */
import { apiGet, request, type Schemas } from './client'

export type Notifications = Schemas['NotificationsOut']
export type Notification = Schemas['NotificationOut']
export type NotificationKind = Schemas['NotificationKind']
export type AppSettings = Schemas['SettingsOut']
export type Background = Schemas['BackgroundOut']

const V1 = '/api/v1'

export const listNotifications = () => apiGet('/api/v1/notifications')

export const markNotificationsRead = (ids?: number[]) =>
  request<Notifications>('POST', `${V1}/notifications/read`, {
    body: { ids: ids ?? null },
  })

export const getAppSettings = () => apiGet('/api/v1/settings')

export const setNotificationKinds = (
  kinds: Partial<Record<NotificationKind, boolean>>,
) =>
  request<AppSettings>('PUT', `${V1}/settings/notifications`, {
    body: { kinds },
  })

export const setSearchQueries = (queries: string[]) =>
  request<AppSettings>('PUT', `${V1}/settings/search-queries`, {
    body: { queries },
  })

export const getBackground = () => apiGet('/api/v1/background')

export const setBackground = (enabled: boolean) =>
  request<Background>('PUT', `${V1}/background`, { body: { enabled } })

export const reviewSource = (id: number, approve: boolean) =>
  request<Schemas['SourceOut']>('POST', `${V1}/sources/${id}/review`, {
    body: { approve },
  })
