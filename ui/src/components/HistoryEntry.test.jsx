import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import HistoryEntry from './HistoryEntry'

const searchEntry = {
  id: 1,
  tool: 'search',
  query: 'bearer token',
  depth: null,
  result: {
    results: [{ text: 'Bearer tokens go in Authorization header', source_url: 'https://docs.example.com/auth' }],
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

const pendingTreeEntry = {
  id: 5,
  tool: 'index-tree',
  query: 'https://docs.example.com/',
  depth: 2,
  result: null,
  error: null,
  urls: ['[indexed] https://docs.example.com/', '[failed] https://docs.example.com/broken'],
  status: 'pending',
}

const doneTreeEntryWithLog = {
  id: 6,
  tool: 'index-tree',
  query: 'https://docs.example.com/',
  depth: 2,
  result: 'Indexed 1 page (0 skipped, 1 failed) starting from https://docs.example.com/',
  error: null,
  urls: ['[indexed] https://docs.example.com/', '[failed] https://docs.example.com/broken'],
  status: 'done',
}

describe('HistoryEntry — index-tree pending', () => {
  it('renders live URL feed with indexed and failed messages', () => {
    render(<HistoryEntry entry={pendingTreeEntry} faded={false} />)
    expect(screen.getByText('[indexed] https://docs.example.com/')).toBeInTheDocument()
    expect(screen.getByText('[failed] https://docs.example.com/broken')).toBeInTheDocument()
  })

  it('renders failed URL in red', () => {
    render(<HistoryEntry entry={pendingTreeEntry} faded={false} />)
    const el = screen.getByText('[failed] https://docs.example.com/broken')
    expect(el).toHaveClass('text-red-400')
  })

  it('shows ⋯ as summary while pending', () => {
    render(<HistoryEntry entry={pendingTreeEntry} faded={false} />)
    expect(screen.getByText('⋯')).toBeInTheDocument()
  })
})

describe('HistoryEntry — index-tree done with URL log', () => {
  it('renders summary and URL log', () => {
    render(<HistoryEntry entry={doneTreeEntryWithLog} faded={false} />)
    expect(screen.getByText(/Indexed 1 page/)).toBeInTheDocument()
    expect(screen.getByText('[indexed] https://docs.example.com/')).toBeInTheDocument()
  })

  it('renders failed URL in red in done log', () => {
    render(<HistoryEntry entry={doneTreeEntryWithLog} faded={false} />)
    const el = screen.getByText('[failed] https://docs.example.com/broken')
    expect(el).toHaveClass('text-red-400')
  })
})
