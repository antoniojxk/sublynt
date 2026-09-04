import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { IssueTable } from '../src/IssueTable'
import type { Issue } from '../src/types'

const issues: Issue[] = [
  { code: 'overlap', severity: 'warning', message: 'Cue overlaps.', cue_index: 2, cue_identifier: '2', timestamp_ms: 1000, repairable: true },
  { code: 'invalid_timestamp', severity: 'error', message: 'Invalid.', cue_index: 3, cue_identifier: '3', timestamp_ms: null, repairable: false },
]

describe('IssueTable', () => {
  it('renders human-readable issues and filters by severity', () => {
    const { rerender } = render(<IssueTable issues={issues} filter="all" />)
    expect(screen.getByText('Cue overlaps.')).toBeInTheDocument()
    rerender(<IssueTable issues={issues} filter="error" />)
    expect(screen.queryByText('Cue overlaps.')).not.toBeInTheDocument()
    expect(screen.getByText('Invalid.')).toBeInTheDocument()
  })
})
