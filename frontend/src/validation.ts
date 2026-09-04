export function validateSubtitleFile(file: File): string | null {
  const extension = file.name.toLowerCase().split('.').pop()
  if (extension !== 'srt' && extension !== 'vtt') return 'Choose an SRT or WebVTT file.'
  if (file.size > 5 * 1024 * 1024) return 'The file must be 5 MB or smaller.'
  if (file.size === 0) return 'The file is empty.'
  return null
}
