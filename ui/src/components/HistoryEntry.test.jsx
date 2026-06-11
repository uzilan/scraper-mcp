import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import HistoryEntry from './HistoryEntry'

const searchEntry = {
  id: 1,
  tool: 'search',
  query: 'bearer token',
  depth: null,
  result: {
    results: [{ text: 'Bearer tokens go in Authorization header', url: 'https://docs.example.com/auth' }],
    references: [],
  },
  error: null,
}

const discoverEntry = {
  id: 2,
  tool: 'discover',
  query: 'https://docs.example.com',
  depth: 2,
  result: ['https://docs.example.com/page1', 'https://docs.example.com/page2'],
  error: null,
}

const indexTreeEntry = {
  id: 3,
  tool: 'index-tree',
  query: 'https://docs.example.com/',
  depth: 2,
  result: 'Indexed 4 pages (0 skipped, 0 failed) starting from https://docs.example.com/',
  error: null,
}

const errorEntry = {
  id: 4,
  tool: 'index-page',
  query: 'https://bad.url',
  depth: null,
  result: null,
  error: 'Failed to fetch page content',
}

describe('HistoryEntry — search', () => {
  it('renders Search badge and query', () => {
    render(<HistoryEntry entry={searchEntry} faded={false} />)
    expect(screen.getByText('Search')).toBeInTheDocument()
    expect(screen.getByText('bearer token')).toBeInTheDocument()
  })

  it('renders result text and source link', () => {
    render(<HistoryEntry entry={searchEntry} faded={false} />)
    expect(screen.getByText('Bearer tokens go in Authorization header')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'https://docs.example.com/auth' })).toHaveAttribute('target', '_blank')
  })

  it('shows result count in header', () => {
    render(<HistoryEntry entry={searchEntry} faded={false} />)
    expect(screen.getByText('1 results')).toBeInTheDocument()
  })
})

describe('HistoryEntry — discover', () => {
  it('renders Discover Links badge and depth', () => {
    render(<HistoryEntry entry={discoverEntry} faded={false} />)
    expect(screen.getByText('Discover Links')).toBeInTheDocument()
    expect(screen.getByText(/depth 2/)).toBeInTheDocument()
  })

  it('renders discovered links', () => {
    render(<HistoryEntry entry={discoverEntry} faded={false} />)
    expect(screen.getByRole('link', { name: 'https://docs.example.com/page1' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'https://docs.example.com/page2' })).toBeInTheDocument()
  })
})

describe('HistoryEntry — index-tree', () => {
  it('renders Index Tree badge and confirmation message', () => {
    render(<HistoryEntry entry={indexTreeEntry} faded={false} />)
    expect(screen.getByText('Index Tree')).toBeInTheDocument()
    expect(screen.getByText(/Indexed 4 pages/)).toBeInTheDocument()
  })
})

describe('HistoryEntry — error', () => {
  it('renders error message in red', () => {
    render(<HistoryEntry entry={errorEntry} faded={false} />)
    expect(screen.getByText('Failed to fetch page content')).toBeInTheDocument()
  })
})

describe('HistoryEntry — faded', () => {
  it('applies reduced opacity class when faded=true', () => {
    const { container } = render(<HistoryEntry entry={searchEntry} faded={true} />)
    expect(container.firstChild).toHaveClass('opacity-45')
  })

  it('does not apply opacity class when faded=false', () => {
    const { container } = render(<HistoryEntry entry={searchEntry} faded={false} />)
    expect(container.firstChild).not.toHaveClass('opacity-45')
  })
})
