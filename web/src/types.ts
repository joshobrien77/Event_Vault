export interface Event {
  id: string
  name: string
  event_type: 'wedding' | 'graduation' | 'birthday' | 'corporate' | 'other'
  event_date: string | null
  status: 'draft' | 'active' | 'archived'
  tier: 'free' | 'standard' | 'premium'
  upload_limit_mb: number
  total_storage_limit_gb: number
  allow_video: boolean
  allow_photo: boolean
  welcome_message: string | null
  expires_at: string | null
  created_at: string
  updated_at: string
}

export interface EventLink {
  id: string
  short_code: string
  full_url: string
  label: string | null
  is_active: boolean
  click_count: number
  expires_at: string | null
  created_at: string
}

export interface StorageConfig {
  id: string
  storage_type: 'dropbox' | 's3' | 'managed_s3'
  bucket_name: string | null
  bucket_region: string | null
  dropbox_folder_path: string | null
  is_verified: boolean
  created_at: string
}

export interface Upload {
  id: string
  guest_name: string | null
  original_filename: string
  file_size_bytes: number
  mime_type: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  thumbnail_path: string | null
  width: number | null
  height: number | null
  duration_seconds: number | null
  exif_taken_at: string | null
  created_at: string
}

export interface UploadStats {
  total_uploads: number
  completed_uploads: number
  failed_uploads: number
  pending_uploads: number
  total_size_bytes: number
  photo_count: number
  video_count: number
}

export interface Tier {
  name: 'free' | 'standard' | 'premium'
  price_cents: number
  max_uploads: number
  max_file_size_mb: number
  max_total_storage_gb: number
  allows_video: boolean
  allows_custom_branding: boolean
  managed_s3_monthly_cents: number
}

export interface GuestEventInfo {
  event_name: string
  event_type: string
  welcome_message: string | null
  allow_photo: boolean
  allow_video: boolean
  upload_limit_mb: number
  requires_pin: boolean
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1_048_576).toFixed(1)} MB`
  return `${(bytes / 1_073_741_824).toFixed(2)} GB`
}
