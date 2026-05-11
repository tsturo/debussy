import { useCallback, useEffect, useState } from 'react'

// ── Types ─────────────────────────────────────────────────────────────────────

/**
 * An image attached (but not yet sent) to the current input.
 * `path`       — absolute FS path passed to --image flag
 * `previewUrl` — object URL used for display (revoked on send/remove)
 * `isTemp`     — true when the file was created by uploadImage (clipboard),
 *                false for real files (drag-and-drop / file-picker)
 */
export interface AttachedImage {
  id: string
  path: string
  previewUrl: string
  isTemp: boolean
}

export interface ImagePayload {
  imagePaths: string[]
  tempPaths: string[]
  previewUrls: string[]
}

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * Encapsulates all image-attachment logic for the conductor chat panel.
 * Pass `inputRef` so the paste handler can guard against out-of-focus pastes.
 */
export function useImageAttachments(inputRef: React.RefObject<HTMLInputElement>) {
  const [attachedImages, setAttachedImages] = useState<AttachedImage[]>([])
  const [isDragOver, setIsDragOver] = useState(false)

  // ── Helpers ────────────────────────────────────────────────────────────────

  function revokePreviewUrls(images: AttachedImage[]) {
    for (const img of images) {
      URL.revokeObjectURL(img.previewUrl)
    }
  }

  function newId() {
    return `img-${Date.now()}-${Math.random()}`
  }

  // ── Paste ──────────────────────────────────────────────────────────────────

  const handlePaste = useCallback(async (e: ClipboardEvent) => {
    // Only intercept when our input is focused
    if (document.activeElement !== inputRef.current) return

    const items = Array.from(e.clipboardData?.items ?? [])
    const imageItem = items.find((item) => item.type.startsWith('image/'))
    if (!imageItem) return  // non-image paste — let default text handling proceed

    e.preventDefault()

    const file = imageItem.getAsFile()
    if (!file) return

    try {
      const path = await window.debussy.conductor.uploadImage(await file.arrayBuffer(), imageItem.type)
      const previewUrl = URL.createObjectURL(file)
      setAttachedImages((prev) => [...prev, { id: newId(), path, previewUrl, isTemp: true }])
    } catch (err) {
      console.error('[conductor] uploadImage failed:', err)
    }
  }, [inputRef])

  useEffect(() => {
    document.addEventListener('paste', handlePaste)
    return () => document.removeEventListener('paste', handlePaste)
  }, [handlePaste])

  // ── Drag & drop ────────────────────────────────────────────────────────────

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    if (!Array.from(e.dataTransfer.types).includes('Files')) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
    setIsDragOver(true)
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>) {
    // Only clear when leaving the panel itself (not a child element)
    if (e.currentTarget.contains(e.relatedTarget as Node)) return
    setIsDragOver(false)
  }

  async function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setIsDragOver(false)

    const imageFiles = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith('image/'))
    const newImages: AttachedImage[] = []

    for (const file of imageFiles) {
      // In Electron the File object has a `path` property
      const filePath = (file as File & { path: string }).path
      if (!filePath) {
        // Fallback: upload via IPC (e.g. when path is unavailable)
        try {
          const path = await window.debussy.conductor.uploadImage(await file.arrayBuffer(), file.type)
          newImages.push({ id: newId(), path, previewUrl: URL.createObjectURL(file), isTemp: true })
        } catch (err) {
          console.error('[conductor] uploadImage (drop fallback) failed:', err)
        }
      } else {
        newImages.push({ id: newId(), path: filePath, previewUrl: `file://${filePath}`, isTemp: false })
      }
    }
    setAttachedImages((prev) => [...prev, ...newImages])
  }

  // ── File picker ────────────────────────────────────────────────────────────

  async function handleOpenFilePicker() {
    try {
      const paths = await window.debussy.conductor.openFileDialog()
      const newImages: AttachedImage[] = paths.map((p) => ({
        id: newId(),
        path: p,
        previewUrl: `file://${p}`,
        isTemp: false,
      }))
      setAttachedImages((prev) => [...prev, ...newImages])
    } catch (err) {
      console.error('[conductor] openFileDialog failed:', err)
    }
  }

  // ── State mutators ─────────────────────────────────────────────────────────

  function handleRemoveImage(id: string) {
    setAttachedImages((prev) => {
      const img = prev.find((i) => i.id === id)
      if (img) URL.revokeObjectURL(img.previewUrl)
      return prev.filter((i) => i.id !== id)
    })
  }

  /** Clear without revoking — used after send (parent holds the object URLs). */
  function clearImages() {
    setAttachedImages([])
  }

  /** Revoke all object URLs then clear — used when starting a new session. */
  function revokeAndClearImages() {
    revokePreviewUrls(attachedImages)
    setAttachedImages([])
  }

  /** Extract the three arrays needed by `onSend`. */
  function getImagePayload(): ImagePayload {
    return {
      imagePaths: attachedImages.map((img) => img.path),
      tempPaths:  attachedImages.filter((img) => img.isTemp).map((img) => img.path),
      previewUrls: attachedImages.map((img) => img.previewUrl),
    }
  }

  return {
    attachedImages,
    isDragOver,
    handlePaste,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    handleOpenFilePicker,
    handleRemoveImage,
    clearImages,
    revokeAndClearImages,
    getImagePayload,
  }
}
