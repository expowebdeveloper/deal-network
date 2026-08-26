/**
 * Frontend uploaded file storage & media management directory helper.
 * 
 * Handles formatting, previewing, and opening post attachments (Images, Videos, Documents).
 */

import { API_URL } from '../lib/api'

/** Construct full absolute URL for uploaded media files */
export function getMediaUrl(path) {
  if (!path) return ''
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('data:')) {
    return path
  }
  return `${API_URL}${path.startsWith('/') ? '' : '/'}${path}`
}

/** Check file category */
export function getFileCategory(file) {
  if (!file) return 'document'
  const kind = file.kind || file.type
  if (kind === 'image' || file.contentType?.startsWith('image/')) return 'image'
  if (kind === 'video' || file.contentType?.startsWith('video/')) return 'video'
  return 'document'
}

/** Format byte size to readable string */
export function formatBytes(bytes) {
  if (!bytes || isNaN(bytes)) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Handle opening/viewing attachment */
export function openAttachment(file) {
  const url = getMediaUrl(file.url || file.path)
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}
