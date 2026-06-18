import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect } from 'vitest'
import DocumentsList from './DocumentsList'

const docs = [
  { name: 'guide.pdf', size: 2048, content_type: 'application/pdf' },
  { name: 'sheet.xlsx', size: 1024, content_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
  { name: 'readme.txt', size: 512, content_type: 'text/plain' },
]

describe('DocumentsList', () => {
  it('renders document count in header', () => {
    render(<DocumentsList documents={docs} onUpload={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText('(3)')).toBeInTheDocument()
  })

  it('renders empty list without error', () => {
    render(<DocumentsList documents={[]} onUpload={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText('(0)')).toBeInTheDocument()
  })

  it('renders each document name', () => {
    render(<DocumentsList documents={docs} onUpload={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText(/guide\.pdf/)).toBeInTheDocument()
    expect(screen.getByText(/sheet\.xlsx/)).toBeInTheDocument()
    expect(screen.getByText(/readme\.txt/)).toBeInTheDocument()
  })

  it('PDF opens in new tab (target _blank, no download attr)', () => {
    render(<DocumentsList documents={[docs[0]]} onUpload={vi.fn()} onDelete={vi.fn()} />)
    const link = screen.getByRole('link', { name: /guide\.pdf/ })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).not.toHaveAttribute('download')
  })

  it('xlsx forces download (download attr, no target _blank)', () => {
    render(<DocumentsList documents={[docs[1]]} onUpload={vi.fn()} onDelete={vi.fn()} />)
    const link = screen.getByRole('link', { name: /sheet\.xlsx/ })
    expect(link).toHaveAttribute('download')
    expect(link).not.toHaveAttribute('target', '_blank')
  })

  it('txt opens in new tab', () => {
    render(<DocumentsList documents={[docs[2]]} onUpload={vi.fn()} onDelete={vi.fn()} />)
    const link = screen.getByRole('link', { name: /readme\.txt/ })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).not.toHaveAttribute('download')
  })

  it('calls onDelete with filename when delete button clicked', async () => {
    const onDelete = vi.fn()
    render(<DocumentsList documents={[docs[0]]} onUpload={vi.fn()} onDelete={onDelete} />)
    await userEvent.click(screen.getByRole('button', { name: /delete guide\.pdf/i }))
    expect(onDelete).toHaveBeenCalledWith('guide.pdf')
  })

  it('calls onUpload when file selected', async () => {
    const onUpload = vi.fn()
    render(<DocumentsList documents={[]} onUpload={onUpload} onDelete={vi.fn()} />)
    const input = document.querySelector('input[type="file"]')
    const file = new File(['content'], 'new.txt', { type: 'text/plain' })
    await userEvent.upload(input, file)
    expect(onUpload).toHaveBeenCalledWith(file)
  })

  it('json file links to swagger-ui wrapper, opens in new tab', () => {
    const docs = [{ name: 'api.json', size: 512, content_type: 'application/json' }]
    render(<DocumentsList documents={docs} onUpload={vi.fn()} onDelete={vi.fn()} />)
    const link = screen.getByRole('link', { name: /api\.json/ })
    expect(link).toHaveAttribute('href', '/swagger-ui?url=%2Fdocuments%2Fapi.json')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).not.toHaveAttribute('download')
  })

  it('yaml file links to swagger-ui wrapper', () => {
    const docs = [{ name: 'spec.yaml', size: 256, content_type: 'application/yaml' }]
    render(<DocumentsList documents={docs} onUpload={vi.fn()} onDelete={vi.fn()} />)
    const link = screen.getByRole('link', { name: /spec\.yaml/ })
    expect(link).toHaveAttribute('href', '/swagger-ui?url=%2Fdocuments%2Fspec.yaml')
  })

  it('yml file links to swagger-ui wrapper', () => {
    const docs = [{ name: 'openapi.yml', size: 256, content_type: 'application/yaml' }]
    render(<DocumentsList documents={docs} onUpload={vi.fn()} onDelete={vi.fn()} />)
    const link = screen.getByRole('link', { name: /openapi\.yml/ })
    expect(link).toHaveAttribute('href', '/swagger-ui?url=%2Fdocuments%2Fopenapi.yml')
  })

  it('shows upload error when onUpload returns { ok: false, error }', async () => {
    const onUpload = vi.fn().mockResolvedValue({ ok: false, error: 'Upload failed' })
    render(<DocumentsList documents={[]} onUpload={onUpload} onDelete={vi.fn()} />)
    const input = document.querySelector('input[type="file"]')
    const file = new File(['content'], 'bad.txt', { type: 'text/plain' })
    await userEvent.upload(input, file)
    await waitFor(() => expect(screen.getByText('Upload failed')).toBeInTheDocument())
  })
})
