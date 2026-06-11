import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect } from 'vitest'
import ToolBar from './ToolBar'

describe('ToolBar', () => {
  it('renders all four tool options', () => {
    render(<ToolBar active="search" onChange={vi.fn()} />)
    expect(screen.getByLabelText('Search')).toBeInTheDocument()
    expect(screen.getByLabelText('Index Page')).toBeInTheDocument()
    expect(screen.getByLabelText('Index Tree')).toBeInTheDocument()
    expect(screen.getByLabelText('Discover Links')).toBeInTheDocument()
  })

  it('checks the active tool radio', () => {
    render(<ToolBar active="index-tree" onChange={vi.fn()} />)
    expect(screen.getByLabelText('Index Tree')).toBeChecked()
    expect(screen.getByLabelText('Search')).not.toBeChecked()
  })

  it('calls onChange with tool id when a radio is selected', async () => {
    const onChange = vi.fn()
    render(<ToolBar active="search" onChange={onChange} />)
    await userEvent.click(screen.getByLabelText('Discover Links'))
    expect(onChange).toHaveBeenCalledWith('discover')
  })
})
