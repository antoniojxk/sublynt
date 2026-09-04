import type { Issue, Severity } from './types'
import { timecode } from './format'

export function IssueTable({ issues, filter }: { issues: Issue[]; filter: Severity | 'all' }) {
  const visible = filter === 'all' ? issues : issues.filter((issue) => issue.severity === filter)
  if (!visible.length) return <p className="empty-state">No issues match this filter.</p>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr><th>Severity</th><th>Cue</th><th>Time</th><th>Finding</th><th>Repair</th></tr>
        </thead>
        <tbody>
          {visible.map((issue, index) => (
            <tr key={`${issue.code}-${issue.cue_index}-${index}`}>
              <td><span className={`severity ${issue.severity}`}>{issue.severity === 'error' ? '●' : issue.severity === 'warning' ? '▲' : '◆'} {issue.severity}</span></td>
              <td>{issue.cue_index ?? 'File'}</td>
              <td><a href={issue.cue_index ? `#cue-${issue.cue_index}` : undefined}>{issue.timestamp_ms == null ? '—' : timecode(issue.timestamp_ms)}</a></td>
              <td><strong>{issue.code.replaceAll('_', ' ')}</strong><small>{issue.message}</small></td>
              <td>{issue.repairable ? 'Available' : 'Review'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
