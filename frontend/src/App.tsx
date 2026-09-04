import { useMemo, useRef, useState } from 'react'
import { deleteJob, downloadUrl, getPreview, transform, upload } from './api'
import { duration, timecode } from './format'
import { IssueTable } from './IssueTable'
import type { Analysis, Job, Preview, Severity, TransformSettings } from './types'
import { validateSubtitleFile } from './validation'
import './styles.css'

type Stage = 'upload' | 'analysis' | 'repair' | 'preview'

const defaults: TransformSettings = {
  preset: 'safe', output_format: 'srt', shift_ms: 0, speed_factor: 1, prevent_negative: true,
  sort_cues: false, renumber_srt: false, remove_empty: false, remove_duplicates: false,
  enforce_gap: false, resolve_overlaps: false, enforce_durations: false, split_long: false,
  merge_short: false, merge_max_gap_ms: 250,
  thresholds: { min_duration_ms: 1000, max_duration_ms: 7000, min_gap_ms: 80, max_cps: 20, max_wpm: 180, max_chars_per_line: 42, max_lines: 2 },
}

function Metric({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>
}

function Summary({ analysis }: { analysis: Analysis }) {
  return <div className="metrics">
    <Metric label="Format" value={analysis.format.toUpperCase()} />
    <Metric label="Captions" value={analysis.caption_count} />
    <Metric label="Timeline" value={duration(analysis.total_duration_ms)} />
    <Metric label="Avg. duration" value={duration(analysis.average_caption_duration_ms)} />
    <Metric label="Reading pace" value={`${analysis.average_cps} cps`} note={`${analysis.average_wpm} wpm`} />
    <Metric label="Issues" value={analysis.issue_count} note={`${analysis.issue_counts.error ?? 0} errors`} />
  </div>
}

function Toggle({ name, label, hint, checked, onChange, danger = false }: { name: keyof TransformSettings; label: string; hint: string; checked: boolean; onChange: (name: keyof TransformSettings, value: boolean) => void; danger?: boolean }) {
  return <label className={`toggle-row ${danger ? 'risk' : ''}`}>
    <span><strong>{label}</strong><small>{hint}</small></span>
    <input name={name} type="checkbox" checked={checked} onChange={(event) => onChange(name, event.target.checked)} />
  </label>
}

export default function App() {
  const [stage, setStage] = useState<Stage>('upload')
  const [job, setJob] = useState<Job | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [settings, setSettings] = useState(defaults)
  const [filter, setFilter] = useState<Severity | 'all'>('all')
  const [changedOnly, setChangedOnly] = useState(false)
  const [progress, setProgress] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file?: File) => {
    if (!file) return
    const validation = validateSubtitleFile(file)
    if (validation) { setError(validation); return }
    setBusy(true); setError(''); setProgress(0)
    try {
      const created = await upload(file, setProgress)
      setJob(created)
      setSettings((value) => ({ ...value, output_format: created.analysis.format }))
      setStage('analysis')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Upload failed.')
    } finally { setBusy(false) }
  }

  const runTransform = async () => {
    if (!job) return
    setBusy(true); setError('')
    try {
      await transform(job.id, settings)
      setPreview(await getPreview(job.id))
      setStage('preview')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Repair failed.')
    } finally { setBusy(false) }
  }

  const startOver = async () => {
    if (job) await deleteJob(job.id).catch(() => undefined)
    setJob(null); setPreview(null); setProgress(0); setError(''); setStage('upload')
  }

  const changedPositions = useMemo(() => new Set(preview?.changes.map((change) => change.cue_index).filter((value): value is number => value != null) ?? []), [preview])
  const originalCues = preview?.original.filter((cue) => !changedOnly || changedPositions.has(cue.index)) ?? []
  const resultCues = preview?.transformed?.filter((cue) => !changedOnly || changedPositions.has(cue.index)) ?? []
  const setFlag = (name: keyof TransformSettings, value: boolean) => setSettings((current) => ({ ...current, [name]: value }))

  return <div className="app-shell">
    <header className="topbar">
      <button className="brand" onClick={() => void startOver()} aria-label="SubLynt home"><span>SL</span>SubLynt</button>
      <div className="status"><span className="status-dot" /> Local processing · Private by design</div>
    </header>
    <main>
      <nav className="steps" aria-label="Workflow progress">
        {(['upload', 'analysis', 'repair', 'preview'] as Stage[]).map((item, index) => <button key={item} disabled={!job && item !== 'upload'} className={stage === item ? 'active' : ''} onClick={() => (item === 'upload' ? void startOver() : setStage(item))}><span>{index + 1}</span>{item === 'preview' ? 'Preview & download' : item}</button>)}
      </nav>

      {error && <div className="alert" role="alert"><strong>Something needs attention</strong>{error}</div>}
      <div aria-live="polite" className="sr-only">{busy ? 'Processing file' : error || (job ? 'File ready' : '')}</div>

      {stage === 'upload' && <section className="hero">
        <div className="eyebrow">Subtitle quality, clearly explained</div>
        <h1>Clean captions.<br/><em>Keep every word.</em></h1>
        <p>Spot timing, readability, and formatting problems. Apply deliberate repairs and inspect every change before downloading.</p>
        <div className="dropzone" role="button" tabIndex={0} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click() }} onClick={() => inputRef.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); void handleFile(event.dataTransfer.files[0]) }}>
          <div className="upload-icon">↥</div><strong>{busy ? 'Analyzing your captions…' : 'Drop a subtitle file here'}</strong><span>or choose a file from your computer</span>
          <button type="button" className="primary" disabled={busy}>Choose file</button>
          <input ref={inputRef} hidden type="file" accept=".srt,.vtt,text/vtt,application/x-subrip" onChange={(event) => void handleFile(event.target.files?.[0])} />
          {busy && <progress value={progress} max="100" aria-label="Upload progress">{progress}%</progress>}
          <small>SRT or WebVTT · UTF-8 · up to 5 MB</small>
        </div>
        <div className="trust-row"><span>✓ Processed locally on this server</span><span>✓ No subtitle text is logged</span><span>✓ Automatic expiry</span></div>
      </section>}

      {stage === 'analysis' && job && <section>
        <div className="section-heading"><div><div className="eyebrow">Analysis complete</div><h1>{job.filename}</h1><p>Here’s the shape of your subtitle track and what could use attention.</p></div><button className="primary" onClick={() => setStage('repair')}>Configure repairs →</button></div>
        <Summary analysis={job.analysis} />
        <div className="panel">
          <div className="panel-title"><div><h2>Detected issues</h2><p>Severity includes a symbol and label, not color alone.</p></div><div className="filters" aria-label="Filter issues">{(['all', 'error', 'warning', 'info'] as const).map((item) => <button className={filter === item ? 'selected' : ''} onClick={() => setFilter(item)} key={item}>{item} {item === 'all' ? job.analysis.issue_count : job.analysis.issue_counts[item] ?? 0}</button>)}</div></div>
          <IssueTable issues={job.analysis.issues} filter={filter} />
        </div>
      </section>}

      {stage === 'repair' && job && <section>
        <div className="section-heading"><div><div className="eyebrow">Repair settings</div><h1>Choose what changes</h1><p>Safe repair is conservative. Timing and text operations stay opt-in.</p></div><button className="primary" disabled={busy} onClick={() => void runTransform()}>{busy ? 'Building preview…' : 'Apply & preview →'}</button></div>
        <div className="repair-grid">
          <div className="panel settings-panel">
            <label className="preset"><input type="radio" checked={settings.preset === 'safe'} onChange={() => setSettings({...settings, preset: 'safe'})}/><span><strong>Safe repair</strong><small>Sort, renumber, remove empties, and fix reversed timing.</small></span><b>Recommended</b></label>
            <label className="preset"><input type="radio" checked={settings.preset === 'none'} onChange={() => setSettings({...settings, preset: 'none'})}/><span><strong>Custom only</strong><small>Apply only the choices below.</small></span></label>
            <h2>Timing</h2>
            <div className="field-row"><label>Shift all timestamps <span><input type="number" value={settings.shift_ms} onChange={(event) => setSettings({...settings, shift_ms: Number(event.target.value)})}/> ms</span></label><label>Playback speed <span><input type="number" min="0.1" max="10" step="0.01" value={settings.speed_factor} onChange={(event) => setSettings({...settings, speed_factor: Number(event.target.value)})}/> ×</span></label></div>
            <Toggle name="resolve_overlaps" label="Resolve overlaps" hint="Move a later cue without deleting text." checked={settings.resolve_overlaps} onChange={setFlag} danger />
            <Toggle name="enforce_gap" label="Enforce minimum gaps" hint="Maintain the configured breathing room between cues." checked={settings.enforce_gap} onChange={setFlag} danger />
            <Toggle name="enforce_durations" label="Clamp durations" hint="Extend or shorten cues to configured limits." checked={settings.enforce_durations} onChange={setFlag} danger />
            <h2>Text & structure</h2>
            <Toggle name="remove_duplicates" label="Remove exact duplicates" hint="Only identical consecutive cues with identical timing." checked={settings.remove_duplicates} onChange={setFlag} />
            <Toggle name="split_long" label="Split long captions" hint="Sentence and punctuation boundaries are preferred." checked={settings.split_long} onChange={setFlag} danger />
            <Toggle name="merge_short" label="Merge short captions" hint="Only compatible neighboring cues are combined." checked={settings.merge_short} onChange={setFlag} danger />
          </div>
          <aside className="panel output-panel"><h2>Output</h2><label>File format<select value={settings.output_format} onChange={(event) => setSettings({...settings, output_format: event.target.value as 'srt' | 'vtt'})}><option value="srt">SubRip (.srt)</option><option value="vtt">WebVTT (.vtt)</option></select></label>
            <details><summary>Advanced thresholds</summary><div className="thresholds">
              {([['min_duration_ms','Minimum duration','ms'],['max_duration_ms','Maximum duration','ms'],['min_gap_ms','Minimum gap','ms'],['max_cps','Maximum reading speed','cps'],['max_wpm','Maximum word speed','wpm'],['max_chars_per_line','Characters per line','chars'],['max_lines','Lines per caption','lines']] as const).map(([key,label,unit]) => <label key={key}>{label}<span><input type="number" value={settings.thresholds[key]} onChange={(event) => setSettings({...settings, thresholds: {...settings.thresholds, [key]: Number(event.target.value)}})}/>{unit}</span></label>)}
            </div></details><div className="notice">⚠ Aggressive options can alter timing or caption grouping. Every modification appears in the change log.</div></aside>
        </div>
      </section>}

      {stage === 'preview' && job && preview && <section>
        <div className="section-heading"><div><div className="eyebrow">Preview ready</div><h1>Inspect before you download</h1><p>{preview.changes.length} recorded changes · Output is valid {settings.output_format.toUpperCase()}</p></div><div className="actions"><button className="secondary" onClick={() => setStage('repair')}>← Settings</button><a className="primary button" href={downloadUrl(job.id)}>Download .{settings.output_format}</a></div></div>
        <div className="preview-toolbar"><label><input type="checkbox" checked={changedOnly} onChange={(event) => setChangedOnly(event.target.checked)}/> Show changed cues only</label><span className="valid">✓ Final parse validation passed</span></div>
        <div className="compare"><div><h2>Original <small>{preview.original.length} cues</small></h2>{originalCues.map((cue) => <article id={`cue-${cue.index}`} className={changedPositions.has(cue.index) ? 'cue changed' : 'cue'} key={cue.index}><b>#{cue.index}</b><time>{timecode(cue.start_ms)} → {timecode(cue.end_ms)}</time><p>{cue.text}</p></article>)}</div><div><h2>Corrected <small>{preview.transformed?.length ?? 0} cues</small></h2>{resultCues.map((cue) => <article className={changedPositions.has(cue.index) ? 'cue changed' : 'cue'} key={`${cue.index}-${cue.start_ms}`}><b>#{cue.index}</b><time>{timecode(cue.start_ms)} → {timecode(cue.end_ms)}</time><p>{cue.text}</p></article>)}</div></div>
        <div className="panel change-log"><h2>Change log</h2>{preview.changes.length ? <ol>{preview.changes.map((change, index) => <li key={`${change.code}-${index}`}><code>{change.code}</code><span>{change.description}{change.cue_index && ` · cue ${change.cue_index}`}</span></li>)}</ol> : <p>No content changes were required. Format normalization was still validated.</p>}</div>
        <div className="finish"><button className="text-button" onClick={() => void startOver()}>Delete job & start over</button></div>
      </section>}
    </main>
    <footer><span>SubLynt</span><p>Readable subtitles make stories easier to enter.</p><small>Files expire after the configured retention period.</small></footer>
  </div>
}
