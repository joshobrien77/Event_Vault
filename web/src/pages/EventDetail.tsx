import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Link2, Upload, HardDrive, Settings, Copy, Check,
  QrCode, Trash2, ExternalLink, RefreshCw, CheckCircle, XCircle,
} from 'lucide-react'
import { format } from 'date-fns'
import { eventsApi, linksApi, uploadsApi, storageApi } from '../lib/api'
import { Event, EventLink, Upload as UploadType, UploadStats, StorageConfig, formatFileSize } from '../types'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Input from '../components/ui/Input'
import Modal from '../components/ui/Modal'
import Spinner from '../components/ui/Spinner'

type Tab = 'overview' | 'links' | 'uploads' | 'storage'

// ─── helpers ───────────────────────────────────────────────────────────────

function statusVariant(s: Event['status']) {
  return ({ draft: 'gray', active: 'green', archived: 'gray' } as const)[s]
}

function uploadStatusVariant(s: UploadType['status']) {
  return ({ pending: 'yellow', processing: 'blue', completed: 'green', failed: 'red' } as const)[s]
}

async function downloadQr(eventId: string, linkId: string, shortCode: string) {
  const token = localStorage.getItem('access_token')
  const res = await fetch(`/api/v1/events/${eventId}/links/${linkId}/qr?format=png&size=512`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `qr-${shortCode}.png`
  a.click()
  URL.revokeObjectURL(url)
}

// ─── Overview tab ───────────────────────────────────────────────────────────

const EVENT_TYPES = ['wedding', 'graduation', 'birthday', 'corporate', 'other']

function OverviewTab({ event }: { event: Event }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(event.name)
  const [eventType, setEventType] = useState(event.event_type)
  const [eventDate, setEventDate] = useState(event.event_date ?? '')
  const [pin, setPin] = useState('')
  const [welcome, setWelcome] = useState(event.welcome_message ?? '')
  const [error, setError] = useState('')

  const update = useMutation({
    mutationFn: () =>
      eventsApi.update(event.id, {
        name,
        event_type: eventType,
        event_date: eventDate || null,
        guest_pin: pin || undefined,
        welcome_message: welcome || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['event', event.id] })
      setEditing(false)
      setError('')
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? 'Update failed'
      setError(msg)
    },
  })

  const archive = useMutation({
    mutationFn: () => eventsApi.archive(event.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['event', event.id] }),
  })

  const deleteEvent = useMutation({
    mutationFn: () => eventsApi.delete(event.id),
    onSuccess: () => navigate('/'),
  })

  const activate = useMutation({
    mutationFn: () => eventsApi.update(event.id, { status: 'active' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['event', event.id] }),
  })

  return (
    <div className="space-y-6">
      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-900">Event settings</h3>
          {!editing && (
            <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
              <Settings className="h-4 w-4" /> Edit
            </Button>
          )}
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        )}

        {editing ? (
          <div className="space-y-4">
            <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} />
            <div className="space-y-1">
              <label className="block text-sm font-medium text-gray-700">Type</label>
              <select
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={eventType}
                onChange={(e) => setEventType(e.target.value as Event['event_type'])}
              >
                {EVENT_TYPES.map((t) => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
              </select>
            </div>
            <Input label="Date (optional)" type="date" value={eventDate} onChange={(e) => setEventDate(e.target.value)} />
            <Input
              label="New PIN (optional, 4–6 digits — leave blank to keep current)"
              type="text" inputMode="numeric" maxLength={6} pattern="\d{4,6}"
              value={pin} onChange={(e) => setPin(e.target.value)} placeholder="e.g. 1234"
            />
            <div className="space-y-1">
              <label className="block text-sm font-medium text-gray-700">Welcome message</label>
              <textarea
                rows={2}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={welcome}
                onChange={(e) => setWelcome(e.target.value)}
              />
            </div>
            <div className="flex gap-3">
              <Button loading={update.isPending} onClick={() => update.mutate()}>Save</Button>
              <Button variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
            </div>
          </div>
        ) : (
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
            <div><dt className="text-gray-500">Type</dt><dd className="mt-1 font-medium capitalize">{event.event_type}</dd></div>
            <div><dt className="text-gray-500">Status</dt><dd className="mt-1"><Badge variant={statusVariant(event.status)}>{event.status}</Badge></dd></div>
            <div><dt className="text-gray-500">Tier</dt><dd className="mt-1 capitalize">{event.tier}</dd></div>
            <div><dt className="text-gray-500">Date</dt><dd className="mt-1 font-medium">{event.event_date ? format(new Date(event.event_date), 'MMM d, yyyy') : '—'}</dd></div>
            <div><dt className="text-gray-500">Upload limit</dt><dd className="mt-1 font-medium">{event.upload_limit_mb} MB / file</dd></div>
            <div><dt className="text-gray-500">PIN</dt><dd className="mt-1 font-medium">{event.guest_pin ? '••••' : 'None'}</dd></div>
            {event.welcome_message && (
              <div className="col-span-2 sm:col-span-3">
                <dt className="text-gray-500">Welcome message</dt>
                <dd className="mt-1">{event.welcome_message}</dd>
              </div>
            )}
          </dl>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        {event.status === 'draft' && (
          <Button variant="secondary" onClick={() => activate.mutate()} loading={activate.isPending}>
            Activate event
          </Button>
        )}
        {event.status === 'active' && (
          <Button variant="secondary" onClick={() => archive.mutate()} loading={archive.isPending}>
            Archive event
          </Button>
        )}
        <Button
          variant="danger"
          onClick={() => { if (confirm('Delete this event permanently?')) deleteEvent.mutate() }}
          loading={deleteEvent.isPending}
        >
          <Trash2 className="h-4 w-4" /> Delete event
        </Button>
      </div>
    </div>
  )
}

// ─── Links tab ───────────────────────────────────────────────────────────────

function LinksTab({ event }: { event: Event }) {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [label, setLabel] = useState('')
  const [copied, setCopied] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['links', event.id],
    queryFn: () => linksApi.list(event.id).then((r) => r.data.data as EventLink[]),
  })

  const create = useMutation({
    mutationFn: () => linksApi.create(event.id, { label: label || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['links', event.id] })
      setShowCreate(false)
      setLabel('')
    },
  })

  const deactivate = useMutation({
    mutationFn: (linkId: string) => linksApi.deactivate(event.id, linkId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['links', event.id] }),
  })

  const copy = (url: string, id: string) => {
    navigator.clipboard.writeText(url)
    setCopied(id)
    setTimeout(() => setCopied(null), 2000)
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setShowCreate(true)}>
          <Link2 className="h-4 w-4" /> Generate link
        </Button>
      </div>

      {isLoading && <div className="flex justify-center py-10"><Spinner className="text-brand-600" /></div>}

      {!isLoading && (!data || data.length === 0) && (
        <div className="rounded-xl border-2 border-dashed border-gray-200 py-14 text-center">
          <Link2 className="mx-auto mb-3 h-8 w-8 text-gray-300" />
          <p className="text-sm text-gray-500">No links yet — generate one to share with guests.</p>
        </div>
      )}

      <div className="space-y-3">
        {data?.map((link) => (
          <div key={link.id} className="rounded-xl border bg-white p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                {link.label && <p className="text-sm font-medium text-gray-900">{link.label}</p>}
                <p className="truncate text-sm text-brand-600">{link.full_url}</p>
                <div className="mt-1 flex items-center gap-3 text-xs text-gray-400">
                  <span>{link.click_count} clicks</span>
                  <span>Created {format(new Date(link.created_at), 'MMM d, yyyy')}</span>
                  {!link.is_active && <Badge variant="red">Deactivated</Badge>}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button
                  onClick={() => copy(link.full_url, link.id)}
                  className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  title="Copy link"
                >
                  {copied === link.id ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
                </button>
                <a href={link.full_url} target="_blank" rel="noreferrer"
                  className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600" title="Open">
                  <ExternalLink className="h-4 w-4" />
                </a>
                <button
                  onClick={() => downloadQr(event.id, link.id, link.short_code)}
                  className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  title="Download QR"
                >
                  <QrCode className="h-4 w-4" />
                </button>
                {link.is_active && (
                  <button
                    onClick={() => { if (confirm('Deactivate this link?')) deactivate.mutate(link.id) }}
                    className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-red-600"
                    title="Deactivate"
                  >
                    <XCircle className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Generate upload link">
        <div className="space-y-4">
          <Input
            label="Label (optional)"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. Table 1 QR"
          />
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button loading={create.isPending} onClick={() => create.mutate()}>Generate</Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

// ─── Uploads tab ─────────────────────────────────────────────────────────────

function UploadsTab({ event }: { event: Event }) {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)

  const { data: stats } = useQuery({
    queryKey: ['upload-stats', event.id],
    queryFn: () => uploadsApi.stats(event.id).then((r) => r.data as UploadStats),
  })

  const { data, isLoading } = useQuery({
    queryKey: ['uploads', event.id, page],
    queryFn: () => uploadsApi.list(event.id, page).then((r) => r.data as { data: UploadType[]; meta: { total: number; per_page: number } }),
  })

  const del = useMutation({
    mutationFn: (uploadId: string) => uploadsApi.delete(event.id, uploadId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uploads', event.id] })
      qc.invalidateQueries({ queryKey: ['upload-stats', event.id] })
    },
  })

  const uploads = data?.data ?? []
  const totalPages = data ? Math.ceil(data.meta.total / data.meta.per_page) : 1

  return (
    <div className="space-y-5">
      {stats && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { label: 'Total', value: stats.total_uploads },
            { label: 'Completed', value: stats.completed_uploads },
            { label: 'Failed', value: stats.failed_uploads },
            { label: 'Total size', value: formatFileSize(stats.total_size_bytes) },
          ].map((s) => (
            <div key={s.label} className="rounded-xl border bg-white p-4 shadow-sm text-center">
              <p className="text-2xl font-bold text-gray-900">{s.value}</p>
              <p className="mt-0.5 text-xs text-gray-500">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {isLoading && <div className="flex justify-center py-10"><Spinner className="text-brand-600" /></div>}

      {!isLoading && uploads.length === 0 && (
        <div className="rounded-xl border-2 border-dashed border-gray-200 py-14 text-center">
          <Upload className="mx-auto mb-3 h-8 w-8 text-gray-300" />
          <p className="text-sm text-gray-500">No uploads yet.</p>
        </div>
      )}

      {uploads.length > 0 && (
        <div className="overflow-hidden rounded-xl border bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                <th className="px-4 py-3">File</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Guest</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {uploads.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="max-w-[180px] truncate px-4 py-3 font-medium text-gray-900" title={u.original_filename}>
                    {u.original_filename}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={u.mime_type.startsWith('image/') ? 'blue' : 'purple'}>
                      {u.mime_type.startsWith('image/') ? 'Photo' : 'Video'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{formatFileSize(u.file_size_bytes)}</td>
                  <td className="px-4 py-3">
                    <Badge variant={uploadStatusVariant(u.status)}>{u.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{u.guest_name ?? '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{format(new Date(u.created_at), 'MMM d, HH:mm')}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => { if (confirm('Delete this upload?')) del.mutate(u.id) }}
                      className="rounded p-1 text-gray-400 hover:text-red-600"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex justify-center gap-2">
          <Button variant="secondary" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</Button>
          <span className="flex items-center px-3 text-sm text-gray-600">Page {page} of {totalPages}</span>
          <Button variant="secondary" size="sm" disabled={page === totalPages} onClick={() => setPage(page + 1)}>Next</Button>
        </div>
      )}
    </div>
  )
}

// ─── Storage tab ─────────────────────────────────────────────────────────────

type StorageView = 'current' | 's3' | 'dropbox' | 'managed'

function StorageTab({ event }: { event: Event }) {
  const qc = useQueryClient()
  const [view, setView] = useState<StorageView>('current')
  const [accessKey, setAccessKey] = useState('')
  const [secretKey, setSecretKey] = useState('')
  const [bucket, setBucket] = useState('')
  const [region, setRegion] = useState('us-east-1')
  const [dbxToken, setDbxToken] = useState('')
  const [dbxFolder, setDbxFolder] = useState('/EventVault')
  const [error, setError] = useState('')

  const { data: storage, isLoading } = useQuery({
    queryKey: ['storage', event.id],
    queryFn: () => storageApi.get(event.id).then((r) => r.data as StorageConfig),
    retry: false,
  })

  const setS3 = useMutation({
    mutationFn: () => storageApi.set(event.id, {
      storage_type: 's3', aws_access_key_id: accessKey,
      aws_secret_access_key: secretKey, bucket_name: bucket, bucket_region: region,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['storage', event.id] }); setView('current'); setError('') },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? 'Failed'
      setError(msg)
    },
  })

  const setDropbox = useMutation({
    mutationFn: () => storageApi.set(event.id, {
      storage_type: 'dropbox', dropbox_access_token: dbxToken, dropbox_folder_path: dbxFolder,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['storage', event.id] }); setView('current'); setError('') },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? 'Failed'
      setError(msg)
    },
  })

  const setManaged = useMutation({
    mutationFn: () => storageApi.provisionManaged(event.id, { region }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['storage', event.id] }); setView('current') },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? 'Failed'
      setError(msg)
    },
  })

  const verify = useMutation({
    mutationFn: () => storageApi.verify(event.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['storage', event.id] }),
  })

  const remove = useMutation({
    mutationFn: () => storageApi.set(event.id, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['storage', event.id] }),
  })

  if (isLoading) return <div className="flex justify-center py-10"><Spinner className="text-brand-600" /></div>

  if (storage && view === 'current') {
    const typeLabel: Record<string, string> = { s3: 'Amazon S3', dropbox: 'Dropbox', managed_s3: 'EventVault Managed S3' }
    return (
      <div className="space-y-4">
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="font-semibold text-gray-900">{typeLabel[storage.storage_type]}</p>
              {storage.bucket_name && <p className="mt-1 text-sm text-gray-500">Bucket: {storage.bucket_name} ({storage.bucket_region})</p>}
              {storage.dropbox_folder_path && <p className="mt-1 text-sm text-gray-500">Folder: {storage.dropbox_folder_path}</p>}
              <div className="mt-2 flex items-center gap-2">
                {storage.is_verified
                  ? <><CheckCircle className="h-4 w-4 text-green-500" /><span className="text-sm text-green-700">Verified</span></>
                  : <><XCircle className="h-4 w-4 text-yellow-500" /><span className="text-sm text-yellow-700">Not verified</span></>}
              </div>
            </div>
            <Button variant="secondary" size="sm" loading={verify.isPending} onClick={() => verify.mutate()}>
              <RefreshCw className="h-4 w-4" /> Verify
            </Button>
          </div>
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" size="sm" onClick={() => setView('s3')}>Change storage</Button>
          <Button
            variant="danger" size="sm"
            onClick={() => { if (confirm('Remove storage configuration?')) remove.mutate() }}
          >
            Remove
          </Button>
        </div>
      </div>
    )
  }

  if (!storage && view === 'current') {
    return (
      <div className="space-y-4">
        <div className="rounded-xl border-2 border-dashed border-gray-200 py-10 text-center">
          <HardDrive className="mx-auto mb-3 h-8 w-8 text-gray-300" />
          <p className="font-medium text-gray-900">No storage configured</p>
          <p className="mt-1 text-sm text-gray-500">Choose where uploaded files will be stored.</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            { key: 's3' as const, title: 'Amazon S3', desc: 'Your own S3 bucket' },
            { key: 'dropbox' as const, title: 'Dropbox', desc: 'Your Dropbox account' },
            { key: 'managed' as const, title: 'EventVault Managed', desc: 'We handle storage for you' },
          ].map((opt) => (
            <button
              key={opt.key}
              onClick={() => setView(opt.key)}
              className="rounded-xl border bg-white p-5 text-left shadow-sm transition hover:border-brand-400 hover:shadow-md"
            >
              <p className="font-semibold text-gray-900">{opt.title}</p>
              <p className="mt-1 text-xs text-gray-500">{opt.desc}</p>
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border bg-white p-6 shadow-sm space-y-4">
      <button onClick={() => setView('current')} className="flex items-center gap-1 text-sm text-brand-600 hover:text-brand-700">
        <ArrowLeft className="h-4 w-4" /> Back
      </button>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      {view === 's3' && (
        <div className="space-y-4">
          <h3 className="font-semibold text-gray-900">Amazon S3</h3>
          <Input label="AWS Access Key ID" value={accessKey} onChange={(e) => setAccessKey(e.target.value)} />
          <Input label="AWS Secret Access Key" type="password" value={secretKey} onChange={(e) => setSecretKey(e.target.value)} />
          <Input label="Bucket name" value={bucket} onChange={(e) => setBucket(e.target.value)} />
          <Input label="Region" value={region} onChange={(e) => setRegion(e.target.value)} placeholder="us-east-1" />
          <div className="flex gap-3">
            <Button loading={setS3.isPending} onClick={() => setS3.mutate()} disabled={!accessKey || !secretKey || !bucket}>Save</Button>
            <Button variant="secondary" onClick={() => setView('current')}>Cancel</Button>
          </div>
        </div>
      )}

      {view === 'dropbox' && (
        <div className="space-y-4">
          <h3 className="font-semibold text-gray-900">Dropbox</h3>
          <Input label="Access token" value={dbxToken} onChange={(e) => setDbxToken(e.target.value)} />
          <Input label="Folder path" value={dbxFolder} onChange={(e) => setDbxFolder(e.target.value)} placeholder="/EventVault" />
          <div className="flex gap-3">
            <Button loading={setDropbox.isPending} onClick={() => setDropbox.mutate()} disabled={!dbxToken}>Save</Button>
            <Button variant="secondary" onClick={() => setView('current')}>Cancel</Button>
          </div>
        </div>
      )}

      {view === 'managed' && (
        <div className="space-y-4">
          <h3 className="font-semibold text-gray-900">EventVault Managed S3</h3>
          <p className="text-sm text-gray-600">We'll provision a dedicated S3 bucket for this event.</p>
          <Input label="Region" value={region} onChange={(e) => setRegion(e.target.value)} placeholder="us-east-1" />
          <div className="flex gap-3">
            <Button loading={setManaged.isPending} onClick={() => setManaged.mutate()}>Provision bucket</Button>
            <Button variant="secondary" onClick={() => setView('current')}>Cancel</Button>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Main page ───────────────────────────────────────────────────────────────

const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: 'overview', label: 'Overview', icon: <Settings className="h-4 w-4" /> },
  { key: 'links', label: 'Links', icon: <Link2 className="h-4 w-4" /> },
  { key: 'uploads', label: 'Uploads', icon: <Upload className="h-4 w-4" /> },
  { key: 'storage', label: 'Storage', icon: <HardDrive className="h-4 w-4" /> },
]

export default function EventDetail() {
  const { id } = useParams<{ id: string }>()
  const [tab, setTab] = useState<Tab>('overview')

  const { data: event, isLoading, isError } = useQuery({
    queryKey: ['event', id],
    queryFn: () => eventsApi.get(id!).then((r) => r.data as Event),
    enabled: !!id,
  })

  if (isLoading) return <div className="flex justify-center py-20"><Spinner size="lg" className="text-brand-600" /></div>
  if (isError || !event) return (
    <div className="text-center py-20 text-gray-500">
      Event not found. <Link to="/" className="text-brand-600">Back to dashboard</Link>
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/" className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900">
          <ArrowLeft className="h-4 w-4" /> Events
        </Link>
        <span className="text-gray-300">/</span>
        <h1 className="text-xl font-bold text-gray-900">{event.name}</h1>
        <Badge variant={({ draft: 'gray', active: 'green', archived: 'gray' } as const)[event.status]}>
          {event.status}
        </Badge>
      </div>

      <div className="border-b">
        <nav className="-mb-px flex gap-6">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 border-b-2 pb-3 text-sm font-medium transition-colors ${
                tab === t.key
                  ? 'border-brand-600 text-brand-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </nav>
      </div>

      {tab === 'overview' && <OverviewTab event={event} />}
      {tab === 'links' && <LinksTab event={event} />}
      {tab === 'uploads' && <UploadsTab event={event} />}
      {tab === 'storage' && <StorageTab event={event} />}
    </div>
  )
}
