import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect } from 'vitest'
import InputArea from './InputArea'

describe('InputArea — ask tool', () => {
  it('shows free-text placeholder and Ask button', () => {
    render(<InputArea tool="ask" onSubmit={vi.fn()} status="idle" />)
    expect(screen.getByPlaceholderText('Ask a question…')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ask' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Depth')).not.toBeInTheDocument()
  })

  it('calls onSubmit with value and null depth on button click', async () => {
    const onSubmit = vi.fn()
    render(<InputArea tool="ask" onSubmit={onSubmit} status="idle" />)
    await userEvent.type(screen.getByRole('textbox'), 'bearer token')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(onSubmit).toHaveBeenCalledWith({ value: 'bearer token', depth: null })
  })

  it('calls onSubmit on Enter key', async () => {
    const onSubmit = vi.fn()
    render(<InputArea tool="ask" onSubmit={onSubmit} status="idle" />)
    await userEvent.type(screen.getByRole('textbox'), 'rate limiting{Enter}')
    expect(onSubmit).toHaveBeenCalledWith({ value: 'rate limiting', depth: null })
  })

  it('does not call onSubmit when disabled and Enter is pressed', async () => {
    const onSubmit = vi.fn()
    const { rerender } = render(<InputArea tool="ask" onSubmit={onSubmit} status="idle" />)
    await userEvent.type(screen.getByRole('textbox'), 'some query')
    rerender(<InputArea tool="ask" onSubmit={onSubmit} status="loading" />)
    await userEvent.keyboard('{Enter}')
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('InputArea — index-page tool', () => {
  it('shows URL placeholder and Index button, no depth', () => {
    render(<InputArea tool="index-page" onSubmit={vi.fn()} status="idle" />)
    expect(screen.getByPlaceholderText('https://docs.example.com/page')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Index' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Depth')).not.toBeInTheDocument()
  })
})

describe('InputArea — index-tree tool', () => {
  it('shows depth input defaulting to 2', () => {
    render(<InputArea tool="index-tree" onSubmit={vi.fn()} status="idle" />)
    expect(screen.getByDisplayValue('2')).toBeInTheDocument()
  })

  it('calls onSubmit with depth value', async () => {
    const onSubmit = vi.fn()
    render(<InputArea tool="index-tree" onSubmit={onSubmit} status="idle" />)
    await userEvent.clear(screen.getByDisplayValue('2'))
    await userEvent.type(screen.getByRole('spinbutton'), '3')
    await userEvent.type(screen.getByPlaceholderText('https://docs.example.com/'), 'https://docs.example.com/{Enter}')
    expect(onSubmit).toHaveBeenCalledWith({ value: 'https://docs.example.com/', depth: 3 })
  })
})

describe('InputArea — discover tool', () => {
  it('shows depth input and Discover button', () => {
    render(<InputArea tool="discover" onSubmit={vi.fn()} status="idle" />)
    expect(screen.getByRole('button', { name: 'Discover' })).toBeInTheDocument()
    expect(screen.getByDisplayValue('2')).toBeInTheDocument()
  })
})
