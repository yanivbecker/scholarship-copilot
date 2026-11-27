/** Typed functions for resume import (FR-P2). */
import type { Fact } from './profile'
import { request, uploadFile, type Schemas } from './client'

export type ResumeUpload = Schemas['ResumeUploadOut']
export type Suggestion = Schemas['SuggestionOut']
export type ConfirmFacts = Schemas['ResumeConfirmIn']['facts']

export const MAX_RESUME_BYTES = 5 * 1024 * 1024 // same as the backend

export const uploadResume = (file: File) =>
  uploadFile<ResumeUpload>('/api/v1/resume', file)

export const confirmResumeFacts = (documentId: number, facts: ConfirmFacts) =>
  request<Fact[]>('POST', `/api/v1/resume/${documentId}/confirm`, {
    body: { facts },
  })

export const deleteResume = (documentId: number) =>
  request<void>('DELETE', `/api/v1/resume/${documentId}`)
