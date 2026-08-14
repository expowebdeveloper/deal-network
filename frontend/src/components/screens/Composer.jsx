import { useRef, useState } from 'react'
import Avatar from '../ui/Avatar'
import { PhotoIcon, DocumentIcon, PinIcon, CloseIcon } from '../icons/Icons'
import { createPost, uploadMedia, deleteMedia, fileSize } from '../../lib/feed'

const IMAGE_TYPES = 'image/jpeg,image/png,image/gif,image/webp'
const DOC_TYPES =
  '.pdf,.txt,.csv,.doc,.docx,.xls,.xlsx,application/pdf,text/plain,text/csv,' +
  'application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,' +
  'application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/**
 * Home composer. Attachments upload immediately (so the member sees progress and
 * errors straight away) and the post then references them by id.
 */
export default function Composer({ currentUser, onPosted }) {
  const [open, setOpen] = useState(false)
  const [body, setBody] = useState('')
  const [attachments, setAttachments] = useState([])
  const [project, setProject] = useState(null) // { title, detail } when adding a project update
  const [busy, setBusy] = useState(false)
  // Counter, not a boolean: both file inputs can be uploading at once and a
  // single flag would unlock the Post button while the second batch is running.
  const [uploads, setUploads] = useState(0)
  const [error, setError] = useState(null)

  const photoInput = useRef(null)
  const docInput = useRef(null)
  // Bumped on cancel/submit so a late upload cannot re-enter a cleared composer.
  const sessionRef = useRef(0)

  const uploading = uploads > 0

  async function handleFiles(event) {
    const files = [...event.target.files]
    event.target.value = '' // let the same file be picked again later
    if (!files.length) return

    const session = sessionRef.current
    setOpen(true)
    setUploads((n) => n + 1)
    setError(null)

    const problems = []
    for (const file of files) {
      try {
        const media = await uploadMedia(file)
        if (sessionRef.current !== session) {
          // Composer was cancelled mid-upload — bin the file rather than
          // silently attaching it to whatever is typed next.
          deleteMedia(media.id).catch(() => {})
          continue
        }
        setAttachments((current) => [...current, media])
      } catch (err) {
        // Keep going: one rejected file should not drop the rest of the batch.
        problems.push(`${file.name}: ${err.message}`)
      }
    }

    if (problems.length && sessionRef.current === session) setError(problems.join(' · '))
    setUploads((n) => Math.max(0, n - 1))
  }

  async function removeAttachment(media) {
    setAttachments((current) => current.filter((a) => a.id !== media.id))
    // Not yet referenced by a post, so it is safe to remove from storage too.
    deleteMedia(media.id).catch(() => {})
  }

  function reset({ keepFiles = false } = {}) {
    // Invalidate in-flight uploads for the session being torn down.
    sessionRef.current += 1
    if (!keepFiles) {
      // Nothing references these yet, so remove them instead of orphaning them.
      attachments.forEach((a) => deleteMedia(a.id).catch(() => {}))
    }
    setBody('')
    setAttachments([])
    setProject(null)
    setOpen(false)
    setError(null)
  }

  async function submit() {
    if (!body.trim() && attachments.length === 0) {
      setError('Write something or attach a file.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const post = await createPost({
        body: body.trim(),
        attachment_ids: attachments.map((a) => a.id),
        embed_title: project?.title?.trim() || null,
        embed_detail: project?.detail?.trim() || null,
      })
      reset({ keepFiles: true }) // the post owns them now
      onPosted?.(post)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card composer">
      <div className="composer-top">
        <Avatar initials={currentUser?.initials} color={currentUser?.color} />
        {open ? (
          <textarea
            className="composer-input"
            placeholder="Share an update with your network…"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={3}
            autoFocus
          />
        ) : (
          <button
            type="button"
            className="composer-fake"
            onClick={() => setOpen(true)}
          >
            Share an update with your network…
          </button>
        )}
      </div>

      {error && <div className="inline-error" style={{ marginTop: 12 }}>{error}</div>}

      {project && (
        <div className="post-embed composer-embed">
          <input
            placeholder="Project name — e.g. Bay Street Conversion"
            value={project.title}
            onChange={(e) => setProject((p) => ({ ...p, title: e.target.value }))}
          />
          <input
            placeholder="Detail — e.g. 64 residential units · Staten Island, NY"
            value={project.detail}
            onChange={(e) => setProject((p) => ({ ...p, detail: e.target.value }))}
          />
          <button className="composer-embed-remove" onClick={() => setProject(null)}>
            <CloseIcon /> Remove project update
          </button>
        </div>
      )}

      {attachments.length > 0 && (
        <div className="composer-files">
          {attachments.map((a) => (
            <div className={`composer-file${a.kind === 'image' ? ' is-image' : ''}`} key={a.id}>
              {a.kind === 'image' ? (
                <img src={a.url} alt={a.name} />
              ) : (
                <div className="composer-file-doc">
                  <DocumentIcon />
                  <div>
                    <div className="n">{a.name}</div>
                    <div className="s">{fileSize(a.sizeBytes)}</div>
                  </div>
                </div>
              )}
              <button
                className="composer-file-remove"
                onClick={() => removeAttachment(a)}
                aria-label={`Remove ${a.name}`}
              >
                <CloseIcon />
              </button>
            </div>
          ))}
        </div>
      )}

      {uploading && <div className="cm-hint">Uploading…</div>}

      <div className="composer-acts">
        <button className="composer-act" onClick={() => photoInput.current?.click()}>
          <PhotoIcon />Photo
        </button>
        <button className="composer-act" onClick={() => docInput.current?.click()}>
          <DocumentIcon />Document
        </button>
        <button
          className="composer-act"
          onClick={() => { setOpen(true); setProject(project ?? { title: '', detail: '' }) }}
        >
          <PinIcon />Project update
        </button>

        {open && (
          <div className="composer-submit">
            <button className="btn btn-quiet btn-sm" onClick={() => reset()} disabled={busy}>
              Cancel
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={submit}
              data-busy={busy}
              disabled={uploading}
            >
              {busy ? 'Posting…' : 'Post'}
            </button>
          </div>
        )}
      </div>

      <input
        ref={photoInput}
        type="file"
        accept={IMAGE_TYPES}
        multiple
        hidden
        onChange={handleFiles}
      />
      <input ref={docInput} type="file" accept={DOC_TYPES} multiple hidden onChange={handleFiles} />
    </div>
  )
}
