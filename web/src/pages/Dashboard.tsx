import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Camera, Calendar, Image, Video, ChevronRight } from 'lucide-react'
import { format } from 'date-fns'
import { eventsApi } from '../lib/api'
import { Event } from '../types'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import Spinner from '../components/ui/Spinner'

const EVENT_TYPES = [
  { value: 'wedding', label: 'Wedding' },
  { value: 'graduation', label: 'Graduation' },
  { value: 'birthday', label: 'Birthday' },
  { value: 'corporate', label: 'Corporate' },
  { value: 'other', label: 'Other' },
]

function statusBadge(status: Event['status']) {
  const map = { draft: 'gray', active: 'green', archived: 'gray' } as const
  return <Badge variant={map[status]}>{status}</Badge>
}

function tierBadge(tier: Event['tier']) {
  const map = { free: 'gray', standard: 'blue', premium: 'purple' } as const
  return <Badge variant={map[tier]}>{tier}</Badge>
}

function CreateEventModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [type, setType] = useState('other')
  const [date, setDate] = useState('')
  const [pin, setPin] = useState('')
  const [allowVideo, setAllowVideo] = useState(true)
  const [allowPhoto, setAllowPhoto] = useState(true)
  const [welcome, setWelcome] = useState('')
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: () =>
      eventsApi.create({
        name,
        event_type: type,
        event_date: date || null,
        guest_pin: pin || null,
        allow_video: allowVideo,
        allow_photo: allowPhoto,
        welcome_message: welcome || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['events'] })
      onClose()
      setName('')
      setType('other')
      setDate('')
      setPin('')
      setWelcome('')
      setError('')
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
          ?.message ?? 'Failed to create event'
      setError(msg)
    },
  })

  return (
    <Modal open={open} onClose={onClose} title="Create event" size="lg">
      <div className="space-y-4">
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        <Input
          label="Event name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Sarah & James' Wedding"
        />
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">Event type</label>
          <select
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            {EVENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <Input
          label="Event date (optional)"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
        <Input
          label="Guest PIN (optional, 4–6 digits)"
          type="text"
          inputMode="numeric"
          maxLength={6}
          pattern="\d{4,6}"
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          placeholder="e.g. 1234"
        />
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">Welcome message (optional)</label>
          <textarea
            rows={2}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500"
            value={welcome}
            onChange={(e) => setWelcome(e.target.value)}
            placeholder="Thanks for coming! Share your photos and videos here."
          />
        </div>
        <div className="flex gap-6">
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input type="checkbox" checked={allowPhoto} onChange={(e) => setAllowPhoto(e.target.checked)} className="rounded" />
            Allow photos
          </label>
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input type="checkbox" checked={allowVideo} onChange={(e) => setAllowVideo(e.target.checked)} className="rounded" />
            Allow videos
          </label>
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={mutation.isPending} onClick={() => mutation.mutate()} disabled={!name.trim()}>
            Create event
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default function Dashboard() {
  const [showCreate, setShowCreate] = useState(false)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['events'],
    queryFn: () => eventsApi.list().then((r) => r.data as { data: Event[]; meta: { total: number } }),
  })

  const events = data?.data ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Your Events</h1>
          <p className="mt-1 text-sm text-gray-500">
            {data ? `${data.meta.total} event${data.meta.total !== 1 ? 's' : ''}` : ''}
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" />
          New event
        </Button>
      </div>

      {isLoading && (
        <div className="flex justify-center py-20">
          <Spinner size="lg" className="text-brand-600" />
        </div>
      )}

      {isError && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-700">
          Failed to load events. Please refresh.
        </div>
      )}

      {!isLoading && !isError && events.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-200 py-20 text-center">
          <Camera className="mb-4 h-12 w-12 text-gray-300" />
          <h3 className="text-lg font-medium text-gray-900">No events yet</h3>
          <p className="mt-1 text-sm text-gray-500">Create your first event to start collecting photos.</p>
          <Button className="mt-6" onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" />
            Create your first event
          </Button>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {events.map((event) => (
          <Link
            key={event.id}
            to={`/events/${event.id}`}
            className="group rounded-xl border bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <p className="truncate font-semibold text-gray-900 group-hover:text-brand-600">
                  {event.name}
                </p>
                <p className="mt-0.5 text-xs capitalize text-gray-500">{event.event_type}</p>
              </div>
              <ChevronRight className="h-5 w-5 flex-shrink-0 text-gray-300 group-hover:text-brand-500" />
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              {statusBadge(event.status)}
              {tierBadge(event.tier)}
            </div>

            <div className="mt-3 flex items-center gap-4 text-xs text-gray-400">
              {event.event_date && (
                <span className="flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5" />
                  {format(new Date(event.event_date), 'MMM d, yyyy')}
                </span>
              )}
              {event.allow_photo && <span className="flex items-center gap-1"><Image className="h-3.5 w-3.5" />Photos</span>}
              {event.allow_video && <span className="flex items-center gap-1"><Video className="h-3.5 w-3.5" />Videos</span>}
            </div>

            <p className="mt-2 text-xs text-gray-400">
              Created {format(new Date(event.created_at), 'MMM d, yyyy')}
            </p>
          </Link>
        ))}
      </div>

      <CreateEventModal open={showCreate} onClose={() => setShowCreate(false)} />
    </div>
  )
}
