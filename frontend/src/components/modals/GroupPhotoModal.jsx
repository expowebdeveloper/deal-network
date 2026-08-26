import { useEffect, useRef } from 'react'
import Avatar from '../ui/Avatar'
import { CloseIcon, CameraIcon, TrashIcon } from '../icons/Icons'
import { ACCEPT } from '../../lib/feed'

/**
 * WhatsApp-style Group Profile Photo Lightbox Viewer & Editor Modal.
 * Opens when a user clicks on the group profile photo.
 * Displays full photo preview and provides controls to change or remove photo.
 */
export default function GroupPhotoModal({
  isOpen,
  onClose,
  logoUrl,
  initials = 'G',
  communityName = 'Group Photo',
  bannerColor = 'a1',
  onUploadPhoto,
  onRemovePhoto,
  canEdit = true,
  busy = false,
}) {
  const fileInputRef = useRef(null)

  /* Escape has to be caught here, not left to the app-wide handler.
     This lightbox opens *on top of* the settings drawer, and AppContext
     listens on document for Escape and closes the modal underneath — so
     without this, dismissing the photo would take the whole panel with it.
     Capture phase, then stopPropagation: the capture listener on document runs
     before the bubble-phase one that AppContext registered. */
  useEffect(() => {
    if (!isOpen) return undefined
    function onKeyDown(e) {
      if (e.key !== 'Escape') return
      e.stopPropagation()
      onClose?.()
    }
    document.addEventListener('keydown', onKeyDown, true)
    return () => document.removeEventListener('keydown', onKeyDown, true)
  }, [isOpen, onClose])

  if (!isOpen) return null

  function handleFileChange(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (file && onUploadPhoto) {
      onUploadPhoto(file)
    }
  }

  return (
    <div className="wa-photo-lightbox-backdrop" onClick={onClose}>
      <div className="wa-photo-lightbox-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="wa-photo-lightbox-head">
          <div className="wa-photo-lightbox-info">
            <h3 className="wa-photo-lightbox-title">{communityName}</h3>
            <span className="wa-photo-lightbox-sub">
              {logoUrl ? 'Group profile photo' : 'Default group icon'}
            </span>
          </div>
          <button
            type="button"
            className="wa-photo-lightbox-close"
            onClick={onClose}
            aria-label="Close photo preview"
          >
            <CloseIcon />
          </button>
        </div>

        <div className="wa-photo-lightbox-body">
          <div className="wa-photo-preview-wrap">
            {logoUrl ? (
              <img
                src={logoUrl}
                alt={communityName}
                className="wa-photo-full-img"
              />
            ) : (
              <Avatar
                initials={initials}
                color={bannerColor}
                size="xl"
                className="wa-photo-avatar-lg"
              />
            )}
          </div>
        </div>

        <div className="wa-photo-lightbox-foot">
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT.image}
            hidden
            onChange={handleFileChange}
          />

          {canEdit && (
            <div className="wa-photo-actions-row">
              <button
                type="button"
                className="wa-photo-act-btn primary"
                onClick={() => fileInputRef.current?.click()}
                disabled={busy}
              >
                <CameraIcon style={{ width: 18, height: 18 }} />
                <span>{logoUrl ? 'Change photo' : 'Upload photo'}</span>
              </button>

              {logoUrl && onRemovePhoto && (
                <button
                  type="button"
                  className="wa-photo-act-btn danger"
                  onClick={onRemovePhoto}
                  disabled={busy}
                >
                  <TrashIcon style={{ width: 18, height: 18 }} />
                  <span>Remove photo</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
