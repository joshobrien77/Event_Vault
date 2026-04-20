import { useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import { Camera, Upload, CheckCircle, XCircle, Lock, Image, Video, CloudUpload } from 'lucide-react'
import { guestApi } from '../lib/api'
import { GuestEventInfo } from '../types'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Spinner from '../components/ui/Spinner'

interface UploadResult {
  file: File
  status: 'uploading' | 'done' | 'error'
  progress: number
  error?: string
}

export default function GuestUpload() {
  const { shortCode } = useParams<{ shortCode: string }>()
  const [pin, setPin] = useState('')
  const [pinVerified, setPinVerified] = useState(false)
  const [pinError, setPinError] = useState('')
  const [pinLoading, setPinLoading] = useState(false)
  const [guestName, setGuestName] = useState('')
  const [uploads, setUploads] = useState<UploadResult[]>([])

  const { data: eventInfo, isLoading, isError, error } = useQuery({
    queryKey: ['guest-event', shortCode],
    queryFn: () => guestApi.resolveLink(shortCode!).then((r) => r.data as GuestEventInfo),
    enabled: !!shortCode,
    retry: false,
  })

  const verifyPin = async () => {
    setPinError('')
    setPinLoading(true)
    try {
      await guestApi.verifyPin(shortCode!, pin)
      setPinVerified(true)
    } catch {
      setPinError('Incorrect PIN. Please try again.')
    } finally {
      setPinLoading(false)
    }
  }

  const uploadFile = useCallback(
    async (file: File) => {
      const id = `${file.name}-${file.lastModified}`
      setUploads((prev) => [
        { file, status: 'uploading', progress: 0 },
        ...prev.filter((u) => `${u.file.name}-${u.file.lastModified}` !== id),
      ])

      const formData = new FormData()
      formData.append('file', file)
      if (guestName.trim()) formData.append('guest_name', guestName.trim())
      if (eventInfo?.requires_pin) formData.append('pin', pin)

      try {
        await guestApi.upload(shortCode!, formData)
        setUploads((prev) =>
          prev.map((u) =>
            `${u.file.name}-${u.file.lastModified}` === id
              ? { ...u, status: 'done', progress: 100 }
              : u,
          ),
        )
      } catch (err: unknown) {
        const msg =
          (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data
            ?.error?.message ?? 'Upload failed'
        setUploads((prev) =>
          prev.map((u) =>
            `${u.file.name}-${u.file.lastModified}` === id
              ? { ...u, status: 'error', error: msg }
              : u,
          ),
        )
      }
    },
    [shortCode, guestName, pin, eventInfo?.requires_pin],
  )

  const accept: Record<string, string[]> = {}
  if (eventInfo?.allow_photo) {
    accept['image/*'] = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic']
  }
  if (eventInfo?.allow_video) {
    accept['video/*'] = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept,
    maxSize: (eventInfo?.upload_limit_mb ?? 25) * 1024 * 1024,
    onDrop: (accepted) => accepted.forEach(uploadFile),
    disabled: !eventInfo || (eventInfo.requires_pin && !pinVerified),
  })

  // ─── Loading state ────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <Spinner size="lg" className="text-brand-600" />
      </div>
    )
  }

  // ─── Error / not found ────────────────────────────────────────────────────

  if (isError) {
    const status = (error as { response?: { status?: number } })?.response?.status
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
        <div className="w-full max-w-sm rounded-xl border bg-white p-8 text-center shadow-sm">
          <XCircle className="mx-auto mb-4 h-12 w-12 text-red-400" />
          <h1 className="text-xl font-bold text-gray-900">
            {status === 410 ? 'Link Expired' : 'Link Not Found'}
          </h1>
          <p className="mt-2 text-sm text-gray-500">
            {status === 410
              ? 'This upload link has expired or the event has ended.'
              : 'This link is invalid or has been deactivated.'}
          </p>
        </div>
      </div>
    )
  }

  // ─── PIN gate ─────────────────────────────────────────────────────────────

  const needsPin = eventInfo?.requires_pin && !pinVerified

  return (
    <div className="min-h-screen bg-gradient-to-b from-brand-50 to-white px-4 py-12">
      <div className="mx-auto w-full max-w-lg space-y-6">
        {/* Header */}
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 text-white">
            <Camera className="h-8 w-8" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{eventInfo?.event_name}</h1>
          {eventInfo?.welcome_message && (
            <p className="mt-2 text-sm text-gray-600">{eventInfo.welcome_message}</p>
          )}
          <div className="mt-3 flex justify-center gap-3 text-xs text-gray-400">
            {eventInfo?.allow_photo && (
              <span className="flex items-center gap-1"><Image className="h-3.5 w-3.5" /> Photos</span>
            )}
            {eventInfo?.allow_video && (
              <span className="flex items-center gap-1"><Video className="h-3.5 w-3.5" /> Videos</span>
            )}
            <span>Max {eventInfo?.upload_limit_mb} MB / file</span>
          </div>
        </div>

        {/* PIN entry */}
        {needsPin && (
          <div className="rounded-xl border bg-white p-6 shadow-sm space-y-4">
            <div className="flex items-center gap-2 text-gray-700">
              <Lock className="h-5 w-5" />
              <p className="font-medium">This event requires a PIN</p>
            </div>
            {pinError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {pinError}
              </div>
            )}
            <Input
              label="Enter PIN"
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && verifyPin()}
              placeholder="e.g. 1234"
            />
            <Button loading={pinLoading} onClick={verifyPin} className="w-full" disabled={!pin}>
              Unlock
            </Button>
          </div>
        )}

        {/* Upload area */}
        {!needsPin && (
          <>
            <div className="rounded-xl border bg-white p-4 shadow-sm">
              <Input
                label="Your name (optional)"
                value={guestName}
                onChange={(e) => setGuestName(e.target.value)}
                placeholder="e.g. Aunt Sarah"
              />
            </div>

            <div
              {...getRootProps()}
              className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
                isDragActive
                  ? 'border-brand-400 bg-brand-50'
                  : 'border-gray-200 bg-white hover:border-brand-300 hover:bg-brand-50'
              }`}
            >
              <input {...getInputProps()} />
              <CloudUpload className="mx-auto mb-3 h-10 w-10 text-brand-400" />
              <p className="font-medium text-gray-700">
                {isDragActive ? 'Drop files here' : 'Tap or drag files to upload'}
              </p>
              <p className="mt-1 text-xs text-gray-400">
                {[eventInfo?.allow_photo && 'Photos', eventInfo?.allow_video && 'Videos']
                  .filter(Boolean)
                  .join(' & ')}{' '}
                · max {eventInfo?.upload_limit_mb} MB each
              </p>
            </div>

            {uploads.length > 0 && (
              <div className="space-y-2">
                {uploads.map((u, i) => (
                  <div key={i} className="flex items-center gap-3 rounded-xl border bg-white p-4 shadow-sm">
                    <div className="flex-1 min-w-0">
                      <p className="truncate text-sm font-medium text-gray-900">{u.file.name}</p>
                      {u.status === 'error' && (
                        <p className="text-xs text-red-600">{u.error}</p>
                      )}
                    </div>
                    <div className="shrink-0">
                      {u.status === 'uploading' && <Spinner size="sm" className="text-brand-600" />}
                      {u.status === 'done' && <CheckCircle className="h-5 w-5 text-green-500" />}
                      {u.status === 'error' && <XCircle className="h-5 w-5 text-red-500" />}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        <p className="text-center text-xs text-gray-400">Powered by EventVault</p>
      </div>
    </div>
  )
}
