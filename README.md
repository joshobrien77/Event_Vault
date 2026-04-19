# EventVault

**Frictionless event photo & video collection — your storage, your media.**

EventVault lets event hosts collect photos and videos from guests via shareable links and QR codes. Media flows directly into the host's own cloud storage (Dropbox, S3, or EventVault-managed S3).

## Quick Start

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your values
uvicorn app.main:app --reload
```

### Web Frontend
```bash
cd web
npm install
npm run dev
```

### Mobile App
```bash
cd mobile
npm install
npx expo start
```

## Architecture

See [docs/RFC-001.md](docs/RFC-001.md) for the full technical specification.

See [CLAUDE.md](CLAUDE.md) for the Claude Code development guide.

## License

Proprietary — All rights reserved.
