// Thumbnail preview for an image attached to a conductor message.
// Shows the image up to 200px wide and provides a remove button.

interface ImagePreviewProps {
  /** Object URL or file:// URL for the image thumbnail */
  src: string
  /** Called when the user clicks the × button */
  onRemove: () => void
}

export function ImagePreview({ src, onRemove }: ImagePreviewProps) {
  return (
    <div
      style={{
        position: 'relative',
        display: 'inline-block',
        maxWidth: 200,
        flexShrink: 0,
      }}
    >
      <img
        src={src}
        alt="Attached image"
        style={{
          maxWidth: 200,
          maxHeight: 120,
          borderRadius: 8,
          display: 'block',
          border: '1px solid var(--t-border)',
          objectFit: 'cover',
        }}
      />
      <button
        onClick={onRemove}
        aria-label="Remove image"
        title="Remove"
        style={{
          position: 'absolute',
          top: -6,
          right: -6,
          width: 18,
          height: 18,
          borderRadius: '50%',
          background: 'var(--t-surface)',
          border: '1px solid var(--t-border)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 0,
          color: 'var(--t-text-2)',
          fontSize: 9,
          lineHeight: 1,
          transition: 'background var(--t-dur-fast)',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'var(--t-bg)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'var(--t-surface)'
        }}
      >
        ×
      </button>
    </div>
  )
}

// ── Inline thumbnail for already-sent images in chat history ─────────────────

interface SentImageThumbnailProps {
  src: string
}

export function SentImageThumbnail({ src }: SentImageThumbnailProps) {
  return (
    <img
      src={src}
      alt="Attached image"
      style={{
        maxWidth: 160,
        maxHeight: 100,
        borderRadius: 8,
        display: 'block',
        border: '1px solid var(--t-border)',
        objectFit: 'cover',
        marginTop: 4,
      }}
    />
  )
}
