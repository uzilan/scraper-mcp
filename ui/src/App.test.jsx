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
    api.listDocuments.mockResolvedValue([])
    api.askAgent.mockResolvedValue({ answer: '', references: [] })
    api.indexPage.mockResolvedValue('Indexed.')
    api.indexTree.mockResolvedValue('Indexed tree.')
    api.discoverLinks.mockResolvedValue([])
    api.indexTreeStream.mockImplementation(async (_url, _depth, _force, onEvent) => {
      onEvent({ type: 'done', summary: 'Indexed tree.' })
      return 'Indexed tree.'
    })
    api.discoverLinksStream.mockImplementation(async (_url, _depth, onEvent) => {
      onEvent({ type: 'done' })
    })
  })

  it('shows current namespace in sidebar on mount', async () => {
    render(<App />)
    await waitFor(() => expect(screen.getByText('test-ns')).toBeInTheDocument())
  })

  it('shows indexed page link after expanding domain', async () => {
    api.listIndexedPages.mockResolvedValue([{ url: 'https://docs.example.com/page', chunks: 3 }])
    render(<App />)
    await waitFor(() => screen.getByText('docs.example.com'))
    await userEvent.click(screen.getByText('docs.example.com'))
    expect(screen.getByRole('link', { name: 'page' })).toBeInTheDocument()
  })

  it('adds an ask result to history on submit', async () => {
    api.askAgent.mockResolvedValue({
      answer: 'Bearer token goes in the Authorization header.',
      references: ['https://docs.example.com/auth'],
    })
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))

    await userEvent.type(screen.getByPlaceholderText('Ask a question…'), 'bearer token')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    await waitFor(() => expect(screen.getByText(/Bearer token goes in the Authorization header/)).toBeInTheDocument())
    expect(screen.getByText('Ask')).toBeInTheDocument()
  })

  it('adds an error entry to history when API call fails', async () => {
    api.askAgent.mockRejectedValue(new Error('No namespace selected'))
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))

    await userEvent.type(screen.getByPlaceholderText('Ask a question…'), 'anything')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    await waitFor(() => expect(screen.getByText('No namespace selected')).toBeInTheDocument())
  })

  it('switching tools changes the input placeholder', async () => {
    render(<App />)
    await userEvent.click(screen.getByLabelText('Index Page'))
    expect(screen.getByPlaceholderText('https://docs.example.com/page')).toBeInTheDocument()
  })

  it('uses indexTreeStream for index-tree tool and shows result', async () => {
    api.indexTreeStream.mockImplementation(async (_url, _depth, _force, onEvent) => {
      onEvent({ type: 'progress', message: '[indexed] http://example.com/' })
      onEvent({ type: 'done', summary: 'Indexed 1 page (0 skipped, 0 failed)' })
      return 'Indexed 1 page (0 skipped, 0 failed)'
    })
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))
    await userEvent.click(screen.getByLabelText('Index Tree'))
    await userEvent.type(screen.getByPlaceholderText('https://docs.example.com/'), 'http://example.com/')
    await userEvent.click(screen.getByRole('button', { name: 'Index' }))
    await waitFor(() => expect(screen.getByText(/Indexed 1 page/)).toBeInTheDocument())
  })

  it('uses discoverLinksStream for discover tool and shows links', async () => {
    api.discoverLinksStream.mockImplementation(async (_url, _depth, onEvent) => {
      onEvent({ type: 'progress', message: 'http://example.com/' })
      onEvent({ type: 'done' })
    })
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))
    await userEvent.click(screen.getByLabelText('Discover Links'))
    await userEvent.type(screen.getByPlaceholderText('https://docs.example.com/'), 'http://example.com/')
    await userEvent.click(screen.getByRole('button', { name: 'Discover' }))
    await waitFor(() => expect(screen.getByText('http://example.com/')).toBeInTheDocument())
  })

  it('history persists across tool switches', async () => {
    api.askAgent.mockResolvedValue({
      answer: 'Rate limits at 100 req/min.',
      references: ['https://docs.example.com/api'],
    })
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))

    await userEvent.type(screen.getByPlaceholderText('Ask a question…'), 'rate limiting')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await waitFor(() => screen.getByText(/Rate limits at 100 req\/min/))

    await userEvent.click(screen.getByLabelText('Index Page'))
    expect(screen.getByText(/Rate limits at 100 req\/min/)).toBeInTheDocument()
  })
})
