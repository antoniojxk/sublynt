export function timecode(milliseconds: number): string {
  const safe = Math.max(0, milliseconds)
  const hours = Math.floor(safe / 3_600_000)
  const minutes = Math.floor((safe % 3_600_000) / 60_000)
  const seconds = Math.floor((safe % 60_000) / 1_000)
  const millis = safe % 1_000
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(millis).padStart(3, '0')}`
}

export function duration(milliseconds: number): string {
  if (milliseconds < 60_000) return `${(milliseconds / 1000).toFixed(1)}s`
  return `${Math.floor(milliseconds / 60_000)}m ${Math.floor((milliseconds % 60_000) / 1000)}s`
}
