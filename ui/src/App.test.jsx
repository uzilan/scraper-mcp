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

  it('shows a pending spinner entry before the ask response arrives', async () => {
    let resolveAsk
    api.askAgent.mockReturnValue(new Promise(resolve => { resolveAsk = resolve }))
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))

    await userEvent.type(screen.getByPlaceholderText('Ask a question…'), 'bearer token')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    await waitFor(() => expect(screen.getByRole('status')).toBeInTheDocument())

    resolveAsk({ answer: 'Use a Bearer token.', references: [] })
    await waitFor(() => expect(screen.getByText(/Use a Bearer token/)).toBeInTheDocument())
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
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

  it('collapses the previous Ask entry only after a new answer arrives and lets it reopen', async () => {
    let resolveAsk
    api.askAgent
      .mockResolvedValueOnce({ answer: 'First answer.', references: [] })
      .mockReturnValueOnce(new Promise(resolve => { resolveAsk = resolve }))
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))

    await userEvent.type(screen.getByPlaceholderText('Ask a question…'), 'first question')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await waitFor(() => expect(screen.getByText('First answer.')).toBeInTheDocument())

    await userEvent.type(screen.getByPlaceholderText('Ask a question…'), 'second question')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByText('First answer.')).toBeInTheDocument()

    resolveAsk({ answer: 'Second answer.', references: [] })
    await waitFor(() => expect(screen.getByText('Second answer.')).toBeInTheDocument())
    expect(screen.queryByText('First answer.')).not.toBeInTheDocument()
    expect(screen.getByText('first question')).toBeInTheDocument()

    await userEvent.click(screen.getByText('first question'))
    expect(screen.getByText('First answer.')).toBeInTheDocument()
    await userEvent.click(screen.getByText('first question'))
    expect(screen.queryByText('First answer.')).not.toBeInTheDocument()
  })

  it('keeps the previous Ask answer expanded when a new request fails', async () => {
    api.askAgent
      .mockResolvedValueOnce({ answer: 'First answer.', references: [] })
      .mockRejectedValueOnce(new Error('Agent unavailable'))
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))

    await userEvent.type(screen.getByPlaceholderText('Ask a question…'), 'first question')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await waitFor(() => screen.getByText('First answer.'))

    await userEvent.type(screen.getByPlaceholderText('Ask a question…'), 'second question')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await waitFor(() => expect(screen.getByText('Agent unavailable')).toBeInTheDocument())
    expect(screen.getByText('First answer.')).toBeInTheDocument()
  })

  it('keeps an Ask answer expanded when another tool returns a result', async () => {
    api.askAgent.mockResolvedValue({ answer: 'First answer.', references: [] })
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))

    await userEvent.type(screen.getByPlaceholderText('Ask a question…'), 'first question')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await waitFor(() => screen.getByText('First answer.'))

    await userEvent.click(screen.getByLabelText('Index Page'))
    await userEvent.type(screen.getByPlaceholderText('https://docs.example.com/page'), 'https://example.com/')
    await userEvent.click(screen.getByRole('button', { name: 'Index' }))
    await waitFor(() => expect(screen.getByText('Indexed.')).toBeInTheDocument())
    expect(screen.getByText('First answer.')).toBeInTheDocument()
  })

  it('keeps each Ask entry tagged with its namespace at submission across namespace switches', async () => {
    let resolveAsk
    api.listNamespaces.mockResolvedValue(['test-ns', 'other-ns'])
    api.useNamespace.mockResolvedValue('Switched namespace.')
    api.askAgent
      .mockReturnValueOnce(new Promise(resolve => { resolveAsk = resolve }))
      .mockResolvedValueOnce({ answer: 'Second answer.', references: [] })
    render(<App />)
    await waitFor(() => screen.getByText('test-ns'))

    await userEvent.type(screen.getByPlaceholderText('Ask a question…'), 'first question')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByLabelText('Namespace: test-ns')).toHaveTextContent('test-ns')

    api.currentNamespace.mockResolvedValue('other-ns')
    await userEvent.click(screen.getByText('other-ns'))
    await waitFor(() => expect(screen.getByText('other-ns')).toHaveClass('font-semibold'))
    expect(screen.getByLabelText('Namespace: test-ns')).toHaveTextContent('test-ns')

    resolveAsk({ answer: 'First answer.', references: [] })
    await waitFor(() => expect(screen.getByText('First answer.')).toBeInTheDocument())
    expect(screen.getByLabelText('Namespace: test-ns')).toHaveTextContent('test-ns')

    await userEvent.type(screen.getByPlaceholderText('Ask a question…'), 'second question')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await waitFor(() => expect(screen.getByText('Second answer.')).toBeInTheDocument())
    expect(screen.getByLabelText('Namespace: other-ns')).toHaveTextContent('other-ns')
    expect(screen.getByLabelText('Namespace: test-ns')).toHaveTextContent('test-ns')
    expect(screen.queryByText('First answer.')).not.toBeInTheDocument()
    await userEvent.click(screen.getByText('first question'))
    expect(screen.getByText('First answer.')).toBeInTheDocument()
    expect(screen.getByLabelText('Namespace: test-ns')).toHaveTextContent('test-ns')
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
