import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import PagesList from './PagesList'

describe('PagesList', () => {
  it('renders leaf pages as links after expanding domain and folder', async () => {
    const pages = [
      { url: 'https://docs.example.com/getting-started', chunks: 4 },
      { url: 'https://docs.example.com/api/auth', chunks: 7 },
    ]
    render(<PagesList pages={pages} />)
    await userEvent.click(screen.getByText('docs.example.com'))
    await userEvent.click(screen.getByText('api/'))
    const gettingStarted = screen.getByTitle('https://docs.example.com/getting-started')
    expect(gettingStarted).toHaveAttribute('href', 'https://docs.example.com/getting-started')
    expect(gettingStarted).toHaveAttribute('target', '_blank')
    expect(gettingStarted).toHaveTextContent('getting-started')
    const auth = screen.getByTitle('https://docs.example.com/api/auth')
    expect(auth).toHaveAttribute('href', 'https://docs.example.com/api/auth')
    expect(auth).toHaveTextContent('auth')
  })

  it('hides children by default', () => {
    const pages = [{ url: 'https://docs.example.com/guide', chunks: 2 }]
    render(<PagesList pages={pages} />)
    expect(screen.queryByTitle('https://docs.example.com/guide')).not.toBeInTheDocument()
  })

  it('shows domain as collapsible group header', () => {
    const pages = [{ url: 'https://docs.example.com/guide', chunks: 2 }]
    render(<PagesList pages={pages} />)
    expect(screen.getByText('docs.example.com')).toBeInTheDocument()
  })

  it('expands domain on click and shows children', async () => {
    const pages = [{ url: 'https://docs.example.com/guide', chunks: 2 }]
    render(<PagesList pages={pages} />)
    await userEvent.click(screen.getByText('docs.example.com'))
    expect(screen.getByTitle('https://docs.example.com/guide')).toBeInTheDocument()
  })

  it('shows folder label after expanding domain', async () => {
    const pages = [{ url: 'https://docs.example.com/api/auth', chunks: 7 }]
    render(<PagesList pages={pages} />)
    await userEvent.click(screen.getByText('docs.example.com'))
    expect(screen.getByText('api/')).toBeInTheDocument()
  })

  it('expands folder on click and shows its children', async () => {
    const pages = [{ url: 'https://docs.example.com/api/auth', chunks: 7 }]
    render(<PagesList pages={pages} />)
    await userEvent.click(screen.getByText('docs.example.com'))
    await userEvent.click(screen.getByText('api/'))
    expect(screen.getByTitle('https://docs.example.com/api/auth')).toBeInTheDocument()
  })

  it('groups pages from multiple domains separately', () => {
    const pages = [
      { url: 'https://docs.example.com/intro', chunks: 1 },
      { url: 'https://api.other.com/reference', chunks: 3 },
    ]
    render(<PagesList pages={pages} />)
    expect(screen.getByText('docs.example.com')).toBeInTheDocument()
    expect(screen.getByText('api.other.com')).toBeInTheDocument()
  })

  it('shows page count', () => {
    render(<PagesList pages={[{ url: 'https://a.com', chunks: 1 }]} />)
    expect(screen.getByText('(1)')).toBeInTheDocument()
  })

  it('renders empty list without error', () => {
    render(<PagesList pages={[]} />)
    expect(screen.getByText('(0)')).toBeInTheDocument()
  })
})
