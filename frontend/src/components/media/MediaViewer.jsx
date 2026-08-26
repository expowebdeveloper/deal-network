import { useState, useEffect } from 'react'
import mammoth from 'mammoth'
import { getMediaUrl, formatBytes } from '../../uploads'
import { DocumentIcon, CloseIcon } from '../icons/Icons'

/**
 * Renders file attachments for posts (Images, Videos, Documents).
 * Clicking an image opens a high-res lightbox preview.
 * Clicking a video allows interactive playback & full-screen viewing.
 * Clicking a document opens an in-app Document Viewer Modal that renders
 * DOCX, PDF, TXT, CSV, and text content directly inside the browser window.
 */
export default function MediaViewer({ files = [] }) {
  const [activeMedia, setActiveMedia] = useState(null)
  const [activeDoc, setActiveDoc] = useState(null)
  const [docHtml, setDocHtml] = useState('')
  const [docText, setDocText] = useState('')
  const [loadingDoc, setLoadingDoc] = useState(false)
  const [docError, setDocError] = useState(null)

  useEffect(() => {
    if (!activeDoc) {
      setDocHtml('')
      setDocText('')
      setLoadingDoc(false)
      setDocError(null)
      return
    }

    const docUrl = getMediaUrl(activeDoc.url)
    const nameLower = (activeDoc.name || '').toLowerCase()

    if (nameLower.endsWith('.docx')) {
      setLoadingDoc(true)
      setDocError(null)
      fetch(docUrl)
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
          return res.arrayBuffer()
        })
        .then((arrayBuffer) => mammoth.convertToHtml({ arrayBuffer }))
        .then((result) => {
          setDocHtml(result.value || '<p>No readable content found in document.</p>')
          setLoadingDoc(false)
        })
        .catch((err) => {
          console.error('Docx rendering error:', err)
          setDocError('Could not load document preview. The file may have been reset or is corrupt.')
          setLoadingDoc(false)
        })
    } else if (
      nameLower.endsWith('.txt') ||
      nameLower.endsWith('.csv') ||
      nameLower.endsWith('.json') ||
      nameLower.endsWith('.md')
    ) {
      setLoadingDoc(true)
      setDocError(null)
      fetch(docUrl)
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`)
          return res.text()
        })
        .then((text) => {
          setDocText(text)
          setLoadingDoc(false)
        })
        .catch(() => {
          setDocError('Could not load text document.')
          setLoadingDoc(false)
        })
    }
  }, [activeDoc])

  if (!files || files.length === 0) return null

  return (
    <>
      <div className="post-files">
        {files.map((file) => {
          const url = getMediaUrl(file.url)
          const isImage = file.kind === 'image' || file.contentType?.startsWith('image/')
          const isVideo = file.kind === 'video' || file.contentType?.startsWith('video/')

          if (isVideo) {
            return (
              <div className="post-media-wrap video-wrap" key={file.id || url}>
                <video
                  className="post-video"
                  src={url}
                  controls
                  preload="metadata"
                  playsInline
                />
              </div>
            )
          }

          if (isImage) {
            return (
              <div
                className="post-media-wrap image-wrap"
                key={file.id || url}
                onClick={() => setActiveMedia(file)}
                title="Click to expand image"
              >
                <img
                  src={url}
                  alt={file.name || 'Post image attachment'}
                  loading="lazy"
                  onError={(e) => {
                    if (e.target.src !== file.url) {
                      e.target.src = file.url
                    }
                  }}
                />
                <div className="media-zoom-overlay">
                  <span>Click to view full image</span>
                </div>
              </div>
            )
          }

          // Document attachment
          return (
            <button
              type="button"
              key={file.id || url}
              className="post-doc post-doc-btn"
              onClick={() => setActiveDoc(file)}
              title={`Click to view document ${file.name}`}
            >
              <DocumentIcon />
              <div className="post-doc-info">
                <div className="n">{file.name}</div>
                <div className="s">{formatBytes(file.sizeBytes)} · Click to view document</div>
              </div>
            </button>
          )
        })}
      </div>

      {/* Lightbox Modal for enlarged image preview */}
      {activeMedia && (
        <div className="media-lightbox-back" onClick={() => setActiveMedia(null)}>
          <div className="media-lightbox-content" onClick={(e) => e.stopPropagation()}>
            <button
              className="media-lightbox-close"
              onClick={() => setActiveMedia(null)}
              aria-label="Close preview"
            >
              <CloseIcon />
            </button>
            <div className="media-lightbox-body">
              <img
                src={getMediaUrl(activeMedia.url)}
                alt={activeMedia.name || 'Enlarged preview'}
              />
            </div>
            <div className="media-lightbox-foot">
              <span>{activeMedia.name}</span>
              <a
                href={getMediaUrl(activeMedia.url)}
                target="_blank"
                rel="noreferrer"
                className="btn btn-primary btn-sm"
              >
                Open in New Tab
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Document Viewer Modal */}
      {activeDoc && (() => {
        const docUrl = getMediaUrl(activeDoc.url)
        const nameLower = (activeDoc.name || '').toLowerCase()
        const isPdf = nameLower.endsWith('.pdf')
        const isDocx = nameLower.endsWith('.docx')

        return (
          <div className="media-lightbox-back" onClick={() => setActiveDoc(null)}>
            <div className="media-lightbox-content doc-modal-content" onClick={(e) => e.stopPropagation()}>
              <div className="doc-modal-head">
                <div className="doc-modal-title">
                  <DocumentIcon />
                  <div>
                    <div className="t">{activeDoc.name}</div>
                    <div className="s">{formatBytes(activeDoc.sizeBytes)}</div>
                  </div>
                </div>
                <button
                  className="media-lightbox-close relative-close"
                  onClick={() => setActiveDoc(null)}
                  aria-label="Close document viewer"
                >
                  <CloseIcon />
                </button>
              </div>

              <div className="doc-modal-body">
                {loadingDoc ? (
                  <div className="doc-loading">
                    <div className="spinner" />
                    <span>Rendering document preview...</span>
                  </div>
                ) : docError ? (
                  <div className="doc-card-view">
                    <div className="doc-card-icon error-icon">
                      <DocumentIcon />
                    </div>
                    <h3>Document Unavailable</h3>
                    <p className="doc-card-hint">{docError}</p>
                  </div>
                ) : isPdf ? (
                  <iframe
                    src={docUrl}
                    title={activeDoc.name}
                    className="doc-iframe"
                  />
                ) : isDocx && docHtml ? (
                  <div
                    className="doc-html-reader"
                    dangerouslySetInnerHTML={{ __html: docHtml }}
                  />
                ) : docText ? (
                  <pre className="doc-text-reader">{docText}</pre>
                ) : (
                  <div className="doc-card-view">
                    <div className="doc-card-icon">
                      <DocumentIcon />
                    </div>
                    <h3>{activeDoc.name}</h3>
                    <p className="doc-card-sub">
                      {formatBytes(activeDoc.sizeBytes)} · Document Attachment
                    </p>
                    <p className="doc-card-hint">
                      This file can be opened directly or saved to your machine.
                    </p>
                    <div className="doc-card-acts">
                      <a
                        href={docUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-primary"
                      >
                        Open Document in New Tab
                      </a>
                      <a
                        href={docUrl}
                        download={activeDoc.name}
                        className="btn btn-ghost"
                      >
                        Download File
                      </a>
                    </div>
                  </div>
                )}
              </div>

              <div className="media-lightbox-foot">
                <span>{activeDoc.name}</span>
                <div style={{ display: 'flex', gap: 8 }}>
                  <a
                    href={docUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="btn btn-primary btn-sm"
                  >
                    Open in New Tab
                  </a>
                  <a
                    href={docUrl}
                    download={activeDoc.name}
                    className="btn btn-ghost btn-sm"
                  >
                    Download
                  </a>
                </div>
              </div>
            </div>
          </div>
        )
      })()}
    </>
  )
}
