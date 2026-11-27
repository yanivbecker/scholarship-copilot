import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { ResumeUpload } from '@/api/resume'
import { catalog, fact } from '@/test/fixtures'
import { mockApi } from '@/test/mockApi'
import { jsonResponse, renderWithQueryClient } from '@/test/render'

import { ResumeImport } from './ResumeImport'

// Fictional upload result (NFR-10).
const upload: ResumeUpload = {
  document_id: 7,
  filename: 'test-cv.pdf',
  suggestions: [
    {
      key: 'gpa',
      label: 'GPA',
      value: 3.72,
      evidence: 'GPA: 3.72/4.0',
      current_value: 3.5,
    },
    {
      key: 'major',
      label: 'Major',
      value: 'Environmental Engineering',
      evidence: 'Bachelor of Science in Environmental Engineering',
      current_value: 'Environmental Engineering',
    },
    {
      key: 'expected_graduation_year',
      label: 'Expected graduation year',
      value: 2027,
      evidence: 'Expected graduation: May 2027',
      current_value: null,
    },
  ],
}

const pdf = () =>
  new File(['%PDF-1.4 test'], 'test-cv.pdf', { type: 'application/pdf' })

async function uploadFile(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText('Resume file'), pdf())
  await user.click(screen.getByRole('button', { name: 'Read resume' }))
  await screen.findByText(/Nothing is saved until you confirm/)
}

const row = (label: string) =>
  screen
    .getByRole('checkbox', { name: `Save ${label}` })
    .closest('li') as HTMLElement

describe('ResumeImport', () => {
  it('shows each suggestion with its evidence and what it replaces', async () => {
    const calls = mockApi({
      'GET /api/v1/facts/catalog': catalog,
      'POST /api/v1/resume': upload,
    })
    const user = userEvent.setup()
    renderWithQueryClient(<ResumeImport />)

    await uploadFile(user)

    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      file: 'test-cv.pdf',
    })
    expect(within(row('GPA')).getByText('GPA: 3.72/4.0')).toBeInTheDocument()
    expect(
      within(row('GPA')).getByText("Replaces what's on file: 3.5"),
    ).toBeInTheDocument()
    expect(
      within(row('Major')).getByText('Already on file.'),
    ).toBeInTheDocument()
    // Unchanged facts start unticked; new or different ones start ticked.
    expect(
      screen.getByRole('checkbox', { name: 'Save Major' }),
    ).not.toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Save GPA' })).toBeChecked()
    expect(screen.getByLabelText('GPA')).toHaveValue('3.72')
  })

  it('saves only ticked facts, including edits, as typed values', async () => {
    const calls = mockApi({
      'GET /api/v1/facts/catalog': catalog,
      'POST /api/v1/resume': upload,
      'POST /api/v1/resume/7/confirm': [fact({ key: 'gpa', value: 3.8 })],
      'GET /api/v1/facts': [],
    })
    const user = userEvent.setup()
    renderWithQueryClient(<ResumeImport />)
    await uploadFile(user)

    await user.clear(screen.getByLabelText('GPA'))
    await user.type(screen.getByLabelText('GPA'), '3.8')
    await user.click(
      screen.getByRole('checkbox', { name: 'Save Expected graduation year' }),
    )
    await user.click(
      screen.getByRole('button', { name: 'Save selected facts' }),
    )

    expect(
      await screen.findByText('Saved 1 fact from your resume.'),
    ).toBeInTheDocument()
    const confirm = calls.find((c) => c.path === '/api/v1/resume/7/confirm')
    expect(confirm?.body).toEqual({ facts: { gpa: 3.8 } })
  })

  it('shows server field errors next to the field', async () => {
    mockApi({
      'GET /api/v1/facts/catalog': catalog,
      'POST /api/v1/resume': upload,
      'POST /api/v1/resume/7/confirm': () =>
        jsonResponse(
          {
            detail: 'Some values need fixing.',
            field_errors: { gpa: 'GPA is off.' },
          },
          422,
        ),
    })
    const user = userEvent.setup()
    renderWithQueryClient(<ResumeImport />)
    await uploadFile(user)

    await user.click(
      screen.getByRole('button', { name: 'Save selected facts' }),
    )

    expect(
      await within(row('GPA')).findByText('GPA is off.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Some values need fixing.')).toBeInTheDocument()
  })

  it('blocks an invalid edit before sending', async () => {
    const calls = mockApi({
      'GET /api/v1/facts/catalog': catalog,
      'POST /api/v1/resume': upload,
    })
    const user = userEvent.setup()
    renderWithQueryClient(<ResumeImport />)
    await uploadFile(user)

    await user.clear(screen.getByLabelText('GPA'))
    await user.type(screen.getByLabelText('GPA'), '9')
    await user.click(
      screen.getByRole('button', { name: 'Save selected facts' }),
    )

    expect(
      await screen.findByText('GPA must be between 0 and 5.'),
    ).toBeInTheDocument()
    expect(calls.some((c) => c.path.endsWith('/confirm'))).toBe(false)
  })

  it('refuses files over 5 MB without uploading them', async () => {
    const calls = mockApi({})
    const user = userEvent.setup()
    renderWithQueryClient(<ResumeImport />)

    const big = new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'big.pdf', {
      type: 'application/pdf',
    })
    await user.upload(screen.getByLabelText('Resume file'), big)
    await user.click(screen.getByRole('button', { name: 'Read resume' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'larger than 5 MB',
    )
    expect(calls).toEqual([])
  })

  it('shows the server reason when a file is rejected', async () => {
    mockApi({
      'POST /api/v1/resume': () =>
        jsonResponse({ detail: 'This PDF is password-protected.' }, 422),
    })
    const user = userEvent.setup()
    renderWithQueryClient(<ResumeImport />)

    await user.upload(screen.getByLabelText('Resume file'), pdf())
    await user.click(screen.getByRole('button', { name: 'Read resume' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'password-protected',
    )
  })

  it('can delete the uploaded file after saving', async () => {
    const calls = mockApi({
      'GET /api/v1/facts/catalog': catalog,
      'POST /api/v1/resume': upload,
      'POST /api/v1/resume/7/confirm': [fact({ key: 'gpa', value: 3.72 })],
      'GET /api/v1/facts': [],
      'DELETE /api/v1/resume/7': undefined,
    })
    const user = userEvent.setup()
    renderWithQueryClient(<ResumeImport />)
    await uploadFile(user)
    await user.click(
      screen.getByRole('button', { name: 'Save selected facts' }),
    )

    await user.click(
      await screen.findByRole('button', { name: 'Delete the uploaded file' }),
    )

    expect(
      await screen.findByText(/The uploaded file was deleted/),
    ).toBeInTheDocument()
    expect(
      calls.some((c) => c.method === 'DELETE' && c.path === '/api/v1/resume/7'),
    ).toBe(true)
  })
})
