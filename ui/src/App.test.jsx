import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import App from './App'
import * as api from './api'

vi.mock('./api')

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.listNamespaces.mockResolvedValue(['test-ns'])
    api.currentNamespace.mockResolvedValue('test-ns')
    api.listIndexedPages.mockResolvedValue([])
    api.searchDocs.mockResolvedValue({ results: [], references: [] })
    api.indexPage.mockResolvedValue('Indexed.')
    api.indexTree.mockResolvedValue('Indexed tree.')
    api.discoverLinks.mockResolvedValue([])
  })

  it('shows current namespace in sidebar on mount', async () => {
    render(<App />)
    await waitFor(() => expect(screen.getByText('test-ns')).toBeInTheDocument())
  })

  it('shows indexed page link after mount', async () => {
    api.listIndexedPages.mockResolvedValue([{ url: 'https://docs.example.com/page', chunks: 3 }])
    render(<App />)
    await waitFor(() => expect(screen.getByRole('link', { name: 'https://docs.example.com/page' })).toBeInTheDocument())
  })

  it('adds a search result to history on submit', async () => {
    api.searchDocs.mockResolvedValue({
      results: [{ text: 'Bearer token goes in Authorization header', url: 'https://docs.example.com/auth' }],
      references: [],
    })
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))

    await userEvent.type(screen.getByPlaceholderText('Search the indexed docs…'), 'bearer token')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() => expect(screen.getByText('Bearer token goes in Authorization header')).toBeInTheDocument())
    expect(screen.getByText('Search')).toBeInTheDocument()
  })

  it('adds an error entry to history when API call fails', async () => {
    api.searchDocs.mockRejectedValue(new Error('No namespace selected'))
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))

    await userEvent.type(screen.getByPlaceholderText('Search the indexed docs…'), 'anything')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() => expect(screen.getByText('No namespace selected')).toBeInTheDocument())
  })

  it('switching tools changes the input placeholder', async () => {
    render(<App />)
    await userEvent.click(screen.getByLabelText('Index Page'))
    expect(screen.getByPlaceholderText('https://docs.example.com/page')).toBeInTheDocument()
  })

  it('history persists across tool switches', async () => {
    api.searchDocs.mockResolvedValue({
      results: [{ text: 'Rate limits at 100 req/min', url: 'https://docs.example.com/api' }],
      references: [],
    })
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))

    await userEvent.type(screen.getByPlaceholderText('Search the indexed docs…'), 'rate limiting')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => screen.getByText('Rate limits at 100 req/min'))

    await userEvent.click(screen.getByLabelText('Index Page'))
    expect(screen.getByText('Rate limits at 100 req/min')).toBeInTheDocument()
  })
})
