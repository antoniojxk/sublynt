export type Severity = 'info' | 'warning' | 'error'

export interface Issue {
  code: string
  severity: Severity
  message: string
  cue_index: number | null
  cue_identifier: string | null
  timestamp_ms: number | null
  repairable: boolean
}

export interface Analysis {
  format: 'srt' | 'vtt'
  caption_count: number
  total_duration_ms: number
  average_caption_duration_ms: number
  average_cps: number
  average_wpm: number
  issue_count: number
  issue_counts: Partial<Record<Severity, number>>
  issues: Issue[]
}

export interface Job {
  id: string
  filename: string
  created_at: string
  analysis: Analysis
  transformed_analysis: Analysis | null
  has_transformation: boolean
  output_format: string | null
}

export interface Cue {
  index: number
  identifier: string | null
  start_ms: number
  end_ms: number
  text: string
  lines: string[]
  settings: string | null
}

export interface Change {
  code: string
  cue_index: number | null
  description: string
  old_value: unknown
  new_value: unknown
}

export interface Preview {
  original: Cue[]
  transformed: Cue[] | null
  changes: Change[]
}

export interface TransformSettings {
  preset: 'none' | 'safe'
  output_format: 'srt' | 'vtt'
  shift_ms: number
  speed_factor: number
  prevent_negative: boolean
  sort_cues: boolean
  renumber_srt: boolean
  remove_empty: boolean
  remove_duplicates: boolean
  enforce_gap: boolean
  resolve_overlaps: boolean
  enforce_durations: boolean
  split_long: boolean
  merge_short: boolean
  merge_max_gap_ms: number
  thresholds: {
    min_duration_ms: number
    max_duration_ms: number
    min_gap_ms: number
    max_cps: number
    max_wpm: number
    max_chars_per_line: number
    max_lines: number
  }
}
