# CLAUDE.md — EventVault Development Guide

## Project Overview

EventVault is a SaaS platform for collecting photos and videos from events (weddings, graduations, etc.). Hosts create events, share a link/QR code, and guests upload media directly to the host's chosen storage backend (Dropbox, S3, or EventVault-managed S3).

## Architecture

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy (async) + PostgreSQL
- **Queue:** Celery + Redis for async upload processing
- **Web Frontend:** React 18 + Vite + Tailwind CSS + React Query
- **Mobile App:** React Native (Expo SDK 51+) — iOS & Android
- **Auth:** JWT for hosts, magic links / PIN-optional for guests
- **Storage Backends:** Dropbox API v2, AWS S3 (boto3), EventVault-managed S3

## Repository Structure

```
eventvault/
├── CLAUDE.md              # This file
├── docs/                  # RFC and architecture docs
│   └── RFC-001.md         # Technical specification
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI app factory
│   │   ├── config.py      # Pydantic settings
│   │   ├── api/           # Route handlers (events, uploads, storage, billing)
│   │   ├── core/          # Auth, security, exceptions
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── services/      # Business logic (storage, upload processing, billing)
│   │   └── workers/       # Celery tasks (upload pipeline, thumbnail gen)
│   ├── migrations/        # Alembic migrations
│   ├── tests/             # pytest test suite
│   ├── requirements.txt
│   └── alembic.ini
├── web/
│   ├── src/
│   │   ├── components/    # Reusable UI components
│   │   ├── pages/         # Route-level page components
│   │   ├── hooks/         # Custom React hooks
│   │   ├── lib/           # API client, utilities
│   │   └── assets/        # Static assets
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
└── mobile/
    ├── src/
    │   ├── screens/       # Screen components
    │   ├── components/    # Shared components
    │   ├── hooks/         # Custom hooks
    │   ├── navigation/    # React Navigation config
    │   └── lib/           # API client, storage helpers
    ├── app.json
    └── package.json
```

## Tech Stack Constraints

### DO use:
- FastAPI with async endpoints
- SQLAlchemy 2.0 async ORM (not 1.x style)
- Pydantic v2 for all schemas
- Alembic for migrations
- boto3 for S3 operations
- dropbox SDK for Dropbox integration
- Celery with Redis broker for background tasks
- Pillow for image thumbnails, ffmpeg for video thumbnails
- python-qrcode for QR generation
- React Query (TanStack Query) for data fetching
- React Router v6 for web routing
- Expo Router for mobile navigation
- Tailwind CSS for web styling
- NativeWind for mobile styling

### DO NOT use:
- Django or Flask
- MongoDB or any NoSQL database
- GraphQL (REST only for now)
- Next.js or SSR frameworks
- Firebase (we own the infrastructure)
- Any JS ORM (Prisma, Drizzle) — backend is Python only
- Docker in development (direct execution)
- Authentication for guests beyond optional PIN

## API Design Principles

1. **API-first:** All features exposed via REST API before any UI
2. **Consistent response format:** `{ "data": ..., "meta": { "page": ..., "total": ... } }`
3. **Error format:** `{ "error": { "code": "EVENT_NOT_FOUND", "message": "..." } }`
4. **Versioned:** All routes prefixed with `/api/v1/`
5. **OpenAPI:** Auto-generated docs at `/docs`

## Database Conventions

- Table names: plural snake_case (`events`, `uploads`, `storage_connections`)
- Primary keys: UUID v4
- Timestamps: `created_at`, `updated_at` on every table (UTC, timezone-aware)
- Soft deletes: `deleted_at` column where needed
- Foreign keys: always indexed
- Sensitive data: encrypted at rest (storage credentials via Fernet)

## Implementation Priority

1. **Backend scaffolding** — FastAPI app, config, database connection
2. **Database models** — All SQLAlchemy models + initial migration
3. **Auth system** — Host JWT auth, guest magic link/PIN
4. **Event CRUD** — Create, read, update, archive events
5. **Link/QR generation** — Short codes + QR code image generation
6. **Storage abstraction** — Interface + Dropbox/S3 implementations
7. **Upload pipeline** — Chunked upload → queue → process → push to storage
8. **Web dashboard** — Host event management UI
9. **Guest upload page** — Responsive web upload experience
10. **Mobile app** — Expo app for guest uploads (camera + gallery)
11. **Billing** — Stripe integration, per-event pricing
12. **Managed S3** — Automated bucket provisioning + upcharge billing

## Key Business Rules

- Events are billed per-event, not per-user
- Guests NEVER need an account — frictionless upload via link/QR
- Each event has exactly ONE storage destination
- Storage credentials are encrypted and never exposed via API
- Upload size limits are configurable per event tier
- QR codes and links can have optional expiration dates
- Managed S3 buckets are provisioned in the host's preferred region

## Testing Strategy

- pytest + pytest-asyncio for backend
- Factory Boy for test fixtures
- httpx AsyncClient for API integration tests
- React Testing Library for web
- Detox for mobile E2E (later phase)

## Environment Variables

```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/eventvault
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<random-64-char-hex>
ENCRYPTION_KEY=<fernet-key-for-storage-creds>
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
AWS_ACCESS_KEY_ID=<for-managed-s3>
AWS_SECRET_ACCESS_KEY=<for-managed-s3>
DROPBOX_APP_KEY=<oauth-app-key>
DROPBOX_APP_SECRET=<oauth-app-secret>
BASE_URL=https://app.eventvault.io
```
