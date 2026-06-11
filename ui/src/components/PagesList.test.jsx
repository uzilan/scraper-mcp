import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import PagesList from './PagesList'

describe('PagesList', () => {
  it('renders page URLs as links opening in new tab', () => {
    const pages = [
      { url: 'https://docs.example.com/getting-started', chunks: 4 },
      { url: 'https://docs.example.com/api/auth', chunks: 7 },
    ]
    render(<PagesList pages={pages} />)
    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(2)
    expect(links[0]).toHaveAttribute('href', 'https://docs.example.com/getting-started')
    expect(links[0]).toHaveAttribute('target', '_blank')
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
