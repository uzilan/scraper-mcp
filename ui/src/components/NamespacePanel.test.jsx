import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import NamespacePanel from './NamespacePanel'

const baseProps = {
  namespaces: ['my-project', 'docs-v1'],
  current: 'my-project',
  onCreate: vi.fn(),
  onSwitch: vi.fn(),
  onDelete: vi.fn(),
}

beforeEach(() => {
  baseProps.onCreate.mockReset()
  baseProps.onSwitch.mockReset()
  baseProps.onDelete.mockReset()
})

describe('NamespacePanel', () => {
  it('renders current namespace', () => {
    render(<NamespacePanel {...baseProps} />)
    expect(screen.getByText('my-project')).toBeInTheDocument()
  })

  it('renders other namespaces as clickable items', () => {
    render(<NamespacePanel {...baseProps} />)
    expect(screen.getByText('docs-v1')).toBeInTheDocument()
  })

  it('calls onSwitch when clicking a non-active namespace', async () => {
    render(<NamespacePanel {...baseProps} />)
    await userEvent.click(screen.getByText('docs-v1'))
    expect(baseProps.onSwitch).toHaveBeenCalledWith('docs-v1')
  })

  it('calls onCreate with trimmed value on Add button click', async () => {
    render(<NamespacePanel {...baseProps} />)
    await userEvent.type(screen.getByPlaceholderText('new namespace…'), 'new-ns')
    await userEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(baseProps.onCreate).toHaveBeenCalledWith('new-ns')
  })

  it('calls onCreate on Enter key press', async () => {
    render(<NamespacePanel {...baseProps} />)
    await userEvent.type(screen.getByPlaceholderText('new namespace…'), 'new-ns{Enter}')
    expect(baseProps.onCreate).toHaveBeenCalledWith('new-ns')
  })

  it('does not call onCreate for empty input', async () => {
    render(<NamespacePanel {...baseProps} />)
    await userEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(baseProps.onCreate).not.toHaveBeenCalled()
  })
})
