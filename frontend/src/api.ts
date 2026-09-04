import type { Job, Preview, TransformSettings } from './types'

const API = import.meta.env.VITE_API_URL ?? '/api/v1'

async function checked<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(payload?.error?.message ?? 'The request could not be completed.')
  }
  return response.json() as Promise<T>
}

export async function upload(file: File, onProgress: (value: number) => void): Promise<Job> {
  const form = new FormData()
  form.append('file', file)
  onProgress(20)
  const request = fetch(`${API}/files`, { method: 'POST', body: form })
  onProgress(55)
  const result = await checked<Job>(await request)
  onProgress(100)
  return result
}

export async function transform(fileId: string, settings: TransformSettings) {
  return checked<{
    file_id: string
    output_format: string
    change_count: number
    changes: unknown[]
    analysis: Job['analysis']
  }>(
    await fetch(`${API}/files/${fileId}/transform`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    }),
  )
}

export async function getPreview(fileId: string): Promise<Preview> {
  return checked<Preview>(await fetch(`${API}/files/${fileId}/preview`))
}

export async function deleteJob(fileId: string): Promise<void> {
  const response = await fetch(`${API}/files/${fileId}`, { method: 'DELETE' })
  if (!response.ok) throw new Error('Could not delete this job.')
}

export function downloadUrl(fileId: string): string {
  return `${API}/files/${fileId}/download`
}
